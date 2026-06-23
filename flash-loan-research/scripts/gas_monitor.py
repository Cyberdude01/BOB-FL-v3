#!/usr/bin/env python3
"""BOB-FL Gas Monitor - Real-time gas usage and cost monitoring.

Read-only script that:
- Fetches current gas prices on Arbitrum and Base
- Checks wallet balances and recent activity
- Estimates actual gas costs for configured strategies
- Reports fee history trends
- Calculates USD costs at current ETH price

No transactions are signed or submitted.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def rpc_call(url: str, method: str, params: Optional[list] = None) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def hex_to_int(value: str) -> int:
    return int(value, 16)


def wei_to_eth(value: int) -> float:
    return value / 10**18


def wei_to_gwei(value: int) -> float:
    return value / 10**9


def get_eth_price_usd() -> Optional[float]:
    """Fetch current ETH price from CoinGecko public API."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["ethereum"]["usd"]
    except Exception:
        return None


def get_gas_price(url: str) -> int:
    """Get current gas price from the network."""
    return hex_to_int(rpc_call(url, "eth_gasPrice"))


def get_fee_history(url: str, block_count: int = 10) -> Dict:
    """Get fee history for recent blocks."""
    try:
        result = rpc_call(url, "eth_feeHistory", [hex(block_count), "latest", [25, 50, 75]])
        return result
    except Exception:
        return {}


def get_nonce(url: str, address: str) -> int:
    """Get transaction count (nonce) for an address."""
    return hex_to_int(rpc_call(url, "eth_getTransactionCount", [address, "latest"]))


def get_balance(url: str, address: str) -> int:
    """Get ETH balance for an address in wei."""
    return hex_to_int(rpc_call(url, "eth_getBalance", [address, "latest"]))


def get_latest_block(url: str) -> Dict:
    """Get latest block info including base fee."""
    block = rpc_call(url, "eth_getBlockByNumber", ["latest", False])
    return block or {}


def estimate_gas_cost(gas_limit: int, gas_price_gwei: float, eth_price_usd: Optional[float]) -> Dict:
    """Calculate estimated gas cost."""
    gas_cost_eth = (gas_limit * gas_price_gwei) / 10**9
    gas_cost_usd = gas_cost_eth * eth_price_usd if eth_price_usd else None
    return {
        "gas_limit": gas_limit,
        "gas_price_gwei": round(gas_price_gwei, 4),
        "gas_cost_eth": round(gas_cost_eth, 8),
        "gas_cost_usd": round(gas_cost_usd, 4) if gas_cost_usd else None,
    }


def main() -> int:
    load_dotenv_file(ROOT / ".env.local")
    load_dotenv_file(ROOT / ".env")

    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")

    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]

    print("=" * 60)
    print("  BOB-FL Gas Monitor - Real-time Network Analysis")
    print("=" * 60)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Wallet: {wallet}")
    print("=" * 60)

    # Get ETH price
    eth_price = get_eth_price_usd()
    if eth_price:
        print(f"\n  ETH Price: ${eth_price:,.2f}")
    else:
        print("\n  ETH Price: Unable to fetch")

    # Strategy gas limits from config
    strategies = {
        "arbitrum": {"gas_limit": 500000, "name": "Camelot flash loan"},
        "base": {"gas_limit": 400000, "name": "Aerodrome flash loan"},
    }

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallet": wallet,
        "eth_price_usd": eth_price,
        "networks": {},
    }

    for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
        print(f"\n{'─' * 60}")
        print(f"  [{network.upper()}]")
        print(f"{'─' * 60}")

        rpc_url = net_cfg["networks"][network].get("public_rpc", "")
        if not rpc_url:
            rpc_url = os.getenv(f"{network.upper()}_RPC", "")
        if not rpc_url:
            print(f"  ERROR: No RPC URL for {network}")
            continue

        try:
            # Current gas price
            gas_price_wei = get_gas_price(rpc_url)
            gas_price_gwei = wei_to_gwei(gas_price_wei)

            # Latest block info
            block = get_latest_block(rpc_url)
            block_number = int(block.get("number", "0x0"), 16) if block.get("number") else 0
            base_fee_per_gas = block.get("baseFeePerGas")
            base_fee_gwei = wei_to_gwei(int(base_fee_per_gas, 16)) if base_fee_per_gas else None

            # Wallet balance and nonce
            balance_wei = get_balance(rpc_url, wallet)
            balance_eth = wei_to_eth(balance_wei)
            nonce = get_nonce(rpc_url, wallet)

            # Fee history (last 10 blocks)
            fee_hist = get_fee_history(rpc_url, 10)
            fee_hist_base_fees = []
            if fee_hist and "baseFeePerGas" in fee_hist:
                for fee in fee_hist["baseFeePerGas"]:
                    fee_hist_base_fees.append(round(wei_to_gwei(int(fee, 16)), 4))

            # Strategy gas cost estimate
            strat = strategies.get(network, {"gas_limit": 450000, "name": "default"})
            gas_estimate = estimate_gas_cost(strat["gas_limit"], gas_price_gwei, eth_price)

            # Print results
            print(f"  Latest Block:      {block_number:,}")
            print(f"  Current Gas Price: {gas_price_gwei:.4f} gwei")
            if base_fee_gwei is not None:
                print(f"  Base Fee:          {base_fee_gwei:.4f} gwei")
            print(f"  Wallet Balance:    {balance_eth:.8f} ETH")
            if eth_price:
                print(f"  Wallet Balance:    ${balance_eth * eth_price:.4f} USD")
            print(f"  Transaction Count: {nonce}")

            if fee_hist_base_fees:
                avg_base_fee = sum(fee_hist_base_fees) / len(fee_hist_base_fees)
                min_base_fee = min(fee_hist_base_fees)
                max_base_fee = max(fee_hist_base_fees)
                print(f"\n  Fee History (last {len(fee_hist_base_fees)} blocks):")
                print(f"    Min base fee:  {min_base_fee:.4f} gwei")
                print(f"    Avg base fee:  {avg_base_fee:.4f} gwei")
                print(f"    Max base fee:  {max_base_fee:.4f} gwei")

            print(f"\n  Strategy: {strat['name']}")
            print(f"  Gas Limit:         {strat['gas_limit']:,}")
            print(f"  Est. Gas Cost:     {gas_estimate['gas_cost_eth']:.8f} ETH")
            if gas_estimate['gas_cost_usd'] is not None:
                print(f"  Est. Gas Cost:     ${gas_estimate['gas_cost_usd']:.4f} USD")

            # Calculate cost as % of wallet balance
            if balance_eth > 0:
                pct_of_balance = (gas_estimate['gas_cost_eth'] / balance_eth) * 100
                print(f"  Cost vs Balance:   {pct_of_balance:.2f}%")

            # Store results
            results["networks"][network] = {
                "block_number": block_number,
                "gas_price_gwei": round(gas_price_gwei, 4),
                "base_fee_gwei": round(base_fee_gwei, 4) if base_fee_gwei else None,
                "wallet_balance_eth": balance_eth,
                "wallet_balance_usd": round(balance_eth * eth_price, 4) if eth_price else None,
                "transaction_count": nonce,
                "fee_history": {
                    "min_gwei": round(min(fee_hist_base_fees), 4) if fee_hist_base_fees else None,
                    "avg_gwei": round(sum(fee_hist_base_fees) / len(fee_hist_base_fees), 4) if fee_hist_base_fees else None,
                    "max_gwei": round(max(fee_hist_base_fees), 4) if fee_hist_base_fees else None,
                },
                "strategy_cost": gas_estimate,
            }

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results["networks"][network] = {"error": str(exc)}

    # Summary comparison
    print(f"\n{'=' * 60}")
    print("  COST COMPARISON SUMMARY")
    print(f"{'=' * 60}")

    arb = results["networks"].get("arbitrum", {})
    base = results["networks"].get("base", {})

    if arb.get("strategy_cost") and base.get("strategy_cost"):
        arb_cost = arb["strategy_cost"]
        base_cost = base["strategy_cost"]
        print(f"\n  Arbitrum:  {arb_cost['gas_cost_eth']:.8f} ETH", end="")
        if arb_cost.get("gas_cost_usd"):
            print(f" (${arb_cost['gas_cost_usd']:.4f})")
        else:
            print()
        print(f"  Base:      {base_cost['gas_cost_eth']:.8f} ETH", end="")
        if base_cost.get("gas_cost_usd"):
            print(f" (${base_cost['gas_cost_usd']:.4f})")
        else:
            print()

        cheaper = "Arbitrum" if arb_cost['gas_cost_eth'] < base_cost['gas_cost_eth'] else "Base"
        savings = abs(arb_cost['gas_cost_eth'] - base_cost['gas_cost_eth'])
        print(f"\n  Cheaper network:   {cheaper}")
        print(f"  Savings per tx:    {savings:.8f} ETH")

    if arb.get("wallet_balance_usd") or base.get("wallet_balance_usd"):
        print(f"\n  Total Wallet Value:")
        arb_usd = arb.get("wallet_balance_usd", 0) or 0
        base_usd = base.get("wallet_balance_usd", 0) or 0
        print(f"    Arbitrum: ${arb_usd:.4f}")
        print(f"    Base:     ${base_usd:.4f}")
        print(f"    Total:    ${arb_usd + base_usd:.4f}")

    # Save report
    report_dir = ROOT / "data" / "gas-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"gas_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n  Report saved: {report_path}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(main())
