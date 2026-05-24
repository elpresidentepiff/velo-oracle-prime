# VÉLØ V14 Architecture Truth Map

**Status:** PATH_VERIFIED (live repo scan 2026-05-23)  
**Purpose:** Canonical reference of what actually exists vs what is claimed or planned.  
**Authority:** Operator (El Presidente). Read-only design input. No runtime changes authorised by this document.

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | File exists and is loadable (pkl confirmed present) |
| ⚠️ | Directory exists but pkl/model binary is missing — metadata.json only |
| ❌ | Reference in CLAUDE.md or docs but path does not exist in repo |
| 🆕 | Exists in repo but NOT documented in CLAUDE.md — unreported |
| 🔒 | Gate-blocked — not activated until operator approval |

---

## 1. Active Scoring Ensemble

**Policy:** `SQPE_IMPROVEMENT_MDS_V1` (live from 2026-05-08, commit `b7e4e0c`)  
**Source:** `src/velo/weight_policy_registry.py` — `LIVE_BASELINE_CURRENT` policy object

| Component | Weight | Model File | Status |
|---|---|---|---|
| sqpe_v17 | 0.45 | `models/sqpe_v17/sqpe_v17.pkl` | ✅ ACTIVE |
| improvement_score | 0.12 | `models/specialist/improvement_model/improvement_model.pkl` | ✅ ACTIVE |
| release_day_prob | 0.10 | `models/specialist/release_window_model/release_window_model.pkl` | ✅ ACTIVE |
| market_deception_score | 0.10 | `models/specialist/market_deception_model/market_deception_model.pkl` | ✅ ACTIVE |
| place_prob | 0.08 | `models/specialist/place_model/place_model.pkl` | ✅ ACTIVE |
| comment_intel_score | 0.08 | `models/specialist/comment_intelligence_model/comment_intelligence_model.pkl` | ✅ ACTIVE |
| longshot_score | 0.07 (gated: SP≥10) | `models/specialist/longshot_model/longshot_model.pkl` | ✅ ACTIVE (gated) |
| draw_bias | badge only | `models/specialist/draw_bias_model/draw_bias_model.pkl` | ✅ badge |

Ensemble orchestrator: `src/intelligence/velo_prime_ensemble.py`  
UMA (Unified Model Assembly): `app/engine/uma.py`

---

## 2. Full Model Registry (Path-Verified)

### SQPE Family

| Model | pkl Path | Status | Notes |
|---|---|---|---|
| sqpe_v17 | `models/sqpe_v17/sqpe_v17.pkl` | ✅ LOADABLE | Active production model |
| sqpe_v18 | `models/sqpe_v18/sqpe_v18.pkl` | 🆕 LOADABLE | Exists, unreported in CLAUDE.md. Not wired. |
| sqpe_v14 | `models/sqpe_v14/` | ⚠️ METADATA ONLY | pkl absent — not loadable |
| sqpe_v15 | `models/sqpe_v15/` | ❌ DOES NOT EXIST | Stale reference in CLAUDE.md — remove |
| sqpe v1_real | `models/v1_real/sqpe/` | ⚠️ META ONLY | `sqpe_meta.json` only — original benchmark reference |
| sqpe v1_real pkl | `models/v1_real/sqpe/sqpe_model.pkl` | ❓ UNVERIFIED | CLAUDE.md says "REAL — trained, loadable" — not re-verified this pass |

### TIE / Longshot / Overlay

| Model | pkl Path | Status | Notes |
|---|---|---|---|
| tie_v9 | `models/tie_v9/tie_v9.pkl` | ✅ LOADABLE | |
| longshot_v6 | `models/longshot_v6/` | ⚠️ METADATA ONLY | pkl absent — not loadable. Superseded by specialist longshot_model |
| overlay_v5 | `models/overlay_v5/` | ⚠️ METADATA ONLY | pkl absent — not loadable |

### Shadow Model Arena

| Path | Contents | Status |
|---|---|---|
| `models/shadow/model_arena/` | lightgbm_win.pkl, lightgbm_frame.pkl, logistic_baseline_win.pkl, logistic_baseline_frame.pkl, ablation/ | 🆕 EXISTS — shadow challenger layer |
| `models/shadow/model_arena_v2/` | (contents not inspected this pass) | 🆕 EXISTS |

### Specialist Models (all verified)

All in `models/specialist/{name}/{name}.pkl` + `metadata.json`:

| Model | pkl | CLAUDE.md AUC | Status |
|---|---|---|---|
| improvement_model | ✅ | 0.896 | ACTIVE |
| market_deception_model | ✅ | 0.920 | ACTIVE |
| release_window_model | ✅ | 0.703 | ACTIVE |
| comment_intelligence_model | ✅ | 0.670 | ACTIVE |
| draw_bias_model | ✅ | 0.614 | badge |
| place_model | ✅ | 0.949 | ACTIVE |
| longshot_model | ✅ | 0.936 | ACTIVE (gated SP≥10) |

---

## 3. Runtime Architecture (Live Scripts)

All under `scripts/app/` (primary live runtime directory):

| Script | Label | Purpose |
|---|---|---|
| `run_prime_today.py` | LIVE_RUNTIME | Daily scoring orchestrator — Railway cron |
| `run_results_sigma.py` | LIVE_RUNTIME | Post-race sigma + results download |
| `ingest_results_to_horse_runs.py` | LIVE_RUNTIME | Upserts results → racing_horse_runs |
| `build_rpdc_daily.py` | LIVE_RUNTIME | RPDC tags → runner_release_candidates |
| `build_innovation_protocol.py` | AUDIT_EVIDENCE | Verdict-result dedup, readonly |
| `router_shadow_audit.py` | AUDIT_EVIDENCE | Router lane evidence accumulation |
| `run_execution_bridge_shadow.py` | PAPER_EXECUTION | Paper ledger — SIM only, hard LIVE guard |
| `run_velo_unified_evidence_audit.py` | AUDIT_EVIDENCE | Master truth audit |
| `velo_daily_harness.py` | LIVE_RUNTIME | Full daily harness orchestrator |
| `run_velo_closed_loop_daily.py` | LIVE_RUNTIME | Closed-loop daily runner |
| `update_mission_control.py` | LIVE_SUPPORT | Dashboard mission control updater |
| `velo_morning_cockpit.py` | LIVE_SUPPORT | Morning cockpit pre-flight |
| `preflight_10am_check.py` | LIVE_SUPPORT | 10am pre-scoring checks |
| `notify_governed_results.py` | LIVE_SUPPORT | Telegram result notification |

**RPDC dependency chain (must run in order):**
```
run_results_sigma → ingest_results_to_horse_runs → build_rpdc_daily → run_prime_today
```

---

## 4. Intelligence Layer

| Module | Path | Status |
|---|---|---|
| VeloPrimeEnsemble | `src/intelligence/velo_prime_ensemble.py` | ✅ LIVE_SUPPORT |
| SQPE Engine | `src/intelligence/sqpe.py` | ✅ LIVE_SUPPORT |
| TIE Engine | `src/intelligence/tie.py` | ✅ LIVE_SUPPORT |
| TIE v3 Gate | `src/intelligence/tie_v3_gate.py` | ✅ EXISTS |
| Race Archetypes | `src/intelligence/race_archetypes.py` | ✅ LIVE_SUPPORT |
| Specialist Loader | `src/intelligence/specialist_models/` | ✅ LIVE_SUPPORT |
| NDS Engine | `src/intelligence/nds.py` | ✅ EXISTS (purpose TBD) |
| Macro Regime | `src/intelligence/macro_regime/` | ✅ EXISTS |
| Horse State Engine | `src/intelligence/horse_state_engine.py` | ✅ EXISTS |
| Track Context | `src/intelligence/track_context.py` | ✅ EXISTS |
| Orchestrator | `src/intelligence/orchestrator.py` | ✅ EXISTS |

---

## 5. VELO Layer (src/velo/)

| Module | Path | Status |
|---|---|---|
| Execution Bridge | `src/velo/execution_bridge.py` | ✅ PAPER_EXECUTION (hard LIVE guard) |
| Product Router | `src/velo/product_router.py` | ✅ LIVE_SUPPORT |
| Weight Policy Registry | `src/velo/weight_policy_registry.py` | ✅ LIVE_SUPPORT |
| Signal Stack | `src/velo/signal_stack.py` | ✅ EXISTS |
| Council Orchestrator | `src/velo/council/council_orchestrator.py` | 🆕 EXISTS (unreported) |
| Council Agents | `src/velo/council/agents.py` | 🆕 EXISTS |
| Council Verification | `src/velo/council/verification.py` | 🆕 EXISTS |
| Council Tool Registry | `src/velo/council/tool_registry.py` | 🆕 EXISTS |
| Council Evidence Packet | `src/velo/council/evidence_packet.py` | 🆕 EXISTS |
| Course ID Resolver | `src/velo/course_identity_resolver.py` | ✅ EXISTS |
| Distance Normalizer | `src/velo/distance_normalizer.py` | ✅ EXISTS |
| Execution Guard | `src/velo/execution_guard.py` | ✅ EXISTS |
| Feature Audit | `src/velo/feature_audit.py` | ✅ EXISTS |
| Midprice Hunter | `src/velo/midprice_hunter.py` | ✅ EXISTS |
| Place Signal Classifier | `src/velo/place_signal_classifier.py` | ✅ EXISTS |
| Racing API Shadow Enrichment | `src/velo/racing_api_shadow_enrichment.py` | ✅ SHADOW_TELEMETRY |

---

## 6. Data Assets (Path-Verified)

### Feature Parquets

| File | Rows | Status |
|---|---|---|
| `data/raceform_v17_features.parquet` | 1,702,741 | ✅ MASTER SOURCE |
| `data/features/hk_prerace_features_v1.parquet` | 81,533 | ✅ HK pre-race V1 |
| `data/features/hk_prerace_features_v2.parquet` | 81,533 | ✅ HK pre-race V2 (+market signal) |
| `data/features/fr_prerace_features_v1.parquet` | 174,329 | ✅ FR pre-race V1 |
| `data/features/fr_prerace_features_v2.parquet` | 174,329 | ✅ FR pre-race V2 (+market signal) |
| `data/features/international_lagged_rating_features.parquet` | 1,702,741 | ✅ Lagged rating features |
| `data/features/race_shape_features_latest.json` | — | ✅ Race shape features |
| `data/features/jtc_d/` | — | ✅ JTC-D profile tables |
| `data/features/v12/` | — | ✅ V12 legacy features |

### JTC-D Profile Tables (in data/features/jtc_d/)

5 tables built from 1.7M row history for trainer/jockey/combo course+distance profiles.

---

## 7. International Expansion — Gate Status

**Governance:** `docs/engineering/INTL_MODEL_PROMOTION_GOVERNANCE_V1.md`  
**Gate:** `INTERNATIONAL_RATING_PROVENANCE_GATE_ACTIVE` (locked at commit `589b428`)  
**Arena scripts:** `scripts/audit_international_prerace_arena_v1.py` / `v2.py`

| Pack | Arena V1 AUC | Arena V1 SR | FavSR | Verdict |
|---|---|---|---|---|
| HK_SHA_TIN_V1 | 0.7130 | 24.40% | 34.70% | FAILS_FAVOURITE_BASELINE |
| HK_HAPPY_VALLEY_V1 | 0.6842 | 20.73% | 26.87% | FAILS_FAVOURITE_BASELINE |
| FR_CHANTILLY_V1 | 0.6643 | 18.07% | 29.42% | FAILS_FAVOURITE_BASELINE |
| FR_FLAT_CORE | 0.6631 | 19.71% | 29.69% | FAILS_FAVOURITE_BASELINE |
| FR_AUTEUIL_JUMPS_V1 | 0.6306 | 18.16% | 27.58% | FAILS_FAVOURITE_BASELINE |

Arena V2 (market signal added) — results pending at time of this document write.

Gate close path: arena V2 must show AUC ≥ 0.75 AND SR > FavSR for at least one pack.  
Then: operator sign-off → migration → worker activation (in that order, no shortcuts).

**Blocked until gate closes:**
- Migration (`migrations/intl_schemas_v1.sql`) — NOT APPLIED
- HKJC/PMU ingest workers — NOT BUILT
- International model training/promotion — BLOCKED

---

## 8. Governance Documents (Path-Verified)

| Document | Path | Status |
|---|---|---|
| Intl Promotion Governance | `docs/engineering/INTL_MODEL_PROMOTION_GOVERNANCE_V1.md` | ✅ |
| Intl Architecture V1 | `docs/engineering/VELO_INTERNATIONAL_ARCHITECTURE_V1.md` | ✅ |
| LLM Council V1 | `docs/engineering/VELO_LLM_COUNCIL_V1.md` | ✅ |
| CPU Shadow Gate Review | `docs/engineering/CPU_SHADOW_GATE_V2_REVIEW_2026_05_22.md` | ✅ |
| Daily Evidence Runbook | `docs/engineering/DAILY_EVIDENCE_ACCUMULATION_RUNBOOK_V1.md` | ✅ |
| EOD Result Study Layer | `docs/engineering/EOD_RESULT_STUDY_LAYER_V1.md` | ✅ |

---

## 9. PATH_UNVERIFIED / Open Items for Operator

| Item | Classification | Notes |
|---|---|---|
| `models/sqpe_v18/sqpe_v18.pkl` | `UNCLASSIFIED_LOADABLE_MODEL` / `NOT_WIRED` / `NO_PROMOTION` / `COUNCIL_CLASSIFICATION_REQUIRED` / `EVIDENCE_TRAIL_REQUIRED` | EXISTS and loadable. Do not delete. Do not wire. Do not evaluate as live. Hygiene risk until Council classifies. |
| `models/sqpe_v15/` | `STALE_REFERENCE_IN_CLAUDE_MD` / `DOCS_REMEDIATION_REQUIRED` / `NO_RUNTIME_IMPACT_CONFIRMED` | Directory does not exist. CLAUDE.md reference is stale. No runtime impact confirmed. |
| `models/longshot_v6/` | `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT` | pkl absent. Not loadable. Superseded by specialist longshot_model. |
| `models/overlay_v5/` | `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT` | pkl absent. Not loadable. |
| `models/sqpe_v14/` | `METADATA_ONLY` / `NOT_LOADABLE` | pkl absent. Not loadable. Confirm archive or delete. |
| `src/velo/council/` | `COUNCIL_MODULE_PRESENT` / `PATH_VERIFIED` | Full module exists. Not in CLAUDE.md. Status to be confirmed by operator. |
| `models/shadow/model_arena/` | `SHADOW_ARENA_PRESENT` / `NO_LIVE_PROMOTION` | EXISTS. Shadow challenger arenas. Not in CLAUDE.md. Not promoted to live. |
| `models/shadow/model_arena_v2/` | `SHADOW_ARENA_PRESENT` / `NO_LIVE_PROMOTION` | EXISTS. V2 shadow arena. Not in CLAUDE.md. Not promoted to live. |

---

## 10. Immutable Safety Constraints (Permanent)

```
NO live staking
NO model promotion without n≥100 and operator sign-off
NO international migration/workers until gate closes (El Presidente)
NO sigma via close_sigma_loops.py — ALWAYS run_results_sigma.py
NO consumed_live=true
NO Telegram format changes
2026-05-20 = SCORING_FLATLINE_CONTAMINATED — never enters training
```

---

```
VELO_V14_TRUTH_MAP_STATUS: PATH_VERIFIED
VERIFIED_AT: 2026-05-23
ACTIVE_MODEL: sqpe_v17
ACTIVE_POLICY: SQPE_IMPROVEMENT_MDS_V1
INTERNATIONAL_GATE: ACTIVE (arena V2 pending)
```
