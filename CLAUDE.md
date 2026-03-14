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
| The Racing API | CONFIGURED | Basic Auth, MCP registered |
| Supabase MCP | REGISTERED | `mcp.supabase.com` — active next session |
| Racing API MCP | REGISTERED | `mcp.theracingapi.com` — active next session |
| Claude API | MISSING KEY | Add `ANTHROPIC_API_KEY` to `.env` |

All credentials live in `.env` — never hardcode, never commit. Read with `os.getenv()`.

---

## Railway Services (sincere-empathy project)
- `velo-oracle` — main FastAPI prediction engine (`app/main.py`)
- `ingestion-spine` — Racing Post PDF parser (`workers/ingestion_spine/`)
- `enchanting-exploration` — purpose unclear, likely legacy

Railway config: `railway.toml` — builds with nixpacks, starts `uvicorn app.main:app`

---

## Supabase Database — All 25 Tables

| Table | Rows | Purpose |
|---|---|---|
| `races` | 10 | Race-level data |
| `runners` | 0 | Runner-level data per race |
| `predictions` | 0 | Engine prediction outputs |
| `results` | 0 | Actual race outcomes |
| `plot_memory_spine` | 0 | PJI scoring, jockey changes, market moves |
| `selections` | 0 | Betting selections made |
| `betting_ledger` | 0 | P&L tracking |
| `sigma_audits` | 37 | Audit log (the "sigma" — DB table not code) |
| `permanent_principles` | 43 | Oracle belief system / rules |
| `learned_patterns` | 3 | Self-learned race patterns |
| `model_versions` | 1 | ML model registry |
| `model_comparison` | 0 | Model A/B results |
| `system_performance` | 1 | System health tracking |
| `race_analysis` | 0 | Deep race analysis output |
| `manipulation_alerts` | 0 | Market manipulation flags |
| `manipulation_effectiveness` | 0 | Manipulation detection accuracy |
| `daily_performance` | 0 | Daily P&L summary |
| `course_profitability` | 0 | Course-level ROI tracking |
| `racecards` | 0 | Live racecard data |
| `betfair_odds` | 0 | Betfair market snapshots |
| `betfair_markets` | 0 | Betfair market metadata |
| `sectional_data` | 0 | Sectional timing data |
| `racing_data` | 0 | Historical racing data |
| `rpd_tags` | 0 | Racing Post Digger tags |
| `import_batches` | 2 | Data ingestion tracking |

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

## What Was Done This Session
- Built `workers/racing_api_fetcher.py` (full HTTP client with retry, cache, normalisation)
- Created `.env` with all confirmed credentials
- Created `plot_memory_spine` table in Supabase (25/25 tables now exist)
- Set all env vars on Railway `velo-oracle` service
- Registered Supabase MCP + Racing API MCP servers
- Linked Railway to `sincere-empathy` project
- Wrote `scripts/test_supabase.py` and `scripts/test_claude.py`
- Fixed Racing API password typo (l→I) in `app/integrations/racing_api_client.py`

## What Is Still Needed
- `ANTHROPIC_API_KEY` — add to `.env` then run `scripts/test_claude.py`
- Supabase DB password — update `SUPABASE_DB_URL` in `.env`
- Fix 5 known bugs in prediction pipeline (listed above)
- Rotate Racing API credentials (exposed in git history on public repo)
- v11 repo — check GitHub under `elpresidentepiff` for `velo-oracle-v11`
