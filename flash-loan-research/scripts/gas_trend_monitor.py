#!/usr/bin/env python3
"""BOB-FL Gas Trend Monitor - Track gas price and performance trends over time.

This script:
- Collects gas price data periodically
- Tracks execution costs and success rates
- Identifies trends and anomalies
- Provides actionable insights for optimization
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


def hex_to_int(value: str) -> int:
    return int(value, 16)


def wei_to_gwei(value: int) -> float:
    return value / 10**9


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


def get_current_gas_data(url: str) -> Dict[str, Any]:
    """Get current gas data for a network."""
    try:
        gas_price_wei = hex_to_int(rpc_call(url, "eth_gasPrice"))
        base_fee_per_gas = hex_to_int(rpc_call(url, "eth_getBlockByNumber", ["latest", False]).get("baseFeePerGas", "0x0"))
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gas_price_gwei": wei_to_gwei(gas_price_wei),
            "base_fee_gwei": wei_to_gwei(base_fee_per_gas),
            "priority_fee_gwei": wei_to_gwei(hex_to_int(rpc_call(url, "eth_maxPriorityFeePerGas", []))),
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_trends(historical_data: List[Dict], window_hours: int = 24) -> Dict[str, Any]:
    """Calculate trends from historical data."""
    if not historical_data:
        return {}
    
    # Filter data from last N hours
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    recent_data = [
        d for d in historical_data 
        if datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")) > cutoff_time
    ]
    
    if not recent_data:
        return {}
    
    # Calculate averages and trends
    avg_gas = sum(d["gas_price_gwei"] for d in recent_data) / len(recent_data)
    min_gas = min(d["gas_price_gwei"] for d in recent_data)
    max_gas = max(d["gas_price_gwei"] for d in recent_data)
    
    # Trend direction (simple slope calculation)
    if len(recent_data) >= 2:
        recent_sorted = sorted(recent_data, key=lambda x: x["timestamp"])
        first = recent_sorted[0]["gas_price_gwei"]
        last = recent_sorted[-1]["gas_price_gwei"]
        trend_direction = "up" if last > first else "down"
        trend_percent = ((last - first) / first) * 100 if first > 0 else 0
    else:
        trend_direction = "stable"
        trend_percent = 0
    
    return {
        "period_hours": window_hours,
        "data_points": len(recent_data),
        "avg_gas_price_gwei": round(avg_gas, 4),
        "min_gas_price_gwei": round(min_gas, 4),
        "max_gas_price_gwei": round(max_gas, 4),
        "current_gas_price_gwei": recent_data[-1]["gas_price_gwei"],
        "trend_direction": trend_direction,
        "trend_percent": round(trend_percent, 2),
    }


def analyze_gas_efficiency(current_gas: float, historical_trends: Dict) -> Dict[str, Any]:
    """Analyze gas efficiency compared to historical trends."""
    if not historical_trends:
        return {"status": "unknown", "message": "No historical data available"}
    
    current = current_gas
    avg = historical_trends.get("avg_gas_price_gwei", current)
    min_historical = historical_trends.get("min_gas_price_gwei", current)
    
    # Efficiency analysis
    if current <= min_historical:
        return {
            "status": "excellent",
            "message": "Current gas prices are at historical minimum",
            "savings_vs_avg": ((avg - current) / avg) * 100 if avg > 0 else 0,
        }
    elif current <= avg:
        return {
            "status": "good",
            "message": "Current gas prices are below average",
            "savings_vs_avg": ((avg - current) / avg) * 100 if avg > 0 else 0,
        }
    else:
        return {
            "status": "expensive",
            "message": "Current gas prices are above average",
            "premium_vs_avg": ((current - avg) / avg) * 100 if avg > 0 else 0,
        }


def generate_recommendations(current_gas_data: Dict, trends: Dict, efficiency: Dict) -> List[str]:
    """Generate optimization recommendations based on current data and trends."""
    recommendations = []
    
    current_gas = current_gas_data.get("gas_price_gwei", 0)
    trend = trends.get("trend_direction", "stable")
    efficiency_status = efficiency.get("status", "unknown")
    
    # Gas price recommendations
    if current_gas > 0.1:  # High gas prices
        if trend == "up":
            recommendations.append("🔥 Gas prices rising - consider delaying non-critical transactions")
        elif trend == "down":
            recommendations.append("💡 Gas prices falling - good time for transactions")
        else:
            recommendations.append("⚡ Current gas prices are high - consider timing optimization")
    
    # Efficiency recommendations
    if efficiency_status == "excellent":
        recommendations.append("🎯 Excellent gas prices - optimal time for execution")
    elif efficiency_status == "expensive":
        recommendations.append("💰 Gas prices are expensive - consider waiting for lower prices")
    
    # Network optimization
    if current_gas < 0.01:
        recommendations.append("✅ Excellent conditions - both networks are cost-effective")
    
    return recommendations


def main() -> int:
    # Load configuration
    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")
    
    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]
    
    print("=" * 80)
    print("  BOB-FL GAS TREND MONITOR")
    print("=" * 80)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    # Get current data
    eth_price = get_eth_price_usd()
    print(f"  ETH Price: ${eth_price:,.2f}" if eth_price else "  ETH Price: Unable to fetch")
    
    # Strategy gas limits
    strategies = {
        "arbitrum": {"gas_limit": 500000, "name": "Camelot"},
        "base": {"gas_limit": 400000, "name": "Aerodrome"},
    }
    
    # Get current gas data for both networks
    current_data = {}
    for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
        rpc_url = net_cfg["networks"][network].get("public_rpc", "")
        if not rpc_url:
            continue
            
        gas_data = get_current_gas_data(rpc_url)
        if "error" not in gas_data:
            current_data[network] = gas_data
    
    # Load historical data
    historical_dir = ROOT / "data" / "gas-history"
    historical_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing historical data or create new
    historical_file = historical_dir / f"gas_history_{datetime.now(timezone.utc).strftime('%Y%m')}.json"
    historical_data = []
    
    if historical_file.exists():
        historical_data = load_json(historical_file)
    
    # Add current data to historical
    for network, data in current_data.items():
        data["network"] = network
        historical_data.append(data)
    
    # Keep only recent data (last 30 days)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)
    historical_data = [
        d for d in historical_data 
        if datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")) > cutoff_time
    ]
    
    # Save updated historical data
    historical_file.write_text(json.dumps(historical_data, indent=2), encoding="utf-8")
    
    # Analyze trends
    trends = {}
    for network in ["arbitrum", "base"]:
        network_data = [d for d in historical_data if d.get("network") == network]
        if network_data:
            trends[network] = calculate_trends(network_data, window_hours=24)
    
    # Print current status
    print(f"\n  CURRENT GAS CONDITIONS")
    print(f"  {'─' * 78}")
    
    for network, data in current_data.items():
        print(f"\n  [{network.upper()}]")
        print(f"    Gas Price:    {data['gas_price_gwei']:.4f} gwei")
        print(f"    Base Fee:    {data['base_fee_gwei']:.4f} gwei")
        print(f"    Priority:    {data['priority_fee_gwei']:.4f} gwei")
        
        # Calculate estimated costs
        gas_limit = strategies[network]["gas_limit"]
        gas_cost_eth = (gas_limit * data['gas_price_gwei']) / 10**9
        gas_cost_usd = gas_cost_eth * eth_price if eth_price else None
        
        print(f"    Est. Cost:   {gas_cost_eth:.8f} ETH", end="")
        if gas_cost_usd:
            print(f" (${gas_cost_usd:.4f})")
        else:
            print()
    
    # Analyze efficiency and trends
    print(f"\n  TREND ANALYSIS")
    print(f"  {'─' * 78}")
    
    for network in ["arbitrum", "base"]:
        if network in trends:
            trend = trends[network]
            current_gas = current_data[network]["gas_price_gwei"]
            efficiency = analyze_gas_efficiency(current_gas, trend)
            
            print(f"\n  [{network.upper()} Trend Analysis]")
            print(f"    Current:      {current_gas:.4f} gwei")
            print(f"    24h Average:  {trend['avg_gas_price_gwei']:.4f} gwei")
            print(f"    24h Min:      {trend['min_gas_price_gwei']:.4f} gwei")
            print(f"    24h Max:      {trend['max_gas_price_gwei']:.4f} gwei")
            print(f"    Trend:        {trend['trend_direction']} ({trend['trend_percent']:+.2f}%)")
            
            print(f"    Efficiency:   {efficiency['status']}")
            if "savings_vs_avg" in efficiency:
                print(f"    Savings:      {efficiency['savings_vs_avg']:+.2f}% vs avg")
            elif "premium_vs_avg" in efficiency:
                print(f"    Premium:      {efficiency['premium_vs_avg']:+.2f}% vs avg")
    
    # Generate recommendations
    print(f"\n  OPTIMIZATION RECOMMENDATIONS")
    print(f"  {'─' * 78}")
    
    recommendations = []
    for network in ["arbitrum", "base"]:
        if network in current_data and network in trends:
            current = current_data[network]
            trend = trends[network]
            efficiency = analyze_gas_efficiency(current["gas_price_gwei"], trend)
            recs = generate_recommendations(current, trend, efficiency)
            recommendations.extend(recs)
    
    # Add network comparison
    if len(current_data) == 2:
        arb_gas = current_data["arbitrum"]["gas_price_gwei"]
        base_gas = current_data["base"]["gas_price_gwei"]
        
        if base_gas < arb_gas * 0.8:  # Base significantly cheaper
            recommendations.append(f"💡 Base is {((arb_gas - base_gas) / arb_gas * 100):.1f}% cheaper")
        elif arb_gas < base_gas * 0.8:
            recommendations.append(f"💡 Arbitrum is {((base_gas - arb_gas) / base_gas * 100):.1f}% cheaper")
    
    # Remove duplicates
    unique_recommendations = []
    seen = set()
    for rec in recommendations:
        if rec not in seen:
            unique_recommendations.append(rec)
            seen.add(rec)
    
    for rec in unique_recommendations:
        print(f"  {rec}")
    
    if not unique_recommendations:
        print("  ✅ No specific recommendations - current conditions are optimal")
    
    # Save trend analysis report
    trend_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_gas_data": current_data,
        "trends": trends,
        "recommendations": unique_recommendations,
        "historical_points": len(historical_data),
    }
    
    report_dir = ROOT / "data" / "trend-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"trend_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(trend_data, indent=2), encoding="utf-8")
    
    print(f"\n  Trend report saved: {report_path}")
    print(f"{'=' * 80}")
    
    return 0


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(main())