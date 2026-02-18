// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/AdHoarding.sol";

/**
 * @title AdHoarding Test Suite
 * @notice Comprehensive tests for the SWOS420 Stadium Ad Hoarding system.
 *         8 tests covering the full lifecycle: registration, renting,
 *         revenue splits, expiry, pricing, demand, and access control.
 *
 * @author SWOS420 / Arwyn Hughes / SWA 🏟️🔥
 */
contract AdHoardingTest is Test {
    AdHoarding public adHoarding;

    address public owner = address(this);
    address public treasury = address(0xBEEF);
    address public creator = address(0xCAFE);  // Arwyn's cut
    address public clubOwner = address(0xDEAD); // Tranmere Rovers wallet
    address public brand1 = address(0x1111);
    address public brand2 = address(0x2222);

    uint256 public constant CLUB_ID = 1;       // Tranmere Rovers
    uint8 public constant MAX_SLOTS = 16;
    uint8 public constant TIER = 2;            // League One

    function setUp() public {
        adHoarding = new AdHoarding(treasury, creator);

        // Register Tranmere Rovers
        adHoarding.registerClub(CLUB_ID, clubOwner, TIER, MAX_SLOTS);

        // Fund brand wallets
        vm.deal(brand1, 100 ether);
        vm.deal(brand2, 100 ether);
    }

    // ── Test 1: Club Registration ────────────────────────────────────────

    function test_RegisterClub() public view {
        (address co, uint8 tier, uint8 maxSlots, bool active) = adHoarding.clubs(CLUB_ID);
        assertEq(co, clubOwner, "Club owner mismatch");
        assertEq(tier, TIER, "Tier mismatch");
        assertEq(maxSlots, MAX_SLOTS, "Max slots mismatch");
        assertTrue(active, "Club should be active");
    }

    // ── Test 2: Rent a Hoarding Slot ─────────────────────────────────────

    function test_RentSlot() public {
        uint256 price = adHoarding.calculatePrice(CLUB_ID, 30);

        vm.prank(brand1);
        adHoarding.rent{value: price}(
            CLUB_ID,
            0,                          // position 0
            30,                         // 30 days
            "ar://arwyn-swa-hoarding"   // Arwyn-branded content
        );

        uint256 slotId = CLUB_ID * 100 + 0;
        assertTrue(adHoarding.isSlotActive(slotId), "Slot should be active");
        assertEq(adHoarding.ownerOf(slotId), brand1, "Brand should own the NFT");
        assertEq(adHoarding.totalRentals(), 1, "Total rentals should be 1");
        assertEq(adHoarding.slotDemand(slotId), 1, "Demand should be 1");
    }

    // ── Test 3: Revenue Split 60/30/10 ───────────────────────────────────

    function test_RevenueSplit_60_30_10() public {
        uint256 price = adHoarding.calculatePrice(CLUB_ID, 30);

        uint256 clubBefore = clubOwner.balance;
        uint256 treasuryBefore = treasury.balance;
        uint256 creatorBefore = creator.balance;

        vm.prank(brand1);
        adHoarding.rent{value: price}(
            CLUB_ID, 0, 30, "ar://test-hoarding"
        );

        uint256 expectedClub = (price * 60) / 100;
        uint256 expectedTreasury = (price * 30) / 100;
        uint256 expectedCreator = price - expectedClub - expectedTreasury;

        assertEq(
            clubOwner.balance - clubBefore, expectedClub,
            "Club should receive 60%"
        );
        assertEq(
            treasury.balance - treasuryBefore, expectedTreasury,
            "Treasury should receive 30%"
        );
        assertEq(
            creator.balance - creatorBefore, expectedCreator,
            "Creator (Arwyn) should receive 10%"
        );
    }

    // ── Test 4: Expiry Auto-Burn on Re-Rent ──────────────────────────────

    function test_ExpiryAutoBurn() public {
        uint256 price = adHoarding.calculatePrice(CLUB_ID, 7);
        uint256 slotId = CLUB_ID * 100 + 0;

        // Brand 1 rents for 7 days
        vm.prank(brand1);
        adHoarding.rent{value: price}(CLUB_ID, 0, 7, "ar://brand1-ad");
        assertEq(adHoarding.ownerOf(slotId), brand1);

        // Fast forward 8 days — slot is now expired
        vm.warp(block.timestamp + 8 days);
        assertFalse(adHoarding.isSlotActive(slotId), "Slot should be expired");

        // Brand 2 rents the same slot — old NFT gets burned automatically
        price = adHoarding.calculatePrice(CLUB_ID, 30);
        vm.prank(brand2);
        adHoarding.rent{value: price}(CLUB_ID, 0, 30, "ar://brand2-ad");

        // Brand 2 now owns the slot
        assertEq(adHoarding.ownerOf(slotId), brand2, "Brand2 should now own the slot");
        assertTrue(adHoarding.isSlotActive(slotId), "Slot should be active again");
        assertEq(adHoarding.totalRentals(), 2, "Should have 2 total rentals");
    }

    // ── Test 5: Tier Pricing Differentials ───────────────────────────────

    function test_TierPricingDifferentials() public {
        // Register clubs at each tier
        adHoarding.registerClub(10, address(0xA1), 1, 12); // League Two
        adHoarding.registerClub(20, address(0xA2), 2, 12); // League One
        adHoarding.registerClub(30, address(0xA3), 3, 12); // Championship
        adHoarding.registerClub(40, address(0xA4), 4, 12); // Premier League

        uint256 priceL2 = adHoarding.calculatePrice(10, 30);
        uint256 priceL1 = adHoarding.calculatePrice(20, 30);
        uint256 priceChamp = adHoarding.calculatePrice(30, 30);
        uint256 pricePrem = adHoarding.calculatePrice(40, 30);

        // Each tier should cost more than the last
        assertTrue(priceL1 > priceL2, "League One should cost more than League Two");
        assertTrue(priceChamp > priceL1, "Championship should cost more than League One");
        assertTrue(pricePrem > priceChamp, "Premier League should cost more than Championship");

        // Premier League should be roughly 4x League Two
        // (with basis point rounding, check ratio is within range)
        uint256 ratio = (pricePrem * 10000) / priceL2;
        assertTrue(ratio >= 39000 && ratio <= 41000, "Prem should be ~4x League Two");
    }

    // ── Test 6: Demand Scaling ───────────────────────────────────────────

    function test_DemandScaling() public {
        uint256 priceNoViewers = adHoarding.calculatePrice(CLUB_ID, 30);

        // Simulate 5000 viewers
        adHoarding.updateViewerCount(5000);
        uint256 priceWithViewers = adHoarding.calculatePrice(CLUB_ID, 30);

        // With 5000 viewers, demand factor = 1 + (5000 * 6000 / 5000) / 10000 = 1.6x
        assertTrue(
            priceWithViewers > priceNoViewers,
            "Price should increase with viewers"
        );

        // Check ratio is approximately 1.6x
        uint256 ratio = (priceWithViewers * 10000) / priceNoViewers;
        assertTrue(ratio >= 15500 && ratio <= 16500, "Demand should be ~1.6x at 5000 viewers");
    }

    // ── Test 7: Content Update by Slot Owner ─────────────────────────────

    function test_ContentUpdate() public {
        uint256 price = adHoarding.calculatePrice(CLUB_ID, 30);
        uint256 slotId = CLUB_ID * 100 + 0;

        vm.prank(brand1);
        adHoarding.rent{value: price}(CLUB_ID, 0, 30, "ar://original-content");

        // Brand1 updates their content
        vm.prank(brand1);
        adHoarding.updateContent(slotId, "ar://updated-arwyn-content");

        string memory content = adHoarding.getSlotContent(slotId);
        assertEq(content, "ar://updated-arwyn-content", "Content should be updated");
    }

    // ── Test 8: Access Control ───────────────────────────────────────────

    function test_AccessControl() public {
        // Non-owner cannot register clubs
        vm.prank(brand1);
        vm.expectRevert();
        adHoarding.registerClub(99, brand1, 1, 12);

        // Non-owner cannot update viewer count
        vm.prank(brand1);
        vm.expectRevert();
        adHoarding.updateViewerCount(10000);

        // Cannot rent at position >= maxSlots
        uint256 price = adHoarding.calculatePrice(CLUB_ID, 30);
        vm.prank(brand1);
        vm.expectRevert(
            abi.encodeWithSelector(AdHoarding.InvalidPosition.selector, 20, MAX_SLOTS)
        );
        adHoarding.rent{value: price}(CLUB_ID, 20, 30, "ar://bad-position");

        // Cannot rent with 0 days
        vm.prank(brand1);
        vm.expectRevert(
            abi.encodeWithSelector(AdHoarding.InvalidDuration.selector, 0)
        );
        adHoarding.rent{value: price}(CLUB_ID, 0, 0, "ar://bad-duration");

        // Non-owner cannot update content
        price = adHoarding.calculatePrice(CLUB_ID, 30);
        vm.prank(brand1);
        adHoarding.rent{value: price}(CLUB_ID, 0, 30, "ar://brand1-ad");

        uint256 slotId = CLUB_ID * 100 + 0;
        vm.prank(brand2);
        vm.expectRevert(
            abi.encodeWithSelector(AdHoarding.NotSlotOwner.selector, slotId, brand2)
        );
        adHoarding.updateContent(slotId, "ar://hijack-attempt");
    }
}
