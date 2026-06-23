#!/usr/bin/env python3
"""Comprehensive executable scanner wrapper.

The previous version mixed executable V2 routes with placeholder V3 calldata.
For safety, this wrapper delegates to live_flashloan_scanner.Scanner, which only
emits candidates whose calldata can be encoded and eth_call-simulated.
"""

import argparse
import json
from datetime import datetime

from live_flashloan_scanner import Scanner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", choices=["ethereum", "optimism", "arbitrum", "base"], required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    out = Scanner(args.network, args.execute).run()
    out["source_scanner"] = "comprehensive"
    out["timestamp"] = datetime.now().isoformat()
    out_file = f"COMPREHENSIVE_FLASHLOAN_SCAN_{args.network.upper()}.json"
    with open(out_file, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for r in out.get("results", [])[:5]:
        print(json.dumps({k: r.get(k) for k in ["borrow", "mid", "amount_human", "route_kind", "net_profit_usd", "simulation_ok", "why_not_executed"]}, indent=2))


if __name__ == "__main__":
    main()
