#!/usr/bin/env bash
# Windows Task Scheduler entrypoint for the 07:00 morning raceday run.
# Replaces the WSL crontab, which fired ZERO times on 2026-07-28/29 because
# WSL was not awake at 07:00 — cron never catches up a missed firing, while
# the registered task (VELO_Raceday_0700, StartWhenAvailable) runs as soon
# as the machine is next available, before racing starts.
set -u
cd /mnt/c/Users/puror/velo-oracle-prime || exit 1
DATE=$(date +%Y-%m-%d)
LOG=data/reports/run_full_raceday_cron.log
{
  echo ""
  echo "===== VELO_Raceday_0700 fired $(date -Is) for ${DATE} ====="
} >> "${LOG}"

TMPLOG=$(mktemp)
PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py \
  --date "${DATE}" --execute >> "${TMPLOG}" 2>&1
RC=$?
cat "${TMPLOG}" >> "${LOG}"

# If the only failure was FormFav coverage gate, retry automatically with partial enrichment.
if [ "${RC}" -ne 0 ] && grep -q "FAIL_CLOSED" "${TMPLOG}"; then
  {
    echo ""
    echo "===== AUTO-RETRY $(date -Is): FormFav coverage gate fired — retrying with --allow-partial-formfav ====="
  } >> "${LOG}"
  PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py \
    --date "${DATE}" --execute --skip-capture --allow-partial-formfav >> "${LOG}" 2>&1
fi
rm -f "${TMPLOG}"
