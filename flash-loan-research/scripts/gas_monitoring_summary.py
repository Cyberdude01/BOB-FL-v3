#!/usr/bin/env python3
"""BOB-FL Gas Monitoring Summary - Comprehensive Analysis

This script creates a consolidated report combining:
- Real-time gas prices and costs
- Historical trend analysis
- Transaction performance data
- Cost optimization insights
- System health status
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


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


def hex_to_int(value: str) -> int:
    return int(value, 16)


def wei_to_gwei(value: int) -> float:
    return value / 10**9


def rpc_call(url: str, method: str, params: Optional[list] = None) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def get_current_gas_data(url: str, network_name: str) -> Dict[str, Any]:
    """Get current gas data for a network."""
    try:
        gas_price_wei = hex_to_int(rpc_call(url, "eth_gasPrice"))
        block = rpc_call(url, "eth_getBlockByNumber", ["latest", False])
        base_fee_per_gas = hex_to_int(block.get("baseFeePerGas", "0x0"))
        priority_fee_wei = hex_to_int(rpc_call(url, "eth_maxPriorityFeePerGas", []))
        
        return {
            "network": network_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gas_price_gwei": wei_to_gwei(gas_price_wei),
            "base_fee_gwei": wei_to_gwei(base_fee_per_gas),
            "priority_fee_gwei": wei_to_gwei(priority_fee_wei),
            "block_number": int(block.get("number", "0x0"), 16) if block.get("number") else 0,
        }
    except Exception as e:
        return {"network": network_name, "error": str(e)}


def get_wallet_balance(url: str, address: str) -> float:
    """Get wallet balance in ETH."""
    try:
        balance_wei = hex_to_int(rpc_call(url, "eth_getBalance", [address, "latest"]))
        return balance_wei / 10**18
    except Exception:
        return 0.0


def analyze_gas_trends(historical_data: List[Dict], network: str) -> Dict[str, Any]:
    """Analyze gas trends for a specific network."""
    network_data = [d for d in historical_data if d.get("network") == network]
    if not network_data:
        return {"status": "no_data"}
    
    # Sort by timestamp
    network_data.sort(key=lambda x: x.get("timestamp", ""))
    
    # Calculate statistics
    gas_prices = [d.get("gas_price_gwei", 0) for d in network_data if "error" not in d]
    
    if not gas_prices:
        return {"status": "no_valid_data"}
    
    current = gas_prices[-1]
    avg = sum(gas_prices) / len(gas_prices)
    min_val = min(gas_prices)
    max_val = max(gas_prices)
    
    # Trend analysis (last 10% of data)
    recent_count = max(1, len(gas_prices) // 10)
    recent_prices = gas_prices[-recent_count:]
    recent_avg = sum(recent_prices) / len(recent_prices)
    
    trend = "stable"
    if recent_avg > avg * 1.05:
        trend = "up"
    elif recent_avg < avg * 0.95:
        trend = "down"
    
    return {
        "current": current,
        "average": avg,
        "minimum": min_val,
        "maximum": max_val,
        "trend": trend,
        "recent_average": recent_avg,
        "data_points": len(gas_prices),
    }


def calculate_estimated_costs(gas_data: Dict, eth_price: Optional[float], network: str) -> Dict[str, Any]:
    """Calculate estimated transaction costs."""
    gas_limits = {
        "arbitrum": 500000,
        "base": 400000,
    }
    
    gas_limit = gas_limits.get(network, 450000)
    gas_price = gas_data.get("gas_price_gwei", 0)
    
    gas_cost_eth = (gas_limit * gas_price) / 10**9
    gas_cost_usd = gas_cost_eth * eth_price if eth_price else None
    
    return {
        "gas_limit": gas_limit,
        "gas_price_gwei": gas_price,
        "gas_cost_eth": gas_cost_eth,
        "gas_cost_usd": gas_cost_usd,
    }


def main() -> int:
    # Load configuration
    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")
    
    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]
    
    print("=" * 80)
    print("  BOB-FL GAS MONITORING SUMMARY")
    print("=" * 80)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Wallet: {wallet}")
    print("=" * 80)
    
    # Get current ETH price
    eth_price = get_eth_price_usd()
    print(f"  ETH Price: ${eth_price:,.2f}" if eth_price else "  ETH Price: Unable to fetch")
    
    # Get current gas data and wallet balances
    current_data = {}
    total_value_eth = 0
    total_value_usd = 0
    
    for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
        rpc_url = net_cfg["networks"][network].get("public_rpc", "")
        if not rpc_url:
            continue
            
        gas_data = get_current_gas_data(rpc_url, network)
        balance_eth = get_wallet_balance(rpc_url, wallet)
        balance_usd = balance_eth * eth_price if eth_price else None
        
        current_data[network] = {
            "gas_data": gas_data,
            "balance_eth": balance_eth,
            "balance_usd": balance_usd,
        }
        
        total_value_eth += balance_eth
        if balance_usd:
            total_value_usd += balance_usd
    
    # Load historical data
    historical_dir = ROOT / "data" / "gas-history"
    historical_data = []
    
    if historical_dir.exists():
        for file in historical_dir.glob("*.json"):
            try:
                historical_data.extend(load_json(file))
            except:
                continue
    
    # Analyze trends
    trends = {}
    for network in ["arbitrum", "base"]:
        trends[network] = analyze_gas_trends(historical_data, network)
    
    # Print current conditions
    print(f"\n  CURRENT GAS CONDITIONS")
    print(f"  {'─' * 78}")
    
    cost_comparison = []
    
    for network in ["arbitrum", "base"]:
        data = current_data.get(network, {})
        gas_data = data.get("gas_data", {})
        
        if "error" in gas_data:
            print(f"\n  [{network.upper()}]: {gas_data['error']}")
            continue
        
        print(f"\n  [{network.upper()}]")
        print(f"    Block:         {gas_data['block_number']:,}")
        print(f"    Gas Price:     {gas_data['gas_price_gwei']:.4f} gwei")
        print(f"    Base Fee:      {gas_data['base_fee_gwei']:.4f} gwei")
        print(f"    Priority:      {gas_data['priority_fee_gwei']:.4f} gwei")
        print(f"    Balance:       {data['balance_eth']:.8f} ETH", end="")
        if data['balance_usd']:
            print(f" (${data['balance_usd']:.4f})")
        else:
            print()
        
        # Calculate estimated costs
        costs = calculate_estimated_costs(gas_data, eth_price, network)
        print(f"    Est. Cost:     {costs['gas_cost_eth']:.8f} ETH", end="")
        if costs['gas_cost_usd']:
            print(f" (${costs['gas_cost_usd']:.4f})")
            cost_comparison.append((network, costs['gas_cost_usd']))
        else:
            print()
    
    # Trend analysis
    print(f"\n  TREND ANALYSIS")
    print(f"  {'─' * 78}")
    
    for network in ["arbitrum", "base"]:
        trend = trends[network]
        if trend.get("status") not in ["no_data", "no_valid_data"]:
            print(f"\n  [{network.upper()} Trend Analysis]")
            print(f"    Current:       {trend['current']:.4f} gwei")
            print(f"    24h Average:   {trend['average']:.4f} gwei")
            print(f"    24h Min:       {trend['minimum']:.4f} gwei")
            print(f"    24h Max:       {trend['maximum']:.4f} gwei")
            print(f"    Trend:         {trend['trend']}")
            print(f"    Recent Avg:    {trend['recent_average']:.4f} gwei")
            print(f"    Data Points:   {trend['data_points']}")
        else:
            print(f"\n  [{network.upper()}]: No trend data available")
    
    # Cost optimization
    print(f"\n  COST OPTIMIZATION")
    print(f"  {'─' * 78}")
    
    if len(cost_comparison) == 2:
        arb_cost = next((c for n, c in cost_comparison if n == "arbitrum"), 0)
        base_cost = next((c for n, c in cost_comparison if n == "base"), 0)
        
        print(f"  Current Estimated Costs:")
        print(f"    Arbitrum: ${arb_cost:.4f}")
        print(f"    Base:     ${base_cost:.4f}")
        
        if arb_cost > base_cost:
            savings = arb_cost - base_cost
            savings_pct = (savings / arb_cost) * 100
            print(f"\n  💡 Base is {savings_pct:.1f}% cheaper")
            print(f"  💡 Savings: ${savings:.4f} per transaction")
            
            # Calculate potential annual savings
            daily_tx = 10  # Assumed daily transactions
            annual_savings = savings * daily_tx * 365
            print(f"  📊 Annual potential savings: ${annual_savings:.2f}")
        elif base_cost > arb_cost:
            savings = base_cost - arb_cost
            savings_pct = (savings / base_cost) * 100
            print(f"\n  💡 Arbitrum is {savings_pct:.1f}% cheaper")
            print(f"  💡 Savings: ${savings:.4f} per transaction")
    
    # System health
    print(f"\n  SYSTEM HEALTH")
    print(f"  {'─' * 78}")
    print(f"  Total Portfolio Value: {total_value_eth:.8f} ETH (${total_value_usd:.2f})")
    
    # Check balances
    min_balance = 0.005
    healthy_balances = True
    
    for network in ["arbitrum", "base"]:
        balance = current_data.get(network, {}).get("balance_eth", 0)
        if balance < min_balance:
            print(f"  ⚠️  {network} balance low: {balance:.6f} ETH")
            healthy_balances = False
        else:
            print(f"  ✅  {network} balance: {balance:.6f} ETH")
    
    if healthy_balances:
        print(f"  ✅ All balances above minimum threshold")
    
    # Gas price health
    avg_gas = sum(d.get("gas_data", {}).get("gas_price_gwei", 0) for d in current_data.values() if "error" not in d.get("gas_data", {})) / len([d for d in current_data.values() if "error" not in d.get("gas_data", {})])
    
    if avg_gas < 0.01:
        print(f"  🎯 Excellent gas conditions: {avg_gas:.4f} gwei average")
    elif avg_gas < 0.05:
        print(f"  ✅ Good gas conditions: {avg_gas:.4f} gwei average")
    else:
        print(f"  ⚠️  High gas prices: {avg_gas:.4f} gwei average")
    
    # Recommendations
    print(f"\n  RECOMMENDATIONS")
    print(f"  {'─' * 78}")
    
    recommendations = []
    
    # Network recommendations
    if len(cost_comparison) == 2:
        arb_cost = next((c for n, c in cost_comparison if n == "arbitrum"), 0)
        base_cost = next((c for n, c in cost_comparison if n == "base"), 0)
        
        if base_cost < arb_cost * 0.8:
            recommendations.append("💡 Use Base network for significant cost savings")
        elif arb_cost < base_cost * 0.8:
            recommendations.append("💡 Use Arbitrum for cost savings")
    
    # Timing recommendations
    all_trends_good = True
    for network, trend in trends.items():
        if trend.get("status") not in ["no_data", "no_valid_data"]:
            if trend["trend"] == "down":
                recommendations.append(f"📉 Gas prices falling on {network} - good time to execute")
            elif trend["trend"] == "up":
                recommendations.append(f"📈 Gas prices rising on {network} - consider delaying")
            if trend["current"] > trend["average"] * 1.1:
                all_trends_good = False
    
    if all_trends_good and len(recommendations) == 0:
        recommendations.append("✅ Current conditions are optimal for execution")
    
    for rec in recommendations:
        print(f"  {rec}")
    
    # Save summary report
    summary_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eth_price_usd": eth_price,
        "total_portfolio_eth": total_value_eth,
        "total_portfolio_usd": total_value_usd,
        "current_conditions": current_data,
        "trends": trends,
        "recommendations": recommendations,
        "cost_comparison": cost_comparison,
    }
    
    report_dir = ROOT / "data" / "summary-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"gas_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    
    print(f"\n  Summary report saved: {report_path}")
    print(f"{'=' * 80}")
    
    return 0


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(main())