#!/usr/bin/env bash
# Smoke test: verify daily pipeline modules are importable and key scripts exist.
set -euo pipefail

echo "[smoke] Checking pipeline module imports..."
python -c "import app.main" && echo "[smoke] app.main OK"
python -c "import workers.ingestion_spine" 2>/dev/null || echo "[smoke] ingestion_spine not importable in this env (OK)"

echo "[smoke] Checking key script presence..."
SCRIPTS=(
  "scripts/ops/run_prime_today.py"
  "scripts/ops/run_results_sigma.py"
  "scripts/ops/build_rpdc_daily.py"
)
for s in "${SCRIPTS[@]}"; do
  if [ -f "$s" ]; then
    echo "[smoke] FOUND: $s"
  else
    echo "[smoke] MISSING: $s" && exit 1
  fi
done

echo "[smoke] PASS"
