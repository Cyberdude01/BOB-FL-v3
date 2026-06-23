#!/usr/bin/env python3
"""Validate BOB-FL dev setup for Arbitrum + Base.

Read-only checks:
- safety gates are off for real execution
- configured wallet address format
- RPC connectivity and chain IDs
- wallet ETH balances
- protocol address code presence where addresses are complete

This script never signs or submits transactions.
It uses only the standard library + requests so it can run before full deps are installed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_rpc_url(network: str, cfg: Dict[str, Any]) -> str:
    ncfg = cfg["networks"][network]
    for key in ["rpc_env", "infura_env", "alchemy_env", "quicknode_env"]:
        env_name = ncfg.get(key)
        if env_name and os.getenv(env_name):
            return os.getenv(env_name, "").strip()
    return ncfg.get("public_rpc", "")


def rpc_call(url: str, method: str, params: Optional[list[Any]] = None) -> Any:
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


def check_code(url: str, address: str) -> str:
    if not address or address.startswith("VERIFY_"):
        return "SKIPPED"
    if not ADDRESS_RE.match(address):
        return "INVALID_ADDRESS"
    try:
        code = rpc_call(url, "eth_getCode", [address, "latest"])
        return "OK" if code and code != "0x" else "NO_CODE"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def main() -> int:
    load_dotenv_file(ROOT / ".env.local")
    load_dotenv_file(ROOT / ".env")

    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")
    addr_cfg = load_json(ROOT / "config" / "protocol-addresses.json")

    print("BOB-FL dev setup check")
    print("=======================")

    execution_enabled = env_bool("EXECUTION_ENABLED", net_cfg.get("execution_enabled", False))
    real_tx_enabled = env_bool("REAL_TRANSACTIONS_ENABLED", net_cfg.get("real_transactions_enabled", False))
    dry_run_mode = env_bool("DRY_RUN_MODE", False)
    
    # Allow execution_enabled=True for Phase 1, with real_transactions_enabled=True AND dry_run_mode=False
    if not execution_enabled:
        print("FAIL: execution_enabled must be true for Phase 1")
        return 2
    # Allow real_transactions_enabled=True with either dry_run_mode=True (signing only) or dry_run_mode=False (full execution)
    if real_tx_enabled and not dry_run_mode:
        print("INFO: Phase 1: real_transactions_enabled=True, dry_run_mode=False (full execution)")
    elif real_tx_enabled and dry_run_mode:
        print("INFO: Phase 1: real_transactions_enabled=True, dry_run_mode=True (signing only)")
    elif not real_tx_enabled and dry_run_mode:
        print("INFO: Phase 1 Dry Run: real_transactions_enabled=False, dry_run_mode=True (no signing)")
    else:
        # Default case when real_transactions_enabled=False and dry_run_mode=False
        print("INFO: Default configuration: real_transactions_enabled=False, dry_run_mode=False")

    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]
    if not ADDRESS_RE.match(wallet):
        print("FAIL: invalid wallet address format")
        return 2
    print(f"wallet={wallet}")

    active = net_cfg.get("active_networks", ["arbitrum", "base"])
    failed = False

    for network in active:
        print(f"\n[{network}]")
        rpc_url = get_rpc_url(network, net_cfg)
        if not rpc_url:
            print("RPC: MISSING")
            failed = True
            continue

        safe_rpc_display = rpc_url.split("?")[0]
        print(f"rpc={safe_rpc_display}")

        try:
            chain_id = hex_to_int(rpc_call(rpc_url, "eth_chainId"))
            expected = net_cfg["networks"][network]["chain_id"]
            print("connected=True")
            print(f"chain_id={chain_id} expected={expected}")
            if chain_id != expected:
                print("FAIL: chain id mismatch")
                failed = True

            balance_wei = hex_to_int(rpc_call(rpc_url, "eth_getBalance", [wallet, "latest"]))
            print(f"wallet_balance_eth={wei_to_eth(balance_wei):.18f}")

            network_addresses = addr_cfg["networks"].get(network, {})
            for group_name, group in network_addresses.items():
                if group_name in {"chain_id", "tokens"} or not isinstance(group, dict):
                    continue
                for contract_name, address in group.items():
                    if contract_name == "note" or not isinstance(address, str):
                        continue
                    status = check_code(rpc_url, address)
                    print(f"code.{group_name}.{contract_name}={status}")
                    if status.startswith("ERROR") or status in {"NO_CODE", "INVALID_ADDRESS"}:
                        failed = True
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}")
            failed = True

    print("\nResult:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
