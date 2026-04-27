# ETCSLV Framework Audit v1

Checkpoint:
- branch: `checkpoint/oasis-clean-spine-audit-v2-passed`
- commit: `0f44411fdb52a2e2e056020408baca51b891c893`

Accepted spine:
- `race_results = 3201`
- `runner_results = 31751`
- `historical_feature_store = 31692`
- `clean_historical_races_integrated_approx = 1913`
- `accepted_oasis_historical_events = 1671`
- `accepted_oasis_historical_hfs_rows = 18331`

Special warnings:
- `OASIS_BLOCK_025` is rejected and rolled back.
- Reason: `2025 macro-year mismatch`. Do not retry until `2025` macro support exists.
- [C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py](C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py) has unrelated unstaged work and is not part of the checkpoint.
- Recovery must start from [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json), not chat memory.

## A. Execution Loop Map
Current workflow:
1. Discover
2. Validate
3. Freeze artifacts
4. Approve
5. Bridge
6. Write manifest
7. Run manifest-scoped HFS reconstruction
8. Audit
9. Accept or reject
10. Roll back if rejected
11. Update state
12. Approve next mission

Manual steps:
- choose the next window or block
- approve discovery outputs before any bridge
- approve each bridge block before writes
- interpret pass/fail audits
- trigger rollback when a gate fails
- create savepoints and handoff artifacts

Automated steps:
- `mine_clean_course_zones.py` scans and freezes discovery artifacts
- `bridge_oasis_block.py` validates selection, writes bridge rows, writes a manifest, and calls HFS reconstruction
- `backfill_historical_feature_store.py` rebuilds HFS from manifest scope
- `normalize_historical_provenance.py` remediates metadata only
- audit scripts replay signal paths or macro paths without new bridge writes

Approval gates:
- discovery accepted before bridge
- bridge accepted before next mission
- global audit accepted before training discussion
- savepoint accepted before major macro/control-plane changes

Failure stops:
- parity failures
- duplicates
- missing vectors
- null signal fields
- macro-year mismatch
- doctrine/provenance incompleteness
- rollback incompleteness

Rollback paths:
- manifest-scoped rollback exists operationally and is proven by Block 025
- there is no dedicated rollback script yet

Resume points:
- [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json)
- window candidate/rejection/cursor files
- bridge manifests
- latest passed global audit
- checkpoint branch and commit

Known weak spots:
- no dedicated scripted global clean spine audit entrypoint
- no dedicated rollback CLI
- no bridge dry-run mode
- discovery does not codify `non_target_count` or `candidate_collision_count`
- final-window sizing still depends on operator-supplied `max-races`
- unrelated unstaged work is present in the repo

## B. Tool Registry
| Tool | Purpose | Inputs | Outputs | DB writes | Dry-run | Manifest | Rollback | Main risks |
|---|---|---|---|---|---|---|---|---|
| `mine_clean_course_zones.py` | Active OASIS discovery | `--batch-size --max-rows --start-id --reset-window` | candidate/rejection/cursor files, stdout audit | no | no | no | no | local artifacts can drift from cursor on interruption; missing codified `non_target_count` and `candidate_collision_count` |
| `bridge_oasis_block.py` | Active OASIS bridge + HFS handoff | `--max-races --candidate-file --manifest-file --exclude-manifest --exclude-race-ids ...` | `races`, `race_results`, `runner_results`, manifest, stdout audit | yes | no | yes | no | no native rollback; no dry-run; HFS runs in subprocess |
| `backfill_historical_feature_store.py` | Manifest-scoped HFS reconstruction | `--limit-races --batch-races --workers --manifest-file --dry-run --replace-existing` | `historical_feature_store`, backfill run rows, stdout log | yes | yes | yes | no | depends on live scoring stack; macro year clamp blocks honest 2025 support |
| `normalize_historical_provenance.py` | Metadata-only remediation | `--dry-run --apply` | `races` upserts, HFS upserts, stdout summary | yes | yes | no | no | broad scoped upserts; no rollback helper |
| `audit_hfs_signal_path.py` | Manifest-scoped signal trace | `--manifest-file --sample-races --sample-runners` | stdout trace | no | yes | yes | no | no structured artifact output |
| `audit_historical_macro_year.py` | Manifest-scoped macro-year audit | `--manifest-files --sample-size` | stdout macro audit | no | yes | yes | no | monkey-patching trace path; no structured artifact output |
| `backfill_horse_identity_registry.py` | Global identity registry population | `--limit-rows --resume-from --dry-run` | `racing_horses`, cursor file, stdout summary | yes | yes | no | no | writes global registry; no provenance/manifest scope |
| `reconcile_historical_archive.py` | Legacy archive bridge/discovery hybrid | implicit `limit_races offset max_scan dry_run` in code | `races`, `race_results`, `runner_results`, stdout | yes | yes | no | no | bare `race_id` logic; no manifests; current file appears incomplete |
| `integrity_hooks.py` | Lightweight HFS RPC heartbeat | function inputs only | IntegrityResult/logs | no | yes | no | no | RPC covers only a narrow subset of integrity checks |
| `discover_clean_archive_zones.py` | Legacy archive density scan | `--max-scan --offset` | stdout zone report | no | yes | no | no | not event-key contract aware; no frozen artifacts |
| `global_clean_spine_audit` | Whole-spine acceptance audit | accepted historical scope + doctrine expectations | audit JSON/MD artifacts | no | yes | no | no | no dedicated script exists yet |

## C. Context Manager Audit
Where context lives:
- [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json)
- [C:\Users\puror\velo-oracle-prime\data\velo_artifact_index.json](C:\Users\puror\velo-oracle-prime\data\velo_artifact_index.json)
- candidate/rejection/cursor files per window
- bridge manifests per block
- global audit artifacts
- handoff/runbook/recovery docs
- git checkpoint branch/commit

Canonical:
- mission phase: `velo_current_state.json`
- block scope: block manifest
- accepted row truth: Supabase tables
- training gate proof: latest passed global audit

What is duplicated:
- counts repeated in state file, docs, audits, and chat
- block status repeated in manifests, logs, artifact index, and docs

What can go stale:
- state JSON if not updated after accept/reject
- artifact index if new artifacts are not indexed
- cursor files after interrupted discovery runs
- docs and handoff files after roadmap changes
- chat summaries

What can be safely resumed:
- frozen discovery windows
- accepted blocks with manifests
- latest passed global audit
- checkpoint branch

Needs stronger handling:
- auto state updates
- canonical quarantined-ID registry
- canonical failed-block registry with rollback proof
- explicit dirty-worktree marker in state

## D. State Store Audit
Source of truth by object:
- accepted data rows: Supabase tables
- discovery outputs: window JSONL/JSON files
- bridge scope: manifest JSON
- audit proof: latest passed audit JSON/MD
- current phase: `velo_current_state.json`
- code/doc checkpoint: git branch + commit

Duplicate state risks:
- copied counts in multiple docs
- artifact index may look authoritative even though it is only an index

Stale state risks:
- dirty working tree can be mistaken for checkpointed work
- legacy scripts remain beside active OASIS scripts

Recommended canonical state model:
1. Supabase for accepted row truth
2. Window artifacts for discovery truth
3. Manifests for block scope truth
4. `velo_current_state.json` for mission truth
5. latest passed global audit for training-gate truth
6. checkpoint commit for code/doc truth

## E. Lifecycle Hook Audit
Existing hooks:
- pre-run discovery reset-window handling
- human approval gate between discovery and bridge
- manifest write before HFS trust
- post-run bridge/HFS audit
- manual manifest-scoped rollback protocol
- savepoint + handoff checkpoint

Missing hooks:
- dedicated bridge dry-run
- dedicated rollback CLI
- automatic state update after accept/reject
- automatic artifact-index refresh
- dedicated scripted global audit
- dirty-worktree preflight guard

Mandatory before training:
- reproducible global clean spine audit entrypoint
- rollback completeness tool or equivalent proof hook
- routine canonical state updates
- 2025 macro support, Block 025 retry, and Global Audit V3 under the current roadmap

Can wait:
- dashboards
- per-batch discovery checkpoints
- structured JSON output for every audit helper
- legacy tool retirement

## F. Verification Interface Audit
Current checks:
- accounting invariant
- duplicate clean event keys
- sampled winner parity in discovery
- duplicate `race_id`
- duplicate `event_key`
- duplicate `race_id + horse_id`
- missing/orphan HFS rows
- vector presence and dimension
- MPI null/min/max/variance
- chaos null/min/max/variance
- macro-year mismatch
- doctrine completeness
- provenance completeness
- `training_eligible` distribution
- rollback completeness by operator procedure
- secret scan before savepoint commit
- checkpoint branch/commit existence

Missing checks:
- codified `non_target_count`
- codified `candidate_collision_count`
- dedicated rollback completeness script
- automated state-vs-audit consistency check
- dirty-worktree preflight gate

Blocking checks:
- parity
- winner parity
- duplicates
- missing/orphan HFS rows
- missing vectors or wrong vector length
- MPI/chaos nulls
- variance collapse
- macro-year mismatch
- doctrine/provenance incompleteness
- `training_eligible` drift
- rollback incompleteness

Warning-only checks:
- yield collapse
- archive exhaustion
- unrelated unstaged work
- legacy tools still present

Recommended schema:
- hard block: data, signal, macro-year, doctrine, provenance, rollback failures
- approval required: discovery acceptance, bridge approval, global audit acceptance, savepoint acceptance
- warning: yield decline, archive exhaustion, dirty tree, legacy adjacency
- evidence only: sample rows, logs, artifact index

## G. Gaps Found
- no dedicated global audit script
- no dedicated rollback tool
- manual state/index updates
- missing codified `non_target_count` and `candidate_collision_count`
- legacy tools beside active tools
- no bridge dry-run
- dirty working tree outside checkpoint

## H. Operational Risks
- future agents may confuse dirty local files with checkpoint state
- future agents may accidentally use legacy tools
- failed bridges still require operator rollback knowledge
- global audit repeatability depends on procedure plus artifacts, not a single entrypoint
- `2025` rows remain blocked until macro support exists

## I. Recommended Fixes
1. Create `scripts/global_clean_spine_audit.py`.
2. Create `scripts/rollback_oasis_block.py`.
3. Create `scripts/update_velo_state.py`.
4. Add codified `non_target_count` and `candidate_collision_count` to `mine_clean_course_zones.py`.
5. Add `--dry-run` to `bridge_oasis_block.py`.
6. Add dirty-worktree preflight guarding.
7. Clearly isolate legacy tools from the active OASIS path.

## J. Must-Fix Before Training
1. Keep training paused until global audit is reproducible by script or equivalent deterministic entrypoint.
2. Keep training paused until rollback completeness is tool-supported or equally provable every time.
3. Keep training paused until `2025` macro support exists, `OASIS_BLOCK_025` is retried, and `Global Clean Spine Audit V3` passes.
4. Keep training paused until canonical state updates are routine and not optional.

## K. Can Wait Until After First Dry-Run Training
- ambiguity resolver for rejected races
- per-batch discovery checkpointing
- structured JSON output for every audit helper
- legacy tool retirement/relocation
- richer dashboards and operator UX polish

## L. Proposed Canonical Agent Startup Checklist
1. Check git branch and git status.
2. Read [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json).
3. Read [C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_HANDOFF.md](C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_HANDOFF.md), [C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md](C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md), [C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_PROCESS_LIST.md](C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_PROCESS_LIST.md), and [C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md](C:\Users\puror\velo-oracle-prime\docs\VELO_RECOVERY_PROTOCOL.md).
4. Read the latest passed global audit artifact.
5. Confirm the latest failed block is fully rolled back.
6. Confirm accepted DB counts match canonical state.
7. Confirm the next mission is explicitly approved.
8. Only then continue.
