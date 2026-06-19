# VÉLØ PRIME — Claude Code Permanent Context

> **READ FIRST: `docs/current/ONE_TRUTH.md` is the operational law and wins
> any conflict with this file.** Much of the state below is historical
> (March–April 2026). Racing API is DECOMMISSIONED for live use (2026-05-14;
> ONE_TRUTH law 2026-06-10) — sidecar/reference/archive only.

## Identity
- **Project**: VÉLØ Oracle Prime — horse racing prediction and betting intelligence system
- **Repo**: `elpresidentepiff/velo-oracle-prime` (PUBLIC on GitHub)
- **Owner**: Purorestrepo1981@gmail.com
- **Local path**: `C:\Users\puror\velo-oracle-prime`
- **Active branch**: `feature/v10-launch` (Railway deploys from `main`)
- **Python**: 3.12 (venv at `venv/`) — always activate before running scripts
- **Stack**: FastAPI + Uvicorn, Supabase (PostgreSQL), Railway (hosting), scikit-learn ML models

---

## Infrastructure Connections

| Service | Status | Detail |
|---|---|---|
| Supabase | CONNECTED | `ltbsxbvfsxtnharjvqcm.supabase.co`, eu-west-2, 54 tables |
| Railway | CONNECTED | Project `sincere-empathy`, service `velo-oracle` |
| GitHub | CONNECTED | `elpresidentepiff/velo-oracle-prime`, default branch `main` |
| The Racing API | **DECOMMISSIONED (live)** | Not a live source since 2026-05-14. Sidecar/reference only — see ONE_TRUTH law |
| Supabase MCP | CONNECTED | `mcp.supabase.com` — live |
| Racing API MCP | **REMOVED** | Not live truth — do not use for race-day data |
| Claude API | MISSING KEY | Add `ANTHROPIC_API_KEY` to `.env` |

All credentials live in `.env` — never hardcode, never commit. Read with `os.getenv()`.

---

## Railway Services (sincere-empathy project)
- `velo-oracle` — main FastAPI prediction engine (`app/main.py`). nixpacks.
- `ingestion-spine` — Racing Post PDF parser (`workers/ingestion_spine/`). **FIXED 2026-03-15. /healthz returns 200.** DOCKERFILE builder, rootDirectory=workers/ingestion_spine, startCommand=`python -u -m uvicorn ingestion_spine.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info`. Service ID: `b9a52e75-6d98-4077-98d0-d9e68b16033e`.
- `enchanting-exploration` — duplicate of velo-oracle. Both running against same DB. Not decommissioned yet.

Railway config: `railway.toml` — builds velo-oracle with nixpacks, starts `uvicorn app.main:app`

**CRITICAL Railway lesson**: Service configuration (startCommand, cronSchedule, rootDirectory) is stored server-side in Railway's DB, NOT derived from local railway.json on each deploy. Change it via Railway GraphQL API: `serviceInstanceUpdate(serviceId, environmentId, input: { startCommand, cronSchedule, rootDirectory, restartPolicyType })`. ingestion-spine was wrongly set to cron mode (cronSchedule="0 6 * * *", buildOnly=true) from day one — fixed by setting cronSchedule=null, restartPolicyType=ON_FAILURE.

---

## Supabase Database — 54 Tables (live count as of 2026-03-16)

**Core prediction data**
| Table | Rows | Purpose |
|---|---|---|
| `races` | 32 | Race-level data |
| `runners` | 2,756 | Runner-level data per race |
| `runner_race_facts` | 243 | Derived per-runner facts |
| `runner_derived_features` | 0 | ML feature store |
| `velo_features` | 0 | VELO feature mart |
| `predictions` | 0 | Engine prediction outputs |
| `velo_verdicts` | 22 | Final betting verdicts |
| `results` | 0 | Actual race outcomes |
| `race_results` | 0 | Race-level results |
| `runner_results` | 0 | Runner-level results |

**Profiles & entities**
| Table | Rows | Purpose |
|---|---|---|
| `horse_profiles` | 243 | Horse profiles |
| `trainer_profiles` | 132 | Trainer profiles |
| `jockey_profiles` | 118 | Jockey profiles |
| `owner_profiles` | 226 | Owner profiles |
| `course_profiles` | 3 | Course profiles |
| `horses` | 0 | Horse registry |
| `trainers` | 0 | Trainer registry |
| `jockeys` | 0 | Jockey registry |

**NLP / comments / events**
| Table | Rows | Purpose |
|---|---|---|
| `horse_comments` | 1,765 | NLP flags from horse comments (Spotlight) |
| `comments_archive` | 1,130 | Raw comments archive |
| `gear_medical_events` | 440 | Gear/medical event log |
| `horse_event_history` | 0 | Full event history |
| `trainer_switch_events` | 0 | Trainer change events |
| `race_spotlight_verdict` | 0 | Spotlight gate log |
| `plot_memory_spine` | 0 | PJI scoring, jockey changes, market moves |

**Market data**
| Table | Rows | Purpose |
|---|---|---|
| `betfair_markets` | 0 | Betfair market metadata |
| `betfair_odds` | 0 | Betfair market snapshots |
| `market_snapshots` | 0 | General market snapshots |
| `odds_snapshots` | 0 | Odds movement snapshots |
| `racecards` | 0 | Live racecard data |
| `sectional_data` | 0 | Sectional timing data |
| `racing_data` | 0 | Historical racing data |

**Ingestion / pipeline**
| Table | Rows | Purpose |
|---|---|---|
| `pipeline_runs` | 14 | Pipeline execution log |
| `import_batches` | 0 | Data ingestion tracking |
| `raw_payloads` | 0 | Raw API payload store |
| `raw_payload_archive` | 25 | Archived raw payloads |
| `ingestion_anomalies` | 0 | Ingestion error log |
| `api_coverage_audit` | 0 | API field coverage audit |

**Intelligence / analysis**
| Table | Rows | Purpose |
|---|---|---|
| `race_analysis` | 0 | Deep race analysis output |
| `manipulation_alerts` | 0 | Market manipulation flags |
| `intent_cases` | 0 | Trainer/jockey intent signals |
| `velo_anomaly_flags` | 0 | System anomaly flags |
| `post_race_reviews` | 0 | Post-race review store |
| `velo_post_race_reviews` | 0 | VELO post-race analysis |

**Betting / ledger**
| Table | Rows | Purpose |
|---|---|---|
| `selections` | 0 | Betting selections made |
| `betting_ledger` | 0 | P&L tracking |

**System / config**
| Table | Rows | Purpose |
|---|---|---|
| `sigma_audits` | 0 | Audit log |
| `permanent_principles` | 0 | Oracle belief system / rules |
| `learned_patterns` | 0 | Self-learned race patterns |
| `model_versions` | 0 | ML model registry |
| `rpd_tags` | 0 | Racing Post Digger tags |

**BHA Macro data** (added 2026-03-16)
| Table | Rows | Purpose |
|---|---|---|
| `bha_industry_stats` | 246 | Atomic BHA Data Pack metrics, 2012-2024 |
| `bha_yearly_summary` | 13 | One row per year: fixtures, field sizes, fav compression |
| `bha_macro_specialty_metrics` | 132 | Going distribution, race type mix, HIT breakdown, prize money |

---

## Architecture — End-to-End Prediction Pipeline

```
The Racing API
      |
workers/racing_api_fetcher.py       <- BUILT (real HTTP, Basic Auth, caching)
      |
app/services/feature_engineering.py <- FeatureEngineer.extract_all_features()
      |                                 20 features: speed, form, draw, jockey etc.
src/intelligence/sqpe.py            <- SQPEEngine (GradientBoosting + isotonic cal.)
      |                                 Trained model: models/v1_real/sqpe/
app/engine/uma.py                   <- UMA: fuses SQPE + TIE + Longshot + Overlay
      |
app/intelligence/chains/
  prediction_chain.py               <- Orchestrates full pipeline (HAS BUGS - see below)
  narrative_chain.py                <- Market story detection [WIRED_REPORT_ONLY — run_prime_today via async_scheduler]
  market_chain.py                   <- Manipulation detection [WIRED_REPORT_ONLY — run_prime_today via async_scheduler]
  pace_chain.py                     <- Pace map analysis [WIRED_REPORT_ONLY — soft-fails without speed data, badge only]
src/intelligence/nds.py             <- Narrative Disruption Scanner [WIRED_REPORT_ONLY — run_prime_today post-scoring]
                                       Attaches: nds_narrative, nds_score, nds_disruption, nds_is_fade per runner.
      |
app/playbooks/playbook_orchestrator.py <- Playbook E/F/G (doctrine, execution, evolution)
      |
app/engine/engine_run.py            <- EngineRun dataclass (solid, fully implemented)
      |
Supabase (predictions, results, plot_memory_spine)
```

---

## ML Models — What Actually Exists

| Model | File | Status |
|---|---|---|
| SQPE v1_real | `models/v1_real/sqpe/sqpe_model.pkl` | REAL — trained, loadable |
| SQPE v14 | `models/sqpe_v14/` | METADATA_ONLY — pkl absent, not loadable |
| SQPE v15 | `models/sqpe_v15/` | MISSING — directory does not exist |
| SQPE v17 | `models/sqpe_v17/sqpe_v17.pkl` | LIVE MODEL — trained 2026-03-16, AUC=0.94. **WARNING (MOT-01):** RPR-dominant (~50% feature importance via rpr_vs_field). SP features (sp_dec, log_sp, implied_prob, sp_rank, is_fav) are trained but ARTIFICIAL at inference — all runners default to sp_dec=10.0 because best_odds_decimal is never populated by RP injection or LOCAL_JSON. Effective RPR weight at morning scoring ≈ 65%. |
| SQPE v18 | `models/sqpe_v18/sqpe_v18.pkl` | UNCLASSIFIED LAB MODEL — NO LIFT verdict, not wired. Same RPR/SP structural issue as v17. |
| TIE v9 | `models/tie_v9/tie_v9.pkl` | **STUB — 126-byte placeholder, NOT loadable.** Contains `StubModel` class only. Not a real trained model. |
| Longshot v6 | `models/longshot_v6/` | METADATA_ONLY — pkl absent, not loadable |
| Overlay v5 | `models/overlay_v5/` | METADATA_ONLY — pkl absent, not loadable |

Load SQPE with: `SQPEEngine.load(Path("models/v1_real/sqpe/"))`

**SP inference fix (2026-06-18, commit b672f0e):** `_resolve_decimal_odds()` now reads `best_odds_decimal` correctly — probability values (0 < v < 1.0) converted to decimal via `1/v`. `_parse_betting_forecast` fixes the `(probability - 1)` string format. `sp_rank` and `is_fav` pre-injected across the full field in `score_race_velo_prime`. NDS wired report-only. Chains (pace/narrative/market) wired report-only via async_scheduler.

---

## Known Bugs — Fix Before Live Prediction

1. **`app/services/model_manager.py`** — `load_sqpe()` returns a metadata dict, never loads `.pkl`. Fix: use `joblib.load()`.
2. **`app/intelligence/chains/prediction_chain.py`**:
   - `get_model_manager()` doesn't exist — should be `ModelManager()` instance
   - `extract_features()` wrong name — should be `FeatureEngineer().extract_all_features()`
   - `unify_output()` has Python bug: `sum(1 for p in p["overlay"]["is_overlay"] for p in predictions)` — `p` reused
   - `run_prediction_chain(race_data)` called with 1 arg in `main.py` but needs 2 args `(race, runners)`
3. **`app/main.py` `/predict/quick`** — calls `UMA()` without `load_models()`, crashes on every request
4. **`app/ml/model_ops/loader.py`** — hardcoded Linux path `/home/ubuntu/velo-oracle/models`
5. **`src/agents/velo_prime.py`** — `sys.path.insert` hack breaks when called via FastAPI

---

## Security Issues — IMPORTANT

- **Racing API credentials committed to git history** in `app/integrations/racing_api_client.py`
- **Repo is PUBLIC** on GitHub — credentials visible to anyone
- `.env` is correctly gitignored (no values ever committed)
- Recommended action: rotate Racing API password, use env vars only

---

## ONE TRUTH — Data Sources and Daily Pipeline

**CANONICAL DATA SOURCE: Racing Post only. No Racing API. No Sporting Life. Ever.**

### Results source (sigma EOD)
- Source: `racing_post_account_collector.py` captures RP results pages post-race
- Results file: `data/results/rp_results_{YYYY_MM_DD}.json`
- The capture MUST run AFTER all races finish (~21:00 BST). Morning captures return empty pages.
- Sigma reads with `--source cache`. Never `--source api`.

### Sigma EOD sequence (run in order, every racing day after 21:00 BST)
```bash
# 1. Re-capture RP results pages (now that races are done)
PYTHONPATH=. python3 scripts/ops/racing_post_account_collector.py capture \
  --url-list data/racing_post_url_lists/rp_results_{YYYY-MM-DD}.txt \
  --date rp-results-{YYYY-MM-DD}-final --execute

# 2. Parse captured HTML into rp_results JSON
PYTHONPATH=. python3 scripts/ops/parse_rp_results_capture.py \
  --date {YYYY-MM-DD} --capture-date rp-results-{YYYY-MM-DD}-final --execute

# 3. Run sigma reconciliation
PYTHONPATH=. python3 scripts/ops/run_results_sigma.py --date {YYYY-MM-DD} --source cache

# 4. Ingest results into horse_runs
PYTHONPATH=. python3 scripts/ops/ingest_results_to_horse_runs.py --date {YYYY-MM-DD}

# 5. Build innovation protocol
PYTHONPATH=. python3 scripts/ops/build_innovation_protocol.py --date {YYYY-MM-DD}

# 6. Rebuild sigma retrieval corpus
PYTHONPATH=. python3 scripts/ops/build_sigma_retrieval_corpus.py
```

### If RP capture gets Angular pages (session expired)
The browser profile needs re-authentication. Run interactively (opens Chromium window):
```bash
PYTHONPATH=. python3 scripts/ops/racing_post_account_collector.py init-login \
  --profile-dir data/browser_profiles/racing_post_account --execute
```
Log in manually in the opened browser, press Enter to save profile. Then re-run captures.

### Racecard pipeline (morning, pre-race)
- Source: `racing_post_account_collector.py` captures RP racecard pages
- Parsed by: `parse_racing_post_racecard_capture.py`
- Output: `data/racing_post_account_parsed/{YYYY-MM-DD}/racecard_injection.json`

### What is RETIRED
- Racing API (`--source api`): RETIRED. Never use for new data.
- Sporting Life scraper (`scrape_results_sl.py`): RETIRED. Emergency fallback only, incomplete.
- `new_build_capture_results.py`: uses Racing API internally — do not use.

---

## Key File Locations

```
app/main.py                         FastAPI entry point
app/engine/uma.py                   Unified Model Assembly (prediction brain)
app/engine/engine_run.py            EngineRun dataclass (reproducible verdicts)
app/intelligence/chains/            Prediction, narrative, market, pace chains
app/playbooks/                      Playbook E/F/G orchestrator
app/services/feature_engineering.py 20-feature engineering pipeline
app/services/model_manager.py       Model loader (needs fixing)
app/ml/model_ops/loader.py          Model ops (hardcoded paths, needs fixing)
src/intelligence/sqpe.py            SQPE ML engine (solid)
src/agents/velo_prime.py            VeloPrime conversational agent
src/modules/five_filters.py         Five-Filter shortlisting system
src/memory/velo_memory.py           Memory layer
workers/racing_api_fetcher.py       Live data fetcher (BUILT this session)
workers/ingestion_spine/            Racing Post PDF parser service
scrapers/velo_scraper.py            rpscrape wrapper (Linux paths, broken on Windows)
scripts/test_supabase.py            Supabase connection test
scripts/test_claude.py              Claude API connection test
models/v1_real/sqpe/                Only confirmed trainedloadable model
data/backtest_50k.csv               50k row training dataset
.env                                All credentials (never commit)
```

---

## Session Start Checklist
1. `cd C:\Users\puror\velo-oracle-prime`
2. Credentials are in `.env` — read only, never print values
3. Activate venv: `source venv/Scripts/activate` (or `venv\Scripts\activate` in cmd)
4. MCP servers available after restart: `supabase`, `the-racing-api`
5. Railway linked to `sincere-empathy` → `velo-oracle`

---

## Real Agent System — MERGED AND TESTED

### 5-Agent Orchestrator (`app/engine/`)
All merged from `copilot/replace-placeholder-agents`. **20/20 tests passing.**

```
app/engine/orchestrator.py              — Orchestrator: runs all 5 agents, produces BettingVerdict
app/engine/agents/form_analyzer.py      — FormAnalyzer: recent form figures, consistency
app/engine/agents/market_analyzer.py   — MarketAnalyzer: odds, value identification
app/engine/agents/connections_analyzer.py    — trainer/jockey connections scoring
app/engine/agents/course_distance_analyzer.py — course/distance specialist analysis
app/engine/agents/ratings_analyzer.py  — OR/RPR/TS ratings engine
app/engine/run_analysis.py             — CLI runner
```

**Agent weights:** Connections 25% | Ratings 20% | Form 20% | Course/Distance 20% | Market 15%
**Betting rules:** BACK 2% if score>70, BACK 1% if score>60, LAY 0.5% if score<40, PASS otherwise

### Sentient Loop — FIXED (PR #52)
`app/playbooks/playbook_g_sentient_loopback.py` — upgraded version:
- Kingmaker uses `run_style` field (correct API schema)
- Fuzzy horse name matching via `difflib.SequenceMatcher`
- State backup to Supabase `learned_patterns` (cloud persistence)
- Playbook F receives `directive_firing_threshold` from appetite state

### Spotlight NLP Layer — MERGED (PR #53)
```
workers/spotlight_parser.py             — NLP parser for horse comment flags
workers/spotlight_ingestion_worker.py   — autonomous ingestion pipeline
docs/VELO_MASTER_OPERATING_PROMPT.md   — full doctrine document
docs/VELO_MODULE_SPEC_V1.md            — module specifications (PJI, Day Classification etc.)
docs/VELO_SPOTLIGHT_HARD_LIMITS.md     — Spotlight CANNOT override structural verdict
```

### LangGraph Pipeline — NOT YET MERGED
`copilot/add-langgraph-agent-orchestration` — held back. Needs `langgraph>=0.2.0` + `langchain-core>=0.3.0`. Add deliberately when ready.

**Total: 51 tables in Supabase** (verified via MCP 2026-03-15)

### Evidence Archive
`evidence/cheltenham-2026/` — Cheltenham Day 3 (March 12) prediction data preserved as benchmark

## What Was Done This Session
- Merged 4 branches: harden-production-security, sentient-feedback-loop, spotlight-layer, replace-placeholder-agents
- All merges conflict-resolved, all syntax clean
- 20/20 agent tests passing
- Created `horse_comments` + `race_spotlight_verdict` tables in Supabase
- Built `workers/racing_api_fetcher.py` (token bucket rate limiter, zero silent failures)
- Created `.env` with all confirmed credentials
- Set all env vars on Railway `velo-oracle` service
- Registered Supabase MCP + Racing API MCP servers
- Linked Railway to `sincere-empathy` project
- CLAUDE.md written as permanent session memory

## MACRO + MICRO + LIVE Integration — In Progress (2026-03-16)

### Phase A — DONE
- `data/bha_industry_stats.json` — complete BHA Data Pack extraction (all metrics, all years, ambiguity flags)
- `data/bha_macro_features.parquet` — derived macro indices: competitiveness, fixture_strain, abandonment_stress, favourite_compression, run_density, field_size_regime
- Supabase tables: `bha_industry_stats` (246 rows), `bha_yearly_summary` (13 rows), `bha_macro_specialty_metrics` (132 rows)
- Scripts: `scripts/load_bha_to_supabase.py`, `scripts/cache_bha_macro_features.py`

### Phase B — DONE
- `src/intelligence/macro_regime/bha_macro_context.py` — MacroContext dataclass + get_macro_context(year, race_code)
- Outputs: competitiveness_index, favourite_compression_index, regime_label, chaos_mode, favourite_trap_risk, low_field_warning
- 13 macro features exposed via .to_feature_dict() for race-level feature attachment

### Phase C — DONE (2026-03-16)
- `scripts/train_specialist_models.py` — 7 specialist models trained and saved
- `src/intelligence/specialist_models/loader.py` — batch inference loader
- Output: `models/specialist/[name]/[name].pkl + metadata.json`

| Model | AUC | Top-1 | Status |
|---|---|---|---|
| improvement_model | 0.896 | 65.4% | LIVE-USABLE |
| market_deception_model | 0.920 | 63.6% | LIVE-USABLE |
| release_window_model | 0.703 | 25.6% | LIVE-USABLE (additive only) |
| comment_intelligence_model | 0.670 | 27.0% | LIVE-USABLE (additive only) |
| draw_bias_model | 0.614 | 12.5% | LIVE-USABLE (additive only) |
| place_model | 0.949 | 75.6% | LIVE-USABLE (each-way target) |
| longshot_model | 0.936 | 80.6% | LIVE-USABLE (sp>=10 only) |

### Phase D — CORE DONE (2026-03-16)
- `src/intelligence/velo_prime_ensemble.py` — VeloPrimeEnsemble producing VELO_PRIME_prob
- `scripts/generate_macro_reports.py` — 3 reports in reports/: structural_trend, macro_volatility, doctrine_linkage
- End-to-end smoke test PASSING: race 856450 (Huntingdon 2024-01-12), winner correctly ranked #1

### Ensemble Surgery v1 — DONE (2026-05-08, commit b7e4e0c)
Active profile: **SQPE_IMPROVEMENT_MDS_V1** (default from 2026-05-08)
- Live weights: `sqpe_v17=0.45`, `improvement_score=0.12`, `market_deception_score=0.10`
- Badge-only (stored, not weighted): `place_prob`, `release_window_score`, `comment_intel_score`
- Frozen (excluded): `longshot_score` (FREEZE_CANDIDATE per control audit)
- Rollback: `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` restores pre-surgery state
- Profile logged in `verdict_flags` as `profile:{name}` on every scored race
- Evidence: sqpe_alone_control_audit n=338-342 → LEGACY ROI=-3.1%, NEW ROI=+13.5%
- VP recalibration: avg VP shifts ~-0.05 (improvement_score raw values lower than place_prob — expected)

## What Is Still Needed
- `ANTHROPIC_API_KEY` — add to `.env` then run `scripts/test_claude.py`
- Racing API subscription upgrade for full racecards
- Supabase DB password — update `SUPABASE_DB_URL` in `.env`
- Wire agents to Racing API fetcher output
- Fix 5 prediction pipeline bugs (listed above in Known Bugs section)
- Rotate Racing API credentials (exposed in git history on public repo)
- Wire VeloPrimeEnsemble to live prediction endpoint (app/main.py /predict routes)
- Persist specialist scores + VELO_PRIME_prob to Supabase `velo_verdicts` table
- Push to main + verify Railway auto-deploy

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **velo-oracle-prime** (6943 symbols, 17378 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/velo-oracle-prime/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/velo-oracle-prime/context` | Codebase overview, check index freshness |
| `gitnexus://repo/velo-oracle-prime/clusters` | All functional areas |
| `gitnexus://repo/velo-oracle-prime/processes` | All execution flows |
| `gitnexus://repo/velo-oracle-prime/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

---

# VÉLØ EVIDENCE LAYER — Master Intelligence Context
## (Read this before any analysis, audit, or product work)

Last updated: 2026-04-30 | Unified Audit commit: 0cfbbed | Evidence baseline: 06ba74b | Phase 6 commit: 3f65b1c

---

## What VÉLØ Is

VÉLØ Oracle Prime is an auditable racing intelligence operating system. It predicts horse racing outcomes, audits its own predictions daily via sigma runs, accumulates evidence through a router shadow ledger, and learns patterns from closed results. It is not a tips service. It is a decision-support and analytics engine.

---

## Daily Operating Scripts — Run In This Order

```bash
# ── MORNING (Railway fires automatically at 06:00 UTC) ──────────────────────
# 0. Build RPDC tags for today's runners (run BEFORE scoring, after yesterday's ingest):
source venv/bin/activate && PYTHONPATH=. python scripts/build_rpdc_daily.py --date YYYY-MM-DD

# 1. Score today's races (Railway cron, or manually):
source venv/bin/activate && PYTHONPATH=. python scripts/run_prime_today.py

# ── EVENING (after results close) ────────────────────────────────────────────
# 2. Sigma audit:
source venv/bin/activate && PYTHONPATH=. python scripts/run_results_sigma.py --date YYYY-MM-DD

# 3. Ingest today's results into racing_horse_runs (feeds tomorrow's RPDC):
source venv/bin/activate && PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date YYYY-MM-DD

# 4. Append new races to innovation protocol:
source venv/bin/activate && PYTHONPATH=. python scripts/build_innovation_protocol.py --date YYYY-MM-DD

# 5. Run router shadow audit (evidence accumulation):
PYTHONUTF8=1 source venv/bin/activate && PYTHONPATH=. python scripts/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv

# 6. Execution bridge paper ledger close:
source venv/bin/activate && PYTHONPATH=. python scripts/run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results

# ── PERIODIC ─────────────────────────────────────────────────────────────────
# 7. Weekly or after 20+ new results — unified evidence audit:
source venv/bin/activate && PYTHONPATH=. python scripts/run_velo_unified_evidence_audit.py
```

### RPDC Pipeline Dependency Chain
```
run_results_sigma (downloads results JSON)
    → ingest_results_to_horse_runs (writes racing_horse_runs)
        → build_rpdc_daily (reads history, writes runner_release_candidates)
            → run_prime_today (_attach_rpdc_from_row reads runner_release_candidates)
```
The chain must run in order. Each step depends on the previous day's output.

---

## Sigma Process — LOCKED FORMAT

ALWAYS use `scripts/run_results_sigma.py --date YYYY-MM-DD`. NEVER use `close_sigma_loops.py`.
The Telegram format is locked — never change it. See memory file `feedback_sigma_process.md`.

---

## Proven Evidence (as of 2026-04-28 Unified Audit V1)

**Audit scope:** 49 race days | 1391 sigma rows | 1604 verdicts in DB | 142 X-tier excluded

### Global Performance
| Metric | Value | Baseline |
|---|---|---|
| Strike rate (non-X) | **20.6%** | 20% |
| Frame rate (non-X) | **48.4%** | 70% |
| Days above baseline | 18/49 | — |
| Days at baseline | 9/49 | — |
| Days below baseline | 22/49 | — |

**Note:** Frame rate of 48.4% is below the 70% target. Frame detection is better in high-VP bands but the system has significant low-VP volume dragging the overall metric.

---

### VP Band Truth (PROVEN — monotonic, consistent across 49 days)

| VP Band | n | SR | Frame | Signal Rank |
|---|---|---|---|---|
| VP < 0.20 | 385 | 14.5% | 33.5% | SUPPRESS |
| VP 0.20–0.30 | 460 | 18.0% | 47.8% | NOISY |
| VP 0.30–0.40 | 245 | 27.3% | 62.9% | PROMISING |
| VP ≥ 0.40 | 100 | 44.0% | 85.0% | PROVEN |
| **VP ≥ 0.30 combined** | **345** | **32.2%** | **69.3%** | **PROMISING** |
| **VP ≥ 0.30 + Tier A** | **162** | **40.1%** | **77.2%** | **PROVEN** |

**VP ≥ 0.30 is the primary live signal gate. Any action on VÉLØ output should require VP ≥ 0.30 as a hard floor.**

---

### Tier Truth

| Tier | n | SR | Frame | Avg VP | Signal Rank |
|---|---|---|---|---|---|
| **Tier A** | **162** | **40.1%** | **77.2%** | 0.425 | **PROVEN** |
| Tier B | 402 | 21.1% | 50.0% | 0.277 | NOISY |
| Tier C | 455 | 15.8% | 42.2% | 0.212 | SUPPRESS |
| Tier D | 112 | 13.4% | 33.9% | 0.164 | SUPPRESS |
| Tier X | 142 | 12.7% | 34.5% | 0.145 | SUPPRESS |
| B VP≥0.30 | 130 | 30.0% | 62.3% | — | WATCHLIST |
| **B VP<0.30** | **272** | **16.9%** | **44.1%** | — | **SUPPRESS** |

**B-tier suppression test:** Removing 272 B-tier VP<0.30 rows (-21.8% coverage) improves SR from 20.6% → 21.6% and Frame from 48.4% → 49.6%. Modest gain, confirmed drag direction.

---

### Sidecar Signal Truth (CRITICAL FINDINGS)

| Signal | n | SR | Lift | Verdict |
|---|---|---|---|---|
| **Market deception score > 0.5** | **31** | **54.8%** | **+34.2%** | **KEEP — exceptional** |
| **Improvement score > 0.40** | **62** | **43.5%** | **+22.9%** | **KEEP — proven** |
| **Place prob > 0.80** | **392** | **31.6%** | **+11.0%** | **KEEP — solid** |
| RPDC release score > 0.5 | 54 | 24.1% | +3.5% | KEEP — watchlist (field mapping fixed 2026-05-08, will populate from next Railway deploy) |
| Archetype=Structure | 270 | 21.1% | +0.5% | WATCHLIST — minimal lift |
| Archetype=Compression | 40 | 20.0% | -0.6% | SUPPRESS — no lift |
| G Shadow multiplier > 1.0 | 0 | — | — | BROKEN_OR_UNWIRED |
| RPDC cash window flag | 1 | — | — | INSUFFICIENT_SAMPLE |
| Macro chaos mode | 0 | — | — | BROKEN_OR_UNWIRED |

**Market deception score > 0.5 (SR=54.8%, Frame=96.8%)** is the highest-lift signal in the system. When VÉLØ fires with high MDS, it is identifying something real. This is the highest-priority signal to wire into candidate lane tracking.

---

### Router Shadow Lanes (evidence accumulation only — no staking)

| Lane | n | SR | ROI | Status | Next gate |
|---|---|---|---|---|---|
| V1_BASE | 27 | 37.0% | +11.5% | WATCHLIST | +23 → SHADOW_CANDIDATE |
| V2_CLASS4_ONLY | 17 | 41.2% | +30.2% | LANE_ACTIVE | +3 → WATCHLIST |
| V6_GOLD_SEAM | 5 | 60.0% | +115.0% | LOW_SAMPLE | +15 → SHADOW_CANDIDATE |

**Protected baseline commit:** 06ba74b
**No router rule changes. No staking. Evidence accumulation only.**

Daily router evidence workflow after each closed results batch:
```bash
python scripts/build_innovation_protocol.py --date YYYY-MM-DD
python scripts/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
```

---

### Miss Class Truth (49-day total)

| Miss Class | Count | % of misses |
|---|---|---|
| mid_priced_won | 279 | 46% |
| outsider_won | 92 | 15% |
| market_decoy_followed | 87 | 14% |
| short_fav_won | 81 | 13% |
| non_runner/untracked | 26 | 4% |

**SP 3.0–8.5 zone misses: 352 = 58% of all misses.** Mid-priced winners are the primary unsolved problem.

---

### Modification Impact Timeline

| Date | Modification | SR delta | Frame delta | n_post |
|---|---|---|---|---|
| 2026-03-16 | VeloPrimeEnsemble (SQPE v17 + 7 specialists) | +23.3% | +55.2% | 116 |
| 2026-03-28 | Playbook G v2 — shadow tracking | +3.4% | +3.4% | 312 |
| 2026-04-10 | Race archetype classification | **+3.9%** | **+6.7%** | 193 |
| 2026-04-16 | RPDC evidence layer | -0.9% | +1.1% | 342 |
| 2026-04-27 | Execution Router v1 SP gate | -1.0% | +14.3%* | 26 |
| 2026-04-28 | Router Evidence Engine hardened | +3.2% | +6.8% | 158 |

*Router SP gate frame uplift at n=26 is too small to be meaningful yet.

**Race archetype layer (Apr 10) shows the strongest post-ensemble modification impact.**
**VeloPrimeEnsemble (Mar 16) is the foundational change — all evidence is post-ensemble.**

---

### Final Signal Rankings

| Signal | n | SR | Frame | Rank |
|---|---|---|---|---|
| VP≥0.30 + Tier A | 162 | 40.1% | 77.2% | **PROVEN_SIGNAL** |
| Tier A (all VP) | 162 | 40.1% | 77.2% | **PROVEN_SIGNAL** |
| Improvement score>0.40 | 62 | 43.5% | 82.3% | **PROVEN_SIGNAL** |
| VP≥0.30 | 345 | 32.2% | 69.3% | PROMISING_SIGNAL |
| Place prob>0.80 | 392 | 31.6% | 66.8% | PROMISING_SIGNAL |
| Market deception score>0.5 | 31 | 54.8% | 96.8% | PROMISING_SIGNAL |
| Tier B VP≥0.30 | 130 | 30.0% | 62.3% | WATCHLIST_SIGNAL |
| V1_BASE router | 27 | 37.0% | 85.2% | WATCHLIST_SIGNAL |
| V2_CLASS4_ONLY router | 17 | 41.2% | 82.4% | WATCHLIST_SIGNAL |
| Tier B (all VP) | 402 | 21.1% | 50.0% | NOISY_SIGNAL |
| Archetype=Structure | 270 | 21.1% | 53.7% | NOISY_SIGNAL |
| Tier B VP<0.30 | 272 | 16.9% | 44.1% | **SUPPRESS_SIGNAL** |
| V6_GOLD_SEAM router | 5 | 60.0% | 100.0% | INSUFFICIENT_SAMPLE |

---

## Hard Operating Rules (PERMANENT — never override)

```
NO live staking
NO candidate_route() changes without evidence gate passed
NO router rule changes
NO SQPE/model training
NO Playbook E
NO model changes from single-day analysis
NO baseline overwrite
NO force push
```

Promotion gates (router lanes):
- V2 → WATCHLIST: n≥20, ROI positive
- V2 → SHADOW_CANDIDATE: n≥30, ROI positive, Frame>75%
- Any lane → LIVE_DISCUSSION: n≥100, multi-week evidence
- Freeze: ROI<0 at n≥20 OR Frame<70% at n≥20

---

## Evidence Artifacts (gitignored data files, local only)

| File | Purpose |
|---|---|
| `data/velo_unified_evidence_audit_v1.json` | Master truth JSON — full audit output |
| `data/velo_unified_evidence_audit_v1.md` | Human-readable audit report |
| `data/velo_unified_evidence_audit_v1_metrics.csv` | Signal rankings table |
| `data/velo_innovation_protocol_1k_deduped.csv` | Router lane dataset (713 rows, deduped) |
| `data/router_shadow_audit_latest.csv` | Latest router lane metrics |
| `data/router_shadow_audit_ledger.csv` | Append-only evidence ledger |
| `data/router_shadow_audit_runs/` | Timestamped immutable snapshots |

---

## Next Operating Protocol

1. **Daily:** Run sigma → build_innovation_protocol → router_shadow_audit after each closed-results batch
2. **Daily:** Run execution bridge close (`run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results`) after each race day
3. **Weekly:** Re-run unified evidence audit to track signal rankings over time
4. **V2 watch:** +3 qualifying results → WATCHLIST gate (currently n=17, need n=20)
5. **POWER_ANCHOR watch:** Paper ledger n=3 — no review until n≥20 (current: 2/2 closed wins)
6. **MDS>0.5 study:** Build dedicated candidate lane for market_deception_score>0.5 + VP≥0.30
7. **Improvement score lane:** Wire improvement_score>0.40 as shadow candidate (SR=43.5% at n=62)
8. **B-tier suppression:** Track — confirmed drag but coverage cost is meaningful (-21.8%)
9. **Mid-priced winner miss study:** SP 3–8.5 zone is 58% of all misses — primary research target
10. **Audit dossier:** Build VELO_AUDIT_DOSSIER.md from unified audit output for whitepaper/funding pack

---

## Company Roadmap (from co-founder session 2026-04-28)

**Stage 1:** Router audit accumulation (active)
**Stage 2:** Audit dossier (VELO_AUDIT_DOSSIER.md)
**Stage 3:** High-confidence lane study (VP≥0.30+TierA+MDS>0.5)
**Stage 4:** Mid-priced winner miss study
**Stage 5:** Website/app MVP spec
**Stage 6:** Whitepaper v1 — "VÉLØ: An Auditable Intelligence OS for Racing Prediction"
**Stage 7:** Business plan v1
**Stage 8:** Funding pack v1
**Stage 9:** Shadow-only controlled release plan

Product positioning: **Auditable racing intelligence and decision support. Not a tips service.**

---

## Canonical Runtime Map — Phase 6A (as of 2026-04-30)

Every file with execution-path relevance classified. Labels are permanent until explicitly changed.

| Label | Meaning |
|---|---|
| `LIVE_RUNTIME` | Executed by Railway cron / daily scoring pipeline |
| `LIVE_SUPPORT` | Imported by LIVE_RUNTIME (utility, not directly scheduled) |
| `SHADOW_TELEMETRY` | Evidence accumulation only — no scoring side effects |
| `PAPER_EXECUTION` | Execution bridge — SIM/PAPER only, hard LIVE guard |
| `AUDIT_EVIDENCE` | Audit/reporting scripts — read-only |
| `EXECUTION_BETTING_NOT_ACTIVE` | Contains betting/order logic, NOT wired to live pipeline |
| `LEGACY_AGENT` | Old agent framework, superseded, not imported live |
| `STALE_PLACEHOLDER` | Exists, all sub-engines are placeholder stubs, no real intelligence |

### Script Classification

| File | Label | Risk | Notes |
|---|---|---|---|
| `scripts/run_prime_today.py` | `LIVE_RUNTIME` | LOW | Daily scoring orchestrator — Railway cron |
| `scripts/run_results_sigma.py` | `LIVE_RUNTIME` | LOW | Post-race sigma audit + results download |
| `scripts/ingest_results_to_horse_runs.py` | `LIVE_RUNTIME` | LOW | Upserts results JSON into racing_horse_runs — run after sigma |
| `scripts/build_rpdc_daily.py` | `LIVE_RUNTIME` | LOW | Computes RPDC tags from history, writes runner_release_candidates — run next morning before scoring |
| `scripts/build_innovation_protocol.py` | `AUDIT_EVIDENCE` | LOW | Verdict-result dedup, readonly |
| `scripts/router_shadow_audit.py` | `AUDIT_EVIDENCE` | LOW | Router lane evidence, readonly |
| `scripts/racing_api_shadow_forward_audit.py` | `AUDIT_EVIDENCE` | LOW | Racing API enrichment audit, readonly |
| `scripts/run_execution_bridge_shadow.py` | `PAPER_EXECUTION` | LOW | Paper ledger CLI — SIM/PAPER only |
| `scripts/run_velo_unified_evidence_audit.py` | `AUDIT_EVIDENCE` | LOW | Master truth audit, readonly |

### Source Classification

| File | Label | Risk | Notes |
|---|---|---|---|
| `src/velo/execution_bridge.py` | `PAPER_EXECUTION` | LOW | Hard RuntimeError on LIVE — simulation_only=True always |
| `src/velo/racing_api_shadow_enrichment.py` | `SHADOW_TELEMETRY` | LOW | Evidence enrichment, readonly |
| `src/velo/product_router.py` | `LIVE_SUPPORT` | LOW | Verdict routing logic, readonly |
| `src/intelligence/velo_prime_ensemble.py` | `LIVE_SUPPORT` | LOW | VeloPrime scoring ensemble |
| `src/intelligence/sqpe.py` | `LIVE_SUPPORT` | LOW | SQPE base probability model |

### Agent / Integration Classification

| File | Label | Risk | Notes |
|---|---|---|---|
| `app/agents/betfair_execution_agent.py` | `EXECUTION_BETTING_NOT_ACTIVE` | **HIGH** | Contains `place_order()` — NEVER import in live path |
| `app/agents/betting_agents.py` | `LEGACY_AGENT` | MEDIUM | 5-agent betting framework, old era, not imported live |
| `app/agents/betfair_trading_agents.py` | `EXECUTION_BETTING_NOT_ACTIVE` | **HIGH** | Contains `place_bet()` (back + lay) — sub-engines are placeholder stubs, not wired |
| `app/agents/odds_movement_predictor.py` | `STALE_PLACEHOLDER` | LOW | All sub-engines return hardcoded values — no real intelligence |
| `app/integrations/betfair_client.py` | `EXECUTION_BETTING_NOT_ACTIVE` | MEDIUM | SIM/DELAYED/LIVE abstraction — safe default SIM, LIVE path untested |
| `app/integrations/racing_api_client.py` | `LIVE_SUPPORT` | LOW | Racing API data fetch — read-only |

### Import Safety Rules (permanent)

```
NEVER import into live scoring path:
  app/agents/betfair_execution_agent.py    — place_order() present
  app/agents/betfair_trading_agents.py     — place_bet() (back + lay) present
  app/agents/betting_agents.py             — legacy framework

SAFE to import (readonly / paper-only):
  src/velo/execution_bridge.py             — hard LIVE guard at module level
  src/velo/product_router.py               — routing logic only
  src/velo/racing_api_shadow_enrichment.py — readonly context enrichment

ALWAYS verify before touching execution code:
  grep -r "place_order\|place_bet" src/ scripts/ | grep -v "app/agents"
  → must return empty
```

---

## Phase 5 — Racing API Shadow Enrichment (commit bfe983a, 2026-04-29)

- Racing API enrichment: 374,639 rows across 6 tables ingested into local staging
- Shadow forward ledger: `data/racing_api_shadow_forward_ledger.csv`
- Leakage status: `RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK` — no production weight changes until prospective validation clears
- Audit script: `scripts/racing_api_shadow_forward_audit.py`
- Router lanes at Phase 5 close: V1_BASE n=27 WATCHLIST, V2_CLASS4_ONLY n=17 (+3→WATCHLIST), V6_GOLD_SEAM n=5 LOW_SAMPLE — all healthy, no freeze

---

## Phase 6 — VeloExecutionBridge (commits c1353ff + 3f65b1c, 2026-04-29)

**Classification:** `LIVE_SHADOW_TELEMETRY_ONLY` | `LIVE_OPERATOR_VISIBILITY_ONLY` | `PAPER_EXECUTION_LEDGER_ACTIVE`
**Betting status:** NOT LIVE — simulation_only=True enforced by hard runtime gates

### Files
- `src/velo/execution_bridge.py` — VeloExecutionBridge, ExecutionDirective, directive mapping
- `scripts/run_execution_bridge_shadow.py` — CLI runner + `--audit-results` flag
- `data/velo_execution_bridge_paper_ledger.csv` — append-only paper ledger (gitignored)

### Hard Safety Gates (permanent — never touch)
- `VELO_EXECUTION_MODE=LIVE` → RuntimeError
- `BETFAIR_MODE=LIVE` → RuntimeError
- `suggested_stake=None` and `max_liability=None` on every directive, always
- `simulation_only=True` always — no place_order, no Telegram, no staking

### Directive Priority Order
`BLOCKED → CHAOS_CONTAINMENT_MODE → POWER_ANCHOR_MODE → FAVOURITE_LIABILITY_MODE → MULTI_THREAT_ZONE_MODE → WATCH_ONLY → BLOCKED`

### POWER_ANCHOR_MODE Trigger Conditions
Tier A + VP≥0.40 + `candidate_execution_allowed=True` (injected from shadow ledger) + no suppression

### Paper Ledger State — as of 2026-04-29 (Phase 6A first close)

| Directive | n | W | SR | Paper P&L |
|---|---|---|---|---|
| POWER_ANCHOR_MODE | 3 | 2 | 66.7% | +1.16 (2 bets closed) |
| WATCH_ONLY | 6 | 1 | 17% | — |
| BLOCKED | 29 | — | 8% | — |

**Gate delta:** POWER_ANCHOR vs WATCH_ONLY = +83.3pp — gate confirmed non-decorative
**Validation row 1:** Hickory Lad SP=1.36 WON (VP=0.661, POWER_ANCHOR_MODE, 2026-04-29)
**Validation row 2:** Infraad SP=1.80 WON (POWER_ANCHOR_MODE, 2026-04-29)

### Promotion Thresholds (POWER_ANCHOR paper ledger)
- n≥20 → first review (earliest possible)
- n≥60 → paper execution candidate discussion
- n≥100 → live discussion
- No automatic promotion at any threshold — operator decision required at every gate

<!-- gitnexus:end -->
