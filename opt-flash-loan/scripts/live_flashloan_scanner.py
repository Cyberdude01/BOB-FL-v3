#!/usr/bin/env python3
"""Live flash-loan route scanner + dry-call simulator.

Conservative rules:
- Uses deployed FlashLoanArbGeneric atomic flash-loan contracts.
- Quotes only routers whose swap calldata this script encodes correctly.
- Arbitrum: V2-compatible Camelot + SushiSwap cross-router routes.
- Base: Aerodrome route-struct swaps, stable/volatile pool combinations.
- Runs eth_call simulation before any live trade.
- Live execution only if --execute is passed and simulation succeeds.
"""

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from dotenv import load_dotenv
from web3 import Web3

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR if (SCRIPT_DIR / "live-flashloan").exists() else SCRIPT_DIR.parent

ETH_PRICE_USD = 1566.32
AAVE_PREMIUM_BPS = 5
MIN_NET_PROFIT_USD = 0.25
SLIPPAGE_BPS = 5

AERO_ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
AERO_FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"
VELO_ROUTER = "0xa062aE8A9c5e11aAa026fc2670b0D65cCc8B2858"
VELO_FACTORY = "0xCc0bDDB707055e04e497aB22a59c2aF4391cd12F"
SLIPSTREAM_ROUTER = "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5"
SLIPSTREAM_QUOTER = "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0"
# Common Aerodrome Slipstream tick spacings seen in production pools.
SLIPSTREAM_TICK_SPACINGS = [1, 50, 100, 200, 2000]
UNIV3_FEES = [100, 500, 3000, 10000]
UNIV3_ROUTER_BY_NETWORK = {
    "ethereum": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
    "optimism": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
    "arbitrum": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
    "base": "0x2626664c2603336E57B271c5C0b26F421741e481",
}
UNIV3_QUOTER_BY_NETWORK = {
    "ethereum": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
    "optimism": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
    "arbitrum": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
    "base": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
}

V2_ROUTER_ABI = [
    {"name": "getAmountsOut", "type": "function", "stateMutability": "view", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "path", "type": "address[]"}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
    {"name": "swapExactTokensForTokens", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"}, {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
]

AERO_ABI = [
    {"name": "getAmountsOut", "type": "function", "stateMutability": "view", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "routes", "type": "tuple[]", "components": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "stable", "type": "bool"}, {"name": "factory", "type": "address"}]}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
    {"name": "swapExactTokensForTokens", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"}, {"name": "routes", "type": "tuple[]", "components": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "stable", "type": "bool"}, {"name": "factory", "type": "address"}]}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "outputs": [{"name": "amounts", "type": "uint256[]"}]},
]

UNIV3_QUOTER_ABI = [
    {"name": "quoteExactInputSingle", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "params", "type": "tuple", "components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"}, {"name": "amountIn", "type": "uint256"}, {"name": "fee", "type": "uint24"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}]}], "outputs": [{"name": "amountOut", "type": "uint256"}, {"name": "sqrtPriceX96After", "type": "uint160"}, {"name": "initializedTicksCrossed", "type": "uint32"}, {"name": "gasEstimate", "type": "uint256"}]},
]
UNIV3_ROUTER_ABI = [
    {"name": "exactInputSingle", "type": "function", "stateMutability": "payable", "inputs": [{"name": "params", "type": "tuple", "components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"}, {"name": "fee", "type": "uint24"}, {"name": "recipient", "type": "address"}, {"name": "amountIn", "type": "uint256"}, {"name": "amountOutMinimum", "type": "uint256"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}]}], "outputs": [{"name": "amountOut", "type": "uint256"}]},
]
SLIPSTREAM_QUOTER_ABI = [
    {"name": "quoteExactInputSingle", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "params", "type": "tuple", "components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"}, {"name": "amountIn", "type": "uint256"}, {"name": "tickSpacing", "type": "int24"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}]}], "outputs": [{"name": "amountOut", "type": "uint256"}, {"name": "sqrtPriceX96After", "type": "uint160"}, {"name": "initializedTicksCrossed", "type": "uint32"}, {"name": "gasEstimate", "type": "uint256"}]},
]
SLIPSTREAM_ROUTER_ABI = [
    {"name": "exactInputSingle", "type": "function", "stateMutability": "payable", "inputs": [{"name": "params", "type": "tuple", "components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"}, {"name": "tickSpacing", "type": "int24"}, {"name": "recipient", "type": "address"}, {"name": "deadline", "type": "uint256"}, {"name": "amountIn", "type": "uint256"}, {"name": "amountOutMinimum", "type": "uint256"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}]}], "outputs": [{"name": "amountOut", "type": "uint256"}]},
]
UNIV3_POOL_ABI = [
    {"name": "fee", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "uint24"}]},
    {"name": "token0", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "address"}]},
    {"name": "token1", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "address"}]},
]

FLASH_ARB_GENERIC_ABI = [
    {"name": "executeArb", "type": "function", "stateMutability": "nonpayable", "inputs": [
        {"name": "p", "type": "tuple", "components": [
            {"name": "routerA", "type": "address"}, {"name": "routerB", "type": "address"},
            {"name": "tokenBorrow", "type": "address"}, {"name": "tokenMid", "type": "address"},
            {"name": "minProfit", "type": "uint256"}, {"name": "callDataA", "type": "bytes"}, {"name": "callDataB", "type": "bytes"},
        ]},
        {"name": "amount", "type": "uint256"},
    ], "outputs": []},
]

READ_RPC_FALLBACKS = {
    "ethereum": ["https://ethereum.publicnode.com", "https://rpc.ankr.com/eth"],
    "optimism": ["https://optimism.publicnode.com", "https://rpc.ankr.com/optimism"],
    "arbitrum": ["https://arbitrum-one.publicnode.com", "https://rpc.ankr.com/arbitrum"],
    "base": ["https://base.publicnode.com", "https://mainnet.base.org"],
}

@dataclass
class Token:
    symbol: str
    address: str
    decimals: int

@dataclass
class Router:
    name: str
    address: str
    kind: str = "v2"
    factory: Optional[str] = None

CONFIG = {
    "ethereum": {
        "chain_id": 1,
        "rpc_env": "ETHEREUM_RPC",
        "tokens": {
            "USDC": Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
            "USDT": Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
            "DAI": Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
            "WETH": Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18),
            "WBTC": Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8),
        },
        "routers": [Router("UniswapV3", UNIV3_ROUTER_BY_NETWORK["ethereum"], "univ3")],
        "univ3_quoter": UNIV3_QUOTER_BY_NETWORK["ethereum"],
    },
    "optimism": {
        "chain_id": 10,
        "rpc_env": "OPTIMISM_RPC",
        "tokens": {
            "USDC": Token("USDC", "0x0b2C639c533813f4Aa9D7837CAF62653d097Ff85", 6),
            "USDT": Token("USDT", "0x94b008aD8dD8bB8C7aA00d9e2B0502F01450F08D", 6),
            "DAI": Token("DAI", "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", 18),
            "WETH": Token("WETH", "0x4200000000000000000000000000000000000006", 18),
            "WBTC": Token("WBTC", "0x68f180fcCe6836688e9084f035309E29Bf0A2095", 8),
        },
        "routers": [
            Router("UniswapV3", UNIV3_ROUTER_BY_NETWORK["optimism"], "univ3"),
            Router("VelodromeV2", VELO_ROUTER, "aerodrome", VELO_FACTORY),
        ],
        "univ3_quoter": UNIV3_QUOTER_BY_NETWORK["optimism"],
    },
    "arbitrum": {
        "chain_id": 42161,
        "rpc_env": "ARBITRUM_RPC",
        "tokens": {
            "USDC": Token("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
            "USDT": Token("USDT", "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
            "DAI": Token("DAI", "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", 18),
            "WETH": Token("WETH", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18),
            "WBTC": Token("WBTC", "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f", 8),
        },
        "routers": [
            Router("CamelotV2", "0x9b35Af8778d3fbd5133da3A1016a656736e6A063", "v2"),
            Router("SushiSwapV2", "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506", "v2"),
            Router("UniswapV3", UNIV3_ROUTER_BY_NETWORK["arbitrum"], "univ3"),
        ],
        "univ3_quoter": UNIV3_QUOTER_BY_NETWORK["arbitrum"],
    },
    "base": {
        "chain_id": 8453,
        "rpc_env": "BASE_RPC",
        "tokens": {
            "USDC": Token("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
            "USDT": Token("USDT", "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2", 6),
            "DAI": Token("DAI", "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", 18),
            "WETH": Token("WETH", "0x4200000000000000000000000000000000000006", 18),
            "WBTC": Token("WBTC", "0x0555E30da8f98308EdB960aa94C0Db47230d2B9c", 8),
            "AERO": Token("AERO", "0x940181a94A35A4569E4529A3CDfB74e38FD98631", 18),
        },
        "routers": [
            Router("Aerodrome", AERO_ROUTER, "aerodrome", AERO_FACTORY),
            Router("AerodromeSlipstream", SLIPSTREAM_ROUTER, "slipstream"),
            Router("UniswapV3", UNIV3_ROUTER_BY_NETWORK["base"], "univ3"),
        ],
        "univ3_quoter": UNIV3_QUOTER_BY_NETWORK["base"],
    },
}

class Scanner:
    def __init__(self, network: str, execute: bool = False):
        load_dotenv(PROJECT_ROOT / ".env.local")
        load_dotenv(SCRIPT_DIR / ".env.local")
        self.network = network
        self.execute = execute
        self.cfg = CONFIG[network]
        rpc_candidates = [os.environ[self.cfg["rpc_env"]]] + READ_RPC_FALLBACKS.get(network, [])
        connected = False
        last_error = None
        self.rpc_url = rpc_candidates[0]
        for rpc_url in rpc_candidates:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
            for attempt in range(3):
                try:
                    connected = bool(self.w3.is_connected())
                    if connected:
                        self.rpc_url = rpc_url
                        break
                except Exception as exc:
                    last_error = exc
                time.sleep(1.0 + attempt)
            if connected:
                break
        if not connected:
            suffix = f": {last_error}" if last_error else ""
            raise RuntimeError(f"RPC not connected for {network}{suffix}")
        self.wallet = Web3.to_checksum_address(os.environ["WALLET_ADDRESS"])
        self.private_key = os.environ["PRIVATE_KEY"]
        with open(PROJECT_ROOT / "live-flashloan" / "deployments.json") as f:
            deployments = json.load(f)["contracts"]
        self.contract_addr = Web3.to_checksum_address(deployments[network]["flashLoanArbGeneric"])
        self.contract = self.w3.eth.contract(address=self.contract_addr, abi=FLASH_ARB_GENERIC_ABI)
        self.v2_iface = self.w3.eth.contract(abi=V2_ROUTER_ABI)
        self.aero = self.w3.eth.contract(address=Web3.to_checksum_address(AERO_ROUTER), abi=AERO_ABI)
        self.univ3_router_iface = self.w3.eth.contract(abi=UNIV3_ROUTER_ABI)
        self.univ3_quoter = self.w3.eth.contract(address=Web3.to_checksum_address(self.cfg["univ3_quoter"]), abi=UNIV3_QUOTER_ABI)
        self.slipstream_router_iface = self.w3.eth.contract(abi=SLIPSTREAM_ROUTER_ABI)
        self.slipstream_quoter = self.w3.eth.contract(address=Web3.to_checksum_address(SLIPSTREAM_QUOTER), abi=SLIPSTREAM_QUOTER_ABI)
        self._quote_cache = {}

    def to_units(self, amount: float, token: Token) -> int:
        return int(amount * (10 ** token.decimals))

    def from_units(self, amount: int, token: Token) -> float:
        return amount / (10 ** token.decimals)

    def gas_cost_usd(self, gas_limit: int = 950000) -> float:
        last_error = None
        for attempt in range(3):
            try:
                return (gas_limit * self.w3.eth.gas_price / 1e18) * ETH_PRICE_USD
            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()
                if "429" in msg or "too many requests" in msg or "timeout" in msg:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"gas_price_fetch_failed: {last_error}")

    def route_struct(self, token_in: str, token_out: str, stable: bool, factory: Optional[str] = None):
        return [(Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out), stable, Web3.to_checksum_address(factory or AERO_FACTORY))]

    def aero_route(self, token_in: str, token_out: str, stable: bool):
        return self.route_struct(token_in, token_out, stable, AERO_FACTORY)

    def quote_v2(self, router: Router, amount_in: int, path: List[str]) -> Optional[List[int]]:
        key = ("v2", router.address.lower(), int(amount_in), tuple(p.lower() for p in path))
        if key in self._quote_cache:
            return self._quote_cache[key]
        try:
            c = self.w3.eth.contract(address=Web3.to_checksum_address(router.address), abi=V2_ROUTER_ABI)
            out = c.functions.getAmountsOut(amount_in, [Web3.to_checksum_address(p) for p in path]).call()
            self._quote_cache[key] = out
            return out
        except Exception:
            self._quote_cache[key] = None
            return None

    def quote_aero(self, amount_in: int, token_in: str, token_out: str, stable: bool, router: Optional[Router] = None) -> Optional[List[int]]:
        router = router or Router("Aerodrome", AERO_ROUTER, "aerodrome", AERO_FACTORY)
        key = ("aero", router.address.lower(), router.factory or AERO_FACTORY, int(amount_in), token_in.lower(), token_out.lower(), bool(stable))
        if key in self._quote_cache:
            return self._quote_cache[key]
        try:
            c = self.w3.eth.contract(address=Web3.to_checksum_address(router.address), abi=AERO_ABI)
            out = c.functions.getAmountsOut(amount_in, self.route_struct(token_in, token_out, stable, router.factory)).call()
            self._quote_cache[key] = out
            return out
        except Exception:
            self._quote_cache[key] = None
            return None

    def quote_univ3(self, amount_in: int, token_in: str, token_out: str, fee: int) -> Optional[int]:
        key = ("univ3", int(amount_in), token_in.lower(), token_out.lower(), int(fee))
        if key in self._quote_cache:
            return self._quote_cache[key]
        try:
            params = (Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out), int(amount_in), int(fee), 0)
            out = self.univ3_quoter.functions.quoteExactInputSingle(params).call({"from": self.wallet})
            amount_out = int(out[0] if isinstance(out, (list, tuple)) else out)
            self._quote_cache[key] = amount_out
            return amount_out
        except Exception:
            self._quote_cache[key] = None
            return None

    def is_pair_in_scope(self, borrow_sym: str, mid_sym: str) -> bool:
        stables = {"USDC", "USDT", "DAI"}
        mids = {"WETH", "WBTC", "AERO"}
        return (borrow_sym in stables and mid_sym in stables) or (borrow_sym in mids and mid_sym in stables) or (borrow_sym in stables and mid_sym in mids)

    def scan_v2(self) -> List[Dict]:
        tokens = self.cfg["tokens"]
        amounts_usd = [25, 100, 500, 2500, 10000]
        candidates = []
        routers = [r for r in self.cfg["routers"] if r.kind == "v2"]
        for borrow_sym, borrow in tokens.items():
            for mid_sym, mid in tokens.items():
                if mid_sym == borrow_sym:
                    continue
                if not self.is_pair_in_scope(borrow_sym, mid_sym):
                    continue
                for amount_usd in amounts_usd:
                    amount = self.to_units(amount_usd, borrow)
                    for router_a in routers:
                        q1 = self.quote_v2(router_a, amount, [borrow.address, mid.address])
                        if not q1:
                            continue
                        mid_out = q1[-1]
                        for router_b in routers:
                            if router_b.address.lower() == router_a.address.lower():
                                continue
                            q2 = self.quote_v2(router_b, mid_out, [mid.address, borrow.address])
                            if not q2:
                                continue
                            self.add_candidate(candidates, borrow_sym, mid_sym, amount_usd, amount, router_a, router_b, mid_out, q2[-1], route_kind="v2")
        return candidates

    def scan_univ3(self) -> List[Dict]:
        tokens = self.cfg["tokens"]
        amounts_usd = [25, 100, 500, 2500, 10000]
        candidates = []
        routers = [r for r in self.cfg["routers"] if r.kind == "univ3"]
        if not routers:
            return candidates
        router = routers[0]
        for borrow_sym, borrow in tokens.items():
            for mid_sym, mid in tokens.items():
                if mid_sym == borrow_sym or not self.is_pair_in_scope(borrow_sym, mid_sym):
                    continue
                for amount_usd in amounts_usd:
                    amount = self.to_units(amount_usd, borrow)
                    for fee_a in UNIV3_FEES:
                        mid_out = self.quote_univ3(amount, borrow.address, mid.address, fee_a)
                        if not mid_out:
                            continue
                        for fee_b in UNIV3_FEES:
                            final_out = self.quote_univ3(mid_out, mid.address, borrow.address, fee_b)
                            if not final_out:
                                continue
                            self.add_candidate(candidates, borrow_sym, mid_sym, amount_usd, amount, router, router, mid_out, final_out, route_kind="univ3", feeA=fee_a, feeB=fee_b)
        return candidates

    def quote_slipstream(self, amount_in: int, token_in: str, token_out: str, tick_spacing: int) -> Optional[int]:
        key = ("slipstream", int(amount_in), token_in.lower(), token_out.lower(), int(tick_spacing))
        if key in self._quote_cache:
            return self._quote_cache[key]
        try:
            params = (Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out), int(amount_in), int(tick_spacing), 0)
            out = self.slipstream_quoter.functions.quoteExactInputSingle(params).call({"from": self.wallet})
            amount_out = int(out[0] if isinstance(out, (list, tuple)) else out)
            self._quote_cache[key] = amount_out
            return amount_out
        except Exception:
            self._quote_cache[key] = None
            return None

    def scan_aerodrome(self) -> List[Dict]:
        tokens = self.cfg["tokens"]
        amounts_usd = [25, 100, 500, 2500, 10000]
        routers = [r for r in self.cfg["routers"] if r.kind == "aerodrome"]
        candidates = []
        for borrow_sym, borrow in tokens.items():
            for mid_sym, mid in tokens.items():
                if mid_sym == borrow_sym:
                    continue
                if not self.is_pair_in_scope(borrow_sym, mid_sym):
                    continue
                for amount_usd in amounts_usd:
                    amount = self.to_units(amount_usd, borrow)
                    for router in routers:
                        for stable_a in [True, False]:
                            q1 = self.quote_aero(amount, borrow.address, mid.address, stable_a, router)
                            if not q1:
                                continue
                            mid_out = q1[-1]
                            for stable_b in [True, False]:
                                # Same router is allowed because stable/volatile pools are distinct markets.
                                q2 = self.quote_aero(mid_out, mid.address, borrow.address, stable_b, router)
                                if not q2:
                                    continue
                                self.add_candidate(candidates, borrow_sym, mid_sym, amount_usd, amount, router, router, mid_out, q2[-1], route_kind="aerodrome", stableA=stable_a, stableB=stable_b)
        return candidates

    def add_candidate(self, candidates: List[Dict], borrow_sym: str, mid_sym: str, amount_usd: float, amount: int, router_a: Router, router_b: Router, mid_out: int, final_out: int, **extra) -> None:
        borrow = self.cfg["tokens"][borrow_sym]
        premium = amount * AAVE_PREMIUM_BPS // 10000
        gross = final_out - amount - premium
        gross_units = self.from_units(gross, borrow)
        try:
            gas_usd = self.gas_cost_usd()
        except Exception:
            # Candidate construction should not collapse on transient RPC gas-price
            # failures; final promotion still requires successful gas estimate.
            gas_usd = 2.0
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
                **extra,
            })

    def scan(self) -> List[Dict]:
        candidates = []
        candidates.extend(self.scan_v2())
        candidates.extend(self.scan_aerodrome())
        candidates.extend(self.scan_univ3())
        candidates.sort(key=lambda x: x["net_profit_usd"], reverse=True)
        return candidates

    def encode_leg(self, leg: str, router_data: Dict, token_in: Token, token_out: Token, amount_in: int, amount_out_min: int, c: Dict, deadline: int) -> str:
        router = Router(**{k: router_data.get(k) for k in ["name", "address", "kind", "factory"] if k in router_data})
        kind = c.get(f"{leg}_route_kind") or router.kind
        if kind == "aerodrome":
            iface = self.w3.eth.contract(address=Web3.to_checksum_address(router.address), abi=AERO_ABI)
            stable = bool(c.get(f"stable{leg}"))
            return iface.functions.swapExactTokensForTokens(
                int(amount_in),
                int(amount_out_min),
                self.route_struct(token_in.address, token_out.address, stable, router.factory),
                self.contract_addr,
                deadline,
            )._encode_transaction_data()
        if kind == "v2":
            return self.v2_iface.functions.swapExactTokensForTokens(
                int(amount_in),
                int(amount_out_min),
                [Web3.to_checksum_address(token_in.address), Web3.to_checksum_address(token_out.address)],
                self.contract_addr,
                deadline,
            )._encode_transaction_data()
        if kind == "univ3":
            fee = int(c.get(f"fee{leg}"))
            return self.univ3_router_iface.functions.exactInputSingle((
                Web3.to_checksum_address(token_in.address),
                Web3.to_checksum_address(token_out.address),
                fee,
                self.contract_addr,
                int(amount_in),
                int(amount_out_min),
                0,
            ))._encode_transaction_data()
        if kind == "slipstream":
            tick_spacing = int(c.get(f"tickSpacing{leg}"))
            return self.slipstream_router_iface.functions.exactInputSingle((
                Web3.to_checksum_address(token_in.address),
                Web3.to_checksum_address(token_out.address),
                tick_spacing,
                self.contract_addr,
                deadline,
                int(amount_in),
                int(amount_out_min),
                0,
            ))._encode_transaction_data()
        raise ValueError(f"unsupported leg kind={kind!r}")

    def build_params(self, c: Dict):
        borrow = self.cfg["tokens"][c["borrow"]]
        mid = self.cfg["tokens"][c["mid"]]
        min_mid = int(c["mid_out"]) * (10000 - SLIPPAGE_BPS) // 10000
        min_final = int(c["final_out"]) * (10000 - SLIPPAGE_BPS) // 10000
        min_profit = max(1, int((float(c["net_profit_usd"]) / 2) * (10 ** borrow.decimals)))
        deadline = int(time.time()) + 120
        call_a = self.encode_leg("A", c["routerA"], borrow, mid, int(c["amount"]), min_mid, c, deadline)
        call_b = self.encode_leg("B", c["routerB"], mid, borrow, int(c["mid_out"]), min_final, c, deadline)

        return (
            Web3.to_checksum_address(c["routerA"]["address"]),
            Web3.to_checksum_address(c["routerB"]["address"]),
            Web3.to_checksum_address(borrow.address),
            Web3.to_checksum_address(mid.address),
            min_profit,
            bytes.fromhex(call_a[2:]),
            bytes.fromhex(call_b[2:]),
        )

    def simulate(self, c: Dict) -> Tuple[bool, str]:
        try:
            self.contract.functions.executeArb(self.build_params(c), int(c["amount"])).call({"from": self.wallet})
            return True, "eth_call simulation passed"
        except Exception as e:
            return False, str(e)[:500]

    def estimate_gas_usd(self, c: Dict) -> Tuple[Optional[int], Optional[float], Optional[str]]:
        try:
            gas = self.contract.functions.executeArb(self.build_params(c), int(c["amount"])).estimate_gas({"from": self.wallet})
            return gas, self.gas_cost_usd(gas), None
        except Exception as e:
            return None, None, str(e)[:500]

    def execute_live(self, c: Dict) -> str:
        if os.getenv("REAL_TRANSACTIONS_ENABLED", "false").lower() != "true" or os.getenv("CONFIRM_LIVE_FLASHLOAN_EXECUTION", "no") != "YES":
            raise RuntimeError("live execution refused: requires REAL_TRANSACTIONS_ENABLED=true and CONFIRM_LIVE_FLASHLOAN_EXECUTION=YES")
        gas_estimate, gas_usd, gas_error = self.estimate_gas_usd(c)
        if gas_error:
            raise RuntimeError(f"gas estimate failed before live tx: {gas_error}")
        if gas_usd is None or gas_usd > 2.0:
            raise RuntimeError(f"gas gate failed before live tx: gas_usd={gas_usd}")
        tx = self.contract.functions.executeArb(self.build_params(c), int(c["amount"])).build_transaction({
            "from": self.wallet,
            "nonce": self.w3.eth.get_transaction_count(self.wallet),
            "chainId": self.cfg["chain_id"],
            "gas": int(gas_estimate * 1.25),
            "maxFeePerGas": int(self.w3.eth.gas_price * 2),
            "maxPriorityFeePerGas": max(1, int(self.w3.eth.gas_price * 0.3)),
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt.status != 1:
            raise RuntimeError(f"live tx reverted: {tx_hash.hex()}")
        return tx_hash.hex()

    def run(self) -> Dict:
        candidates = self.scan()
        results = []
        for c in candidates[:10]:
            gas_estimate, gas_usd, gas_error = self.estimate_gas_usd(c)
            ok, msg = self.simulate(c)
            c["simulation_ok"] = ok
            c["simulation_message"] = msg
            c["estimated_gas_units"] = gas_estimate
            c["estimated_gas_cost_usd"] = gas_usd
            c["gas_estimate_error"] = gas_error
            c["execution_gate"] = {
                "source_allowed": True,
                "simulation_ok": ok,
                "contract_exists": bool(self.w3.eth.get_code(self.contract_addr)),
                "gas_under_2_usd": gas_usd is not None and gas_usd <= 2.0,
                "net_profit_positive": float(c.get("net_profit_usd") or 0) > 0,
                "live_flag_enabled": self.execute,
            }
            c["why_not_executed"] = [k for k, v in c["execution_gate"].items() if not v]
            if ok and self.execute and not c["why_not_executed"]:
                c["tx_hash"] = self.execute_live(c)
            results.append(c)
        out = {
            "timestamp": datetime.now().isoformat(),
            "network": self.network,
            "contract": self.contract_addr,
            "source_scanner": "live",
            "candidates_found": len(candidates),
            "results": results,
        }
        with open(f"LIVE_FLASHLOAN_SCAN_{self.network.upper()}.json", "w") as f:
            json.dump(out, f, indent=2)
        return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", choices=["ethereum", "optimism", "arbitrum", "base"], required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    out = Scanner(args.network, args.execute).run()
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for r in out["results"][:5]:
        print(json.dumps({k: r.get(k) for k in ["borrow", "mid", "amount_human", "route_kind", "routerA", "routerB", "net_profit_usd", "simulation_ok", "simulation_message", "why_not_executed"]}, indent=2))

if __name__ == "__main__":
    main()
