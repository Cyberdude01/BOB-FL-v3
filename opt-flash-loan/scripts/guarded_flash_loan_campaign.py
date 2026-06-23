#!/usr/bin/env python3
"""Guarded flash-loan campaign runner.

Rules enforced:
- Success is counted ONLY when wallet balance increases after a confirmed on-chain action.
- Simulation-only or test/self-transfer paths are refused.
- Stop after repeated failures to avoid wasting gas.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from web3 import Web3

from arbitrum_execution_engine import ArbitrumExecutionEngine, ArbitrumOpportunity
from base_execution_engine import BaseExecutionEngine, BaseOpportunity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TARGET_PER_NETWORK = 12
MAX_CONSECUTIVE_FAILURES = 4
ETH_PRICE_USD = 1566.32
MIN_BALANCE_INCREASE_ETH = 0.000001

class GuardedCampaign:
    def __init__(self):
        load_dotenv(".env.local")
        self.wallet_address = os.getenv("WALLET_ADDRESS")
        self.arbitrum_rpc = os.getenv("ARBITRUM_RPC")
        self.base_rpc = os.getenv("BASE_RPC")
        self.w3_arbitrum = Web3(Web3.HTTPProvider(self.arbitrum_rpc))
        self.w3_base = Web3(Web3.HTTPProvider(self.base_rpc))
        self.arbitrum_engine = ArbitrumExecutionEngine(db_path="guarded_arbitrum.db")
        self.base_engine = BaseExecutionEngine()
        self.stats = {
            "target_per_network": TARGET_PER_NETWORK,
            "arbitrum_success": 0,
            "base_success": 0,
            "arbitrum_attempts": 0,
            "base_attempts": 0,
            "consecutive_failures": 0,
            "started_at": datetime.now().isoformat(),
            "events": [],
        }

    def balance(self) -> Dict[str, float]:
        arb_wei = self.w3_arbitrum.eth.get_balance(self.wallet_address)
        base_wei = self.w3_base.eth.get_balance(self.wallet_address)
        arb_eth = float(self.w3_arbitrum.from_wei(arb_wei, "ether"))
        base_eth = float(self.w3_base.from_wei(base_wei, "ether"))
        total_eth = arb_eth + base_eth
        return {
            "arbitrum_eth": arb_eth,
            "base_eth": base_eth,
            "total_eth": total_eth,
            "arbitrum_usd": arb_eth * ETH_PRICE_USD,
            "base_usd": base_eth * ETH_PRICE_USD,
            "total_usd": total_eth * ETH_PRICE_USD,
            "timestamp": datetime.now().isoformat(),
        }

    def opportunity(self, network: str) -> Any:
        now = int(time.time())
        if network == "arbitrum":
            return ArbitrumOpportunity(
                id=f"guarded_arbitrum_{now}",
                timestamp=datetime.now(),
                network="arbitrum",
                protocol="camelot",
                opportunity_type="flash_loan",
                token_pair="USDC-USDT",
                estimated_profit_usd=10.0,
                gas_cost_usd=0.25,
                liquidity_usd=50000,
                confidence_score=0.99,
                details={"guarded": True},
            )
        return BaseOpportunity(
            id=f"guarded_base_{now}",
            timestamp=datetime.now(),
            network="base",
            protocol="aerodrome",
            opportunity_type="flash_loan",
            token_pair="USDC-USDT",
            estimated_profit_usd=10.0,
            gas_cost_usd=0.20,
            liquidity_usd=50000,
            confidence_score=0.99,
        )

    async def attempt(self, network: str) -> Dict[str, Any]:
        before = self.balance()
        logger.info("%s balance before: %.9f ETH ($%.2f)", network, before["total_eth"], before["total_usd"])
        opp = self.opportunity(network)

        if network == "arbitrum":
            self.stats["arbitrum_attempts"] += 1
            result = await self.arbitrum_engine.execute_opportunity(opp)
        else:
            self.stats["base_attempts"] += 1
            result = await self.base_engine.execute_flash_loan_arbitrage(opp)

        # Allow RPC indexers a moment to reflect state.
        await asyncio.sleep(8)
        after = self.balance()
        diff = after["total_eth"] - before["total_eth"]
        success = diff > MIN_BALANCE_INCREASE_ETH
        event = {
            "network": network,
            "opportunity_id": opp.id,
            "before": before,
            "after": after,
            "balance_diff_eth": diff,
            "balance_diff_usd": diff * ETH_PRICE_USD,
            "engine_result": result,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }
        self.stats["events"].append(event)

        if success:
            self.stats[f"{network}_success"] += 1
            self.stats["consecutive_failures"] = 0
            logger.info("✅ %s SUCCESS by wallet balance: %+0.9f ETH ($%+.4f)", network, diff, diff * ETH_PRICE_USD)
        else:
            self.stats["consecutive_failures"] += 1
            logger.warning("❌ %s failed by wallet balance: %+0.9f ETH ($%+.4f)", network, diff, diff * ETH_PRICE_USD)
        self.save()
        return event

    def done(self) -> bool:
        return self.stats["arbitrum_success"] >= TARGET_PER_NETWORK and self.stats["base_success"] >= TARGET_PER_NETWORK

    def save(self):
        self.stats["updated_at"] = datetime.now().isoformat()
        self.stats["current_balance"] = self.balance()
        with open("GUARDED_CAMPAIGN_RESULTS.json", "w") as f:
            json.dump(self.stats, f, indent=2, default=str)

    async def run(self):
        logger.info("Starting guarded campaign: target %d successes per network", TARGET_PER_NETWORK)
        logger.info("Initial balance: %s", json.dumps(self.balance(), indent=2))
        while not self.done():
            if self.stats["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                logger.error("Stopping after %d consecutive balance-verified failures to avoid wasting gas", MAX_CONSECUTIVE_FAILURES)
                break
            if self.stats["arbitrum_success"] < TARGET_PER_NETWORK:
                await self.attempt("arbitrum")
            if self.stats["base_success"] < TARGET_PER_NETWORK and self.stats["consecutive_failures"] < MAX_CONSECUTIVE_FAILURES:
                await self.attempt("base")
        self.save()
        logger.info("Final stats: %s", json.dumps({k: v for k, v in self.stats.items() if k != "events"}, indent=2, default=str))

async def main():
    await GuardedCampaign().run()

if __name__ == "__main__":
    asyncio.run(main())
