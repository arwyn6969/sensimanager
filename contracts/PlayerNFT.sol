// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * SWOS420 Player NFT — Phase 3 Stub
 *
 * Each token represents a player in the SWOS420 universe.
 * Token IDs correspond to SWOSPlayer.base_id (deterministic hash
 * of sofifa_id + season).
 *
 * Deployment target: Base L2
 *
 * Features (to be implemented):
 * - Batch minting via ERC721A for gas efficiency
 * - Dynamic metadata updates from the match engine oracle
 * - Wage claim function for NFT owners ($CM ERC-20)
 * - Royalty support (ERC-2981)
 *
 * Dependencies:
 * - OpenZeppelin Contracts v5.0+
 * - ERC721A (chiru-labs/ERC721A)
 *
 * NOTE: This is a non-functional stub for architecture planning.
 * Do NOT deploy to mainnet without full audit.
 */

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract PlayerNFT is ERC721, Ownable {

    // Match engine oracle address (updates player metadata)
    address public oracle;

    // Player metadata URI mapping
    mapping(uint256 => string) private _tokenURIs;

    // Wage accumulation per token (in $CM wei)
    mapping(uint256 => uint256) public accumulatedWages;

    // $CM token contract address (ERC-20)
    address public cmToken;

    event MetadataUpdated(uint256 indexed tokenId, string newUri);
    event WagesClaimed(uint256 indexed tokenId, address indexed owner, uint256 amount);
    event OracleUpdated(address indexed newOracle);

    modifier onlyOracle() {
        require(msg.sender == oracle, "PlayerNFT: caller is not the oracle");
        _;
    }

    constructor(address _oracle)
        ERC721("SWOS420 Player", "SWOS")
        Ownable(msg.sender)
    {
        oracle = _oracle;
    }

    /// @notice Mint a single player NFT
    /// @param to Recipient address
    /// @param tokenId Player base_id from the simulation
    function mint(address to, uint256 tokenId) external onlyOwner {
        _safeMint(to, tokenId);
    }

    /// @notice Batch mint player NFTs (gas-optimized for initial roster)
    /// @param to Recipient address
    /// @param tokenIds Array of player base_ids
    function mintBatch(address to, uint256[] calldata tokenIds) external onlyOwner {
        for (uint256 i = 0; i < tokenIds.length; i++) {
            _safeMint(to, tokenIds[i]);
        }
    }

    /// @notice Update player metadata from match engine results
    /// @param tokenId Player base_id
    /// @param newUri Updated metadata URI (IPFS or Arweave)
    function updateMetadata(uint256 tokenId, string memory newUri) external onlyOracle {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        _tokenURIs[tokenId] = newUri;
        emit MetadataUpdated(tokenId, newUri);
    }

    /// @notice Accumulate wages for a player (called by oracle after each matchday)
    /// @param tokenId Player base_id
    /// @param amount Wage amount in $CM wei
    function addWages(uint256 tokenId, uint256 amount) external onlyOracle {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        accumulatedWages[tokenId] += amount;
    }

    /// @notice Claim accumulated wages for a player you own
    /// @param tokenId Player base_id
    function claimWages(uint256 tokenId) external {
        require(ownerOf(tokenId) == msg.sender, "PlayerNFT: not token owner");
        uint256 amount = accumulatedWages[tokenId];
        require(amount > 0, "PlayerNFT: no wages to claim");

        accumulatedWages[tokenId] = 0;

        // TODO: Transfer $CM tokens to msg.sender
        // ICMToken(cmToken).transfer(msg.sender, amount);

        emit WagesClaimed(tokenId, msg.sender, amount);
    }

    /// @notice Update the oracle address
    function setOracle(address _oracle) external onlyOwner {
        oracle = _oracle;
        emit OracleUpdated(_oracle);
    }

    /// @notice Update the $CM token contract address
    function setCMToken(address _cmToken) external onlyOwner {
        cmToken = _cmToken;
    }

    /// @notice Return the metadata URI for a token
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "PlayerNFT: nonexistent token");
        return _tokenURIs[tokenId];
    }
}
