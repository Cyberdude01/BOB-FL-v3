#!/usr/bin/env bash
set -euo pipefail
DRY_RUN=1
if [[ "${1:-}" == "--apply" ]]; then DRY_RUN=0; fi
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_SRC="$PROJECT_ROOT/cron/discovered-cron-jobs.txt"
SANITIZED="/tmp/bob-fl-v3-cron.sanitized"
if [[ ! -f "$CRON_SRC" ]]; then echo "No cron template found: $CRON_SRC"; exit 0; fi
# Keep comments and safe command lines only; remove secret-like inline assignments.
sed -E \
  -e 's/(PRIVATE_KEY|SECRET|TOKEN|API_KEY|PASSWORD|MNEMONIC|SEED_PHRASE)=[^[:space:]]+/\1=REDACTED/gI' \
  -e 's@/root/.openclaw/workspace/flash-loan-research@/opt/flash-loan@g' \
  "$CRON_SRC" > "$SANITIZED"
echo "Sanitized cron to install:"; cat "$SANITIZED"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run only. Re-run with: sudo ./restore/restore_cron.sh --apply"
else
  crontab "$SANITIZED"
  echo "Cron installed for current user. Review with: crontab -l"
fi
