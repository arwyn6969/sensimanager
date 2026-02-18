// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/SWOSPlayerNFT.sol";

/**
 * @title SWOSPlayerNFT — tokenURI Tests
 * @notice Tests for setBaseURI, setTokenURI, setTokenURIBatch, and tokenURI override.
 */
contract SWOSPlayerNFTTokenURITest is Test {
    SWOSPlayerNFT public nft;
    address public owner = address(this);
    address public oracle = address(0xBEEF);
    address public alice = address(0xA11CE);

    uint8[7] internal baseSkills = [uint8(7), 5, 6, 4, 6, 5, 7];

    function setUp() public {
        nft = new SWOSPlayerNFT();
        nft.setOracle(oracle);
        // Mint 3 players for testing
        nft.mintPlayer(alice, 1001, "Van Basten", baseSkills, 25, 10_000_000);
        nft.mintPlayer(alice, 1002, "Gullit", baseSkills, 28, 8_000_000);
        nft.mintPlayer(alice, 1003, "Rijkaard", baseSkills, 29, 6_000_000);
    }

    // ── tokenURI returns empty by default ────────────────────────────

    function test_tokenURI_emptyByDefault() public view {
        string memory uri = nft.tokenURI(1001);
        assertEq(bytes(uri).length, 0, "URI should be empty before any URI is set");
    }

    // ── setTokenURI: owner can set per-token URI ─────────────────────

    function test_setTokenURI_works() public {
        string memory arweaveURI = "ar://abc123def456";
        nft.setTokenURI(1001, arweaveURI);
        assertEq(nft.tokenURI(1001), arweaveURI);
    }

    function test_setTokenURI_emitsEvent() public {
        vm.expectEmit(true, false, false, true);
        emit SWOSPlayerNFT.TokenURIUpdated(1001, "ar://test123");
        nft.setTokenURI(1001, "ar://test123");
    }

    function test_setTokenURI_revertsNonOwner() public {
        vm.prank(alice);
        vm.expectRevert();
        nft.setTokenURI(1001, "ar://hack");
    }

    function test_setTokenURI_revertsNonexistentToken() public {
        vm.expectRevert(abi.encodeWithSelector(SWOSPlayerNFT.PlayerDoesNotExist.selector, 9999));
        nft.setTokenURI(9999, "ar://nope");
    }

    // ── setTokenURIBatch: batch set for multiple tokens ──────────────

    function test_setTokenURIBatch_works() public {
        uint256[] memory ids = new uint256[](3);
        ids[0] = 1001; ids[1] = 1002; ids[2] = 1003;

        string[] memory uris = new string[](3);
        uris[0] = "ar://player1001";
        uris[1] = "ar://player1002";
        uris[2] = "ar://player1003";

        nft.setTokenURIBatch(ids, uris);

        assertEq(nft.tokenURI(1001), "ar://player1001");
        assertEq(nft.tokenURI(1002), "ar://player1002");
        assertEq(nft.tokenURI(1003), "ar://player1003");
    }

    function test_setTokenURIBatch_revertsLengthMismatch() public {
        uint256[] memory ids = new uint256[](2);
        ids[0] = 1001; ids[1] = 1002;

        string[] memory uris = new string[](1);
        uris[0] = "ar://only_one";

        vm.expectRevert("Array length mismatch");
        nft.setTokenURIBatch(ids, uris);
    }

    function test_setTokenURIBatch_revertsNonexistentToken() public {
        uint256[] memory ids = new uint256[](2);
        ids[0] = 1001; ids[1] = 9999; // nonexistent

        string[] memory uris = new string[](2);
        uris[0] = "ar://good";
        uris[1] = "ar://bad";

        vm.expectRevert(abi.encodeWithSelector(SWOSPlayerNFT.PlayerDoesNotExist.selector, 9999));
        nft.setTokenURIBatch(ids, uris);
    }

    function test_setTokenURIBatch_revertsNonOwner() public {
        uint256[] memory ids = new uint256[](1);
        ids[0] = 1001;
        string[] memory uris = new string[](1);
        uris[0] = "ar://hack";

        vm.prank(alice);
        vm.expectRevert();
        nft.setTokenURIBatch(ids, uris);
    }

    // ── setBaseURI: fallback pattern ─────────────────────────────────

    function test_setBaseURI_fallback() public {
        nft.setBaseURI("ar://manifest123/");
        // No per-token URI set → should fall back to base + tokenId + ".json"
        assertEq(nft.tokenURI(1001), "ar://manifest123/1001.json");
        assertEq(nft.tokenURI(1002), "ar://manifest123/1002.json");
    }

    function test_setBaseURI_emitsEvent() public {
        vm.expectEmit(false, false, false, true);
        emit SWOSPlayerNFT.BaseURIUpdated("ar://manifest/");
        nft.setBaseURI("ar://manifest/");
    }

    function test_setBaseURI_revertsNonOwner() public {
        vm.prank(alice);
        vm.expectRevert();
        nft.setBaseURI("ar://hack/");
    }

    // ── Per-token URI overrides baseURI ──────────────────────────────

    function test_perTokenURI_overridesBaseURI() public {
        nft.setBaseURI("ar://manifest123/");
        nft.setTokenURI(1001, "ar://custom_vanbasten_uri");

        // Token 1001 has a per-token URI → should use it
        assertEq(nft.tokenURI(1001), "ar://custom_vanbasten_uri");
        // Token 1002 has no per-token URI → should fall back to base
        assertEq(nft.tokenURI(1002), "ar://manifest123/1002.json");
    }

    // ── tokenURI reverts for nonexistent token ───────────────────────

    function test_tokenURI_revertsNonexistent() public {
        vm.expectRevert(abi.encodeWithSelector(SWOSPlayerNFT.PlayerDoesNotExist.selector, 9999));
        nft.tokenURI(9999);
    }

    // ── Arweave-format URIs work correctly ───────────────────────────

    function test_arweaveFormatURI() public {
        // Full Arweave gateway URL format
        nft.setTokenURI(1001, "https://arweave.net/abc123def456ghi789");
        assertEq(nft.tokenURI(1001), "https://arweave.net/abc123def456ghi789");

        // ar:// protocol format
        nft.setTokenURI(1002, "ar://xyz789_special-chars.ok");
        assertEq(nft.tokenURI(1002), "ar://xyz789_special-chars.ok");
    }

    // ── URI can be updated ───────────────────────────────────────────

    function test_tokenURI_canBeUpdated() public {
        nft.setTokenURI(1001, "ar://version1");
        assertEq(nft.tokenURI(1001), "ar://version1");

        nft.setTokenURI(1001, "ar://version2");
        assertEq(nft.tokenURI(1001), "ar://version2");
    }
}
