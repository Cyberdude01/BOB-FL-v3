#!/usr/bin/env python3
"""BOB-FL Comprehensive Gas & Transaction Dashboard

Combines real-time gas monitoring with transaction analysis to provide:
- Current gas prices and costs
- Actual execution results vs estimates
- Performance trends and optimization recommendations
- Cost analysis and savings opportunities
- System health monitoring
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
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


def wei_to_eth(value: int) -> float:
    return value / 10**18


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


def get_gas_info(url: str) -> Dict[str, Any]:
    """Get current gas information for a network."""
    try:
        gas_price_wei = hex_to_int(rpc_call(url, "eth_gasPrice"))
        block = rpc_call(url, "eth_getBlockByNumber", ["latest", False])
        
        return {
            "gas_price_gwei": wei_to_gwei(gas_price_wei),
            "block_number": int(block.get("number", "0x0"), 16) if block.get("number") else 0,
            "base_fee_per_gas": wei_to_gwei(hex_to_int(block.get("baseFeePerGas", "0x0"))) if block.get("baseFeePerGas") else None,
        }
    except Exception:
        return {}


def get_wallet_balance(url: str, address: str) -> float:
    """Get wallet balance in ETH."""
    try:
        balance_wei = hex_to_int(rpc_call(url, "eth_getBalance", [address, "latest"]))
        return wei_to_eth(balance_wei)
    except Exception:
        return 0.0


def calculate_gas_costs(network_data: Dict, eth_price: Optional[float]) -> Dict[str, Any]:
    """Calculate gas costs for both networks."""
    costs = {}
    
    for network, info in network_data.items():
        gas_price = info.get("gas_info", {}).get("gas_price_gwei", 0)
        gas_limit = info.get("gas_limit", 450000)  # Default fallback
        
        gas_cost_eth = (gas_limit * gas_price) / 10**9
        gas_cost_usd = gas_cost_eth * eth_price if eth_price else None
        
        costs[network] = {
            "gas_price_gwei": round(gas_price, 4),
            "gas_limit": gas_limit,
            "gas_cost_eth": round(gas_cost_eth, 8),
            "gas_cost_usd": round(gas_cost_usd, 4) if gas_cost_usd else None,
        }
    
    return costs


def analyze_executions() -> Dict[str, Any]:
    """Analyze recent execution results."""
    exec_dir = ROOT / "data" / "live-executions"
    if not exec_dir.exists():
        return {"error": "No execution data available"}
    
    exec_files = sorted(exec_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not exec_files:
        return {"error": "No execution files found"}
    
    latest = load_json(exec_files[0])
    
    # Get gas estimates
    gas_dir = ROOT / "data" / "gas-reports"
    if gas_dir.exists():
        gas_files = sorted(gas_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if gas_files:
            gas_data = load_json(gas_files[0])
            latest["gas_estimates"] = gas_data.get("networks", {})
    
    return latest


def main() -> int:
    # Load configuration
    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")
    env_file = ROOT / ".env.local"
    
    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]
    
    print("=" * 80)
    print("  BOB-FL GAS & TRANSACTION DASHBOARD")
    print("=" * 80)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Wallet: {wallet}")
    print("=" * 80)
    
    # Get current ETH price
    eth_price = get_eth_price_usd()
    print(f"  ETH Price: ${eth_price:,.2f}" if eth_price else "  ETH Price: Unable to fetch")
    
    # Strategy gas limits from config
    strategies = {
        "arbitrum": {"gas_limit": 500000, "name": "Camelot flash loan"},
        "base": {"gas_limit": 400000, "name": "Aerodrome flash loan"},
    }
    
    # Get current gas and balance data
    network_data = {}
    total_value_usd = 0
    
    for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
        rpc_url = net_cfg["networks"][network].get("public_rpc", "")
        if not rpc_url:
            continue
            
        try:
            gas_info = get_gas_info(rpc_url)
            balance_eth = get_wallet_balance(rpc_url, wallet)
            balance_usd = balance_eth * eth_price if eth_price else None
            
            network_data[network] = {
                "gas_info": gas_info,
                "balance_eth": balance_eth,
                "balance_usd": balance_usd,
                "strategy": strategies.get(network, {"name": "default"}),
            }
            
            if balance_usd:
                total_value_usd += balance_usd
                
        except Exception as e:
            print(f"  {network}: Error - {e}")
            network_data[network] = {"error": str(e)}
    
    # Calculate gas costs
    gas_costs = calculate_gas_costs(network_data, eth_price)
    
    # Print current status
    print(f"\n  CURRENT NETWORK STATUS")
    print(f"  {'─' * 78}")
    
    for network in ["arbitrum", "base"]:
        data = network_data.get(network, {})
        costs = gas_costs.get(network, {})
        strategy = data.get("strategy", {})
        
        if "error" in data:
            print(f"  {network.upper()}: {data['error']}")
            continue
            
        print(f"\n  [{network.upper()}]")
        print(f"    Block:         {data['gas_info'].get('block_number', 'N/A'):,}")
        print(f"    Gas Price:     {costs.get('gas_price_gwei', 0):.4f} gwei")
        print(f"    Base Fee:      {data['gas_info'].get('base_fee_per_gas', 'N/A')} gwei")
        print(f"    Balance:       {data['balance_eth']:.8f} ETH", end="")
        if data['balance_usd']:
            print(f" (${data['balance_usd']:.4f})")
        else:
            print()
        print(f"    Strategy:      {strategy.get('name', 'unknown')}")
        
        if costs.get('gas_cost_usd'):
            print(f"    Est. Gas Cost: ${costs['gas_cost_usd']:.4f} ({costs['gas_cost_eth']:.8f} ETH)")
            if data['balance_eth'] > 0:
                pct = (costs['gas_cost_eth'] / data['balance_eth']) * 100
                print(f"    Cost %:        {pct:.2f}% of balance")
    
    # Analysis of recent executions
    print(f"\n  EXECUTION ANALYSIS")
    print(f"  {'─' * 78}")
    
    exec_analysis = analyze_executions()
    if "error" not in exec_analysis:
        latest = exec_analysis
        networks = latest.get("networks", {})
        
        success_count = sum(1 for n in networks.values() if n.get("success"))
        total_count = len(networks)
        
        print(f"\n  Latest Execution ({latest.get('mode', 'unknown')}):")
        print(f"    Success Rate: {success_count}/{total_count} ({(success_count/total_count)*100:.1f}%)")
        
        for network, data in networks.items():
            status = "✅ SUCCESS" if data.get("success") else "❌ FAILED"
            print(f"    {network}: {status}")
            
            if data.get("success"):
                exec_time = data.get("execution_time", 0)
                print(f"      Time: {exec_time:.4f}s")
                profit = data.get("opportunity", {}).get("estimated_profit_usd", 0)
                print(f"      Est. Profit: ${profit:.2f}")
    
    # Cost optimization
    print(f"\n  COST OPTIMIZATION")
    print(f"  {'─' * 78}")
    
    if len(gas_costs) == 2:
        arb_cost = gas_costs["arbitrum"].get("gas_cost_usd", 0)
        base_cost = gas_costs["base"].get("gas_cost_usd", 0)
        
        print(f"  Cost Comparison:")
        print(f"    Arbitrum: ${arb_cost:.4f}")
        print(f"    Base:     ${base_cost:.4f}")
        
        if abs(arb_cost - base_cost) > 0.001:  # More than 0.1 cent difference
            savings = abs(arb_cost - base_cost)
            cheaper = "Base" if base_cost < arb_cost else "Arbitrum"
            print(f"\n  💡 Recommendation: Use {cheaper} for ${savings:.4f} savings per transaction")
            
            # Calculate potential monthly savings
            daily_tx = 10  # Assuming 10 transactions per day
            monthly_savings = savings * daily_tx * 30
            print(f"  📊 Potential monthly savings: ${monthly_savings:.2f}")
    
    # System health
    print(f"\n  SYSTEM HEALTH")
    print(f"  {'─' * 78}")
    
    # Check wallet balances
    min_balance = 0.005  # Minimum balance threshold
    for network, data in network_data.items():
        if "error" not in data and data.get("balance_eth", 0) < min_balance:
            print(f"  ⚠️  {network} balance low: {data['balance_eth']:.6f} ETH")
        elif "error" not in data:
            print(f"  ✅  {network} balance: {data['balance_eth']:.6f} ETH")
    
    total_eth = sum(d.get("balance_eth", 0) for d in network_data.values() if "error" not in d)
    print(f"\n  Total Portfolio Value: {total_eth:.8f} ETH (${total_value_usd:.2f})")
    
    # Generate recommendations
    print(f"\n  RECOMMENDATIONS")
    print(f"  {'─' * 78}")
    
    recommendations = []
    
    # Gas price recommendations
    avg_gas = sum(d.get("gas_info", {}).get("gas_price_gwei", 0) for d in network_data.values() if "error" not in d) / len([d for d in network_data.values() if "error" not in d])
    if avg_gas > 0.1:  # High gas prices
        recommendations.append("🔥 Gas prices are elevated - consider waiting for lower prices")
    
    # Balance recommendations
    for network, data in network_data.items():
        if "error" not in data and data.get("balance_eth", 0) < min_balance:
            recommendations.append(f"⚠️  Fund {network} wallet with at least {min_balance} ETH")
    
    # Network recommendations
    if len(gas_costs) == 2:
        arb_cost = gas_costs["arbitrum"].get("gas_cost_usd", 0)
        base_cost = gas_costs["base"].get("gas_cost_usd", 0)
        if base_cost < arb_cost * 0.8:  # Base is significantly cheaper
            recommendations.append("💡 Use Base network for cost savings")
    
    if not recommendations:
        recommendations.append("✅ System is operating optimally")
    
    for rec in recommendations:
        print(f"  {rec}")
    
    # Save dashboard report
    dashboard_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eth_price_usd": eth_price,
        "total_portfolio_usd": total_value_usd,
        "network_status": network_data,
        "gas_costs": gas_costs,
        "recommendations": recommendations,
    }
    
    report_dir = ROOT / "data" / "dashboard-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"dashboard_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(dashboard_data, indent=2), encoding="utf-8")
    
    print(f"\n  Dashboard report saved: {report_path}")
    print(f"{'=' * 80}")
    
    return 0


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(main())