// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {FlashLoanArbGeneric} from "../src/FlashLoanArbGeneric.sol";

contract DeployFlashLoanArbGeneric is Script {
    function run() external returns (FlashLoanArbGeneric arb) {
        address pool = vm.envAddress("AAVE_POOL");
        vm.startBroadcast();
        arb = new FlashLoanArbGeneric(pool);
        vm.stopBroadcast();
    }
}
