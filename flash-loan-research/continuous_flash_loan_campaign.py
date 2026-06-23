#!/usr/bin/env python3
"""
Continuous flash loan campaign manager.
Scans for profitable opportunities and executes live trades when found.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import eth_abi
from dotenv import load_dotenv
from web3 import Web3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ETH_PRICE_USD = 1566.32
AAVE_PREMIUM_BPS = 5
MIN_NET_PROFIT_USD = 1.0  # Higher threshold for live execution
SLIPPAGE_BPS = 10

# Contract ABIs
V2_ROUTER_ABI = [
    {"name": "getAmountsOut", "type": "function", "stateMutability": "view", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "path", "type": "address[]"}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
    {"name": "swapExactTokensForTokens", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"}, {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
]

FLASH_ARB_ABI = [
    {"name": "executeArb", "type": "function", "stateMutability": "nonpayable", "inputs": [
        {"name": "p", "type": "tuple", "components": [
            {"name": "routerA", "type": "address"},
            {"name": "routerB", "type": "address"},
            {"name": "tokenBorrow", "type": "address"},
            {"name": "tokenMid", "type": "address"},
            {"name": "minProfit", "type": "uint256"},
            {"name": "callDataA", "type": "bytes"},
            {"name": "callDataB", "type": "bytes"}
        ]},
        {"name": "amount", "type": "uint256"}
    ], "outputs": []},
]

@dataclass
class Token:
    symbol: str
    address: str
    decimals: int

@dataclass
class Router:
    name: str
    address: str
    abi: List[Dict]

# Token configurations
ARBITRUM_TOKENS = {
    "USDC": Token("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    "USDT": Token("USDT", "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
    "DAI": Token("DAI", "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", 18),
    "WETH": Token("WETH", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18),
}

BASE_TOKENS = {
    "USDC": Token("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
    "USDT": Token("USDT", "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2", 6),
    "DAI": Token("DAI", "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", 18),
    "ARB": Token("ARB", "0x912CE59144191C1204E64559FE8253a0e49E6548", 18),
}

ARBITRUM_ROUTERS = [
    Router("Camelot", "0x9b35Af8778d3fbd5133da3A1016a656736e6A063", V2_ROUTER_ABI),
]

BASE_ROUTERS = [
    Router("Aerodrome", "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43", V2_ROUTER_ABI),
]

class ContinuousCampaign:
    def __init__(self):
        load_dotenv(".env.local")
        
        # Initialize networks
        self.arbitrum_w3 = Web3(Web3.HTTPProvider(os.environ["ARBITRUM_RPC"]))
        self.base_w3 = Web3(Web3.HTTPProvider(os.environ["BASE_RPC"]))
        self.wallet = Web3.to_checksum_address(os.environ["WALLET_ADDRESS"])
        self.private_key = os.environ["PRIVATE_KEY"]
        
        # Load deployments
        with open("live-flashloan/deployments.json") as f:
            deployments = json.load(f)["contracts"]
        
        self.arbitrum_contract = self.arbitrum_w3.eth.contract(
            address=Web3.to_checksum_address(deployments["arbitrum"]["flashLoanArb"]),
            abi=FLASH_ARB_ABI
        )
        self.base_contract = self.base_w3.eth.contract(
            address=Web3.to_checksum_address(deployments["base"]["flashLoanArb"]),
            abi=FLASH_ARB_ABI
        )
        
        self.arbitrum_tokens = ARBITRUM_TOKENS
        self.base_tokens = BASE_TOKENS
        self.arbitrum_routers = ARBITRUM_ROUTERS
        self.base_routers = BASE_ROUTERS
        
        # Campaign state
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "arbitrum_success": 0,
            "base_success": 0,
            "arbitrum_attempts": 0,
            "base_attempts": 0,
            "total_profit_usd": 0.0,
            "last_profitable_scan": None,
            "scan_count": 0
        }
        
        logger.info("🚀 Continuous flash loan campaign initialized")
        logger.info(f"   Target: 12 successful transactions per network")
        logger.info(f"   Wallet: {self.wallet}")
        logger.info(f"   ETH Price: ${ETH_PRICE_USD}")

    def get_balance(self, network: str) -> Dict:
        """Get wallet balance for a network"""
        w3 = self.arbitrum_w3 if network == "arbitrum" else self.base_w3
        balance = w3.eth.get_balance(self.wallet)
        eth_balance = float(w3.from_wei(balance, 'ether'))
        usd_balance = eth_balance * ETH_PRICE_USD
        
        return {
            "eth": eth_balance,
            "usd": usd_balance,
            "timestamp": datetime.now().isoformat()
        }

    def quote_v2(self, router: Router, amount_in: int, path: List[str], network: str) -> Optional[List[int]]:
        """Quote V2 router path"""
        try:
            w3 = self.arbitrum_w3 if network == "arbitrum" else self.base_w3
            c = w3.eth.contract(address=Web3.to_checksum_address(router.address), abi=router.abi)
            return c.functions.getAmountsOut(amount_in, [Web3.to_checksum_address(p) for p in path]).call()
        except Exception:
            return None

    def scan_network(self, network: str) -> List[Dict]:
        """Scan a network for profitable opportunities"""
        logger.info(f"🔍 Scanning {network} for profitable opportunities...")
        
        tokens = self.arbitrum_tokens if network == "arbitrum" else self.base_tokens
        routers = self.arbitrum_routers if network == "arbitrum" else self.base_routers
        w3 = self.arbitrum_w3 if network == "arbitrum" else self.base_w3
        
        candidates = []
        amounts = [1000, 2500, 5000, 10000, 25000]
        
        for borrow_sym, borrow in tokens.items():
            for mid_sym, mid in tokens.items():
                if mid_sym == borrow_sym:
                    continue
                
                for amount_usd in amounts:
                    amount = int(amount_usd * (10 ** borrow.decimals))
                    
                    # Try all router combinations
                    for router_a in routers:
                        q1 = self.quote_v2(router_a, amount, [borrow.address, mid.address], network)
                        if not q1:
                            continue
                        
                        mid_out = q1[-1]
                        
                        for router_b in routers:
                            if router_b.address.lower() == router_a.address.lower():
                                continue
                            
                            q2 = self.quote_v2(router_b, mid_out, [mid.address, borrow.address], network)
                            if not q2:
                                continue
                            
                            final_out = q2[-1]
                            
                            # Calculate profitability
                            premium = amount * AAVE_PREMIUM_BPS // 10000
                            gross = final_out - amount - premium
                            gross_units = gross / (10 ** borrow.decimals)
                            
                            # Estimate gas cost
                            gas_limit = 1000000
                            gas_usd = (gas_limit * w3.eth.gas_price / 1e18) * ETH_PRICE_USD
                            net_usd = gross_units - gas_usd
                            
                            if net_usd > MIN_NET_PROFIT_USD:
                                candidates.append({
                                    "network": network,
                                    "borrow": borrow_sym,
                                    "mid": mid_sym,
                                    "amount": amount,
                                    "amount_human": amount_usd,
                                    "routerA": router_a.__dict__,
                                    "routerB": router_b.__dict__,
                                    "mid_out": mid_out,
                                    "final_out": final_out,
                                    "premium": premium,
                                    "gross_profit_usd": gross_units,
                                    "gas_usd": gas_usd,
                                    "net_profit_usd": net_usd,
                                })
        
        logger.info(f"   Found {len(candidates)} profitable candidates")
        return sorted(candidates, key=lambda x: x["net_profit_usd"], reverse=True)

    def execute_trade(self, opportunity: Dict, network: str) -> Dict:
        """Execute a live trade"""
        logger.info(f"🚀 Executing live trade on {network}")
        logger.info(f"   Borrow: {opportunity['borrow']} -> {opportunity['mid']}")
        logger.info(f"   Amount: ${opportunity['amount_human']}")
        logger.info(f"   Net Profit: ${opportunity['net_profit_usd']:.2f}")
        
        # Get balance before
        balance_before = self.get_balance(network)
        logger.info(f"   Balance before: {balance_before['eth']:.6f} ETH (${balance_before['usd']:.2f})")
        
        # Execute trade
        w3 = self.arbitrum_w3 if network == "arbitrum" else self.base_w3
        contract = self.arbitrum_contract if network == "arbitrum" else self.base_contract
        
        try:
            # Build transaction parameters
            borrow = self.arbitrum_tokens if network == "arbitrum" else self.base_tokens
            borrow_token = borrow[opportunity["borrow"]]
            mid_token = borrow[opportunity["mid"]]
            
            min_mid = opportunity["mid_out"] * (10000 - SLIPPAGE_BPS) // 10000
            min_final = opportunity["final_out"] * (10000 - SLIPPAGE_BPS) // 10000
            min_profit = max(1, int((opportunity["net_profit_usd"] / 2) * (10 ** borrow_token.decimals)))
            deadline = int(time.time()) + 120
            
            # Build V2 swap call data
            call_a = self._encode_v2_swap(
                opportunity["amount"], min_mid, 
                [borrow_token.address, mid_token.address], deadline
            )
            call_b = self._encode_v2_swap(
                opportunity["mid_out"], min_final,
                [mid_token.address, borrow_token.address], deadline
            )
            
            # Execute transaction
            tx = contract.functions.executeArb(
                (
                    Web3.to_checksum_address(opportunity["routerA"]["address"]),
                    Web3.to_checksum_address(opportunity["routerB"]["address"]),
                    Web3.to_checksum_address(borrow_token.address),
                    Web3.to_checksum_address(mid_token.address),
                    min_profit,
                    call_a,
                    call_b,
                ),
                opportunity["amount"]
            ).build_transaction({
                "from": self.wallet,
                "nonce": w3.eth.get_transaction_count(self.wallet),
                "chainId": 42161 if network == "arbitrum" else 8453,
                "gas": 1200000,
                "maxFeePerGas": int(w3.eth.gas_price * 2),
                "maxPriorityFeePerGas": max(1, int(w3.eth.gas_price * 0.3)),
            })
            
            signed = w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            # Get balance after
            time.sleep(10)
            balance_after = self.get_balance(network)
            
            # Calculate result
            balance_diff = balance_after["eth"] - balance_before["eth"]
            profit_usd = balance_diff * ETH_PRICE_USD
            success = balance_diff > 0.000001
            
            # Update stats
            if success:
                self.stats[f"{network}_success"] += 1
                self.stats["total_profit_usd"] += profit_usd
                logger.info(f"   ✅ SUCCESS! Profit: ${profit_usd:.2f}")
            else:
                logger.info(f"   ❌ FAILED. Balance change: {balance_diff:.6f} ETH")
            
            return {
                "success": success,
                "tx_hash": tx_hash.hex(),
                "balance_before": balance_before,
                "balance_after": balance_after,
                "profit_usd": profit_usd,
                "expected_profit_usd": opportunity["net_profit_usd"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"   ❌ Execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _encode_v2_swap(self, amount_in: int, amount_out_min: int, path: List[str], deadline: int) -> bytes:
        """Encode V2 swap transaction"""
        return b'\xa9\x05\x9c\xbb' + amount_in.to_bytes(32, 'big') + amount_out_min.to_bytes(32, 'big') + len(path).to_bytes(32, 'big') + b''.join([Web3.to_checksum_address(p).lower() for p in path]) + self.wallet.lower() + deadline.to_bytes(32, 'big')

    async def run_campaign(self):
        """Run the continuous campaign"""
        logger.info("🚀 Starting continuous flash loan campaign")
        logger.info("=" * 80)
        
        # Target: 12 successful transactions per network
        target_per_network = 12
        
        while self.stats["arbitrum_success"] < target_per_network or self.stats["base_success"] < target_per_network:
            logger.info(f"\n{'='*80}")
            logger.info(f"🎯 Campaign Progress")
            logger.info(f"   Arbitrum: {self.stats['arbitrum_success']}/{target_per_network}")
            logger.info(f"   Base: {self.stats['base_success']}/{target_per_network}")
            logger.info(f"   Total Profit: ${self.stats['total_profit_usd']:.2f}")
            logger.info(f"{'='*80}")
            
            # Scan both networks
            self.stats["scan_count"] += 1
            
            arbitrum_candidates = self.scan_network("arbitrum")
            base_candidates = self.scan_network("base")
            
            # Execute best opportunity if found
            all_candidates = arbitrum_candidates + base_candidates
            if all_candidates:
                best = all_candidates[0]
                logger.info(f"🎯 Best opportunity: {best['network']} ${best['net_profit_usd']:.2f}")
                
                # Execute if profitable
                if best["net_profit_usd"] > MIN_NET_PROFIT_USD:
                    result = self.execute_trade(best, best["network"])
                    
                    # Update stats
                    self.stats[f"{best['network']}_attempts"] += 1
                    if result["success"]:
                        logger.info(f"✅ Trade successful on {best['network']}")
                    else:
                        logger.warning(f"❌ Trade failed on {best['network']}")
                else:
                    logger.info("No profitable opportunities above threshold")
            else:
                logger.info("No profitable opportunities found")
            
            # Wait before next scan
            logger.info("⏳ Waiting 60 seconds before next scan...")
            await asyncio.sleep(60)
        
        # Campaign completed
        logger.info(f"\n🎉 Campaign completed!")
        logger.info(f"   Arbitrum Success: {self.stats['arbitrum_success']}/{target_per_network}")
        logger.info(f"   Base Success: {self.stats['base_success']}/{target_per_network}")
        logger.info(f"   Total Profit: ${self.stats['total_profit_usd']:.2f}")
        
        # Save results
        with open("CONTINUOUS_CAMPAIGN_RESULTS.json", "w") as f:
            json.dump(self.stats, f, indent=2)

async def main():
    campaign = ContinuousCampaign()
    await campaign.run_campaign()

if __name__ == "__main__":
    asyncio.run(main())