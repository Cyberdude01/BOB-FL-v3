#!/usr/bin/env python3
"""Research-only flash-loan opportunity scanner using public market data.

This scanner does not execute trades. It looks for same-chain price spreads for
major assets across DEX venues with enough liquidity to be worth deeper route
simulation. It is intended to complement the deployed route/dry-call scanner,
especially on networks where no atomic contract route scanner is configured yet.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

NETWORKS = {
    "ethereum": {
        "dexscreener_chain": "ethereum",
        "gas_usd": 0.05,
        "tokens": {
            "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
            "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        },
    },
    "optimism": {
        "dexscreener_chain": "optimism",
        "gas_usd": 0.001,
        "tokens": {
            "WETH": "0x4200000000000000000000000000000000000006",
            "WBTC": "0x68f180fcce6836688e9084f035309e29bf0a2095",
            "LINK": "0x350a791Bfc2C21F9Ed5d10980Dad2e2638f6Ecd8",
            "OP": "0x4200000000000000000000000000000000000042",
        },
    },
    "arbitrum": {
        "dexscreener_chain": "arbitrum",
        "gas_usd": 0.002,
        "tokens": {
            "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
            "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
            "LINK": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
            "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        },
    },
    "base": {
        "dexscreener_chain": "base",
        "gas_usd": 0.001,
        "tokens": {
            "WETH": "0x4200000000000000000000000000000000000006",
            "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
            "AERO": "0x940181a94A35A4569E4529A3CDfB74e38FD98631",
            "DEGEN": "0x4ed4E862860beD7a18B58d8a415E748a08f5C0d7",
        },
    },
}

STABLE_SYMBOLS = {"USDC", "USDbC", "USDT", "DAI"}
MIN_LIQUIDITY_USD = 25_000
MIN_VOLUME_24H_USD = 10_000
MIN_SPREAD_BPS = 20  # 0.20%; research signal threshold before route sim
AAVE_PREMIUM_BPS = 5
TRADE_SIZE_USD = 10_000


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_pairs(chain: str, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token}"
    resp = requests.get(url, timeout=20, headers={"User-Agent": "OpenClaw flashloan research"})
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def price_usd(pair: Dict[str, Any]) -> Optional[float]:
    try:
        val = pair.get("priceUsd")
        return float(val) if val is not None else None
    except Exception:
        return None


def liquidity_usd(pair: Dict[str, Any]) -> float:
    try:
        return float((pair.get("liquidity") or {}).get("usd") or 0)
    except Exception:
        return 0.0


def volume_24h_usd(pair: Dict[str, Any]) -> float:
    try:
        return float((pair.get("volume") or {}).get("h24") or 0)
    except Exception:
        return 0.0


def stable_quote(pair: Dict[str, Any], symbol: str) -> bool:
    base = (pair.get("baseToken") or {}).get("symbol")
    quote = (pair.get("quoteToken") or {}).get("symbol")
    return symbol in {base, quote} and bool(STABLE_SYMBOLS.intersection({base, quote}))


def scan_token(network: str, symbol: str, address: str) -> List[Dict[str, Any]]:
    cfg = NETWORKS[network]
    pairs = []
    for pair in fetch_pairs(cfg["dexscreener_chain"], address):
        p = price_usd(pair)
        liq = liquidity_usd(pair)
        vol = volume_24h_usd(pair)
        if p is None or p <= 0 or liq < MIN_LIQUIDITY_USD or vol < MIN_VOLUME_24H_USD:
            continue
        if not stable_quote(pair, symbol):
            continue
        pairs.append(pair)

    # Need at least two venues/pools for an intra-chain spread.
    if len(pairs) < 2:
        return []

    pairs.sort(key=lambda x: price_usd(x) or 0)
    low = pairs[0]
    high = pairs[-1]
    low_price = price_usd(low)
    high_price = price_usd(high)
    if not low_price or not high_price or high_price <= low_price:
        return []

    mid = statistics.median([price_usd(p) for p in pairs if price_usd(p)])
    spread_bps = ((high_price - low_price) / mid) * 10_000 if mid else 0
    if spread_bps < MIN_SPREAD_BPS:
        return []

    limiting_liquidity = min(liquidity_usd(low), liquidity_usd(high))
    notional = min(TRADE_SIZE_USD, limiting_liquidity * 0.02)
    gross_usd = notional * (spread_bps / 10_000)
    premium_usd = notional * (AAVE_PREMIUM_BPS / 10_000)
    gas_usd = cfg["gas_usd"]
    net_usd = gross_usd - premium_usd - gas_usd
    if net_usd <= 0:
        return []

    return [{
        "network": network,
        "borrow": "USDC",
        "mid": symbol,
        "amount": int(notional * 1_000_000),
        "amount_human": round(notional, 2),
        "routerA": {
            "name": low.get("dexId") or "unknown",
            "address": low.get("pairAddress"),
            "url": low.get("url"),
            "role": "buy_low_pool",
        },
        "routerB": {
            "name": high.get("dexId") or "unknown",
            "address": high.get("pairAddress"),
            "url": high.get("url"),
            "role": "sell_high_pool",
        },
        "mid_out": None,
        "final_out": None,
        "premium": premium_usd,
        "gross_profit_token": round(gross_usd, 6),
        "gas_usd": gas_usd,
        "net_profit_usd": round(net_usd, 6),
        "spread_bps": round(spread_bps, 2),
        "low_price_usd": low_price,
        "high_price_usd": high_price,
        "liquidity_usd_low_pool": liquidity_usd(low),
        "liquidity_usd_high_pool": liquidity_usd(high),
        "volume_24h_usd_low_pool": volume_24h_usd(low),
        "volume_24h_usd_high_pool": volume_24h_usd(high),
        "simulation_ok": False,
        "simulation_message": "Market-data research signal only; requires route quote and eth_call simulation before execution.",
        "research_source": "dexscreener token-pairs",
    }]


def scan(network: str) -> Dict[str, Any]:
    if network not in NETWORKS:
        raise ValueError(f"unsupported network: {network}")
    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    for symbol, address in NETWORKS[network]["tokens"].items():
        try:
            results.extend(scan_token(network, symbol, address))
            time.sleep(0.25)  # be gentle with public API
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    results.sort(key=lambda x: x["net_profit_usd"], reverse=True)
    out = {
        "timestamp": now_iso(),
        "network": network,
        "contract": None,
        "scanner": "market_spread",
        "candidates_found": len(results),
        "results": results,
        "errors": errors,
        "thresholds": {
            "min_liquidity_usd": MIN_LIQUIDITY_USD,
            "min_volume_24h_usd": MIN_VOLUME_24H_USD,
            "min_spread_bps": MIN_SPREAD_BPS,
            "trade_size_usd": TRADE_SIZE_USD,
        },
    }
    with open(f"MARKET_SPREAD_FLASHLOAN_SCAN_{network.upper()}.json", "w") as f:
        json.dump(out, f, indent=2)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", choices=sorted(NETWORKS), required=True)
    args = ap.parse_args()
    out = scan(args.network)
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for row in out["results"][:5]:
        print(json.dumps({
            "network": row["network"],
            "asset": row["mid"],
            "spread_bps": row["spread_bps"],
            "net_profit_usd": row["net_profit_usd"],
            "buy": row["routerA"],
            "sell": row["routerB"],
        }, indent=2))


if __name__ == "__main__":
    main()
