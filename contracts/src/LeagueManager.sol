// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable2Step.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

import "./SWOSPlayerNFT.sol";
import "./SENSIToken.sol";

/**
 * @title LeagueManager
 * @notice Season lifecycle + wage distribution for SWOS420.
 *
 * Flow:
 *   1. registerTeam()   → owner registers team with player token IDs
 *   2. startSeason()    → locks teams, begins matchday cycle
 *   3. settleMatchday() → push results, distribute match wages
 *   4. settleSeason()   → distribute bonuses, reset season stats, age players
 *
 * Bonuses from rules.json:
 *   - Top scorer: 10,000 $SENSI
 *   - League winner: 100,000 $SENSI
 *   - Clean sheet: 500 $SENSI per match
 */
contract LeagueManager is Ownable2Step, ReentrancyGuard, Pausable {

    // ── Data Structures ─────────────────────────────────────────────────

    struct Team {
        address manager;           // Team manager wallet
        uint256[] playerTokenIds;  // NFT token IDs in squad
        uint256 points;
        uint256 goalsFor;
        uint256 goalsAgainst;
        bool registered;
    }

    enum SeasonState { Registration, Active, Settled }

    // ── State ────────────────────────────────────────────────────────────

    SWOSPlayerNFT public playerNFT;
    SENSIToken public sensiToken;

    uint256 public currentSeason;
    SeasonState public seasonState;
    uint256 public matchday;

    mapping(uint256 => mapping(bytes32 => Team)) public teams;  // season => teamCode => Team
    mapping(uint256 => bytes32[]) public seasonTeams;           // season => team codes

    // Wage rate: base multiplier (0.0018 × value in off-chain, simplified on-chain)
    uint256 public wageRatePerMatch = 1 ether;  // $SENSI per match per player (configurable)

    // League multipliers (matching rules.json)
    mapping(bytes32 => uint256) public leagueMultipliers;  // league name hash => multiplier (100 = 1.0x)

    // ── Events ───────────────────────────────────────────────────────────

    event TeamRegistered(uint256 indexed season, bytes32 indexed teamCode, address manager);
    event SeasonStarted(uint256 indexed season, uint256 teamCount);
    event MatchdaySettled(uint256 indexed season, uint256 matchday);
    event SeasonSettled(uint256 indexed season, bytes32 winner, bytes32 topScorer);
    event WagesDistributed(uint256 indexed season, uint256 matchday, uint256 totalWages);
    event BonusPaid(uint256 indexed season, string bonusType, address recipient, uint256 amount);

    // ── Constructor ──────────────────────────────────────────────────────

    constructor(
        address _playerNFT,
        address _sensiToken
    ) Ownable(msg.sender) {
        playerNFT = SWOSPlayerNFT(_playerNFT);
        sensiToken = SENSIToken(_sensiToken);
        currentSeason = 1;
        seasonState = SeasonState.Registration;

        // Default league multipliers (100 = 1.0x)
        leagueMultipliers[keccak256("Premier League")] = 180;
        leagueMultipliers[keccak256("La Liga")] = 150;
        leagueMultipliers[keccak256("Bundesliga")] = 130;
        leagueMultipliers[keccak256("Serie A")] = 130;
        leagueMultipliers[keccak256("Ligue 1")] = 120;
        leagueMultipliers[keccak256("default")] = 100;
    }

    // ── Registration ─────────────────────────────────────────────────────

    /// @notice Register a team for the current season.
    function registerTeam(
        bytes32 teamCode,
        uint256[] calldata playerTokenIds
    ) external whenNotPaused {
        require(seasonState == SeasonState.Registration, "Not registration phase");
        require(!teams[currentSeason][teamCode].registered, "Already registered");
        require(playerTokenIds.length >= 11, "Need at least 11 players");

        teams[currentSeason][teamCode] = Team({
            manager: msg.sender,
            playerTokenIds: playerTokenIds,
            points: 0,
            goalsFor: 0,
            goalsAgainst: 0,
            registered: true
        });
        seasonTeams[currentSeason].push(teamCode);

        emit TeamRegistered(currentSeason, teamCode, msg.sender);
    }

    // ── Season Lifecycle ─────────────────────────────────────────────────

    /// @notice Start the season (owner only).
    function startSeason() external onlyOwner {
        require(seasonState == SeasonState.Registration, "Not registration phase");
        require(seasonTeams[currentSeason].length >= 2, "Need at least 2 teams");

        seasonState = SeasonState.Active;
        matchday = 0;

        emit SeasonStarted(currentSeason, seasonTeams[currentSeason].length);
    }

    /// @notice Record matchday results and distribute wages (oracle/owner).
    function settleMatchday(
        bytes32[] calldata homeTeams,
        bytes32[] calldata awayTeams,
        uint256[] calldata homeGoals,
        uint256[] calldata awayGoals
    ) external onlyOwner nonReentrant whenNotPaused {
        require(seasonState == SeasonState.Active, "Season not active");
        require(
            homeTeams.length == awayTeams.length &&
            homeTeams.length == homeGoals.length &&
            homeTeams.length == awayGoals.length,
            "Array mismatch"
        );

        matchday++;
        uint256 totalWages = 0;

        for (uint256 i = 0; i < homeTeams.length; i++) {
            Team storage home = teams[currentSeason][homeTeams[i]];
            Team storage away = teams[currentSeason][awayTeams[i]];

            home.goalsFor += homeGoals[i];
            home.goalsAgainst += awayGoals[i];
            away.goalsFor += awayGoals[i];
            away.goalsAgainst += homeGoals[i];

            if (homeGoals[i] > awayGoals[i]) {
                home.points += 3;
            } else if (homeGoals[i] < awayGoals[i]) {
                away.points += 3;
            } else {
                home.points += 1;
                away.points += 1;
            }

            // Distribute match wages to all players in both teams
            totalWages += _distributeMatchWages(home);
            totalWages += _distributeMatchWages(away);
        }

        emit MatchdaySettled(currentSeason, matchday);
        emit WagesDistributed(currentSeason, matchday, totalWages);
    }

    /// @notice Settle season: bonuses + reset + advance.
    function settleSeason(
        bytes32 winnerCode,
        uint256 topScorerTokenId
    ) external onlyOwner nonReentrant {
        require(seasonState == SeasonState.Active, "Season not active");

        // League winner bonus
        Team storage winner = teams[currentSeason][winnerCode];
        require(winner.registered, "Winner not registered");
        sensiToken.mint(winner.manager, sensiToken.LEAGUE_WINNER_BONUS());
        emit BonusPaid(currentSeason, "league_winner", winner.manager, sensiToken.LEAGUE_WINNER_BONUS());

        // Top scorer bonus
        address topScorerOwner = playerNFT.ownerOf(topScorerTokenId);
        sensiToken.mint(topScorerOwner, sensiToken.TOP_SCORER_BONUS());
        emit BonusPaid(currentSeason, "top_scorer", topScorerOwner, sensiToken.TOP_SCORER_BONUS());

        // Reset season stats on all player NFTs
        bytes32[] memory teamCodes = seasonTeams[currentSeason];
        for (uint256 i = 0; i < teamCodes.length; i++) {
            Team storage t = teams[currentSeason][teamCodes[i]];
            for (uint256 j = 0; j < t.playerTokenIds.length; j++) {
                playerNFT.resetSeason(t.playerTokenIds[j]);
            }
        }

        seasonState = SeasonState.Settled;
        emit SeasonSettled(currentSeason, winnerCode, bytes32(topScorerTokenId));

        // Advance to next season
        currentSeason++;
        seasonState = SeasonState.Registration;
        matchday = 0;
    }

    // ── Admin ────────────────────────────────────────────────────────────

    function setWageRate(uint256 newRate) external onlyOwner {
        wageRatePerMatch = newRate;
    }

    function setLeagueMultiplier(string calldata league, uint256 multiplier) external onlyOwner {
        leagueMultipliers[keccak256(bytes(league))] = multiplier;
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ── Views ────────────────────────────────────────────────────────────

    function getTeam(uint256 season, bytes32 teamCode) external view returns (Team memory) {
        return teams[season][teamCode];
    }

    function getStandings(uint256 season) external view returns (bytes32[] memory) {
        return seasonTeams[season];
    }

    function getMatchday() external view returns (uint256) {
        return matchday;
    }

    // ── Internal ─────────────────────────────────────────────────────────

    function _distributeMatchWages(Team storage team) internal returns (uint256 totalPaid) {
        for (uint256 i = 0; i < team.playerTokenIds.length; i++) {
            uint256 tokenId = team.playerTokenIds[i];
            address owner = playerNFT.ownerOf(tokenId);
            sensiToken.distributeWages(owner, wageRatePerMatch);
            totalPaid += wageRatePerMatch;
        }
    }
}
