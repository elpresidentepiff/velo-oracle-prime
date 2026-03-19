# VÉLØ SYSTEM MAP
**Generated:** 2026-03-18 | **Status:** Canonical production system

---

## INFRASTRUCTURE

| Layer | Service | Host | Status |
|---|---|---|---|
| Main API | `velo-oracle` | Railway / sincere-empathy | LIVE |
| PDF Ingestion | `ingestion-spine` | Railway / sincere-empathy | LIVE |
| Database | Supabase PostgreSQL | ltbsxbvfsxtnharjvqcm.supabase.co (eu-west-2) | LIVE — 54 tables |
| Data Source | The Racing API | api.theracingapi.com | LIVE — Basic plan |
| Version Control | GitHub | elpresidentepiff/velo-oracle-prime | PUBLIC |
| LLM | Anthropic Claude | claude-sonnet-4-6 | KEY MISSING |

---

## DATA FLOW — END TO END

```
THE RACING API
    │  HTTP Basic Auth, token-bucket rate limiter
    ▼
workers/racing_api_fetcher.py
    │  normalize_race() → canonical race dict
    ▼
workers/racing_api_normalizer.py
    │  Standardized: runners[], race_id, date, going, distance_f, race_class, type
    ▼
app/services/velo_prime_service.py :: score_race_velo_prime(race)
    ├── _build_live_features(runner, race)      ← 30+ feature dict per runner
    ├── ModelManager.predict_sqpe()             ← SQPE v17 probability
    ├── specialist_models/loader.py             ← 7 specialist scores
    └── VeloPrimeEnsemble.predict_race()        ← VELO_PRIME_prob (final output)
    ▼
scripts/run_prime_today.py                      ← daily orchestration script
    ├── persist_race_predictions()              → velo_verdicts (1 row/race)
    └── [runner_derived_features deferred]
    ▼
SUPABASE
    ├── velo_verdicts           ← top pick + full_analysis JSONB
    ├── runner_derived_features ← per-runner specialist scores
    └── learned_patterns        ← sigma feedback accumulation
    ▼
scripts/close_sigma_loops.py                    ← nightly sigma (cron on Railway)
    ├── Fetch today's results from Racing API
    ├── Reconcile vs velo_verdicts
    ├── _attribute_miss_signals()               ← forensic signal attribution
    ├── Write velo_post_race_reviews
    ├── Write sigma_audits
    └── _update_learned_patterns()              ← learning layer
```

---

## PREDICTION ENGINE — MODULE DETAIL

### SQPE v17 (Primary Signal — 45% weight in ensemble)
- **File:** `models/sqpe_v17/sqpe_v17.pkl`
- **Loader:** `app/services/model_manager.py :: ModelManager.predict_sqpe()`
- **Features:** `src/intelligence/v17_feature_extractor.py` — 17 doctrine features + base 16 = 33 total
- **Performance:** AUC 0.9400, Top-1 73.8%, ratings-only 75.9%
- **Training data:** `data/backtest_50k.csv` (50k+ rows)

### 7 Specialist Models (secondary signals)
| Model | File | Weight | AUC | Purpose |
|---|---|---|---|---|
| improvement_model | `models/specialist/improvement_model/` | additive | 0.896 | Horse in form cycle |
| market_deception_model | `models/specialist/market_deception_model/` | additive | 0.920 | Hidden value vs market |
| release_window_model | `models/specialist/release_window_model/` | additive | 0.703 | Trainer intent signal |
| comment_intelligence_model | `models/specialist/comment_intelligence_model/` | additive | 0.670 | NLP comment flag |
| draw_bias_model | `models/specialist/draw_bias_model/` | additive | 0.614 | Draw position effect |
| place_model | `models/specialist/place_model/` | additive | 0.949 | Each-way target |
| longshot_model | `models/specialist/longshot_model/` | additive | 0.936 | SP≥10 value |

### VeloPrimeEnsemble
- **File:** `src/intelligence/velo_prime_ensemble.py`
- **Input:** `ensemble_inputs[]` — SQPE + specialist scores per runner
- **Output:** `VELO_PRIME_prob`, `confidence_level`, `verdict_flags`, `macro_regime_label`
- **Macro context:** `src/intelligence/macro_regime/bha_macro_context.py` — 13 macro features from BHA Data Pack

### BHA Macro Layer
- **Tables:** `bha_industry_stats` (246 rows), `bha_yearly_summary` (13), `bha_macro_specialty_metrics` (132)
- **Features:** competitiveness_index, favourite_compression_index, regime_label, chaos_mode, favourite_trap_risk
- **Inputs to:** VeloPrimeEnsemble macro_context parameter

---

## 5-AGENT ORCHESTRATOR (Structural Layer)

**Entry:** `app/engine/orchestrator.py :: Orchestrator`
**Output:** `BettingVerdict` dataclass

| Agent | File | Weight | Scores |
|---|---|---|---|
| FormAnalyzer | `app/engine/agents/form_analyzer.py` | 20% | Recent form, consistency |
| MarketAnalyzer | `app/engine/agents/market_analyzer.py` | 15% | Odds, value |
| ConnectionsAnalyzer | `app/engine/agents/connections_analyzer.py` | 25% | Trainer/jockey signals |
| CoursDistanceAnalyzer | `app/engine/agents/course_distance_analyzer.py` | 20% | Course/distance record |
| RatingsAnalyzer | `app/engine/agents/ratings_analyzer.py` | 20% | OR/RPR/TS |

**Betting rules:** BACK 2% if score>70 | BACK 1% if score>60 | LAY 0.5% if score<40 | PASS otherwise

**Status:** 20/20 tests passing. NOT yet wired to live prediction pipeline. Runs independently via `app/engine/run_analysis.py`.

---

## SIGMA LOOP (Learning Layer)

**File:** `scripts/close_sigma_loops.py`
**Trigger:** Railway cron — `python scripts/close_sigma_loops.py` — runs nightly
**Railway service:** `velo-oracle` (same service, cron mode via service config)

**Stages:**
1. Load open `velo_verdicts` (race_id, top_rank_horse_id, full_analysis)
2. Fetch results from Racing API `/results/today`
3. Reconcile — identify WIN / PLACED / MISS
4. `_attribute_miss_signals()` — forensic comparison: winner vs top_pick across 7 specialist signals
5. Write `velo_post_race_reviews` (review_outcome JSONB with signal_attribution)
6. Write `sigma_audits` (horse_id, outcome, decision_tier)
7. `_update_learned_patterns()` — cumulative pattern store:
   - `tier_{tier}_accuracy` — win rate per decision tier
   - `miss_reason_{reason}` — what caused the miss
   - `signal_miss_{signal}` — which specialist signal failed (NEW — forensic layer)
   - `tier_{tier}_primary_miss_signal` — which signal fails most per tier (NEW)

---

## SPOTLIGHT NLP LAYER

**Files:**
- `workers/spotlight_parser.py` — NLP parser, flags horse comments for signals
- `workers/spotlight_ingestion_worker.py` — autonomous ingestion pipeline
- Writes to: `horse_comments` (1,765 rows), `comments_archive` (1,130), `gear_medical_events` (440)

**Hard limit:** Spotlight CANNOT override structural verdict (`docs/VELO_SPOTLIGHT_HARD_LIMITS.md`)

---

## FASTAPI ENDPOINTS (app/main.py)

| Route | Status | Notes |
|---|---|---|
| `GET /health` | LIVE | Returns 200 |
| `GET /openapi.json` | LIVE | Deploy proof endpoint |
| `POST /predict/quick` | BROKEN | Calls UMA() without load_models() |
| `POST /predict/full` | BROKEN | prediction_chain bugs (see Known Bugs) |
| `GET /debug/routes` | PROTECTED | Admin only after security hardening |

---

## INGESTION SPINE (Railway service: ingestion-spine)

**Entry:** `workers/ingestion_spine/ingestion_spine/main.py`
**Start command:** `python -u -m uvicorn ingestion_spine.main:app --host 0.0.0.0 --port ${PORT:-8080}`
**Function:** Racing Post PDF parser — extracts Spotlight comments → horse_comments
**Status:** LIVE, /healthz returns 200. Fixed 2026-03-15.

---

## KNOWN BROKEN PATHS (do not call in production)

1. `app/intelligence/chains/prediction_chain.py` — `get_model_manager()` does not exist, `extract_features()` wrong name, `run_prediction_chain()` arg count wrong
2. `app/main.py /predict/quick` — UMA() called without load_models()
3. `app/ml/model_ops/loader.py` — hardcoded Linux path `/home/ubuntu/velo-oracle/models`
4. `src/agents/velo_prime.py` — sys.path.insert hack breaks FastAPI
5. `scrapers/velo_scraper.py` — Linux paths, broken on Windows

---

## ENVIRONMENT (all from .env, never hardcoded)

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Database endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | Full DB access |
| `SUPABASE_ANON_KEY` | Public key |
| `SUPABASE_DB_URL` | Direct PostgreSQL connection |
| `RACING_API_USERNAME` | Racing API auth |
| `RACING_API_PASSWORD` | Racing API auth |
| `ANTHROPIC_API_KEY` | Claude API (MISSING) |
| `RAILWAY_TOKEN` | Railway GraphQL API |
| `TELEGRAM_BOT_TOKEN` | Telegram notifications |
| `TELEGRAM_CHAT_ID` | Telegram channel |
