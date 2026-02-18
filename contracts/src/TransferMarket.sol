// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable2Step.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import "./SWOSPlayerNFT.sol";

/**
 * @title TransferMarket
 * @notice On-chain transfer market for SWOS420 player NFTs.
 *
 * Mirrors the Python `transfer_market.py` sealed-bid auction:
 *   - List a player with minimum price + bidding window
 *   - Submit bids (open, ascending — highest bid wins)
 *   - Release clause: auto-accept if bid ≥ clause amount
 *   - Transfer fees: 5% burned + 5% to treasury (from $SENSI)
 *
 * Loan system: temporary custody with recall date.
 */
contract TransferMarket is Ownable2Step, ReentrancyGuard, Pausable {

    // ── Data Structures ─────────────────────────────────────────────────

    struct Listing {
        address seller;
        uint256 tokenId;
        uint256 minPrice;           // Minimum acceptable bid
        uint256 releaseClause;      // Auto-accept threshold (0 = no clause)
        uint256 deadline;           // Block timestamp deadline
        uint256 highestBid;
        address highestBidder;
        bool active;
    }

    struct Loan {
        address lender;             // Original owner
        address borrower;           // Temporary holder
        uint256 tokenId;
        uint256 recallDate;         // Timestamp when loan expires
        uint256 fee;                // $SENSI fee paid for loan
        bool active;
    }

    // ── State ────────────────────────────────────────────────────────────

    SWOSPlayerNFT public playerNFT;
    IERC20 public sensiToken;
    address public treasury;

    uint256 public nextListingId;
    mapping(uint256 => Listing) public listings;        // listingId => Listing
    mapping(uint256 => uint256) public tokenToListing;  // tokenId => listingId

    uint256 public nextLoanId;
    mapping(uint256 => Loan) public loans;              // loanId => Loan
    mapping(uint256 => uint256) public tokenToLoan;     // tokenId => loanId

    uint256 public constant FEE_BPS = 1000;             // 10% total (5% burn + 5% treasury)
    uint256 public constant BID_WINDOW = 3 days;

    // ── Events ───────────────────────────────────────────────────────────

    event PlayerListed(uint256 indexed listingId, uint256 indexed tokenId, uint256 minPrice, uint256 releaseClause);
    event BidPlaced(uint256 indexed listingId, address indexed bidder, uint256 amount);
    event TransferCompleted(uint256 indexed listingId, uint256 indexed tokenId, address from, address to, uint256 price);
    event ListingCancelled(uint256 indexed listingId);
    event LoanCreated(uint256 indexed loanId, uint256 indexed tokenId, address lender, address borrower, uint256 recallDate);
    event LoanRecalled(uint256 indexed loanId, uint256 indexed tokenId);

    // ── Constructor ──────────────────────────────────────────────────────

    constructor(
        address _playerNFT,
        address _sensiToken,
        address _treasury
    ) Ownable(msg.sender) {
        playerNFT = SWOSPlayerNFT(_playerNFT);
        sensiToken = IERC20(_sensiToken);
        treasury = _treasury;
    }

    // ── Listing ──────────────────────────────────────────────────────────

    /// @notice List a player for sale.
    /// @param tokenId Player NFT token ID
    /// @param minPrice Minimum acceptable bid in $SENSI
    /// @param releaseClause Auto-accept price (0 = disabled)
    function listPlayer(
        uint256 tokenId,
        uint256 minPrice,
        uint256 releaseClause
    ) external whenNotPaused {
        require(playerNFT.ownerOf(tokenId) == msg.sender, "Not owner");
        require(tokenToListing[tokenId] == 0, "Already listed");
        require(tokenToLoan[tokenId] == 0, "On loan");

        // Transfer NFT to market escrow
        playerNFT.transferFrom(msg.sender, address(this), tokenId);

        nextListingId++;
        listings[nextListingId] = Listing({
            seller: msg.sender,
            tokenId: tokenId,
            minPrice: minPrice,
            releaseClause: releaseClause,
            deadline: block.timestamp + BID_WINDOW,
            highestBid: 0,
            highestBidder: address(0),
            active: true
        });
        tokenToListing[tokenId] = nextListingId;

        emit PlayerListed(nextListingId, tokenId, minPrice, releaseClause);
    }

    /// @notice Place a bid on a listed player.
    function placeBid(uint256 listingId, uint256 amount) external nonReentrant whenNotPaused {
        Listing storage l = listings[listingId];
        require(l.active, "Not active");
        require(block.timestamp <= l.deadline, "Expired");
        require(amount >= l.minPrice, "Below minimum");
        require(amount > l.highestBid, "Not highest");

        // Refund previous highest bidder
        if (l.highestBidder != address(0)) {
            sensiToken.transfer(l.highestBidder, l.highestBid);
        }

        // Take new bid escrow
        sensiToken.transferFrom(msg.sender, address(this), amount);
        l.highestBid = amount;
        l.highestBidder = msg.sender;

        emit BidPlaced(listingId, msg.sender, amount);

        // Auto-accept if release clause met
        if (l.releaseClause > 0 && amount >= l.releaseClause) {
            _completeListing(listingId);
        }
    }

    /// @notice Resolve auction after deadline.
    function resolveListing(uint256 listingId) external nonReentrant {
        Listing storage l = listings[listingId];
        require(l.active, "Not active");
        require(block.timestamp > l.deadline, "Still open");

        if (l.highestBidder == address(0)) {
            // No bids — return NFT to seller
            playerNFT.transferFrom(address(this), l.seller, l.tokenId);
            l.active = false;
            tokenToListing[l.tokenId] = 0;
            emit ListingCancelled(listingId);
        } else {
            _completeListing(listingId);
        }
    }

    /// @notice Cancel listing (only if no bids yet).
    function cancelListing(uint256 listingId) external {
        Listing storage l = listings[listingId];
        require(l.active, "Not active");
        require(l.seller == msg.sender, "Not seller");
        require(l.highestBidder == address(0), "Has bids");

        playerNFT.transferFrom(address(this), l.seller, l.tokenId);
        l.active = false;
        tokenToListing[l.tokenId] = 0;
        emit ListingCancelled(listingId);
    }

    // ── Loans ────────────────────────────────────────────────────────────

    /// @notice Loan a player to another address.
    function createLoan(
        uint256 tokenId,
        address borrower,
        uint256 durationDays,
        uint256 fee
    ) external nonReentrant whenNotPaused {
        require(playerNFT.ownerOf(tokenId) == msg.sender, "Not owner");
        require(tokenToLoan[tokenId] == 0, "Already loaned");
        require(tokenToListing[tokenId] == 0, "Listed for sale");

        // Take loan fee from borrower
        if (fee > 0) {
            sensiToken.transferFrom(borrower, msg.sender, fee);
        }

        // Transfer custody
        playerNFT.transferFrom(msg.sender, borrower, tokenId);

        nextLoanId++;
        loans[nextLoanId] = Loan({
            lender: msg.sender,
            borrower: borrower,
            tokenId: tokenId,
            recallDate: block.timestamp + (durationDays * 1 days),
            fee: fee,
            active: true
        });
        tokenToLoan[tokenId] = nextLoanId;

        emit LoanCreated(nextLoanId, tokenId, msg.sender, borrower, loans[nextLoanId].recallDate);
    }

    /// @notice Recall a loan after expiry.
    function recallLoan(uint256 loanId) external nonReentrant {
        Loan storage l = loans[loanId];
        require(l.active, "Not active");
        require(l.lender == msg.sender || block.timestamp >= l.recallDate, "Not recallable");

        // Return player to lender
        playerNFT.transferFrom(l.borrower, l.lender, l.tokenId);
        l.active = false;
        tokenToLoan[l.tokenId] = 0;

        emit LoanRecalled(loanId, l.tokenId);
    }

    // ── Admin ────────────────────────────────────────────────────────────

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function setTreasury(address newTreasury) external onlyOwner {
        treasury = newTreasury;
    }

    // ── Internal ─────────────────────────────────────────────────────────

    function _completeListing(uint256 listingId) internal {
        Listing storage l = listings[listingId];

        uint256 fee = (l.highestBid * FEE_BPS) / 10000; // 10%
        uint256 burnAmount = fee / 2;                     // 5% burned
        uint256 treasuryAmount = fee - burnAmount;         // 5% treasury
        uint256 sellerProceeds = l.highestBid - fee;

        // Pay seller
        sensiToken.transfer(l.seller, sellerProceeds);
        // Treasury cut
        sensiToken.transfer(treasury, treasuryAmount);
        // Burn — send to zero (or use ERC20Burnable if available)
        sensiToken.transfer(address(0xdead), burnAmount);

        // Transfer NFT to buyer
        playerNFT.transferFrom(address(this), l.highestBidder, l.tokenId);

        l.active = false;
        tokenToListing[l.tokenId] = 0;

        emit TransferCompleted(listingId, l.tokenId, l.seller, l.highestBidder, l.highestBid);
    }
}
