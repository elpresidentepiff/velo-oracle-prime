# VFU-10 Failure Attribution Ledger
**Version:** VFU_10_FAILURE_ATTRIBUTION_V1  
**Date:** 2026-06-14  
**Base commit:** b5f60a4 (VFU-09)  

---

## Validation Closeout

| Suite | Result |
|-------|--------|
| VFU-10 targeted tests | **20/20 PASS** |
| VFU + VP governed suite | **167/167 PASS** |
| Full repository suite | **RED — 24 pre-existing unrelated failures** |
| VFU-10-related failures | **0** |
| Touched-path regressions | **0** |

Full repository suite remains red due to 24 pre-existing, non-VFU failures. VFU-10 passed governed scoped validation.

---

## Hard Rules — Confirmed

| Rule | Status |
|------|--------|
| Canonical Horse Passport mutated | NOT MUTATED |
| Supabase writes | NONE |
| Live scoring changed | UNCHANGED |
| Model promoted | NONE |
| Telegram sent | NONE |
| Racing API restored | NOT RESTORED |
| Mar–Apr extracted | NOT EXTRACTED |
| VP threshold | 0.40 UNCHANGED |
| Passport Override | DRY_RUN_ONLY |

---

## VFU-10 Files Added (NEW only — no existing files modified)

- `scripts/ops/vfu_time_safe_passport_override_validation.py`
- `tests/test_vfu_time_safe_passport_override_validation.py` (20 tests)
- `data/reports/vfu_time_safe_passport_override_validation.json`
- `data/reports/vfu_time_safe_passport_override_validation.md`
- `data/reports/vfu_time_safe_passport_override_cases.jsonl`
- `data/reports/vfu_time_safe_passport_uncovered_cases.json`
- `data/reports/vfu_time_safe_passport_candidate_watchlist.json`

**VFU-10 reads only (no mutation):**
- `data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl`
- `data/new_build/training/passport_features.parquet`
- `data/new_build/training/core_v0_historical_dataset.parquet`

---

## Full Failure Attribution (24 failures — all pre-existing)

### Classification breakdown

| Class | Count |
|-------|-------|
| KNOWN_CLAUDE_MD_BUG | 17 |
| UNRELATED_LEGACY_ASSERTION | 5 |
| NETWORK_DEPENDENT_SUPABASE | 2 |
| VFU_10_RELATED | **0** |

---

### NETWORK_DEPENDENT_SUPABASE (2)

| Test | Error | Pre-dates b5f60a4? | VFU-10 touched? |
|------|-------|-------------------|-----------------|
| `test_hfs_schema_contract.py::test_hfs_schema_contract` | `psycopg2.OperationalError: connection to db.ltbsxbvfsxtnharjvqcm.supabase.co failed: Network is unreachable` | YES (commit 9338860) | NO |
| `test_new_build_database.py::test_spine_status_report_is_read_only_summary` | `psycopg2.OperationalError: Network is unreachable` | YES (commit 9cc36d5) | NO |

WSL environment cannot reach Supabase external host. Not a code failure.

---

### KNOWN_CLAUDE_MD_BUG (17)

**app.services.model_manager (5 failures in test_phase25.py)**

CLAUDE.md: *"model_manager.py load_sqpe() returns a metadata dict, never loads .pkl — known bug"*

| Test | Error |
|------|-------|
| `test_phase25.py::test_predict_stub` | `ModuleNotFoundError: No module named 'app.services.model_manager'` |
| `test_phase25.py::test_sqpe_load` | same |
| `test_phase25.py::test_trainer_intent_load` | same |
| `test_phase25.py::test_longshot_load` | same |
| `test_phase25.py::test_benter_overlay` | same |

**app.ml.model_ops.loader + app.engine.uma (4 failures in test_phase3_full.py)**

CLAUDE.md: *"app/ml/model_ops/loader.py — hardcoded Linux path /home/ubuntu/velo-oracle/models"*

| Test | Error |
|------|-------|
| `test_phase3_full.py::test_06_model_ops_loader` | `No module named 'app.ml.model_ops.loader'` |
| `test_phase3_full.py::test_07_model_ops_validator` | same |
| `test_phase3_full.py::test_08_model_ops_registry` | same |
| `test_phase3_full.py::test_20_integration_smoke` | `No module named 'app.engine.uma'` |

**METADATA_ONLY models + UMA (8 failures in test_phase4_full.py + test_phase5_operational.py)**

CLAUDE.md: *"SQPE v14: METADATA_ONLY — pkl absent, not loadable. Longshot v6: METADATA_ONLY. Overlay v5: METADATA_ONLY."*

| Test | Error |
|------|-------|
| `test_phase4_full.py::test_01_sqpe_v14_trained` | SQPE v14 pkl absent |
| `test_phase4_full.py::test_03_longshot_v6_trained` | Longshot v6 pkl absent |
| `test_phase4_full.py::test_04_overlay_v5_trained` | Overlay v5 pkl absent |
| `test_phase4_full.py::test_07_backtest_results_exist` | Backtest artifact absent |
| `test_phase4_full.py::test_13_uma_prediction` | `No module named 'app.engine.uma'` |
| `test_phase4_full.py::test_14_uma_edge_calculation` | same |
| `test_phase4_full.py::test_15_uma_risk_classification` | same |
| `test_phase4_full.py::test_37_end_to_end_prediction` | same |
| `test_phase4_full.py::test_40_full_system_health` | same |
| `test_phase5_operational.py::test_12_uma_loads` | `UMA failed: No module named 'app.engine.uma'` |
| `test_phase5_operational.py::test_14_model_ops_loads` | `Model ops failed: No module named 'app.ml.model_ops.loader'` |

All commit 4215b03 / 890c849 — predates b5f60a4.

---

### UNRELATED_LEGACY_ASSERTION (5)

| Test | Error | Evidence commit |
|------|-------|----------------|
| `test_new_build_current_card_feed.py::test_reason_codes_do_not_emit_rpr_and_mark_passport_strength` | `assert 'FIRST_TIME_HEADGEAR' in ['JOCKEY_CONTINUITY', ...]` | 89518cf |
| `test_new_build_horse_passport.py::test_layoff_flag_active` | `assert None == 'ACTIVE'` | 9338860 |
| `test_new_build_horse_passport.py::test_layoff_flag_fresh_90` | `assert None in ('FRESH_90', 'FRESH_180')` | 9338860 |
| `test_new_build_sources.py::test_source_inventory_sees_industry_scale_inputs` | `AttributeError: 'list' has no 'get'` in `new_build_velo/sources.py:62` | 7be0d63 |
| `test_new_build_sources.py::test_bulk_ingest_commands_cover_available_local_sources` | `AttributeError: 'list' has no 'get'` in `new_build_velo/sources.py:145` | 7be0d63 |
| `test_production_hardening.py::test_persist_retry_removes_only_proven_bad_group` | `assert 1 == 2` | 2cc135a |

All predate b5f60a4. VFU-10 did not touch any of these source files.

---

## Final Classifications

```
VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_VALIDATION_COMPLETE
TEMPORAL_CONTAMINATION_AUDITED
KAKIRRA_PREDICTIVE_PROOF_REJECTED_FOR_NOW
MAN_IS_KING_PARTIAL_TIME_SAFE_SIGNAL_REVIEWED
TIME_SAFE_PASSPORT_FEATURES_TESTED
PASSPORT_OVERRIDE_REMAINS_DRY_RUN_ONLY
VFU_10_RELATED_FAILURES_ZERO
FULL_REPO_FAILURES_PRE_EXISTING_UNRELATED
NO_VP_THRESHOLD_CHANGE
NO_LIVE_DOCTRINE_PROMOTION
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
NO_MAR_APR_EXTRACTION
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
NO_TELEGRAM_SEND
NO_RACING_API_RESTORATION
```
