#!/bin/bash
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1

# Activate the project venv
source venv/bin/activate
export PYTHONPATH=.

echo "=== Step 0: Install bs4 if missing ==="
pip install beautifulsoup4 --quiet

echo "=== Step 1: Re-login to Racing Post (browser will open) ==="
python scripts/ops/racing_post_account_collector.py init-login --profile-dir data/browser_profiles/racing_post_account --execute

echo "=== Step 2: Capture results pages ==="
python scripts/ops/racing_post_account_collector.py capture --url-list data/racing_post_url_lists/rp_results_2026-06-04.txt --date rp-results-2026-06-04-final --execute

echo "=== Step 3: Parse results ==="
python scripts/ops/parse_rp_results_capture.py --date 2026-06-04 --capture-date rp-results-2026-06-04-final --execute

echo "=== Step 4: Run sigma ==="
python scripts/ops/run_results_sigma.py --date 2026-06-04 --source cache

echo "=== SIGMA COMPLETE ==="
