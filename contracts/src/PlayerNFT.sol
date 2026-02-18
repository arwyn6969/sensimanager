// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * SWOS420 Player NFT — Production ERC-721
 *
 * Each token represents a player in the SWOS420 universe.
 * Token IDs correspond to SWOSPlayer.base_id (deterministic hash
 * of sofifa_id + season), converted from hex string to uint256.
 *
 * Deployment target: Base L2 (Sepolia testnet first)
 *
 * Features:
 * - Single + batch minting for initial roster deployment
 * - Dynamic metadata updates from match engine oracle
 * - Wage accumulation + claim (wired to $SENSI ERC-20)
 * - Oracle pattern for off-chain simulation integration
 *
 * Dependencies:
 * - OpenZeppelin Contracts v5.0+
 */

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";

interface IERC20Transfer {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract PlayerNFT is ERC721, Ownable2Step {
    /// @notice Match engine oracle address (updates player metadata + wages)
    address public oracle;

    /// @notice $SENSI token contract for wage claims
    IERC20Transfer public sensiToken;

    /// @notice Player metadata URI mapping (IPFS/Arweave hashes)
    mapping(uint256 => string) private _tokenURIs;

    /// @notice Accumulated wages per token (in $SENSI wei)
    mapping(uint256 => uint256) public accumulatedWages;

    /// @notice Total number of players minted
    uint256 public totalMinted;

    // ── Events ──────────────────────────────────────────────────────────

    event MetadataUpdated(uint256 indexed tokenId, string newUri);
    event WagesClaimed(uint256 indexed tokenId, address indexed owner, uint256 amount);
    event WagesAdded(uint256 indexed tokenId, uint256 amount);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    event SENSITokenUpdated(address indexed oldToken, address indexed newToken);

    // ── Modifiers ───────────────────────────────────────────────────────

    modifier onlyOracle() {
        require(msg.sender == oracle, "PlayerNFT: caller is not the oracle");
        _;
    }

    // ── Constructor ─────────────────────────────────────────────────────

    constructor(address _oracle) ERC721("SWOS420 Player", "SWOS") Ownable(msg.sender) {
        require(_oracle != address(0), "PlayerNFT: oracle is zero address");
        oracle = _oracle;
    }

    // ── Minting ─────────────────────────────────────────────────────────

    /// @notice Mint a single player NFT
    /// @param to Recipient address
    /// @param tokenId Player base_id (hex → uint256) from the simulation
    function mint(address to, uint256 tokenId) external onlyOwner {
        require(to != address(0), "PlayerNFT: mint to zero address");
        _safeMint(to, tokenId);
        totalMinted++;
    }

    /// @notice Batch mint player NFTs (gas savings for initial roster)
    /// @param to Recipient address
    /// @param tokenIds Array of player base_ids
    function mintBatch(address to, uint256[] calldata tokenIds) external onlyOwner {
        require(to != address(0), "PlayerNFT: mint to zero address");
        require(tokenIds.length > 0, "PlayerNFT: empty array");
        require(tokenIds.length <= 100, "PlayerNFT: batch too large");

        for (uint256 i = 0; i < tokenIds.length; i++) {
            _safeMint(to, tokenIds[i]);
        }
        totalMinted += tokenIds.length;
    }

    // ── Oracle Functions ────────────────────────────────────────────────

    /// @notice Update player metadata after match/season events
    /// @param tokenId Player base_id
    /// @param newUri Updated metadata URI (IPFS CID or Arweave TX)
    function updateMetadata(uint256 tokenId, string memory newUri) external onlyOracle {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        require(bytes(newUri).length > 0, "PlayerNFT: empty URI");
        _tokenURIs[tokenId] = newUri;
        emit MetadataUpdated(tokenId, newUri);
    }

    /// @notice Accumulate wages for a player (called by oracle after each matchday)
    /// @param tokenId Player base_id
    /// @param amount Wage amount in $SENSI wei
    function addWages(uint256 tokenId, uint256 amount) external onlyOracle {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        require(amount > 0, "PlayerNFT: zero wage");
        accumulatedWages[tokenId] += amount;
        emit WagesAdded(tokenId, amount);
    }

    /// @notice Batch add wages for multiple players
    /// @param tokenIds Array of player base_ids
    /// @param amounts Array of wage amounts in $SENSI wei
    function addWagesBatch(
        uint256[] calldata tokenIds,
        uint256[] calldata amounts
    ) external onlyOracle {
        require(tokenIds.length == amounts.length, "PlayerNFT: length mismatch");
        require(tokenIds.length > 0, "PlayerNFT: empty array");

        for (uint256 i = 0; i < tokenIds.length; i++) {
            require(_ownerOf(tokenIds[i]) != address(0), "PlayerNFT: nonexistent token");
            require(amounts[i] > 0, "PlayerNFT: zero wage");
            accumulatedWages[tokenIds[i]] += amounts[i];
            emit WagesAdded(tokenIds[i], amounts[i]);
        }
    }

    // ── Wage Claims ─────────────────────────────────────────────────────

    /// @notice Claim accumulated wages for a player you own
    /// @param tokenId Player base_id
    function claimWages(uint256 tokenId) external {
        require(ownerOf(tokenId) == msg.sender, "PlayerNFT: not token owner");
        uint256 amount = accumulatedWages[tokenId];
        require(amount > 0, "PlayerNFT: no wages to claim");

        // Clear before transfer (checks-effects-interactions)
        accumulatedWages[tokenId] = 0;

        // Transfer $SENSI from this contract to the NFT owner
        require(
            address(sensiToken) != address(0),
            "PlayerNFT: SENSI token not set"
        );
        require(
            sensiToken.transfer(msg.sender, amount),
            "PlayerNFT: SENSI transfer failed"
        );

        emit WagesClaimed(tokenId, msg.sender, amount);
    }

    // ── Admin ───────────────────────────────────────────────────────────

    /// @notice Update the oracle address
    /// @param _oracle New oracle address
    function setOracle(address _oracle) external onlyOwner {
        require(_oracle != address(0), "PlayerNFT: oracle is zero address");
        address old = oracle;
        oracle = _oracle;
        emit OracleUpdated(old, _oracle);
    }

    /// @notice Set the $SENSI token contract address
    /// @param _sensiToken Address of the SENSIToken contract
    function setSENSIToken(address _sensiToken) external onlyOwner {
        require(_sensiToken != address(0), "PlayerNFT: token is zero address");
        address old = address(sensiToken);
        sensiToken = IERC20Transfer(_sensiToken);
        emit SENSITokenUpdated(old, _sensiToken);
    }

    // ── Views ───────────────────────────────────────────────────────────

    /// @notice Return the metadata URI for a token
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        return _tokenURIs[tokenId];
    }
}
