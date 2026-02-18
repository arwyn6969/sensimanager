// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/SENSIToken.sol";

contract SENSITokenTest is Test {
    SENSIToken public sensi;

    address public owner = address(this);
    address public treasury = address(0xDAD);
    address public user1 = address(0x1);
    address public user2 = address(0x2);

    function setUp() public {
        sensi = new SENSIToken(treasury);
    }

    // ── Genesis ─────────────────────────────────────────────────────────

    function testGenesisSupply() public view {
        assertEq(sensi.totalSupply(), 1_000_000_000 ether);
        assertEq(sensi.balanceOf(owner), 1_000_000_000 ether);
    }

    function testNameAndSymbol() public view {
        assertEq(sensi.name(), "Sensible Token");
        assertEq(sensi.symbol(), "SENSI");
    }

    function testTreasury() public view {
        assertEq(sensi.treasury(), treasury);
    }

    // ── Minting ─────────────────────────────────────────────────────────

    function testMintRewards() public {
        sensi.mintRewards(user1, 1000 ether);
        assertEq(sensi.balanceOf(user1), 1000 ether);
    }

    function testMintRewards_notOwner_reverts() public {
        vm.prank(user1);
        vm.expectRevert();
        sensi.mintRewards(user1, 1000 ether);
    }

    function testMintRewards_zeroAddress_reverts() public {
        vm.expectRevert("SENSIToken: mint to zero address");
        sensi.mintRewards(address(0), 1000 ether);
    }

    function testMintRewards_zeroAmount_reverts() public {
        vm.expectRevert("SENSIToken: zero amount");
        sensi.mintRewards(user1, 0);
    }

    // ── Wage Distribution ───────────────────────────────────────────────

    function testDistributeWage_splits() public {
        uint256 totalWage = 10_000 ether;

        uint256 treasuryBefore = sensi.balanceOf(treasury);
        uint256 supplyBefore = sensi.totalSupply();

        sensi.distributeWage(user1, totalWage);

        // 90% to owner
        assertEq(sensi.balanceOf(user1), 9_000 ether);
        // 5% to treasury
        assertEq(sensi.balanceOf(treasury) - treasuryBefore, 500 ether);
        // 5% burned — net supply should increase by 9500 (owner + treasury)
        assertEq(sensi.totalSupply() - supplyBefore, 9_500 ether);
    }

    function testDistributeWage_smallAmount() public {
        // Test rounding with small wages
        sensi.distributeWage(user1, 100);

        // 90% of 100 = 90
        assertEq(sensi.balanceOf(user1), 90);
        // 5% of 100 = 5 (burn)
        // remainder = 100 - 90 - 5 = 5 (treasury)
        assertEq(sensi.balanceOf(treasury), 5);
    }

    function testDistributeWage_notOwner_reverts() public {
        vm.prank(user1);
        vm.expectRevert();
        sensi.distributeWage(user1, 1000 ether);
    }

    function testDistributeWage_zeroAddress_reverts() public {
        vm.expectRevert("SENSIToken: owner is zero address");
        sensi.distributeWage(address(0), 1000 ether);
    }

    // ── Burn ────────────────────────────────────────────────────────────

    function testBurn() public {
        uint256 burnAmount = 1000 ether;
        uint256 supplyBefore = sensi.totalSupply();

        sensi.burn(burnAmount);

        assertEq(sensi.totalSupply(), supplyBefore - burnAmount);
        assertEq(sensi.balanceOf(owner), supplyBefore - burnAmount);
    }

    // ── Transfer ────────────────────────────────────────────────────────

    function testTransfer() public {
        sensi.transfer(user1, 5000 ether);
        assertEq(sensi.balanceOf(user1), 5000 ether);
    }

    // ── Treasury Update ─────────────────────────────────────────────────

    function testSetTreasury() public {
        address newTreasury = address(0xBEEF);
        sensi.setTreasury(newTreasury);
        assertEq(sensi.treasury(), newTreasury);
    }

    function testSetTreasury_zeroAddress_reverts() public {
        vm.expectRevert("SENSIToken: treasury is zero address");
        sensi.setTreasury(address(0));
    }

    // ── Constants ───────────────────────────────────────────────────────

    function testRewardConstants() public view {
        assertEq(sensi.REWARD_PER_WIN(), 100 ether);
        assertEq(sensi.REWARD_PER_DRAW(), 50 ether);
        assertEq(sensi.LEAGUE_WINNER_BONUS(), 100_000 ether);
        assertEq(sensi.TOP_SCORER_BONUS(), 10_000 ether);
        assertEq(sensi.CLEAN_SHEET_BONUS(), 500 ether);
    }
}
