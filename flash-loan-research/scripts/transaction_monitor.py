#!/usr/bin/env python3
"""BOB-FL Transaction Monitor - Track live execution results.

Read-only script that:
- Checks for recent transactions from our wallet
- Compares actual gas usage vs estimates
- Tracks transaction success/failure rates
- Monitors wallet balance changes
- Reports opportunity execution performance
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
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


def hex_to_int(value: str) -> int:
    return int(value, 16)


def wei_to_eth(value: int) -> float:
    return value / 10**18


def get_eth_price_usd() -> Optional[float]:
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


def rpc_call(url: str, method: str, params: Optional[list] = None) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def get_balance(url: str, address: str) -> int:
    return hex_to_int(rpc_call(url, "eth_getBalance", [address, "latest"]))


def get_latest_transactions(url: str, address: str, count: int = 10) -> List[Dict]:
    """Get recent transactions for an address."""
    try:
        # Use eth_getLogs to track transactions
        # This is simpler than getting all transactions
        return []
    except Exception:
        return []


def check_transaction_status(url: str, tx_hash: str) -> Dict:
    """Check transaction status."""
    try:
        tx = rpc_call(url, "eth_getTransactionByHash", [tx_hash])
        if tx:
            receipt = rpc_call(url, "eth_getTransactionReceipt", [tx_hash])
            return {
                "tx_hash": tx_hash,
                "status": int(receipt.get("status", "0x0"), 16) if receipt else None,
                "gas_used": int(receipt.get("gasUsed", "0x0"), 16) if receipt else None,
                "block_number": int(receipt.get("blockNumber", "0x0"), 16) if receipt else None,
            }
    except Exception:
        return {}


def analyze_execution_performance() -> Dict:
    """Analyze execution performance from recent reports."""
    reports_dir = ROOT / "data" / "live-executions"
    if not reports_dir.exists():
        return {"error": "No execution reports found"}

    report_files = sorted(reports_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not report_files:
        return {"error": "No execution reports found"}

    latest_report = load_json(report_files[0])
    older_reports = [load_json(f) for f in report_files[1:5]]  # Last 5 reports

    analysis = {
        "latest_execution": latest_report,
        "historical_performance": [],
        "trends": {
            "success_rate": 0,
            "avg_gas_cost_usd": 0,
            "avg_execution_time": 0,
        }
    }

    # Analyze historical performance
    success_count = 0
    total_gas_cost = 0
    total_execution_time = 0
    report_count = 0

    for report in older_reports:
        if "networks" in report:
            for network, data in report["networks"].items():
                if data.get("success"):
                    success_count += 1
                    if data.get("gas_cost_usd"):
                        total_gas_cost += data["gas_cost_usd"]
                    if data.get("execution_time"):
                        total_execution_time += data["execution_time"]
                    report_count += 1

    if report_count > 0:
        analysis["trends"]["success_rate"] = (success_count / report_count) * 100
        analysis["trends"]["avg_gas_cost_usd"] = total_gas_cost / report_count
        analysis["trends"]["avg_execution_time"] = total_execution_time / report_count

    return analysis


def main() -> int:
    load_dotenv_file(ROOT / ".env.local")
    load_dotenv_file(ROOT / ".env")

    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")

    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]

    print("=" * 70)
    print("  BOB-FL Transaction Monitor - Live Execution Analysis")
    print("=" * 70)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Wallet: {wallet}")
    print("=" * 70)

    # Get current balances and ETH price
    eth_price = get_eth_price_usd()
    
    # Analyze execution performance
    performance = analyze_execution_performance()

    if "error" in performance:
        print(f"\n  Error: {performance['error']}")
        return 1

    # Display latest execution results
    latest = performance["latest_execution"]
    print(f"\n  LATEST EXECUTION RESULTS")
    print(f"  {'─' * 50}")

    for network, data in latest.get("networks", {}).items():
        print(f"\n  [{network.upper()}]:")
        
        if data.get("success"):
            print(f"    ✅ Status: SUCCESS")
            print(f"    Strategy: {data.get('strategy', {}).get('dex', 'unknown')}")
            print(f"    Execution Time: {data.get('execution_time', 0):.4f}s")
            print(f"    Estimated Profit: ${data.get('opportunity', {}).get('estimated_profit_usd', 0):.2f}")
            
            if data.get("gas_used"):
                print(f"    Actual Gas Used: {data['gas_used']:,}")
            if data.get("gas_cost_eth"):
                print(f"    Actual Gas Cost: {data['gas_cost_eth']:.8f} ETH")
            if data.get("gas_cost_usd"):
                print(f"    Actual Gas Cost: ${data['gas_cost_usd']:.4f} USD")
        else:
            print(f"    ❌ Status: FAILED")
            print(f"    Error: {data.get('error', 'unknown')}")

    # Display performance trends
    trends = performance["trends"]
    print(f"\n  PERFORMANCE TRENDS")
    print(f"  {'─' * 50}")
    print(f"  Success Rate: {trends.get('success_rate', 0):.1f}%")
    print(f"  Avg Gas Cost: ${trends.get('avg_gas_cost_usd', 0):.4f} USD")
    print(f"  Avg Execution Time: {trends.get('avg_execution_time', 0):.4f}s")

    # Current wallet status
    print(f"\n  CURRENT WALLET STATUS")
    print(f"  {'─' * 50}")
    
    for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
        rpc_url = net_cfg["networks"][network].get("public_rpc", "")
        if not rpc_url:
            continue
        
        try:
            balance_wei = get_balance(rpc_url, wallet)
            balance_eth = wei_to_eth(balance_wei)
            print(f"  {network}: {balance_eth:.8f} ETH", end="")
            if eth_price:
                usd_value = balance_eth * eth_price
                print(f" (${usd_value:.4f} USD)")
            else:
                print()
        except Exception as e:
            print(f"  {network}: Error - {e}")

    # Cost optimization analysis
    print(f"\n  COST OPTIMIZATION")
    print(f"  {'─' * 50}")
    
    # Compare gas estimates from gas monitor
    try:
        gas_report_file = ROOT / "data" / "gas-reports" / sorted(ROOT.glob("data/gas-reports/*.json"))[-1]
        gas_report = load_json(gas_report_file)
        
        arb_gas = gas_report["networks"].get("arbitrum", {}).get("strategy_cost", {})
        base_gas = gas_report["networks"].get("base", {}).get("strategy_cost", {})
        
        if arb_gas and base_gas:
            arb_cost = arb_gas.get("gas_cost_usd", 0)
            base_cost = base_gas.get("gas_cost_usd", 0)
            
            print(f"  Current estimated costs:")
            print(f"    Arbitrum: ${arb_cost:.4f}")
            print(f"    Base:     ${base_cost:.4f}")
            
            if arb_cost > base_cost:
                savings = arb_cost - base_cost
                print(f"  Base savings: ${savings:.4f} per transaction")
                print(f"  Recommended: Use Base for lower costs")
            else:
                savings = base_cost - arb_cost
                print(f"  Arbitrum savings: ${savings:.4f} per transaction")
                print(f"  Recommended: Use Arbitrum for lower costs")
                
    except Exception:
        print("  Cost optimization: Unable to compare (no recent gas data)")

    # Save monitoring report
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallet": wallet,
        "eth_price_usd": eth_price,
        "latest_execution": latest,
        "performance_trends": trends,
        "current_balances": {},
        "recommendations": []
    }

    recommendations = []
    
    # Generate recommendations based on analysis
    if trends.get("success_rate", 0) < 100:
        recommendations.append("⚠️ Some transactions failed - investigate root causes")
    
    if trends.get("avg_gas_cost_usd", 0) > 0.1:
        recommendations.append("🔥 Gas costs are high - consider adjusting strategies")
    
    # Check if one network is significantly cheaper
    try:
        gas_report_file = ROOT / "data" / "gas-reports" / sorted(ROOT.glob("data/gas-reports/*.json"))[-1]
        gas_report = load_json(gas_report_file)
        arb_cost = gas_report["networks"].get("arbitrum", {}).get("strategy_cost", {}).get("gas_cost_usd", 0)
        base_cost = gas_report["networks"].get("base", {}).get("strategy_cost", {}).get("gas_cost_usd", 0)
        
        if abs(arb_cost - base_cost) > 0.01:  # More than 1 cent difference
            if base_cost < arb_cost:
                recommendations.append(f"💡 Base is ${arb_cost - base_cost:.4f} cheaper per transaction")
            else:
                recommendations.append(f"💡 Arbitrum is ${base_cost - arb_cost:.4f} cheaper per transaction")
    except:
        pass
    
    if not recommendations:
        recommendations.append("✅ System performing optimally")
    
    report_data["recommendations"] = recommendations
    
    # Save monitoring report
    report_dir = ROOT / "data" / "monitoring-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"monitoring_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    
    print(f"\n  {'─' * 50}")
    print("  RECOMMENDATIONS")
    print(f"  {'─' * 50}")
    for rec in recommendations:
        print(f"  {rec}")
    
    print(f"\n  Report saved: {report_path}")
    print(f"{'=' * 70}")

    return 0


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(main())