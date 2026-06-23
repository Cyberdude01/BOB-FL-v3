# Backup Manifest: BOB-FL-v3

This repository is a sanitized, restorable backup of the flash-loan VM project.

## Included
- Active Python flash-loan scanner/executor/orchestrator source from `/root/.openclaw/workspace/flash-loan-research`.
- Active production subset from `/opt/flash-loan` under `opt-flash-loan/`.
- Solidity Foundry source/scripts/tests, excluding build artifacts and vendored libs.
- Safe config files and protocol/network address JSON.
- Systemd/supervisor templates only; nothing auto-starts during restore.
- Discovered cron templates with restore script that sanitizes paths/secrets.
- `.env.example` containing variable names only; no real values.
- Install, restore, and healthcheck scripts.

## Excluded intentionally
- `.env`, `.env.local`, `.env.backup*`, private keys, API keys, tokens, wallet files, browser/cookie/session files.
- `venv`, `node_modules`, Foundry `out/cache/broadcast/lib`, `__pycache__`.
- Logs, SQLite DBs, runtime handoff/register state, large archives, generated backups.
- OpenClaw personal memory/context files and unrelated workspace projects.

## Source paths inspected
- `/root/.openclaw/workspace/flash-loan-research`
- `/opt/flash-loan`
- `/root/.openclaw/workspace/BOB-FL-v2/config/flash-loan.service`

## Runtime posture
Live trading is disabled by default in `.env.example`:
- `REAL_TRANSACTIONS_ENABLED=false`
- `CONFIRM_LIVE_FLASHLOAN_EXECUTION=NO`

Only enable live execution after funding, RPC, contract addresses, gas cap, and simulation gates are confirmed.
