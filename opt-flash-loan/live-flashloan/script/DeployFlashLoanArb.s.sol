// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {FlashLoanArb} from "../src/FlashLoanArb.sol";

contract DeployFlashLoanArb is Script {
    function run() external returns (FlashLoanArb arb) {
        address pool = vm.envAddress("AAVE_POOL");
        vm.startBroadcast();
        arb = new FlashLoanArb(pool);
        vm.stopBroadcast();
    }
}
