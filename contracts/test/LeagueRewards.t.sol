// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/SENSIToken.sol";
import "../src/LeagueRewards.sol";

contract LeagueRewardsTest is Test {
    SENSIToken public sensi;
    LeagueRewards public rewards;

    address public owner = address(this);
    address public treasury = address(0xDAD);
    address public manager1 = address(0x1);
    address public manager2 = address(0x2);

    bytes32 public matchId1 = keccak256("season25/26-md1-MCI-ARS");
    bytes32 public matchId2 = keccak256("season25/26-md1-LIV-CHE");
    bytes32 public seasonId = keccak256("season25/26");

    function setUp() public {
        sensi = new SENSIToken(treasury);
        rewards = new LeagueRewards(address(sensi));

        // Transfer SENSI ownership to LeagueRewards so it can mint
        sensi.transferOwnership(address(rewards));
        vm.prank(address(rewards));
        sensi.acceptOwnership();
    }

    // ── Match Settlement ────────────────────────────────────────────────

    function testSettleMatch_win() public {
        rewards.settleMatch(matchId1, manager1, manager2, false, true);

        // Winner gets 100 SENSI
        assertEq(sensi.balanceOf(manager1), 100 ether);
        // Loser gets 0
        assertEq(sensi.balanceOf(manager2), 0);
        // Match is settled
        assertTrue(rewards.settledMatches(matchId1));
    }

    function testSettleMatch_draw() public {
        rewards.settleMatch(matchId1, manager1, manager2, true, false);

        // Both get 50 SENSI
        assertEq(sensi.balanceOf(manager1), 50 ether);
        assertEq(sensi.balanceOf(manager2), 50 ether);
    }

    function testSettleMatch_doubleSettle_reverts() public {
        rewards.settleMatch(matchId1, manager1, manager2, false, true);

        vm.expectRevert("LeagueRewards: match already settled");
        rewards.settleMatch(matchId1, manager1, manager2, false, true);
    }

    function testSettleMatch_differentMatches() public {
        rewards.settleMatch(matchId1, manager1, manager2, false, true);
        rewards.settleMatch(matchId2, manager1, manager2, false, false);

        // manager1 won first, lost second: 100 SENSI
        assertEq(sensi.balanceOf(manager1), 100 ether);
        // manager2 lost first, won second: 100 SENSI
        assertEq(sensi.balanceOf(manager2), 100 ether);
    }

    function testSettleMatch_notOwner_reverts() public {
        vm.prank(manager1);
        vm.expectRevert();
        rewards.settleMatch(matchId1, manager1, manager2, false, true);
    }

    function testSettleMatch_zeroAddress_reverts() public {
        vm.expectRevert("LeagueRewards: zero address");
        rewards.settleMatch(matchId1, address(0), manager2, false, true);
    }

    // ── Season Bonuses ──────────────────────────────────────────────────

    function testDistributeChampionBonus() public {
        rewards.distributeChampionBonus(seasonId, manager1);
        assertEq(sensi.balanceOf(manager1), 100_000 ether);
    }

    function testDistributeChampionBonus_double_reverts() public {
        rewards.distributeChampionBonus(seasonId, manager1);

        vm.expectRevert("LeagueRewards: bonus already distributed");
        rewards.distributeChampionBonus(seasonId, manager1);
    }

    function testDistributeTopScorerBonus() public {
        rewards.distributeTopScorerBonus(seasonId, manager1);
        assertEq(sensi.balanceOf(manager1), 10_000 ether);
    }

    function testDistributeCleanSheetBonus() public {
        rewards.distributeCleanSheetBonus(seasonId, manager1, 15);
        // 500 * 15 = 7500 SENSI
        assertEq(sensi.balanceOf(manager1), 7_500 ether);
    }

    function testDistributeCleanSheetBonus_zeroSheets_reverts() public {
        vm.expectRevert("LeagueRewards: zero clean sheets");
        rewards.distributeCleanSheetBonus(seasonId, manager1, 0);
    }

    // ── Full Season Scenario ────────────────────────────────────────────

    function testFullSeasonScenario() public {
        // Settle 3 matches
        rewards.settleMatch(keccak256("md1"), manager1, manager2, false, true);  // m1 wins
        rewards.settleMatch(keccak256("md2"), manager1, manager2, true, false);  // draw
        rewards.settleMatch(keccak256("md3"), manager1, manager2, false, false); // m2 wins

        // Expected: manager1 = 100 + 50 = 150, manager2 = 50 + 100 = 150
        assertEq(sensi.balanceOf(manager1), 150 ether);
        assertEq(sensi.balanceOf(manager2), 150 ether);

        // Season bonuses — manager1 is champion and top scorer
        rewards.distributeChampionBonus(seasonId, manager1);
        rewards.distributeTopScorerBonus(seasonId, manager1);
        rewards.distributeCleanSheetBonus(seasonId, manager2, 10);

        // Final: manager1 = 150 + 100000 + 10000 = 110150
        assertEq(sensi.balanceOf(manager1), 110_150 ether);
        // Final: manager2 = 150 + 5000 = 5150
        assertEq(sensi.balanceOf(manager2), 5_150 ether);
    }
}
