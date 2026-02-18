// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * SWOS420 $SENSI Token — ERC-20 Economy Token
 *
 * Powers the entire SWOS420 economy:
 * - Player wages (paid weekly to NFT owners)
 * - Match result rewards (win/draw/loss)
 * - Season bonuses (champion, top scorer, clean sheets)
 *
 * Tokenomics (from config/rules.json):
 * - 90% of wages → NFT owner
 * - 5% → burn (deflationary pressure)
 * - 5% → treasury (development fund)
 *
 * Deployment target: Base L2 (Sepolia testnet first)
 */

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";

contract SENSIToken is ERC20, ERC20Burnable, Ownable2Step {
    /// @notice Genesis supply: 1 billion SENSI
    uint256 public constant GENESIS_SUPPLY = 1_000_000_000 ether;

    /// @notice Match reward constants (in SENSI wei)
    uint256 public constant REWARD_PER_WIN = 100 ether;
    uint256 public constant REWARD_PER_DRAW = 50 ether;

    /// @notice Season bonus constants (from rules.json economy section)
    uint256 public constant LEAGUE_WINNER_BONUS = 100_000 ether;
    uint256 public constant TOP_SCORER_BONUS = 10_000 ether;
    uint256 public constant CLEAN_SHEET_BONUS = 500 ether;

    /// @notice Treasury address for the 5% treasury share
    address public treasury;

    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event RewardsMinted(address indexed to, uint256 amount, string reason);

    constructor(address _treasury) ERC20("Sensible Token", "SENSI") Ownable(msg.sender) {
        require(_treasury != address(0), "SENSIToken: treasury is zero address");
        treasury = _treasury;
        _mint(msg.sender, GENESIS_SUPPLY);
    }

    /// @notice Mint reward tokens — only callable by owner (LeagueRewards contract)
    /// @param to Recipient address
    /// @param amount Amount in SENSI wei
    function mintRewards(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "SENSIToken: mint to zero address");
        require(amount > 0, "SENSIToken: zero amount");
        _mint(to, amount);
    }

    /// @notice Distribute wages with economy splits (90/5/5)
    /// @dev Called by the wage distribution script/contract
    /// @param nftOwner NFT owner receiving 90% of wages
    /// @param totalWage Total wage amount before splits
    function distributeWage(address nftOwner, uint256 totalWage) external onlyOwner {
        require(nftOwner != address(0), "SENSIToken: owner is zero address");
        require(totalWage > 0, "SENSIToken: zero wage");

        // 90% to NFT owner
        uint256 ownerShare = (totalWage * 90) / 100;
        // 5% burn (deflationary)
        uint256 burnShare = (totalWage * 5) / 100;
        // 5% treasury (remainder to avoid rounding loss)
        uint256 treasuryShare = totalWage - ownerShare - burnShare;

        _mint(nftOwner, ownerShare);
        _mint(treasury, treasuryShare);
        // Burn share: mint then burn for event transparency
        _mint(address(this), burnShare);
        _burn(address(this), burnShare);
    }

    /// @notice Update the treasury address
    /// @param _treasury New treasury address
    function setTreasury(address _treasury) external onlyOwner {
        require(_treasury != address(0), "SENSIToken: treasury is zero address");
        address old = treasury;
        treasury = _treasury;
        emit TreasuryUpdated(old, _treasury);
    }
}
