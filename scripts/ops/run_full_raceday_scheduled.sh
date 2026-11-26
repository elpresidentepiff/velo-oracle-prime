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

# A FormFav coverage failure is a hard gate.  Never silently convert it into a
# partial-enrichment scoring run: an operator must review the dated report and
# invoke the explicit, auditable override only where policy allows it.
if [ "${RC}" -ne 0 ]; then
  {
    echo ""
    echo "===== RACEDAY FAILED $(date -Is): exit=${RC}; no partial-enrichment retry performed ====="
  } >> "${LOG}"
  rm -f "${TMPLOG}"
  exit "${RC}"
fi
rm -f "${TMPLOG}"
exit 0
