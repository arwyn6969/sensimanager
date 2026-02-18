// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * SWOS420 Stadium Ad Hoarding — NFT-Based Expiring Leases
 *
 * Each club stadium gets 12–20 fixed hoarding slots (perimeter + behind goals).
 * Brands rent slots as ERC-721 NFTs that automatically expire.
 *
 * Slot ID encoding: clubId * 100 + position (0–19)
 *   e.g. Tranmere (clubId=1) → slots 100–119
 *
 * Revenue split on every rental:
 *   60% → club owner wallet (team finances boost)
 *   30% → $SENSI treasury (platform fund)
 *   10% → creator wallet (Arwyn/founder cut)
 *
 * Dynamic pricing factors:
 *   - Club tier (Prem=4x, Champ=2.5x, L1=1.5x, L2=1x)
 *   - Duration multiplier: 1 + (days / 365) * 1.8
 *   - Demand factor from on-chain viewer oracle
 *
 * Deployment target: Base L2 (Sepolia first, then mainnet)
 * Integrates with: OBS overlay, match_sim.py, ad_manager.py
 *
 * @author SWOS420 / Arwyn Hughes / SWA 🏟️🔥
 */
contract AdHoarding is ERC721, Ownable2Step, ReentrancyGuard {

    // ── Data Structures ─────────────────────────────────────────────────

    struct Slot {
        uint256 expiresAt;       // Unix timestamp when the lease expires
        address brand;           // Address of the renting brand
        string  contentURI;      // IPFS/Arweave URI to the hoarding image
        uint256 clubId;          // Club this hoarding belongs to
        uint8   position;        // Slot position within the stadium (0–19)
        uint256 paidAmount;      // Total ETH paid for this lease
    }

    struct ClubConfig {
        address clubOwner;       // Wallet receiving 60% revenue
        uint8   tier;            // 1=League Two, 2=League One, 3=Championship, 4=Premier League
        uint8   maxSlots;        // Number of hoarding positions (default 12)
        bool    active;          // Whether club accepts hoardings
    }

    // ── Storage ──────────────────────────────────────────────────────────

    mapping(uint256 => Slot)       public slots;        // slotId => Slot
    mapping(uint256 => ClubConfig) public clubs;        // clubId => ClubConfig
    mapping(uint256 => uint256)    public slotDemand;   // slotId => rental count (demand signal)

    address public treasury;                             // 30% revenue destination
    address public creator;                              // 10% revenue destination (Arwyn)
    uint256 public basePricePerDay = 0.001 ether;       // Base price (bootstrap-friendly)
    uint256 public totalRentals;                         // Global rental counter
    uint256 public viewerCount;                          // On-chain viewer oracle value

    uint256 private _nextTokenId = 1;

    // ── Tier multipliers (basis points, 10000 = 1.0x) ────────────────
    mapping(uint8 => uint256) public tierMultiplier;

    // ── Events ───────────────────────────────────────────────────────────

    event SlotRented(
        uint256 indexed slotId,
        uint256 indexed clubId,
        address indexed brand,
        string contentURI,
        uint256 expiresAt,
        uint256 paidAmount
    );
    event SlotExpired(uint256 indexed slotId);
    event ClubRegistered(uint256 indexed clubId, address clubOwner, uint8 tier, uint8 maxSlots);
    event ClubUpdated(uint256 indexed clubId, address clubOwner, uint8 tier);
    event ViewerCountUpdated(uint256 newCount);
    event ContentUpdated(uint256 indexed slotId, string newContentURI);
    event BasePriceUpdated(uint256 newPrice);

    // ── Errors ───────────────────────────────────────────────────────────

    error SlotStillActive(uint256 slotId, uint256 expiresAt);
    error ClubNotActive(uint256 clubId);
    error InvalidPosition(uint8 position, uint8 maxSlots);
    error InsufficientPayment(uint256 required, uint256 sent);
    error InvalidDuration(uint256 days_);
    error ClubNotRegistered(uint256 clubId);
    error NotSlotOwner(uint256 slotId, address caller);
    error TransferFailed(address to, uint256 amount);

    // ── Constructor ──────────────────────────────────────────────────────

    constructor(
        address _treasury,
        address _creator
    ) ERC721("SWOS420 Ad Hoarding", "SWOSAD") Ownable(msg.sender) {
        require(_treasury != address(0), "AdHoarding: treasury is zero");
        require(_creator != address(0), "AdHoarding: creator is zero");
        treasury = _treasury;
        creator = _creator;

        // Default tier multipliers (basis points)
        tierMultiplier[1] = 10000;    // League Two: 1.0x
        tierMultiplier[2] = 15000;    // League One: 1.5x
        tierMultiplier[3] = 25000;    // Championship: 2.5x
        tierMultiplier[4] = 40000;    // Premier League: 4.0x
    }

    // ── Club Management (Owner only) ─────────────────────────────────────

    /// @notice Register a club for hoarding rentals
    /// @param clubId Unique club identifier (matches Python Team model)
    /// @param clubOwner Wallet that receives 60% of rental revenue
    /// @param tier Club tier (1-4, affects pricing)
    /// @param maxSlots Number of hoarding positions (12-20)
    function registerClub(
        uint256 clubId,
        address clubOwner,
        uint8 tier,
        uint8 maxSlots
    ) external onlyOwner {
        require(clubOwner != address(0), "AdHoarding: owner is zero");
        require(tier >= 1 && tier <= 4, "AdHoarding: tier must be 1-4");
        require(maxSlots >= 1 && maxSlots <= 20, "AdHoarding: maxSlots 1-20");

        clubs[clubId] = ClubConfig({
            clubOwner: clubOwner,
            tier: tier,
            maxSlots: maxSlots,
            active: true
        });

        emit ClubRegistered(clubId, clubOwner, tier, maxSlots);
    }

    /// @notice Update club config
    function updateClub(
        uint256 clubId,
        address clubOwner,
        uint8 tier
    ) external onlyOwner {
        ClubConfig storage c = clubs[clubId];
        if (!c.active) revert ClubNotRegistered(clubId);

        c.clubOwner = clubOwner;
        c.tier = tier;
        emit ClubUpdated(clubId, clubOwner, tier);
    }

    // ── Core: Rent a Hoarding Slot ──────────────────────────────────────

    /// @notice Rent a hoarding slot for a specified number of days
    /// @param clubId The club whose stadium you're advertising in
    /// @param position Slot position (0 to maxSlots-1)
    /// @param days_ Rental duration in days (1-365)
    /// @param contentURI IPFS/Arweave URI to the hoarding image (SVG/PNG)
    function rent(
        uint256 clubId,
        uint8 position,
        uint256 days_,
        string calldata contentURI
    ) external payable nonReentrant {
        ClubConfig storage club = clubs[clubId];
        if (!club.active) revert ClubNotActive(clubId);
        if (position >= club.maxSlots) revert InvalidPosition(position, club.maxSlots);
        if (days_ == 0 || days_ > 365) revert InvalidDuration(days_);

        uint256 slotId = clubId * 100 + position;

        // Check if slot is currently rented
        if (slots[slotId].expiresAt > block.timestamp) {
            revert SlotStillActive(slotId, slots[slotId].expiresAt);
        }

        uint256 price = calculatePrice(clubId, days_);
        if (msg.value < price) revert InsufficientPayment(price, msg.value);

        // If an expired NFT exists, burn it first
        if (_ownerOf(slotId) != address(0)) {
            _burn(slotId);
            emit SlotExpired(slotId);
        }

        // Mint NFT to the renter
        _mint(msg.sender, slotId);

        // Store slot data
        uint256 expires = block.timestamp + days_ * 1 days;
        slots[slotId] = Slot({
            expiresAt: expires,
            brand: msg.sender,
            contentURI: contentURI,
            clubId: clubId,
            position: position,
            paidAmount: msg.value
        });

        // Update demand signal
        slotDemand[slotId]++;
        totalRentals++;

        // ── Revenue Split: 60/30/10 ──
        uint256 clubShare = (msg.value * 60) / 100;
        uint256 treasuryShare = (msg.value * 30) / 100;
        uint256 creatorShare = msg.value - clubShare - treasuryShare; // remainder = 10%

        _safeTransfer(club.clubOwner, clubShare);
        _safeTransfer(treasury, treasuryShare);
        _safeTransfer(creator, creatorShare);

        emit SlotRented(slotId, clubId, msg.sender, contentURI, expires, msg.value);
    }

    // ── Pricing ──────────────────────────────────────────────────────────

    /// @notice Calculate the rental price for a slot
    /// @dev price = basePricePerDay * days * tierMult * durationPremium * demandFactor
    function calculatePrice(uint256 clubId, uint256 days_) public view returns (uint256) {
        ClubConfig storage club = clubs[clubId];
        if (!club.active) revert ClubNotRegistered(clubId);

        // Tier multiplier (basis points → div 10000)
        uint256 tierMult = tierMultiplier[club.tier];
        if (tierMult == 0) tierMult = 10000; // fallback

        // Duration premium: 1.0 + (days / 365) * 1.8 → in basis points
        // At 7 days:   ~1.035x
        // At 30 days:  ~1.148x
        // At 365 days: ~2.8x
        uint256 durationPremium = 10000 + (days_ * 18000) / 365;

        // Demand factor: 1.0 + (viewerCount / 5000) * 0.6 → basis points
        // At 0 viewers:    1.0x (bootstrap friendly)
        // At 5000 viewers: 1.6x
        // At 10000 viewers: 2.2x
        uint256 demandFactor = 10000 + (viewerCount * 6000) / 5000;

        // Final price calculation
        uint256 price = basePricePerDay * days_;
        price = (price * tierMult) / 10000;
        price = (price * durationPremium) / 10000;
        price = (price * demandFactor) / 10000;

        return price;
    }

    // ── Slot Management ──────────────────────────────────────────────────

    /// @notice Update the content URI of a slot you own
    function updateContent(uint256 slotId, string calldata newContentURI) external {
        if (ownerOf(slotId) != msg.sender) revert NotSlotOwner(slotId, msg.sender);
        if (slots[slotId].expiresAt <= block.timestamp) revert SlotStillActive(slotId, 0);
        slots[slotId].contentURI = newContentURI;
        emit ContentUpdated(slotId, newContentURI);
    }

    /// @notice Check if a slot is currently active (not expired)
    function isSlotActive(uint256 slotId) public view returns (bool) {
        return slots[slotId].expiresAt > block.timestamp;
    }

    /// @notice Get all active slots for a club
    function getActiveSlots(uint256 clubId) external view returns (uint256[] memory) {
        ClubConfig storage club = clubs[clubId];
        uint256[] memory active = new uint256[](club.maxSlots);
        uint256 count = 0;

        for (uint8 i = 0; i < club.maxSlots; i++) {
            uint256 slotId = clubId * 100 + i;
            if (isSlotActive(slotId)) {
                active[count] = slotId;
                count++;
            }
        }

        // Trim array
        uint256[] memory result = new uint256[](count);
        for (uint256 i = 0; i < count; i++) {
            result[i] = active[i];
        }
        return result;
    }

    /// @notice Get the content URI for a slot (returns empty if expired)
    function getSlotContent(uint256 slotId) external view returns (string memory) {
        if (!isSlotActive(slotId)) return "";
        return slots[slotId].contentURI;
    }

    // ── Oracle: Viewer Count ─────────────────────────────────────────────

    /// @notice Update the current viewer count (affects dynamic pricing)
    /// @dev Called by off-chain oracle or streamer bot
    function updateViewerCount(uint256 _viewerCount) external onlyOwner {
        viewerCount = _viewerCount;
        emit ViewerCountUpdated(_viewerCount);
    }

    // ── Admin ────────────────────────────────────────────────────────────

    function setBasePrice(uint256 _price) external onlyOwner {
        basePricePerDay = _price;
        emit BasePriceUpdated(_price);
    }

    function setTreasury(address _treasury) external onlyOwner {
        require(_treasury != address(0), "AdHoarding: zero addr");
        treasury = _treasury;
    }

    function setCreator(address _creator) external onlyOwner {
        require(_creator != address(0), "AdHoarding: zero addr");
        creator = _creator;
    }

    function setTierMultiplier(uint8 tier, uint256 multiplierBps) external onlyOwner {
        require(tier >= 1 && tier <= 4, "AdHoarding: tier 1-4");
        tierMultiplier[tier] = multiplierBps;
    }

    // ── Internal ─────────────────────────────────────────────────────────

    function _safeTransfer(address to, uint256 amount) internal {
        if (amount == 0) return;
        (bool success, ) = payable(to).call{value: amount}("");
        if (!success) revert TransferFailed(to, amount);
    }
}
