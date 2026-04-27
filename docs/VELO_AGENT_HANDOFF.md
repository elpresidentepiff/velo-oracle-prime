# VELO Agent Handoff

## 1. Current Mission
Preserve the accepted historical OASIS spine after `global_clean_spine_audit_v2` passed, then hand off into `ETCSLV Framework Audit`. No training, no Playbook E, no bridging, and no HFS reconstruction are approved at this stage.

## 2. What Has Been Completed
- Historical archive discovery completed through `Window 014`; archive exhausted.
- Accepted OASIS bridge blocks completed through `OASIS_BLOCK_024`.
- `OASIS_BLOCK_025` attempted, failed the macro-year gate, and was fully rolled back by manifest scope.
- Historical Provenance Normalization completed.
- `global_clean_spine_audit_v2` passed.

## 3. What Failed And Why
- `OASIS_BLOCK_025` is rejected.
- Failure reason: `2025` race events were bridge-clean but not signal-clean because the macro context layer currently supports `2012-2024` only.
- Fallback behavior would have masked `2025 -> 2024`, so the gate stopped the block and the run was rolled back.

## 4. Current Accepted Database Counts
- `race_results: 3201`
- `runner_results: 31751`
- `historical_feature_store: 31692`
- `clean historical races integrated: ~1913`
- Accepted OASIS historical audit scope:
  - `race events: 1671`
  - `runner rows: 18331`
  - `HFS rows: 18331`

## 5. Accepted Doctrine
- `source = historical_raceform`
- `bridge_version = RACEFORM_BRIDGE_V1`
- `discovery_version = CLEAN_INDEX_V1`
- `signal_contract_version = HISTORICAL_SIGNAL_PROXY_V1`
- `mpi_source = archive_proxy_market_rank_v1`
- `chaos_bloom_source = archive_proxy_market_entropy_going_v1`
- `event_identity_contract = race_id_course_race_date`
- `data_owner_confirmed = true`
- `training_eligible = pending_global_training_gate`

## 6. Required Gates Before Training
- `race / runner / HFS parity` must hold
- `winner parity = 100%`
- duplicates must remain `0`
- `missing vectors = 0`
- vector length must remain `37`
- `MPI nulls = 0`
- `chaos_bloom nulls = 0`
- `macro-year mismatch = 0`
- doctrine tags complete
- provenance tags complete
- `training_eligible = pending_global_training_gate` for all accepted scoped rows
- global audit must pass after any future remediation

## 7. Exact Next Command Sequence
1. Read [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json).
2. Read [C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.json](C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.json) and [C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.md](C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.md).
3. Read [C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md](C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md) and [C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md](C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md).
4. Run `ETCSLV Framework Audit`.
5. Only after ETCSLV audit completes, build `2025` macro context support.
6. Retry `OASIS_BLOCK_025`.
7. Run `Global Clean Spine Audit V3`.
8. Decide whether a Playbook G dry-run training gate is permissible.

## 8. Files And Artifacts To Inspect First
- [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json)
- [C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.json](C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.json)
- [C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.md](C:\Users\puror\velo-oracle-prime\data\global_clean_spine_audit_v2.md)
- [C:\Users\puror\velo-oracle-prime\data\bridge_manifest_oasis_block_024.json](C:\Users\puror\velo-oracle-prime\data\bridge_manifest_oasis_block_024.json)
- [C:\Users\puror\velo-oracle-prime\data\bridge_manifest_oasis_block_025.json](C:\Users\puror\velo-oracle-prime\data\bridge_manifest_oasis_block_025.json)
- [C:\Users\puror\velo-oracle-prime\data\oasis_block_025_run.log](C:\Users\puror\velo-oracle-prime\data\oasis_block_025_run.log)
- [C:\Users\puror\velo-oracle-prime\data\oasis_block_025_err.log](C:\Users\puror\velo-oracle-prime\data\oasis_block_025_err.log)
- [C:\Users\puror\velo-oracle-prime\data\velo_artifact_index.json](C:\Users\puror\velo-oracle-prime\data\velo_artifact_index.json)

## 9. Rules Agents Must Never Violate
- Do not train.
- Do not run Playbook E.
- Do not bridge new rows before explicit approval.
- Do not relax filters.
- Do not use `2025` rows until macro support is fixed.
- Do not resume from memory alone.
- Do not rollback outside manifest scope.
- Do not treat console output as sufficient proof when stored-state verification is available.

## 10. Recovery Procedure If Interrupted
Follow [C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md](C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md) exactly. The short version is: inspect git state, inspect canonical state, inspect latest manifest, verify DB counts, verify no partial rows remain, then resume only from durable artifacts.
