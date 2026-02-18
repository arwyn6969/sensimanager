// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * SWOS420 League Rewards — Match Settlement & Season Bonuses
 *
 * Orchestrates all $SENSI reward distribution:
 * - Match results: WIN = 100 SENSI, DRAW = 50 SENSI each
 * - Season bonuses: Champion (100K), Top Scorer (10K), Clean Sheet (500)
 *
 * Only the owner (oracle/backend) can settle matches and distribute bonuses.
 * All rewards are minted via SENSIToken.mintRewards().
 *
 * Deployment: Deploy after SENSIToken. Transfer SENSIToken ownership to this contract
 * so it can call mintRewards().
 */

import "@openzeppelin/contracts/access/Ownable2Step.sol";

interface ISENSIToken {
    function mintRewards(address to, uint256 amount) external;
    function REWARD_PER_WIN() external view returns (uint256);
    function REWARD_PER_DRAW() external view returns (uint256);
    function LEAGUE_WINNER_BONUS() external view returns (uint256);
    function TOP_SCORER_BONUS() external view returns (uint256);
    function CLEAN_SHEET_BONUS() external view returns (uint256);
}

contract LeagueRewards is Ownable2Step {
    ISENSIToken public sensiToken;

    /// @notice Track settled matches to prevent double-settlement
    mapping(bytes32 => bool) public settledMatches;

    /// @notice Track distributed season bonuses
    mapping(bytes32 => bool) public distributedBonuses;

    event MatchSettled(
        bytes32 indexed matchId,
        address indexed winner,
        address indexed loser,
        bool isDraw,
        uint256 winnerReward,
        uint256 loserReward
    );

    event SeasonBonusDistributed(
        string indexed bonusType,
        address indexed recipient,
        uint256 amount
    );

    constructor(address _sensiToken) Ownable(msg.sender) {
        require(_sensiToken != address(0), "LeagueRewards: token is zero address");
        sensiToken = ISENSIToken(_sensiToken);
    }

    /// @notice Settle a match and distribute rewards
    /// @param matchId Unique match identifier (keccak256 of season + matchday + teams)
    /// @param manager1 Address of home manager
    /// @param manager2 Address of away manager
    /// @param isDraw True if the match ended in a draw
    /// @param manager1Won True if manager1 won (ignored if isDraw)
    function settleMatch(
        bytes32 matchId,
        address manager1,
        address manager2,
        bool isDraw,
        bool manager1Won
    ) external onlyOwner {
        require(!settledMatches[matchId], "LeagueRewards: match already settled");
        require(manager1 != address(0) && manager2 != address(0), "LeagueRewards: zero address");

        settledMatches[matchId] = true;

        if (isDraw) {
            uint256 drawReward = sensiToken.REWARD_PER_DRAW();
            sensiToken.mintRewards(manager1, drawReward);
            sensiToken.mintRewards(manager2, drawReward);
            emit MatchSettled(matchId, manager1, manager2, true, drawReward, drawReward);
        } else {
            uint256 winReward = sensiToken.REWARD_PER_WIN();
            address winner = manager1Won ? manager1 : manager2;
            address loser = manager1Won ? manager2 : manager1;
            sensiToken.mintRewards(winner, winReward);
            emit MatchSettled(matchId, winner, loser, false, winReward, 0);
        }
    }

    /// @notice Distribute season champion bonus
    /// @param seasonId Unique season identifier
    /// @param champion Address of the league champion's manager
    function distributeChampionBonus(bytes32 seasonId, address champion) external onlyOwner {
        bytes32 key = keccak256(abi.encodePacked(seasonId, "champion"));
        require(!distributedBonuses[key], "LeagueRewards: bonus already distributed");
        require(champion != address(0), "LeagueRewards: zero address");

        distributedBonuses[key] = true;
        uint256 bonus = sensiToken.LEAGUE_WINNER_BONUS();
        sensiToken.mintRewards(champion, bonus);
        emit SeasonBonusDistributed("champion", champion, bonus);
    }

    /// @notice Distribute top scorer bonus
    /// @param seasonId Unique season identifier
    /// @param topScorer Address of the top scorer's manager
    function distributeTopScorerBonus(bytes32 seasonId, address topScorer) external onlyOwner {
        bytes32 key = keccak256(abi.encodePacked(seasonId, "topScorer"));
        require(!distributedBonuses[key], "LeagueRewards: bonus already distributed");
        require(topScorer != address(0), "LeagueRewards: zero address");

        distributedBonuses[key] = true;
        uint256 bonus = sensiToken.TOP_SCORER_BONUS();
        sensiToken.mintRewards(topScorer, bonus);
        emit SeasonBonusDistributed("topScorer", topScorer, bonus);
    }

    /// @notice Distribute clean sheet bonus to a goalkeeper's manager
    /// @param seasonId Unique season identifier
    /// @param keeperManager Address of the GK's manager
    /// @param cleanSheets Number of clean sheets to reward
    function distributeCleanSheetBonus(
        bytes32 seasonId,
        address keeperManager,
        uint256 cleanSheets
    ) external onlyOwner {
        bytes32 key = keccak256(abi.encodePacked(seasonId, keeperManager, "cleanSheet"));
        require(!distributedBonuses[key], "LeagueRewards: bonus already distributed");
        require(keeperManager != address(0), "LeagueRewards: zero address");
        require(cleanSheets > 0, "LeagueRewards: zero clean sheets");

        distributedBonuses[key] = true;
        uint256 bonus = sensiToken.CLEAN_SHEET_BONUS() * cleanSheets;
        sensiToken.mintRewards(keeperManager, bonus);
        emit SeasonBonusDistributed("cleanSheet", keeperManager, bonus);
    }

    /// @notice Update the SENSI token contract address
    /// @param _sensiToken New SENSIToken address
    function setSENSIToken(address _sensiToken) external onlyOwner {
        require(_sensiToken != address(0), "LeagueRewards: token is zero address");
        sensiToken = ISENSIToken(_sensiToken);
    }
}
