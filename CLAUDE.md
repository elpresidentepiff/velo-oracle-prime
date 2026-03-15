# VÉLØ PRIME — Claude Code Permanent Context

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
| Supabase | CONNECTED | `ltbsxbvfsxtnharjvqcm.supabase.co`, eu-west-2, 25 tables |
| Railway | CONNECTED | Project `sincere-empathy`, service `velo-oracle` |
| GitHub | CONNECTED | `elpresidentepiff/velo-oracle-prime`, default branch `main` |
| The Racing API | CONNECTED | Basic Auth + MCP active |
| Supabase MCP | CONNECTED | `mcp.supabase.com` — live |
| Racing API MCP | CONNECTED | `mcp.theracingapi.com` — live |
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

## Supabase Database — 51 Tables (live count as of 2026-03-15)

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
  narrative_chain.py                <- Market story detection
  market_chain.py                   <- Manipulation detection
  pace_chain.py                     <- Pace map analysis
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
| SQPE v14 | `models/sqpe_v14/sqpe_v14.pkl` | EXISTS on disk |
| SQPE v15 | `models/sqpe_v15/sqpe_v15.pkl` | EXISTS on disk |
| TIE v9 | `models/tie_v9/tie_v9.pkl` | EXISTS on disk |
| Longshot v6 | `models/longshot_v6/longshot_v6.pkl` | EXISTS on disk |
| Overlay v5 | `models/overlay_v5/overlay_v5.pkl` | EXISTS on disk |

Load SQPE with: `SQPEEngine.load(Path("models/v1_real/sqpe/"))`

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

## What Is Still Needed
- `ANTHROPIC_API_KEY` — add to `.env` then run `scripts/test_claude.py` (user getting this now)
- Racing API subscription upgrade — user getting this now
- Supabase DB password — update `SUPABASE_DB_URL` in `.env`
- Wire agents to Racing API fetcher output
- Fix 5 prediction pipeline bugs (listed above in Known Bugs section)
- Rotate Racing API credentials (exposed in git history on public repo)
- Push to main + verify Railway auto-deploy
