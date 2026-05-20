# Playbook G Shadow Adapter Safety V1

## Overview
The Playbook G Shadow Adapter is a safety-first wrapper designed to enable shadow learning replay while strictly isolating the live production environment. It acts as the final gatekeeper for VÉLØ's sentient intelligence layer during its shadow-only evolutionary phase.

## Safety Architecture
1.  **Cloud Isolation**: Patches the `SentientLoopbackEngine` with a `disable_cloud_backup` flag to prevent unauthorized writes to Supabase.
2.  **File Isolation**: Hardcoded to only accept state files named `sentient_state_shadow.json`, preventing accidental mutation of `sentient_state.json`.
3.  **Gatekeeper**: Strictly enforces the `learning_allowed` flag on every incoming outcome event. If `HFS_TRAINING_SAFE` is false, no learning occurs.
4.  **Idempotency**: Manages a per-session `idempotency_key` registry to prevent double-counting of race outcomes in the sentient state.
5.  **Audit Trail**: Produces a detailed `playbook_g_shadow_adapter_audit_v1.json` for every run, logging all skipped and replayed events.

## Execution Flow
1.  Initialize `SentientLoopbackEngine` with `disable_cloud_backup=True`.
2.  Load `playbook_g_outcome_events_shadow.jsonl`.
3.  Filter events:
    *   Skip if `idempotency_key` already processed.
    *   Skip if `learning_allowed` is `False`.
4.  Reconstruct `race_data`, `prediction`, and `actual_result` snapshots.
5.  Invoke `engine.observe_race_outcome()`.
6.  Generate Audit Report.

## Audit Contract
The adapter produces a verdict:
*   `PASS_GATED`: All events were successfully read, but all learning was correctly suppressed due to the safety gate.
*   `PASS_EVOLVED`: Authorized learning events were replayed into the shadow state.
*   `FAIL`: A critical failure occurred during processing.

## Usage
```bash
PYTHONPATH=. python3 scripts/playbook_g_shadow_adapter.py \
    --events data/playbook_g_outcome_events_shadow.jsonl \
    --state data/sentient_state_shadow.json \
    --audit data/playbook_g_shadow_adapter_audit_v1.json
```
