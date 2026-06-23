# BOB-FL-v3 — Sanitized VM Restore Backup

Safe backup of the flash-loan project from the VM. This repo is designed to clone onto a new VM and rebuild the same project structure/dependencies without committing secrets or generated junk.

## Quick restore on a brand-new Debian/Ubuntu VM

```bash
git clone https://github.com/Cyberdude01/BOB-FL-v3.git
cd BOB-FL-v3
sudo ./install_dependencies.sh
sudo nano /opt/flash-loan/.env
sudo ./restore/restore_cron.sh --dry-run
sudo ./restore/restore_systemd.sh --dry-run
sudo ./healthcheck.sh
```

After reviewing cron/systemd templates:

```bash
sudo ./restore/restore_cron.sh --apply      # optional
sudo ./restore/restore_systemd.sh --apply   # optional, installs only; does not enable/start
```

## Required local secrets/config on new VM

Fill `/opt/flash-loan/.env` from `.env.example`. Do **not** commit it.
Common required values:
- `PRIVATE_KEY` / wallet signing config
- `WALLET_ADDRESS`
- `ARBITRUM_RPC_URL`
- `BASE_RPC_URL`
- optional `ETHEREUM_RPC_URL`, `OPTIMISM_RPC_URL`
- `MAX_GAS_COST_USD=2`
- `REAL_TRANSACTIONS_ENABLED=false` until ready
- `CONFIRM_LIVE_FLASHLOAN_EXECUTION=NO` until explicitly approved

## Manual start commands

Dry/safe scanner examples:

```bash
cd /opt/flash-loan
source venv/bin/activate
python scripts/live_flashloan_scanner.py --network base
python scripts/live_flashloan_scanner.py --network arbitrum
python scripts/comprehensive_flash_loan_scanner.py --network base
```

Live execution should only be started when the strict gates are intentionally enabled:

```bash
# Only after .env is filled and reviewed
REAL_TRANSACTIONS_ENABLED=true CONFIRM_LIVE_FLASHLOAN_EXECUTION=YES \
  /opt/flash-loan/venv/bin/python /opt/flash-loan/scripts/optimized_flash_loan_campaign.py --execute
```

## Safety notes

- No service is enabled or started automatically by restore scripts.
- Supervisor template has `autostart=false`.
- Runtime DBs/logs/opportunity registers are excluded; the new VM starts clean.
- Run `./scripts/secret_scan.sh .` before every commit.
