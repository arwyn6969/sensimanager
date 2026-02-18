// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/SWOSPlayerNFT.sol";
import "../src/SENSIToken.sol";
import "../src/TransferMarket.sol";
import "../src/LeagueManager.sol";

/**
 * @title SWOS420 Contract Test Suite
 * @notice Comprehensive Forge tests for all 4 contracts.
 */
contract SWOSPlayerNFTTest is Test {
    SWOSPlayerNFT public nft;
    address public owner = address(this);
    address public oracle = address(0xBEEF);
    address public alice = address(0xA11CE);

    function setUp() public {
        nft = new SWOSPlayerNFT();
        nft.setOracle(oracle);
    }

    // ── Minting ──────────────────────────────────────────────────────

    function test_mintPlayer() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Thierry Henry", skills, 27, 10_000_000);

        assertEq(nft.ownerOf(1), alice);
        SWOSPlayerNFT.Player memory p = nft.getPlayer(1);
        assertEq(p.name, "Thierry Henry");
        assertEq(p.baseSkills[0], 7); // PA
        assertEq(p.baseSkills[6], 7); // FI
        assertEq(p.age, 27);
        assertEq(p.value, 10_000_000);
        assertEq(p.form, 0);
    }

    function test_mintBatch() public {
        uint256[] memory ids = new uint256[](3);
        ids[0] = 1; ids[1] = 2; ids[2] = 3;

        string[] memory names = new string[](3);
        names[0] = "Henry"; names[1] = "Bergkamp"; names[2] = "Vieira";

        uint8[7][] memory skills = new uint8[7][](3);
        skills[0] = [uint8(7), 5, 6, 4, 6, 5, 7];
        skills[1] = [uint8(6), 4, 5, 5, 7, 4, 6];
        skills[2] = [uint8(5), 6, 6, 7, 5, 6, 4];

        uint8[] memory ages = new uint8[](3);
        ages[0] = 27; ages[1] = 33; ages[2] = 28;

        uint256[] memory values = new uint256[](3);
        values[0] = 10_000_000; values[1] = 5_000_000; values[2] = 8_000_000;

        nft.mintBatch(alice, ids, names, skills, ages, values);

        assertEq(nft.balanceOf(alice), 3);
        assertEq(nft.getPlayer(2).name, "Bergkamp");
    }

    function test_mintOnlyOwner() public {
        vm.prank(alice);
        uint8[7] memory skills;
        vm.expectRevert();
        nft.mintPlayer(alice, 1, "Test", skills, 25, 1_000_000);
    }

    // ── Oracle Updates ───────────────────────────────────────────────

    function test_updateForm() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);

        vm.prank(oracle);
        nft.updateForm(1, 25, 2);

        SWOSPlayerNFT.Player memory p = nft.getPlayer(1);
        assertEq(p.form, 25);
        assertEq(p.seasonGoals, 2);
        assertEq(p.totalGoals, 2);
        assertTrue(p.value > 0); // Value should be recalculated
    }

    function test_updateFormOnlyOracle() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);

        vm.prank(alice);
        vm.expectRevert(SWOSPlayerNFT.OnlyOracle.selector);
        nft.updateForm(1, 10, 1);
    }

    function test_batchUpdateForm() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);
        nft.mintPlayer(alice, 2, "Bergkamp", skills, 33, 5_000_000);

        uint256[] memory ids = new uint256[](2);
        ids[0] = 1; ids[1] = 2;

        int8[] memory forms = new int8[](2);
        forms[0] = 30; forms[1] = -10;

        uint16[] memory goals = new uint16[](2);
        goals[0] = 2; goals[1] = 0;

        vm.prank(oracle);
        nft.batchUpdateForm(ids, forms, goals);

        assertEq(nft.getPlayer(1).form, 30);
        assertEq(nft.getPlayer(2).form, -10);
    }

    // ── Effective Skills ─────────────────────────────────────────────

    function test_effectiveSkillsNeutralForm() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);

        uint8[7] memory eff = nft.getEffectiveSkills(1);
        // form = 0 → effective = base × 100/100 = base
        assertEq(eff[0], 7);
        assertEq(eff[1], 5);
    }

    function test_effectiveSkillsPositiveForm() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);

        vm.prank(oracle);
        nft.updateForm(1, 50, 0); // +50% form

        uint8[7] memory eff = nft.getEffectiveSkills(1);
        // 7 × 150/100 = 10 (capped at 15)
        assertEq(eff[0], 10);
    }

    function test_effectiveSkillsNegativeFormClamps() public {
        // Very low skills with very negative form → should clamp to 0
        uint8[7] memory skills = [uint8(2), 2, 2, 2, 2, 2, 2];
        nft.mintPlayer(alice, 1, "Weak", skills, 30, 100_000);

        vm.prank(oracle);
        nft.updateForm(1, -100, 0); // form = -100

        uint8[7] memory eff = nft.getEffectiveSkills(1);
        // 2 × 0/100 = 0 (clamped)
        assertEq(eff[0], 0);
    }

    // ── Season Reset ─────────────────────────────────────────────────

    function test_resetSeason() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "Henry", skills, 27, 10_000_000);

        vm.prank(oracle);
        nft.updateForm(1, 20, 15);

        vm.prank(oracle);
        nft.resetSeason(1);

        SWOSPlayerNFT.Player memory p = nft.getPlayer(1);
        assertEq(p.seasonGoals, 0);
        assertEq(p.totalGoals, 15); // Total preserved
        assertEq(p.age, 28); // Aged by 1
    }

    // ── Pausable ─────────────────────────────────────────────────────

    function test_pauseBlocksMint() public {
        nft.pause();
        uint8[7] memory skills;
        vm.expectRevert();
        nft.mintPlayer(alice, 1, "Test", skills, 25, 1_000_000);
    }

    // ── Enumerable ───────────────────────────────────────────────────

    function test_totalSupply() public {
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(alice, 1, "A", skills, 25, 1_000_000);
        nft.mintPlayer(alice, 2, "B", skills, 25, 1_000_000);
        assertEq(nft.totalSupply(), 2);
    }
}


contract SENSITokenTest is Test {
    SENSIToken public sensi;
    address public owner = address(this);
    address public treasury = address(0x7EA5);
    address public alice = address(0xA11CE);
    address public bob = address(0xB0B);

    function setUp() public {
        sensi = new SENSIToken(treasury);
    }

    function test_initialSupply() public view {
        assertEq(sensi.totalSupply(), 1_000_000_000 ether);
        assertEq(sensi.balanceOf(owner), 1_000_000_000 ether);
    }

    function test_name() public view {
        assertEq(sensi.name(), "Sensible Token");
        assertEq(sensi.symbol(), "SENSI");
    }

    function test_mint() public {
        sensi.mint(alice, 1_000 ether);
        assertEq(sensi.balanceOf(alice), 1_000 ether);
    }

    function test_mintOnlyOwner() public {
        vm.prank(alice);
        vm.expectRevert();
        sensi.mint(alice, 1_000 ether);
    }

    function test_distributeWages() public {
        sensi.distributeWages(alice, 1_000 ether);

        // 90% to owner
        assertEq(sensi.balanceOf(alice), 900 ether);
        // 5% to treasury
        assertEq(sensi.balanceOf(treasury), 50 ether);
        // 5% burned (net zero on contract balance)
    }

    function test_distributeWagesTwice() public {
        sensi.distributeWages(alice, 1_000 ether);
        sensi.distributeWages(bob, 500 ether);

        assertEq(sensi.balanceOf(alice), 900 ether);
        assertEq(sensi.balanceOf(bob), 450 ether);
    }

    function test_burn() public {
        sensi.burn(100 ether);
        assertEq(sensi.balanceOf(owner), 1_000_000_000 ether - 100 ether);
    }

    function test_constants() public view {
        assertEq(sensi.TOP_SCORER_BONUS(), 10_000 ether);
        assertEq(sensi.LEAGUE_WINNER_BONUS(), 100_000 ether);
        assertEq(sensi.CLEAN_SHEET_BONUS(), 500 ether);
    }
}


contract TransferMarketTest is Test {
    SWOSPlayerNFT public nft;
    SENSIToken public sensi;
    TransferMarket public market;
    address public owner = address(this);
    address public treasury = address(0x7EA5);
    address public seller = address(0x5E11);
    address public buyer = address(0xBEE);

    function setUp() public {
        nft = new SWOSPlayerNFT();
        sensi = new SENSIToken(treasury);
        market = new TransferMarket(address(nft), address(sensi), treasury);

        // Mint a player to seller
        uint8[7] memory skills = [uint8(7), 5, 6, 4, 6, 5, 7];
        nft.mintPlayer(seller, 1, "Henry", skills, 27, 10_000_000);

        // Give buyer some $SENSI
        sensi.transfer(buyer, 1_000_000 ether);
    }

    function test_listPlayer() public {
        vm.startPrank(seller);
        nft.approve(address(market), 1);
        market.listPlayer(1, 100 ether, 500 ether);
        vm.stopPrank();

        assertEq(nft.ownerOf(1), address(market)); // Escrowed
    }

    function test_placeBidAndResolve() public {
        // List
        vm.startPrank(seller);
        nft.approve(address(market), 1);
        market.listPlayer(1, 100 ether, 0);
        vm.stopPrank();

        // Bid
        vm.startPrank(buyer);
        sensi.approve(address(market), 200 ether);
        market.placeBid(1, 200 ether);
        vm.stopPrank();

        // Fast forward past deadline
        vm.warp(block.timestamp + 4 days);
        market.resolveListing(1);

        assertEq(nft.ownerOf(1), buyer);
    }

    function test_releaseClauseAutoAccepts() public {
        // List with release clause of 300 $SENSI
        vm.startPrank(seller);
        nft.approve(address(market), 1);
        market.listPlayer(1, 100 ether, 300 ether);
        vm.stopPrank();

        // Bid at release clause → auto-resolve
        vm.startPrank(buyer);
        sensi.approve(address(market), 300 ether);
        market.placeBid(1, 300 ether);
        vm.stopPrank();

        // Should already be transferred
        assertEq(nft.ownerOf(1), buyer);
    }

    function test_cancelListingNoBids() public {
        vm.startPrank(seller);
        nft.approve(address(market), 1);
        market.listPlayer(1, 100 ether, 0);
        market.cancelListing(1);
        vm.stopPrank();

        assertEq(nft.ownerOf(1), seller); // Returned
    }
}


contract LeagueManagerTest is Test {
    SWOSPlayerNFT public nft;
    SENSIToken public sensi;
    LeagueManager public league;
    address public owner = address(this);
    address public treasury = address(0x7EA5);
    address public manager1 = address(0xAA);
    address public manager2 = address(0xBB);

    function setUp() public {
        nft = new SWOSPlayerNFT();
        sensi = new SENSIToken(treasury);
        league = new LeagueManager(address(nft), address(sensi));

        // Transfer ownership to league so it can mint/distribute (2-step)
        sensi.transferOwnership(address(league));
        vm.prank(address(league));
        sensi.acceptOwnership();
        // Set league as oracle so it can reset seasons
        nft.setOracle(address(league));

        // Mint 11 players per team
        uint8[7] memory skills = [uint8(5), 5, 5, 5, 5, 5, 5];
        for (uint256 i = 1; i <= 11; i++) {
            nft.mintPlayer(manager1, i, "P1", skills, 25, 500_000);
            nft.mintPlayer(manager2, i + 100, "P2", skills, 25, 500_000);
        }
    }

    function test_registerTeam() public {
        uint256[] memory ids = new uint256[](11);
        for (uint256 i = 0; i < 11; i++) ids[i] = i + 1;

        vm.prank(manager1);
        league.registerTeam(keccak256("Arsenal"), ids);
    }

    function test_seasonLifecycle() public {
        // Register two teams
        uint256[] memory ids1 = new uint256[](11);
        uint256[] memory ids2 = new uint256[](11);
        for (uint256 i = 0; i < 11; i++) {
            ids1[i] = i + 1;
            ids2[i] = i + 101;
        }

        vm.prank(manager1);
        league.registerTeam(keccak256("Arsenal"), ids1);
        vm.prank(manager2);
        league.registerTeam(keccak256("Liverpool"), ids2);

        // Start season
        league.startSeason();

        // Settle a matchday
        bytes32[] memory home = new bytes32[](1);
        bytes32[] memory away = new bytes32[](1);
        uint256[] memory hGoals = new uint256[](1);
        uint256[] memory aGoals = new uint256[](1);
        home[0] = keccak256("Arsenal");
        away[0] = keccak256("Liverpool");
        hGoals[0] = 3;
        aGoals[0] = 1;

        league.settleMatchday(home, away, hGoals, aGoals);

        // Check points
        assertEq(league.matchday(), 1);

        // Settle season
        league.settleSeason(keccak256("Arsenal"), 1);

        // Verify season advanced
        assertEq(league.currentSeason(), 2);
    }
}
