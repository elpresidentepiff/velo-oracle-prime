#!/usr/bin/env bash
# Windows Task Scheduler entrypoint for the 07:00 morning raceday run.
# Replaces the WSL crontab, which fired ZERO times on 2026-07-28/29 because
# WSL was not awake at 07:00 — cron never catches up a missed firing, while
# the registered task (VELO_Raceday_0700, StartWhenAvailable) runs as soon
# as the machine is next available, before racing starts.
set -u
cd /mnt/c/Users/puror/velo-oracle-prime || exit 1
DATE=$(date +%Y-%m-%d)
{
  echo ""
  echo "===== VELO_Raceday_0700 fired $(date -Is) for ${DATE} ====="
} >> data/reports/run_full_raceday_cron.log
PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py \
  --date "${DATE}" --execute >> data/reports/run_full_raceday_cron.log 2>&1
