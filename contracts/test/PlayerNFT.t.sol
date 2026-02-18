// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/SENSIToken.sol";
import "../src/PlayerNFT.sol";

contract PlayerNFTTest is Test {
    PlayerNFT public nft;
    SENSIToken public sensi;

    address public owner = address(this);
    address public oracle = address(0xBEEF);
    address public user1 = address(0x1);
    address public user2 = address(0x2);
    address public treasury = address(0xDAD);

    uint256 public constant TOKEN_1 = 0xabcdef1234567890;
    uint256 public constant TOKEN_2 = 0xfedcba0987654321;
    uint256 public constant TOKEN_3 = 0x1111111111111111;

    function setUp() public {
        nft = new PlayerNFT(oracle);
        sensi = new SENSIToken(treasury);
        nft.setSENSIToken(address(sensi));
    }

    // ── Minting ─────────────────────────────────────────────────────────

    function testMint() public {
        nft.mint(user1, TOKEN_1);
        assertEq(nft.ownerOf(TOKEN_1), user1);
        assertEq(nft.totalMinted(), 1);
    }

    function testMintBatch() public {
        uint256[] memory ids = new uint256[](3);
        ids[0] = TOKEN_1;
        ids[1] = TOKEN_2;
        ids[2] = TOKEN_3;

        nft.mintBatch(user1, ids);
        assertEq(nft.ownerOf(TOKEN_1), user1);
        assertEq(nft.ownerOf(TOKEN_2), user1);
        assertEq(nft.ownerOf(TOKEN_3), user1);
        assertEq(nft.totalMinted(), 3);
    }

    function testMint_notOwner_reverts() public {
        vm.prank(user1);
        vm.expectRevert();
        nft.mint(user1, TOKEN_1);
    }

    function testMint_zeroAddress_reverts() public {
        vm.expectRevert("PlayerNFT: mint to zero address");
        nft.mint(address(0), TOKEN_1);
    }

    function testMintBatch_emptyArray_reverts() public {
        uint256[] memory ids = new uint256[](0);
        vm.expectRevert("PlayerNFT: empty array");
        nft.mintBatch(user1, ids);
    }

    // ── Metadata ────────────────────────────────────────────────────────

    function testUpdateMetadata() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(oracle);
        nft.updateMetadata(TOKEN_1, "ipfs://QmTest123");

        assertEq(nft.tokenURI(TOKEN_1), "ipfs://QmTest123");
    }

    function testUpdateMetadata_notOracle_reverts() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(user1);
        vm.expectRevert("PlayerNFT: caller is not the oracle");
        nft.updateMetadata(TOKEN_1, "ipfs://QmTest123");
    }

    function testUpdateMetadata_nonexistent_reverts() public {
        vm.prank(oracle);
        vm.expectRevert("PlayerNFT: nonexistent token");
        nft.updateMetadata(TOKEN_1, "ipfs://QmTest123");
    }

    function testUpdateMetadata_emptyUri_reverts() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(oracle);
        vm.expectRevert("PlayerNFT: empty URI");
        nft.updateMetadata(TOKEN_1, "");
    }

    // ── Wages ───────────────────────────────────────────────────────────

    function testAddWages() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(oracle);
        nft.addWages(TOKEN_1, 1000 ether);

        assertEq(nft.accumulatedWages(TOKEN_1), 1000 ether);
    }

    function testAddWages_accumulates() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(oracle);
        nft.addWages(TOKEN_1, 500 ether);
        vm.prank(oracle);
        nft.addWages(TOKEN_1, 300 ether);

        assertEq(nft.accumulatedWages(TOKEN_1), 800 ether);
    }

    function testAddWagesBatch() public {
        nft.mint(user1, TOKEN_1);
        nft.mint(user2, TOKEN_2);

        uint256[] memory ids = new uint256[](2);
        ids[0] = TOKEN_1;
        ids[1] = TOKEN_2;
        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 100 ether;
        amounts[1] = 200 ether;

        vm.prank(oracle);
        nft.addWagesBatch(ids, amounts);

        assertEq(nft.accumulatedWages(TOKEN_1), 100 ether);
        assertEq(nft.accumulatedWages(TOKEN_2), 200 ether);
    }

    function testClaimWages() public {
        nft.mint(user1, TOKEN_1);

        // Fund the NFT contract with SENSI for wage payouts
        sensi.transfer(address(nft), 10_000 ether);

        // Oracle adds wages
        vm.prank(oracle);
        nft.addWages(TOKEN_1, 1000 ether);

        // User claims
        uint256 balBefore = sensi.balanceOf(user1);
        vm.prank(user1);
        nft.claimWages(TOKEN_1);

        assertEq(sensi.balanceOf(user1), balBefore + 1000 ether);
        assertEq(nft.accumulatedWages(TOKEN_1), 0);
    }

    function testClaimWages_notOwner_reverts() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(oracle);
        nft.addWages(TOKEN_1, 1000 ether);

        vm.prank(user2);
        vm.expectRevert("PlayerNFT: not token owner");
        nft.claimWages(TOKEN_1);
    }

    function testClaimWages_noWages_reverts() public {
        nft.mint(user1, TOKEN_1);

        vm.prank(user1);
        vm.expectRevert("PlayerNFT: no wages to claim");
        nft.claimWages(TOKEN_1);
    }

    // ── Admin ───────────────────────────────────────────────────────────

    function testSetOracle() public {
        address newOracle = address(0xCAFE);
        nft.setOracle(newOracle);
        assertEq(nft.oracle(), newOracle);
    }

    function testSetOracle_zeroAddress_reverts() public {
        vm.expectRevert("PlayerNFT: oracle is zero address");
        nft.setOracle(address(0));
    }

    function testSetSENSIToken() public {
        address newToken = address(0xDEAD);
        nft.setSENSIToken(newToken);
        assertEq(address(nft.sensiToken()), newToken);
    }

    function testName() public view {
        assertEq(nft.name(), "SWOS420 Player");
        assertEq(nft.symbol(), "SWOS");
    }
}
