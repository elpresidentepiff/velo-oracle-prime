# VÉLØ ARTIFACT MAP
**Generated:** 2026-03-18 | **Canonical spine:** `main` @ `012608e`

---

## ML MODELS

| Artifact | Path | Status | Notes |
|---|---|---|---|
| SQPE v17 | `models/sqpe_v17/sqpe_v17.pkl` | **CANON — production** | AUC 0.940, 33 features. Loaded via ModelManager. |
| SQPE v17 dev | `models/sqpe_v17_dev/` | STAGING | Dev variant. Do not promote without audit. |
| SQPE v16 | `models/sqpe_v16/` | SUPERSEDED | Keep for rollback only. |
| SQPE v15 | `models/sqpe_v15/sqpe_v15.pkl` | SUPERSEDED | Keep for rollback only. |
| SQPE v14 | `models/sqpe_v14/sqpe_v14.pkl` | SUPERSEDED | Keep for rollback only. |
| SQPE v1_real | `models/v1_real/sqpe/sqpe_model.pkl` | LEGACY — loadable | Only confirmed-trained pkl. Use only if v17 fails. |
| TIE v9 | `models/tie_v9/tie_v9.pkl` | DORMANT | Not wired to ensemble. Was UMA component. |
| Longshot v6 | `models/longshot_v6/longshot_v6.pkl` | SUPERSEDED | Replaced by `models/specialist/longshot_model/` |
| Overlay v5 | `models/overlay_v5/overlay_v5.pkl` | SUPERSEDED | Was UMA overlay. Not in current ensemble. |
| VeloPrime predictor v1 | `models/velo_predictor_v1.pkl` | LEGACY | Pre-ensemble era. Do not use. |
| Improvement | `models/specialist/improvement_model/` | **CANON** | AUC 0.896. Live in specialist loader. |
| Market Deception | `models/specialist/market_deception_model/` | **CANON** | AUC 0.920. Live in specialist loader. |
| Release Window | `models/specialist/release_window_model/` | **CANON** | AUC 0.703. Additive only. |
| Comment Intelligence | `models/specialist/comment_intelligence_model/` | **CANON** | AUC 0.670. Additive only. |
| Draw Bias | `models/specialist/draw_bias_model/` | **CANON** | AUC 0.614. Additive only. |
| Place | `models/specialist/place_model/` | **CANON** | AUC 0.949. Each-way target. |
| Longshot (specialist) | `models/specialist/longshot_model/` | **CANON** | AUC 0.936. SP≥10 filter. |

---

## TRAINING DATA

| Artifact | Path | Status | Notes |
|---|---|---|---|
| Primary dataset | `data/backtest_50k.csv` | **CANON** | 50k+ rows. Source for all v14+ training. |
| BHA industry stats | `data/bha_industry_stats.json` | **CANON** | Complete BHA Data Pack 2012–2024. All metrics, ambiguity flags. |
| BHA macro features | `data/bha_macro_features.parquet` | **CANON** | Derived indices: competitiveness, fixture_strain, favourite_compression etc. |
| Backtest 10k | `models/backtest_10k_results.json` | REFERENCE | Earlier backtest results. Historical only. |
| Backtest recalibrated | `models/backtest_recalibrated.json` | REFERENCE | Calibration run results. |
| Benter weights | `models/benter_weights.json` | REFERENCE | Feature weight reference. |
| SQPE v17 feature importance | `models/sqpe_v17/feature_importance.csv` | **CANON** | Per-feature importances. Use for doctrine review. |
| SQPE v17 metadata | `models/sqpe_v17/metadata.json` | **CANON** | Version, features list, AUC, training date. |

---

## REPORTS

| Artifact | Path | Status | Notes |
|---|---|---|---|
| Structural trend | `reports/structural_trend_report.txt` | **CANON** | BHA macro trend analysis 2012–2024. |
| Macro volatility | `reports/macro_volatility_report.txt` | **CANON** | Chaos mode indicators, volatility regimes. |
| Doctrine linkage | `reports/doctrine_linkage_report.txt` | **CANON** | Which BHA metrics link to which VÉLØ doctrine features. |
| Weekly reports | `reports/weekly/` | ACTIVE | Accumulated weekly summaries (if populated). |
| Evidently reports | `reports/evidently/` | DORMANT | Model drift monitoring. Not in active use. |

---

## EVIDENCE ARCHIVE

| Artifact | Path | Status | Notes |
|---|---|---|---|
| Cheltenham 2026-03-12 | `evidence/cheltenham-2026/` | **BENCHMARK** | Day 3 predictions. Multi-model consensus. First real benchmark. Preserve forever. |
| Cheltenham 2026-03-10 | `feature/sentient-feedback-loop` (branch) | MERGED | 4 strikes, 3 quarantines — training signal |

---

## DOCUMENTATION

**Canonical docs (authoritative — follow these):**

| Doc | Path | Purpose |
|---|---|---|
| Session memory | `CLAUDE.md` | Permanent context for Claude — architecture, bugs, status |
| Branch map | `BRANCH_MAP.md` | All branches, status, merge disposition |
| System map | `SYSTEM_MAP.md` | Full architecture and data flow |
| Artifact map | `ARTIFACT_MAP.md` | This file |
| Master operating prompt | `docs/VELO_MASTER_OPERATING_PROMPT.md` | VÉLØ doctrine — prediction philosophy |
| Module spec | `docs/VELO_MODULE_SPEC_V1.md` | PJI, Day Classification, module specs |
| Spotlight hard limits | `docs/VELO_SPOTLIGHT_HARD_LIMITS.md` | What Spotlight cannot override |
| Deploy proof rule | `docs/VELO_DEPLOY_PROOF_RULE.md` | Never declare deployed without /openapi.json proof |
| Canonical state | `docs/VELO_CANONICAL_STATE.md` | Point-in-time canonical snapshot |
| Developer blueprint | `docs/VELO_DEVELOPER_BLUEPRINT.md` | Developer onboarding guide |
| Incident log | `docs/VELO_INCIDENT_LOG.md` | Production incidents log |

**Reference docs (informational, not directive):**

| Doc | Path | Notes |
|---|---|---|
| Architecture | `docs/ARCHITECTURE.md` | Pre-v10 architecture. Partially outdated. |
| Database schema | `docs/DATABASE_SCHEMA.md` | Pre-v10 schema. Check Supabase for live state. |
| ML model | `docs/ML_MODEL.md` | Pre-v17 ML docs. SQPE_v17 supersedes. |
| Special sauce | `docs/VELO_SPECIAL_SAUCE.md` | Doctrine philosophy. Still valid. |
| Phase 2 report | `docs/PHASE2_REPORT.md` | Historical milestone. Reference only. |

**Archive (do not reference for active dev):**

- `docs/archive/` — 79 consolidated root-level MDs from pre-cleanup era
- `docs/agent_zero/` — Pre-takeover agent architecture. Superseded.
- `docs/architecture/` — Early architecture diagrams. Superseded.

---

## SCRIPTS (operational)

| Script | Purpose | Status |
|---|---|---|
| `scripts/run_prime_today.py` | Daily prediction run — fetch cards, score, persist to velo_verdicts | **CANON — daily driver** |
| `scripts/close_sigma_loops.py` | Nightly sigma — results, forensic attribution, learned_patterns | **CANON — nightly driver** |
| `scripts/populate_entity_bibles.py` | Backfill horse/trainer/jockey bible tables | OPERATIONAL |
| `scripts/load_bha_to_supabase.py` | Load BHA Data Pack → Supabase tables | DONE (run once) |
| `scripts/cache_bha_macro_features.py` | Derive macro features → parquet | DONE (run once) |
| `scripts/train_specialist_models.py` | Train all 7 specialist models | RUN TO RETRAIN |
| `scripts/generate_macro_reports.py` | Generate doctrine_linkage, volatility, structural reports | OPERATIONAL |
| `scripts/audit_sqpe_v17.py` | Audit SQPE v17 against backtest data | OPERATIONAL |
| `scripts/deploy_now.py` | Trigger Railway deploy via GraphQL | OPERATIONAL |

**Dormant / experimental scripts (do not run in production):**

| Script | Notes |
|---|---|
| `scripts/feed_sigma_loop.py` | Manual sigma feed — superseded by close_sigma_loops.py |
| `scripts/generate_verdicts.py` | Old verdict generator — superseded by run_prime_today.py |
| `scripts/backtest.py` | Full backtest runner — for model training only |
| `scripts/continuous_training.py` | Experimental continuous training — not production-safe |
| `scripts/activate_betfair_live.py` | Betfair live trading — not operational (no Betfair integration) |
| `scripts/gate_e_evidence.py` | Gate E playbook evidence — experimental |

---

## SUPABASE TABLES — LIVE DATA STATUS

**Populated (active):**

| Table | Rows | Written By |
|---|---|---|
| `velo_verdicts` | 22 | `run_prime_today.py` |
| `runners` | 2,756 | racing_api_normalizer |
| `races` | 32 | racing_api_normalizer |
| `horse_profiles` | 243 | racing_api_fetcher |
| `trainer_profiles` | 132 | racing_api_fetcher |
| `jockey_profiles` | 118 | racing_api_fetcher |
| `owner_profiles` | 226 | racing_api_fetcher |
| `horse_comments` | 1,765 | spotlight_ingestion_worker |
| `comments_archive` | 1,130 | spotlight_ingestion_worker |
| `gear_medical_events` | 440 | spotlight_parser |
| `runner_race_facts` | 243 | racing_api_normalizer |
| `pipeline_runs` | 14 | run_prime_today.py |
| `raw_payload_archive` | 25 | racing_api_fetcher |
| `bha_industry_stats` | 246 | load_bha_to_supabase.py |
| `bha_yearly_summary` | 13 | load_bha_to_supabase.py |
| `bha_macro_specialty_metrics` | 132 | load_bha_to_supabase.py |
| `course_profiles` | 3 | manual |

**Empty (pending live data):**

`runner_derived_features`, `predictions`, `results`, `race_results`, `runner_results`, `sigma_audits`, `velo_post_race_reviews`, `learned_patterns`, `selections`, `betting_ledger`, `market_snapshots`, `betfair_markets`, `betfair_odds`, `odds_snapshots`, `manipulation_alerts`, `intent_cases`, `plot_memory_spine`, `race_spotlight_verdict`

---

## MEMORY LAYERS

| Layer | Path | Content |
|---|---|---|
| Claude session memory | `C:\Users\puror\.claude\projects\...\memory\` | User profile, feedback, project state |
| CLAUDE.md | `CLAUDE.md` (repo root) | Architecture, bugs, session checklist — checked into git |
| learned_patterns | Supabase `learned_patterns` table | Sigma-derived pattern accumulation |
| Cheltenham benchmark | `evidence/cheltenham-2026/` | First real prediction evidence |
| Sigma audits | Supabase `sigma_audits` | Per-race outcome log |
| velo_post_race_reviews | Supabase `velo_post_race_reviews` | Full forensic review with signal_attribution |
