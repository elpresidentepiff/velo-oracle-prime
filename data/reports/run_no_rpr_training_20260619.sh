#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/puror/velo-oracle-prime
source venv/bin/activate
python -u scripts/ops/retrain_sqpe_no_rpr.py > data/reports/no_rpr_retrain_20260619_full.log 2>&1
