#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "Prefect Daily Pipeline Smoke Test"
echo "========================================"

# Force logging visibility
export PREFECT_LOGGING_LEVEL=INFO
export PREFECT_LOGGING_INTERNAL_LEVEL=INFO
export PYTHONUNBUFFERED=1

# Log file
LOG_FILE="/tmp/velo_prefect_run.log"
rm -f "$LOG_FILE"

echo "Running flow with as_of_date=2026-01-09..."

# Note: Using a fixed date (2026-01-09) for reproducibility.
# The smoke test validates logging structure, not data processing.
# Run the flow
python -c "from flows.daily_pipeline import daily_meeting_pipeline; daily_meeting_pipeline(as_of_date='2026-01-09')" 2>&1 | tee "$LOG_FILE"

echo ""
echo "Checking log output..."

# Verify critical log lines exist
if ! grep -q "BOOT flow start" "$LOG_FILE"; then
    echo "❌ FAIL: 'BOOT flow start' not found in logs"
    exit 1
fi

if ! grep -q "DONE" "$LOG_FILE"; then
    echo "❌ FAIL: 'DONE' not found in logs"
    exit 1
fi

echo "✅ PASS: All required log lines present"
echo ""
echo "Log file saved to: $LOG_FILE"
