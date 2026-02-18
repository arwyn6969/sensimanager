// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Script.sol";
import "../src/SWOSPlayerNFT.sol";
import "../src/SENSIToken.sol";
import "../src/TransferMarket.sol";
import "../src/LeagueManager.sol";
import "../src/AdHoarding.sol";

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
        address deployer = vm.addr(deployerPrivateKey);

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

        // 5. Deploy AdHoarding (Stadium Hoardings)
        AdHoarding adHoarding = new AdHoarding(treasury, deployer);
        console.log("AdHoarding:", address(adHoarding));

        // Register Tranmere Rovers (clubId=1, tier=2=League One, 16 slots)
        adHoarding.registerClub(1, deployer, 2, 16);
        console.log("Registered: Tranmere Rovers (clubId=1)");

        // ── Wire permissions ──────────────────────────────────────────

        // LeagueManager needs owner role for $SENSI (wage distribution + minting)
        sensiToken.transferOwnership(address(leagueManager));

        // LeagueManager is the oracle for PlayerNFT (season resets)
        playerNFT.setOracle(address(leagueManager));

        console.log("--- Deployment complete ---");
        console.log("Treasury:", treasury);
        console.log("AdHoarding creator:", deployer);

        vm.stopBroadcast();
    }
}
