# BOB-FL Development Setup: Arbitrum + Base First

Status: initial real-connectivity setup, read-only by default.

## Decisions

- Active networks: Arbitrum + Base only.
- Deferred networks: Ethereum, Optimism, cross-chain.
- Wallet model: single dedicated hot wallet for development/testing.
- Public wallet address: `0xc18EDe537AE7fD823d7A20942E11DfB067D47694`.
- Funding: tiny mainnet funds on Arbitrum and Base first.
- Pilot capital after dry-run/read-only checks: `$50-$100`.
- Dev max loss/exposure: `$50`.
- MEV path: Flashbots first.
- Eden: deferred until docs/endpoints are validated.
- RPC: public/free endpoints for development; Infura, Alchemy, and QuickNode placeholders for later.
- Monitoring: Telegram alerts to Mark + local dashboard.
- Real execution: disabled until wallet, RPC, protocol addresses, and circuit breakers pass checks.

## Files Added / Updated

- `.env.example` — safe development environment template.
- `config/dev_networks.json` — active network/RPC/MEV config.
- `config/wallets.example.json` — public wallet + dev limits, no private keys.
- `config/protocol-addresses.json` — v1 protocol/token address registry.
- `config/alerts.json` — Telegram/dashboard alert event config.
- `scripts/check_dev_setup.py` — read-only connectivity/balance/address-code checker.
- `docs/KEY_MANAGEMENT_PLAN.md` — security and backup plan.
- `docs/PRODUCTION_READINESS_CHECKLIST.md` — gates before production.

## Required Local Setup

1. Copy the example env file:

```bash
cp .env.example .env.local
```

2. Keep these gates disabled during development:

```bash
EXECUTION_ENABLED=false
REAL_TRANSACTIONS_ENABLED=false
REQUIRE_MANUAL_APPROVAL_FOR_REAL_TX=true
```

3. Add optional provider URLs later in `.env.local` only:

```bash
INFURA_ARBITRUM_RPC=
INFURA_BASE_RPC=
ALCHEMY_ARBITRUM_RPC=
ALCHEMY_BASE_RPC=
QUICKNODE_ARBITRUM_RPC=
QUICKNODE_BASE_RPC=
```

Never commit `.env.local`.

## Read-Only Validation

Run:

```bash
python scripts/check_dev_setup.py
```

The script checks:

- real execution gates are disabled
- wallet address is valid
- Arbitrum/Base RPC connectivity
- chain ID matches
- ETH gas balance on each chain
- deployed code exists at configured protocol addresses where complete

It does not sign or send transactions.

## Funding Guidance

For first pass, only fund enough ETH for gas testing on:

- Arbitrum
- Base

Keep the hot wallet capped. Suggested development cap: `$100` total wallet value.

## Execution Gate Policy

Real execution remains blocked until all are true:

- read-only setup check passes
- wallet has minimum gas balance on Arbitrum and Base
- protocol addresses are verified against official docs and block explorers
- circuit breaker thresholds are configured
- Telegram/dashboard alerts are working
- dry-run opportunity detection and simulated execution pass
- human explicitly approves enabling real transactions

## Notes

The old reports monitored Ethereum, Polygon, Avalanche, and BSC. This setup aligns new development with the Phase 3 execution priority: Arbitrum + Base first.
