# Nightly EOD Learning Automation V1

## Overview
The Nightly EOD Learning Runner is a hardened, recurring process that enables VÉLØ to evolve its shadow intelligence layer every night following the completion of daily race results. It leverages real prediction and result data to reconcile outcomes and update the shadow sentient state.

## Operational Flow
1.  **Discovery**: Scans `data/` for `velo_prime_verdicts_{date}.json` and `results_{date}.json`.
2.  **Reconciliation**: Matches races and classifies outcomes (WIN/LOSS/VOID).
3.  **Gating**: Creates **OUTCOME-ONLY** events, strictly excluding unsafe HFS doctrine features.
4.  **Imprinting**: Replays events into `sentient_state_shadow.json` via the `PlaybookGShadowAdapter`.
5.  **Validation**: Executes a second replay pass to verify absolute idempotency (zero state mutation).
6.  **Reporting**: Generates a nightly status JSON, a failure ledger, and a council audit report.

## Safety Constraints
- **Shadow-Only**: Hardcoded to never touch `sentient_state.json`.
- **Cloud-Isolated**: Supabase backups are disabled during the run.
- **Data-Gated**: If the `DATA_ERROR` rate (unmatched predictions) exceeds the threshold (default 10%), the run fails.
- **HFS-Blocked**: Explicitly blocks any event containing `strictly_ordered_vector` to prevent unsafe feature contamination.

## Reporting Artifacts
- `data/nightly_eod_learning_status_{date}.json`: Comprehensive run metrics.
- `data/nightly_eod_learning_failures_{date}.json`: Grouped failure forensics.
- `data/nightly_eod_learning_council_audit_{date}.json`: Verification summary for the LLM Council.

## Execution
```bash
PYTHONPATH=. python3 scripts/nightly_eod_learning_runner.py --date YYYY-MM-DD
```
