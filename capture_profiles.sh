#!/usr/bin/env bash
set -e
cd /mnt/c/Users/puror/velo-oracle-prime
source venv/bin/activate

echo "=== May 28 (146 horses — resuming from scratch) ==="
PYTHONPATH=. python scripts/ops/racing_post_account_collector.py capture --date 2026-05-28 --url-list data/racing_post_url_lists/rp_profiles_2026-05-28_form.txt --headed --execute

echo "=== May 29 (106 horses) ==="
PYTHONPATH=. python scripts/ops/racing_post_account_collector.py capture --date 2026-05-29 --url-list data/racing_post_url_lists/rp_profiles_2026-05-29_form.txt --headed --execute

echo "=== Capture complete for May 28 + 29 ==="
