# VÉLØ SENTIENT LOOP REPAIR AUDIT V1

Generated: 2026-05-08T01:27:05.141869Z
Mode: **FULL_RUN**

## A — Broken Files and Functions

### `eod_shadow_learning_bridge.py::_prepare_engine_inputs()`

- mpi = vp * 100  ← WRONG. Real formula: (vp*0.6 + mds*0.4)*100
- chaos_bloom = top_pick.get('chaos_bloom') * 100  ← ALWAYS NULL (field not in prediction snapshot)
- sp = 5.0  ← HARDCODED. Real SP available in results_YYYY_MM_DD.json runners[0].sp_dec

### `eod_shadow_learning_bridge.py::event dict`

- learning_allowed hardcoded False  ← BLOCKS all adapter replay

### `eod_shadow_learning_bridge.py::_load_processed_races()`

- Tracks race_id only (global). Same event can never feed a new shadow state.

### `playbook_g_shadow_adapter.py::_prepare_engine_inputs()`

- Same wrong MPI formula: mpi = vp * 100

## B — Why MPI and chaos_bloom Were Missing

**MPI:** VeloPrimePrediction._compute_hfs_signals() computes mpi internally but to_dict() does NOT include mpi in the output dict. So mpi is NOT stored in velo_prime_verdicts_YYYY_MM_DD.json. EOD bridge used velo_prime_prob * 100 as a proxy — this is wrong. Fix: compute from available fields: (vp*0.6 + mds*0.4)*100. Both velo_prime_prob and market_deception_score ARE in the snapshot.

**chaos_bloom:** chaos_bloom is computed from macro_context object which is not serialised to the prediction file. However macro_chaos_mode (bool) and favourite_trap_risk (str) ARE serialised. Fix: reconstruct chaos_bloom from macro_chaos_mode + favourite_trap_risk. This matches the ensemble formula exactly.

## C — Event Payload Before vs After

| Field | Before (broken) | After (repaired) |
|---|---|---|
| `mpi` | velo_prime_prob * 100  (proxy, not real MPI) | (velo_prime_prob*0.6 + market_deception_score*0.4)*100 |
| `chaos_bloom` | None  (field not in prediction snapshot) | derived from macro_chaos_mode + favourite_trap_risk → [30, 70, 100]*100 range |
| `sp` | 5.0  (hardcoded) | results_file runners[position=1].sp_dec  (real SP) |
| `learning_allowed` | False  (hardcoded) | True when result verified + race_id present + not consumed |
| `consumption_key` | race_id  (global — prevents cross-state replay) | race_id:date|target_state_path  (per target state) |

## D — Duplicate Guard Fix

- **Old:** Tracked race_id in JSONL. Same race_id could never be fed to a new shadow state.
- **New:** Tracks consumption_key = f'{idempotency_key}|{target_state_path}'. Same event CAN feed a different shadow state file. Cannot double-feed the same state (idempotent per target).
- **Ledger:** `sentient_loop_repair_consumed_events.jsonl`

## E — 5-Event Shadow Proof

| Race | Date | Outcome | VP | MPI | chaos | SP | Obs Called | Obs OK | Δ races |
|---|---|---|---|---|---|---|---|---|---|
| rac_11874382 | 2026-03-17 | LOSS | 0.1451 | 10.59 | 30.0 | 2.5 | True | True | +1 |
| rac_11874369 | 2026-03-17 | LOSS | 0.1258 | 7.62 | 30.0 | 3.25 | True | True | +1 |
| rac_11874421 | 2026-03-17 | LOSS | 0.1998 | 13.0 | 30.0 | 21.0 | True | True | +1 |
| rac_11874408 | 2026-03-17 | LOSS | 0.3557 | 24.01 | 30.0 | 4.33 | True | True | +1 |
| rac_11874447 | 2026-03-17 | LOSS | 0.2212 | 14.66 | 30.0 | 13.0 | True | True | +1 |

## F — Full Run Summary

| Metric | Value |
|---|---|
| Total events processed | 925 |
| observe_race_outcome called | 925 |
| observe_race_outcome success | 924 |
| Skipped (duplicate) | 5 |
| MPI null events | 0 |
| chaos_bloom null events | 1 |

## G — observe_race_outcome Fired?

**Fired: True** | Success count: 924

## H — Shadow State Mutated?

**Mutated: True**
- races_observed before: 5
- races_observed after: 930
- delta: +925
- aggression after: 0.3

## I — Live State Untouched?

**Untouched: True**
- Hash before: `1016d89dceb28da5d5cad5c33850d6fe…`
- Hash after: `1016d89dceb28da5d5cad5c33850d6fe…`

## J — HFS_TRAINING_SAFE Still Blocks Live?

**Yes — live promotion still blocked.** This script does NOT modify HFS_TRAINING_SAFE. Shadow learning proceeds without it. Live promotion still requires HFS_TRAINING_SAFE=True AND operator sign-off.

## K — Remaining Blockers

- CHAOS_NULL: 1 events had no chaos_bloom (macro context not available)
- HFS_TRAINING_SAFE=False still blocks LIVE promotion — shadow accumulation only
- Training artifact (4,643 races) not promoted — requires operator decision
- 7–14 day shadow accumulation required before any promotion discussion

## Hard Rules

- No live sentient_state.json modified.
- No Supabase writes.
- No scoring changes.
- No model changes.
- No router/staking/Telegram.
- No fabricated MPI or chaos_bloom.
- Shadow accumulation only. Live promotion requires HFS_TRAINING_SAFE=True + operator sign-off.