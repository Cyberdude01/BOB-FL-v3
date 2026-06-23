#!/usr/bin/env python3
"""
Expanded flash loan scanner with more tokens, higher amounts, and aggressive quoting.
"""

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import eth_abi
from dotenv import load_dotenv
from web3 import Web3

ETH_PRICE_USD = 1566.32
AAVE_PREMIUM_BPS = 5
MIN_NET_PROFIT_USD = 0.50  # Higher threshold for live execution
SLIPPAGE_BPS = 10  # Higher slippage for larger trades

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

# Expanded token configurations
ARBITRUM_TOKENS = {
    "USDC": Token("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    "USDT": Token("USDT", "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
    "DAI": Token("DAI", "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", 18),
    "WETH": Token("WETH", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18),
    "LINK": Token("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", 18),
    "CRV": Token("CRV", "0x0000000000000000000000000000000000000000", 18),  # Placeholder
}

BASE_TOKENS = {
    "USDC": Token("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
    "USDT": Token("USDT", "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2", 6),
    "DAI": Token("DAI", "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", 18),
    "WETH": Token("WETH", "0x4200000000000000000000000000000000000006", 18),
    "ARB": Token("ARB", "0x912CE59144191C1204E64559FE8253a0e49E6548", 18),
}

ARBITRUM_ROUTERS = [
    Router("Camelot", "0x9b35Af8778d3fbd5133da3A1016a656736e6A063", V2_ROUTER_ABI),
    Router("UniswapV2", "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45", V2_ROUTER_ABI),
]

BASE_ROUTERS = [
    Router("Aerodrome", "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43", V2_ROUTER_ABI),
]

class ExpandedScanner:
    def __init__(self, network: str, execute: bool = False):
        load_dotenv(".env.local")
        self.network = network
        self.execute = execute
        self.w3 = Web3(Web3.HTTPProvider(os.environ[f"{network.upper()}_RPC"]))
        self.wallet = Web3.to_checksum_address(os.environ["WALLET_ADDRESS"])
        self.private_key = os.environ["PRIVATE_KEY"]
        
        with open("live-flashloan/deployments.json") as f:
            deployments = json.load(f)["contracts"][network]
        self.contract_addr = Web3.to_checksum_address(deployments["flashLoanArb"])
        self.contract = self.w3.eth.contract(address=self.contract_addr, abi=FLASH_ARB_ABI)
        
        self.tokens = ARBITRUM_TOKENS if network == "arbitrum" else BASE_TOKENS
        self.routers = ARBITRUM_ROUTERS if network == "arbitrum" else BASE_ROUTERS

    def to_units(self, amount: float, token: Token) -> int:
        return int(amount * (10 ** token.decimals))

    def from_units(self, amount: int, token: Token) -> float:
        return amount / (10 ** token.decimals)

    def quote_v2(self, router: Router, amount_in: int, path: List[str]) -> Optional[List[int]]:
        try:
            c = self.w3.eth.contract(address=Web3.to_checksum_address(router.address), abi=router.abi)
            return c.functions.getAmountsOut(amount_in, [Web3.to_checksum_address(p) for p in path]).call()
        except Exception:
            return None

    def gas_cost_usd(self, gas_limit: int = 1000000) -> float:
        return (gas_limit * self.w3.eth.gas_price / 1e18) * ETH_PRICE_USD

    def scan(self) -> List[Dict]:
        candidates = []
        
        # Expanded amount ranges
        amount_ranges = {
            "stable": [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000],
            "large": [5000, 10000, 25000, 50000, 100000, 250000, 500000],
        }
        
        for borrow_sym, borrow in self.tokens.items():
            for mid_sym, mid in self.tokens.items():
                if mid_sym == borrow_sym:
                    continue
                
                # Use different amount ranges based on token types
                if borrow_sym in ["USDC", "USDT", "DAI"] and mid_sym in ["USDC", "USDT", "DAI"]:
                    amounts = amount_ranges["stable"]
                else:
                    amounts = amount_ranges["large"]
                
                for amount_usd in amounts:
                    amount = self.to_units(amount_usd, borrow)
                    
                    # Try all router combinations
                    for router_a in self.routers:
                        q1 = self.quote_v2(router_a, amount, [borrow.address, mid.address])
                        if not q1:
                            continue
                        
                        mid_out = q1[-1]
                        
                        for router_b in self.routers:
                            if router_b.address.lower() == router_a.address.lower():
                                continue
                            
                            q2 = self.quote_v2(router_b, mid_out, [mid.address, borrow.address])
                            if not q2:
                                continue
                            
                            final_out = q2[-1]
                            
                            # Calculate profitability
                            premium = amount * AAVE_PREMIUM_BPS // 10000
                            gross = final_out - amount - premium
                            gross_units = self.from_units(gross, borrow)
                            gas_usd = self.gas_cost_usd()
                            net_usd = gross_units - gas_usd
                            
                            if net_usd > MIN_NET_PROFIT_USD:
                                candidates.append({
                                    "network": self.network,
                                    "borrow": borrow_sym,
                                    "mid": mid_sym,
                                    "amount": amount,
                                    "amount_human": amount_usd,
                                    "routerA": router_a.__dict__,
                                    "routerB": router_b.__dict__,
                                    "mid_out": mid_out,
                                    "final_out": final_out,
                                    "premium": premium,
                                    "gross_profit_token": gross_units,
                                    "gas_usd": gas_usd,
                                    "net_profit_usd": net_usd,
                                })
        
        candidates.sort(key=lambda x: x["net_profit_usd"], reverse=True)
        return candidates

    def build_params(self, c: Dict):
        borrow = self.tokens[c["borrow"]]
        mid = self.tokens[c["mid"]]
        min_mid = c["mid_out"] * (10000 - SLIPPAGE_BPS) // 10000
        min_final = c["final_out"] * (10000 - SLIPPAGE_BPS) // 10000
        min_profit = max(1, int((c["net_profit_usd"] / 2) * (10 ** borrow.decimals)))
        deadline = int(time.time()) + 120
        
        router_a = Router(**c["routerA"])
        router_b = Router(**c["routerB"])
        
        # Build V2 swap call data
        call_a = self._encode_v2_swap(c["amount"], min_mid, [borrow.address, mid.address], deadline)
        call_b = self._encode_v2_swap(c["mid_out"], min_final, [mid.address, borrow.address], deadline)
        
        return (
            Web3.to_checksum_address(router_a.address),
            Web3.to_checksum_address(router_b.address),
            Web3.to_checksum_address(borrow.address),
            Web3.to_checksum_address(mid.address),
            min_profit,
            call_a,
            call_b,
        )

    def _encode_v2_swap(self, amount_in: int, amount_out_min: int, path: List[str], deadline: int) -> bytes:
        # Simplified V2 swap encoding
        return b'\xa9\x05\x9c\xbb' + amount_in.to_bytes(32, 'big') + amount_out_min.to_bytes(32, 'big') + len(path).to_bytes(32, 'big') + b''.join([Web3.to_checksum_address(p).lower() for p in path]) + self.wallet.lower() + deadline.to_bytes(32, 'big')

    def simulate(self, c: Dict) -> Tuple[bool, str]:
        try:
            self.contract.functions.executeArb(self.build_params(c), c["amount"]).call({"from": self.wallet})
            return True, "eth_call simulation passed"
        except Exception as e:
            return False, str(e)[:500]

    def execute_live(self, c: Dict) -> str:
        tx = self.contract.functions.executeArb(self.build_params(c), c["amount"]).build_transaction({
            "from": self.wallet,
            "nonce": self.w3.eth.get_transaction_count(self.wallet),
            "chainId": 42161 if self.network == "arbitrum" else 8453,
            "gas": 1200000,
            "maxFeePerGas": int(self.w3.eth.gas_price * 2),
            "maxPriorityFeePerGas": max(1, int(self.w3.eth.gas_price * 0.3)),
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status != 1:
            raise RuntimeError(f"live tx reverted: {tx_hash.hex()}")
        return tx_hash.hex()

    def run(self) -> Dict:
        candidates = self.scan()
        results = []
        
        for c in candidates[:5]:  # Limit to top 5 candidates
            ok, msg = self.simulate(c)
            c["simulation_ok"] = ok
            c["simulation_message"] = msg
            
            if ok and self.execute:
                c["tx_hash"] = self.execute_live(c)
            
            results.append(c)
        
        out = {
            "timestamp": datetime.now().isoformat(),
            "network": self.network,
            "contract": self.contract_addr,
            "candidates_found": len(candidates),
            "results": results
        }
        
        with open(f"EXPANDED_FLASHLOAN_SCAN_{self.network.upper()}.json", "w") as f:
            json.dump(out, f, indent=2)
        
        return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", choices=["arbitrum", "base"], required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    
    scanner = ExpandedScanner(args.network, args.execute)
    out = scanner.run()
    
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for r in out["results"]:
        print(json.dumps({k: r[k] for k in ["borrow", "mid", "amount_human", "routerA", "routerB", "net_profit_usd", "simulation_ok", "simulation_message"]}, indent=2))

if __name__ == "__main__":
    main()