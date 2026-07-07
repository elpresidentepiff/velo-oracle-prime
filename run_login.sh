#!/bin/bash
cd /mnt/c/Users/puror/velo-oracle-prime
source venv/bin/activate
python3 scripts/ops/racing_post_account_collector.py init-login --execute --profile-dir data/browser_profiles/racing_post_firefox
