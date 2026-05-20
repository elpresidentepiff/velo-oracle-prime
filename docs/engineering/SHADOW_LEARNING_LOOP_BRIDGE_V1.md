# VÉLØ Shadow Learning Loop Bridge V1

## Overview
The Shadow Learning Loop Bridge provides a safe, idempotent mechanism for reconciling confirmed race outcomes with VÉLØ's sentient intelligence layer without polluting the live production state. It enables "shadow learning" where the engine's evolution can be audited and verified before being promoted to live operation.

## Architecture
The bridge operates as an End-Of-Day (EOD) process:
1. **Ingest**: Loads local prediction snapshots (`velo_prime_verdicts_{date}.json`) and confirmed result snapshots (`results_{date}.json`).
2. **Reconcile**: Matches predictions to results via `race_id` and `horse_id`.
3. **Classify**: Categorizes outcomes and losses using a standardized taxonomy.
4. **Emit**: Generates an idempotent outcome event ledger.
5. **Stage**: Updates the shadow sentient state (`sentient_state_shadow.json`).

## Loss Taxonomy
- `WRONG_HORSE`: Prediction failed but data was clean.
- `MARKET_LIED`: Favourite won while model was diverted by decoy signals.
- `CHAOS_RACE`: Race exceeded the `chaos_bloom` stability threshold.
- `SIGNAL_GAP`: High confidence prediction failed (Alpha/Strike).
- `DATA_ERROR`: Missing or malformed prediction/result records.
- `CALIBRATION_ERROR`: Low confidence prediction failed (expected but tracked).
- `NONE`: Prediction was correct (WIN).

## Safety Gates
- **HFS Isolation**: If `HFS_TRAINING_SAFE` is false, `learning_allowed` is forced to `false` in all emitted events.
- **State Protection**: The bridge is hardcoded to never modify `sentient_state.json`.
- **Cloud Isolation**: No Supabase writes are performed.
- **Idempotency**: All events are keyed by `race_id:event_date` to prevent double-learning.

## File Manifest
- `scripts/eod_shadow_learning_bridge.py`: Core bridge logic.
- `data/playbook_g_outcome_events_shadow.jsonl`: Verified outcome event stream.
- `data/eod_loss_ledger_shadow.jsonl`: Classification ledger for forensic audit.
- `data/sentient_state_shadow.json`: The evolved shadow intelligence state.
- `data/eod_flags_shadow_{date}.json`: Execution audit summary.

## Usage
```bash
PYTHONPATH=. python3 scripts/eod_shadow_learning_bridge.py --date YYYY-MM-DD
```
