**ETCSLV Project Audit V1**

Project-wide architecture audit only. No bridge, no HFS reconstruction, no training, no Playbook E execution, no macro changes.

**Checkpoint**
- Branch: `checkpoint/oasis-clean-spine-audit-v2-passed`
- OASIS ETCSLV checkpoint commit: `beba855`
- Clean spine savepoint commit: `0f44411fdb52a2e2e056020408baca51b891c893`

**Current Accepted Spine**
- `race_results = 3201`
- `runner_results = 31751`
- `historical_feature_store = 31692`
- `clean_historical_races_integrated_approx = 1913`
- `accepted_oasis_historical_events = 1671`
- `accepted_oasis_historical_hfs_rows = 18331`

**Hard Warnings**
- `OASIS_BLOCK_025` is rejected and rolled back.
- Reason: `2025 macro-year mismatch`.
- Do not retry `OASIS_BLOCK_025` until `2025` macro context support exists.
- [C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py](C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py) has unrelated unstaged work and is not checkpointed.
- Recovery must start from [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json), not chat memory.

**Inventory Summary**
- Execution loops mapped: `14`
- Total tools classified: `196`
- Active tools: `60`
- Legacy/dead tools: `121`
- Unknown/quarantine tools: `15`
- State stores identified: `23`
- Lifecycle operations audited: `16`
- Verification checks mapped: `24`

**A. Execution Loop Map**

| Loop | Entrypoint | Maturity | Risk | Notes |
| --- | --- | --- | --- | --- |
| Historical discovery | `scripts/mine_clean_course_zones.py` | Semi-automated | Medium | Strong accounting invariant; missing first-class `non_target_count` and `candidate_collision_count` outputs |
| Historical bridge | `scripts/bridge_oasis_block.py` | Semi-automated | Medium | Good manifest discipline; no dry-run or reusable rollback tool |
| Historical HFS reconstruction | `scripts/backfill_historical_feature_store.py` | Semi-automated | Medium | Manifest scope exists; macro layer is the limiting control |
| Global clean spine audit | No dedicated script | Manual | High | Current biggest control-plane gap |
| Live race ingestion | `scripts/run_prime_today.py` | Automated | High | Strong runtime chain, weak rollback and artifact freeze |
| Live results reconciliation | `scripts/run_results_sigma.py` | Automated | High | Writes learning side effects together with reconciliation |
| Racecard-to-result | `run_prime_today` -> `run_results_sigma` | Semi-automated | High | Cross-script lifecycle, no unified frozen artifact |
| VELO scoring | `app/services/velo_prime_service.py` | Automated | Medium | Canonical score path, but current file has unrelated unstaged work |
| Model load/score | `app/services/model_manager.py` | Automated | Medium | Clear 37-feature contract, but mixed champion/stub model surface |
| Macro context | `src/intelligence/macro_regime/bha_macro_context.py` | Semi-automated | High | Current support ends at 2024 |
| Training prep | `scripts/train_sqpe_v17.py`, `scripts/train_specialist_models.py`, `src/training/pipeline.py` | Manual | High | Multiple training stacks, no unified gate |
| Playbook execution | `app/playbooks/playbook_orchestrator.py` | Semi-automated | High | Code exists, operational status remains paused |
| Rollback/recovery | Recovery docs + manual manifest queries | Manual | High | Works, but not reusable or scripted |
| Agent handoff | `data/velo_current_state.json` + docs | Semi-automated | Medium | Good now, but refresh remains manual |

Manual steps:
- Approve discovery windows before bridge.
- Approve bridge blocks before execution.
- Accept or reject blocks after audit.
- Perform rollback manually by manifest scope.
- Refresh state file, artifact index, and handoff docs.

Automated steps:
- Discovery scan.
- Bridge insert logic.
- HFS reconstruction.
- Live score and sigma scripts.
- Model loading.
- Macro context lookup.

Failure stops:
- Accounting invariant failure.
- Duplicate `event_key`.
- Winner parity failure.
- Macro-year mismatch.
- Missing vectors or null signal fields.
- Preflight failure in live loops.

Rollback paths:
- Historical: manifest-scoped manual rollback only.
- Live: date/run-id manual cleanup only.

Resume points:
- Frozen candidate/rejection files.
- Bridge manifests.
- `data/velo_current_state.json`.
- Latest audit artifacts.
- `pipeline_runs` for live loops.

Known weak spots:
- No dedicated global audit script.
- No dedicated rollback tool.
- Live loops lack OASIS-style freeze artifacts.
- Training control plane is split.

**B. Tool Registry Table**

Active OASIS tools:
- `scripts/mine_clean_course_zones.py`: historical discovery; reads `raceform`, writes frozen candidate/rejection/cursor files; keep/harden.
- `scripts/bridge_oasis_block.py`: historical manifest bridge; writes `races`, `race_results`, `runner_results`; harden.
- `scripts/backfill_historical_feature_store.py`: manifest-scoped HFS reconstructor; writes `historical_feature_store`; harden.
- `scripts/normalize_historical_provenance.py`: metadata-only remediation; dry-run supported; keep.
- `scripts/audit_hfs_signal_path.py`: manifest forensic audit; stdout-only; harden.
- `scripts/audit_historical_macro_year.py`: manifest macro audit; stdout-only; keep.
- `scripts/integrity_hooks.py`: thin RPC integrity wrapper; harden.
- `scripts/backfill_horse_identity_registry.py`: identity registry backfill; global mutation; harden.
- `scripts/discover_clean_archive_zones.py`: exploratory archive density scan; quarantine from governed flow.

Active live/ops scripts:
- `scripts/run_prime_today.py`: canonical live scoring loop; harden.
- `scripts/run_results_sigma.py`: canonical live reconciliation/sigma loop; harden.
- `scripts/ingest_racecard_pdfs.py`: operational PDF ingestion helper; keep.
- `scripts/preflight_10am_check.py`: readiness gate; keep.
- `scripts/production_checks.py`: operational checks; harden into mandatory preflight family.
- `scripts/notify_governed_results.py`: messaging helper; keep.
- `scripts/generate_daily_report.py`: report writer; keep.
- `scripts/generate_verdict_report.py`: report writer; keep.
- `scripts/run_live_analysis.py`: ad hoc analysis path; harden or constrain.
- `scripts/run_todays_races.py`: overlapping live wrapper; quarantine until ownership is clarified.
- `scripts/velo_morning_cockpit.py`: operator cockpit; keep.
- `scripts/velo_ops_check.py`: ops check; harden into standard lifecycle.
- `scripts/train_specialist_models.py`: training path exists but remains gated; quarantine from runtime.

Active app/services and app-level control plane:
- `app/main.py`: primary FastAPI app and trigger surface; harden.
- `app/api/router.py`: route aggregator; keep.
- `app/api/v1/predict.py`: prediction API; harden because auth/examples and mode spread need cleanup.
- `app/api/v1/intel.py`, `app/api/v1/models.py`, `app/api/v1/system.py`: active API surfaces; harden.
- `app/services/model_manager.py`: canonical live model loader; keep.
- `app/services/velo_prime_service.py`: canonical scoring service; keep, but note current unstaged unrelated edits.
- `app/services/model_registry.py`, `predictor.py`, `feature_engineering.py`, `validation.py`, `security_validator.py`, `v17_feature_extractor.py`: active service modules; harden around ownership and consistency.
- `app/playbooks/playbook_orchestrator.py`, `playbook_e_attack_doctrine.py`, `playbook_f_execution_sequencer.py`, `playbook_g_sentient_loopback.py`: active code, paused operationally; harden/quarantine by gate.
- `app/pipeline/orchestrator.py`, `predictor.py`, `ingestion.py`, `value_betting.py`: still present, but not canonical to current OASIS/live control plane; quarantine or clarify.

Active `src/` tools:
- `src/service/api.py`, `src/service/api_v2.py`, `src/service/cache_client.py`: alternate service stack; harden or consolidate.
- `src/pipelines/ingest_racecards.py`, `ingest_results.py`, `postrace_update.py`: generic ingestion/reconciliation scaffolds; currently not canonical; quarantine or harden.
- `src/training/pipeline.py`, `feature_store.py`, `model_registry.py`, `labels.py`, `metrics.py`, `train_benter.py`: active training stack, still gated.
- `src/learning/auto_retrain.py`, `genesis_protocol.py`, `post_race_evaluator.py`: learning stack exists, but not approved for operation.
- `src/data/supabase_client.py`, `src/data/data_pipeline.py`: active data layer; harden.
- `src/intelligence/macro_regime/bha_macro_context.py`: active macro layer; must be extended before 2025 retry.

Legacy/dead/unknown:
- `scripts/reconcile_historical_archive.py`: legacy and incomplete; quarantine.
- Unknown/quarantine top-level utilities: `build_multiples.py`, `build_multiples_0423.py`, `build_rp_runner_signals.py`, `check_results.py`, `check_results_0422.py`, `convert_to_parquet_v2.py`, `explore_racing_api.py`, `export_plot_board.py`, `fetch_results_0422.py`, `fetch_results_0423.py`, `generate_one_line_report.py`, `generate_verdict_0424.py`, `test_claude.py`, `test_supabase.py`.
- `archive/dead_scripts/*.py`: `121` dead archived scripts; not part of active control plane.

**C. Context Manager Audit**

Where context currently lives:
- `data/velo_current_state.json`
- `data/velo_artifact_index.json`
- frozen candidate/rejection/cursor files
- bridge manifests
- global audit artifacts
- `pipeline_runs` for live loops
- handoff/recovery docs
- checkpoint git branch

What is canonical:
- `data/velo_current_state.json` for phase, gate state, latest passed/failed block, accepted spine counts
- bridge manifests for block scope
- frozen window files for discovery scope
- latest accepted global audit for training-gate truth

What is duplicated:
- accepted spine counts appear in state file, audit docs, and chat history
- live loop state appears in `pipeline_runs`, logs, and sometimes daily backup files
- model ownership appears across `app/services/model_registry.py`, `src/training/model_registry.py`, and model artifacts

What can go stale:
- state file and artifact index if not refreshed
- cursor state if a future agent reads the wrong window
- playbook/training status if inferred from code instead of state

What can be safely resumed:
- OASIS historical work from state file + artifacts
- live pipeline reruns by `pipeline_runs`
- rollback from manifest + recovery doc

What still needs stronger handling:
- macro support state
- model version truth
- live loop ownership
- rejected block residual-proof tracking

Chat-memory failures:
- Global audit is not yet a reusable script, so agents can over-rely on narrative memory.
- Macro support state is still inferred from code and parquet range, not a single canonical state file field.

**D. State Store Audit**

Sources of truth by object:
- Historical accepted events/results/features: Supabase tables plus accepted audit/state file.
- Discovery windows: frozen JSONL + cursor files.
- Bridge scope: manifest JSON files.
- Global governance: audit artifacts + state file.
- Live runtime: `pipeline_runs`, `trigger_reject_events`, `velo_verdicts`, logs.
- Recovery/handoff: state file, handoff docs, checkpoint branch.

Duplicate state risks:
- state file vs audit docs
- multiple API stacks
- multiple training stacks
- multiple pipeline implementations

Stale state risks:
- artifact index not refreshed
- live logs treated as source of truth
- dirty working tree mistaken for checkpointed state

Recommended canonical state model:
- state file for phase and gate state
- manifest for scoped writes
- audit artifacts for pass/fail proof
- `pipeline_runs` for live run ownership
- one future dedicated model-state artifact for model/version truth

**E. Lifecycle Hook Audit**

Existing strong hooks:
- OASIS discovery accounting invariant
- bridge manifest freeze
- HFS post-run audit
- provenance normalization dry-run/apply split
- checkpoint/handoff documents

Missing hooks:
- reusable global audit script
- manifest-scoped rollback tool
- automatic state updates
- live loop artifact freeze
- macro data pack release lifecycle
- training gate controller
- Playbook activation gate

Mandatory before training:
- global audit script
- rollback verifier/tool
- state update automation
- leakage verifier
- training control-plane unification

Can wait:
- dead-script cleanup
- docs consolidation
- artifact index automation polish

**F. Verification Interface Audit**

Current blocking checks are strong on the historical accepted spine:
- accounting invariant
- winner parity
- duplicate `race_id`
- duplicate `event_key`
- duplicate `race_id + horse_id`
- missing/orphan HFS rows
- vector null and dimension checks
- MPI null and variance
- chaos null and variance
- macro-year mismatch
- doctrine completeness
- provenance completeness
- training_eligible completeness
- rollback completeness by proof

Current blind spots:
- no unified live-vs-historical separation verifier
- no dedicated leakage verifier script
- no project-wide rollback verifier
- no project-wide secret/config preflight standard
- no single pass/fail schema shared across historical, live, training, and playbook paths

Recommended pass/fail rule:
- treat parity, winner, duplicates, vector, signal nulls, macro-year, doctrine, provenance, training eligibility, rollback completeness as blocking
- treat secret scan, checkpoint status, source completeness, and report lineage as blocking for release/checkpoint operations
- treat exploratory utility classification and docs polish as warning-only

**G. Gaps Found**
- No dedicated reusable `global_clean_spine_audit` script
- No dedicated manifest-scoped rollback tool
- Canonical state updates are still manual
- `2025` macro context unsupported
- Legacy/dead scripts can confuse future agents
- Unrelated unstaged `app/services/velo_prime_service.py` work exists
- Chat memory can still be mistaken for source of truth if startup docs are skipped
- Live loops do not freeze artifacts the way OASIS does
- Multiple API/pipeline/training stacks coexist without one documented authority

**H. Operational Risks**
- Wrong entrypoint selection by a future agent
- Live rerun duplication without manifest isolation
- Training code paths invoked outside governance gate
- Macro layer silently clamping unsupported years unless blocked by audit
- Dirty working tree mistaken for checkpointed state

**I. Recommended Fixes**
- Build a reusable global clean spine audit script
- Add a dedicated manifest-scoped rollback tool or verifier
- Automate state file and artifact index refresh
- Create one authoritative training gate controller
- Govern macro data pack updates as release artifacts
- Quarantine or clearly label non-canonical pipelines and API stacks

**J. Must-Fix Before Training**
- Reusable `global_clean_spine_audit`
- Reusable manifest rollback/rollback verifier
- Automated canonical state refresh
- Unified training control plane
- Leakage and post-race field exclusion verifier

**K. Must-Fix Before 2025 Block 025 Retry**
- Build `2025` macro context support
- Add a retry preflight that proves `macro_year_used = race_date year`
- Preserve rollback proof until retry passes

**L. Recommended Next Mission**
- Review ETCSLV must-fix gaps
- Then build `2025` macro context support
- Then retry `OASIS_BLOCK_025`
- Then run `Global Clean Spine Audit V3`
- Training remains paused until that sequence passes
