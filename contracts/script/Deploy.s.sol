// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Script.sol";
import "../src/SWOSPlayerNFT.sol";
import "../src/SENSIToken.sol";
import "../src/TransferMarket.sol";
import "../src/LeagueManager.sol";

/**
 * @title SWOS420 Deployment Script
 * @notice Deploy all contracts to Base Sepolia (or mainnet).
 *
 * Usage:
 *   forge script script/Deploy.s.sol:DeploySWOS420 \
 *     --rpc-url base_sepolia \
 *     --broadcast \
 *     --verify
 */
contract DeploySWOS420 is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address treasury = vm.envAddress("TREASURY_ADDRESS");

        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy PlayerNFT
        SWOSPlayerNFT playerNFT = new SWOSPlayerNFT();
        console.log("SWOSPlayerNFT:", address(playerNFT));

        // 2. Deploy $SENSI
        SENSIToken sensiToken = new SENSIToken(treasury);
        console.log("SENSIToken:", address(sensiToken));

        // 3. Deploy TransferMarket
        TransferMarket transferMarket = new TransferMarket(
            address(playerNFT),
            address(sensiToken),
            treasury
        );
        console.log("TransferMarket:", address(transferMarket));

        // 4. Deploy LeagueManager
        LeagueManager leagueManager = new LeagueManager(
            address(playerNFT),
            address(sensiToken)
        );
        console.log("LeagueManager:", address(leagueManager));

        // ── Wire permissions ──────────────────────────────────────────

        // LeagueManager needs minter role for $SENSI (wage distribution)
        sensiToken.setMinter(address(leagueManager), true);

        // LeagueManager is the oracle for PlayerNFT (season resets)
        playerNFT.setOracle(address(leagueManager));

        console.log("--- Deployment complete ---");
        console.log("Treasury:", treasury);

        vm.stopBroadcast();
    }
}
