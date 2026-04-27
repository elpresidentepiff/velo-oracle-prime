# VELO OASIS Runbook

## Canonical Flow
1. Discovery window
2. Freeze candidate and rejection files
3. Verify accounting invariant
4. Human approval before bridge
5. Bridge block
6. Write manifest
7. Run manifest-scoped HFS reconstruction
8. Audit
9. Accept or reject
10. Roll back by manifest scope only if rejected
11. Update [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json)

## Discovery Phase
- Run `mine_clean_course_zones.py` for the approved window only.
- Freeze outputs into:
  - candidate JSONL
  - rejection JSONL
  - cursor JSON
  - discovery run log
- Verify:
  - accounting invariant
  - no duplicate clean `event_key`
  - no duplicate bare `race_id`
  - sampled winner parity
  - `non_target_count = 0`
  - `candidate_collision_count = 0`

## Bridge Phase
- Use only the approved candidate file.
- Exclude prior manifests and already-existing rows.
- Maintain:
  - `event_identity_contract = race_id_course_race_date`
  - `source = historical_raceform`
  - `bridge_version = RACEFORM_BRIDGE_V1`
  - `discovery_version = CLEAN_INDEX_V1`
  - `signal_contract_version = HISTORICAL_SIGNAL_PROXY_V1`
  - `mpi_source = archive_proxy_market_rank_v1`
  - `chaos_bloom_source = archive_proxy_market_entropy_going_v1`
  - `data_owner_confirmed = true`
  - `training_eligible = pending_global_training_gate`

## Manifest Requirements
- Every block must write a manifest before HFS is trusted.
- Manifest must define the exact block scope:
  - source candidate file
  - race events
  - event keys
  - runner count
  - jurisdiction breakdown
  - discovery window
  - doctrine/provenance tags
- Rejected blocks must still preserve the manifest for rollback and audit.

## HFS Phase
- Run HFS only against the accepted manifest scope.
- Do not run broad HFS backfills during a block flow.
- Verify doctrine and provenance on exact scoped HFS rows.

## Pass Gates
- `winner parity = 100%`
- `duplicates = 0`
- `event_key duplicates = 0`
- `missing vectors = 0`
- `MPI nulls = 0`
- `chaos nulls = 0`
- `macro-year mismatch = 0`
- `vector length = 37`
- `data_owner_confirmed = true`
- `training_eligible = pending_global_training_gate`

## Reject Gates
- Any macro-year mismatch
- Any duplicate event keys
- Any vector nulls
- Any incomplete doctrine or provenance required for the active doctrine version
- Any row count mismatch between bridge and HFS scope

## Rollback Rule
- Roll back by manifest scope only.
- Never use broad deletes.
- Never assume a failed run is clean until stored-state verification confirms zero remaining scoped rows.

## State Update Rule
- After every accepted or rejected block, update:
  - canonical state file
  - artifact index
  - relevant audit documents
- Durable state is part of the control plane, not optional documentation.
