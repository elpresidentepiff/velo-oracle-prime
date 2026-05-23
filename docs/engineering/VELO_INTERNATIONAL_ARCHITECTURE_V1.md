# VÉLØ International — Architecture V1
## France (FR) + Hong Kong (HK) Expansion Framework

**Date:** 2026-05-23  
**Status:** DESIGN DOCUMENT — Phase 0 COMPLETE | Phase 1A Offline Baseline Arena COMPLETE  
**Author:** Claude Prime / Co-Founder  
**Classification:** Strategic — Not a live-runtime change  
**Updated:** 2026-05-23 — Racing API removed, verified substrate 255,862 rows, Auteuil reclassified FR_JUMPS, all 5 packs VIABLE_SHADOW_CANDIDATE

---

## 0. Foundation Audit — What We Already Own

Before building anything, run the inventory. We are not starting from zero.

| Asset | Location | State | Notes |
|---|---|---|---|
| FR training rows | `data/raceform_v17_features.parquet` | 172,329 rows | Chantilly 47K, Deauville 46K, Auteuil 31K, Saint-Cloud 27K, Longchamp 20K |
| HK training rows | `data/raceform_v17_features.parquet` | 81,533 rows | Sha Tin 50K, Happy Valley 30K |
| HK ingestion worker | `archive/dead_workers/hk_daily_ingest.py` | DEAD — needs os import + reactivation | Tables: `hk_research.hk_races/results/history` |
| FR ingestion worker | `archive/dead_workers/fr_daily_ingest.py` | DEAD — needs os import fix | Tables: `fr_research.fr_races/runners/results` |
| Benter model | `src/models/benter.py` | IMPLEMENTED — α=0.9, β=1.1 | Calibrate() method included |
| hk_research schema | Supabase | NOT YET CREATED — migration ready, awaiting approval | `migrations/intl_schemas_v1.sql` — 9 HK tables defined |
| fr_research schema | Supabase | NOT YET CREATED — migration ready, awaiting approval | `migrations/intl_schemas_v1.sql` — 7 FR tables defined |

**Signal quality from parquet (confirmed):**
- `rpr_vs_field` correlation with winner target: HK=0.3257, FR=0.3363 — strong, consistent
- `sp_rank` correlation: HK=-0.2563, FR=-0.2232 — market signal works in both jurisdictions
- `mark_compression_score` nonzero: Sha Tin 86%, Chantilly 100% — OR delta features computable
- Favourite SR: Sha Tin 32.1%, Happy Valley 28.3%, Chantilly 28.8% — higher than UK (20%), tighter fields
- RPR top-20% lift vs bottom 80%: HK 7-9x, FR 7-10x — RPR is the cross-jurisdiction engine

---

## 1. The Lesson We Learned Building UK VÉLØ

Do not repeat these mistakes in international expansion:

| Mistake | What It Cost | International Rule |
|---|---|---|
| Racing API dependency for horse history | improvement_score flatlined — 0.0872 constant | Build RP-sourced feature fallbacks from day one |
| Single scoring pipeline for all race types | Handicaps and conditions races scored identically | Segment the pipeline by race category from day one |
| OR assumed universal | OR=0 in France — entire mark_compression system broken | Jurisdiction-aware feature engineering required |
| Mid-price blind spot never addressed | 58% of misses, still unresolved | Build mid-price layer into international before deployment |
| Cold archive started late | Lost 2+ years of live data before archiving began | Start FR/HK cold archive immediately, even while in design |

---

## 2. Data Sources — Ranked Options by Jurisdiction

### 2A. France (FR)

**Priority 1 — Racing API (Active, we already pay for it)**
- Endpoint: `GET /v1/racecards?date={YYYY-MM-DD}` with `region=FR` filter
- Returns: FR racecards with RPR, TS, form, trainer/jockey IDs
- OR equivalent: `or_rating` field — **will be 0 for French horses**. Use `rpr` instead.
- Going: Text field (e.g. "Bon", "Souple") — needs penetrometer mapping table
- Cost: Already included in current subscription
- Worker: `archive/dead_workers/fr_daily_ingest.py` — fix `os` import + reactivate
- Verdict: **START HERE. Zero marginal cost.**

**Priority 2 — PMU Unofficial API (Free, community-documented)**
- Base: `https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}`
- Returns: Race programme JSON including course, distance, prize, field
- Additional: `https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}/partants/{raceNum}` for runners
- PMU odds: `https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}/rapports-simple` post-race
- Status: Unofficial, no auth required, community-maintained, no SLA
- Key value: **Going penetrometer numbers** (official PMU publishes GoingStick numeric equivalent), **Quinté+ flag**, early morning odds
- Verdict: **Phase 2 supplement. Build a lightweight scraper for PMU programme + penetrometer.**

**Priority 3 — France Galop Official Website**
- `https://www.france-galop.com/fr/programme-et-resultats`
- Contains: Official Valeur ratings (20-62 scale), prize money, race classification (Listed/Group)
- Valeur ≠ UK OR. Mapping: Valeur 62 ≈ top-rated. For UK-trained horses running in FR, OR is available.
- Scraping: HTML scraping, fragile. Use only for Valeur rating extraction.
- Verdict: **Phase 3 — enrich valeur ratings for French-trained horses only.**

**Priority 4 — Racing and Sports (Australia)**
- `https://www.racingandports.com.au` — Australian platform with extensive French data
- Contains: Form figures, trainer/jockey stats, international ratings
- Access: Subscription ($AUD 30-50/month)
- Verdict: **Phase 3 optional — if Racing API FR coverage proves thin for form figures.**

**Priority 5 — AtTheRaces / RP International**
- Racing Post covers French racing extensively with RPR figures
- RP PDFs (F_0010) include some FR races for major meetings
- Verdict: **Opportunistic — when major FR meetings (Arc de Triomphe, Prix du Jockey Club) overlap UK card.**

---

### 2B. Hong Kong (HK)

**Priority 1 — Racing API (Active, we already pay for it)**
- Endpoint: `GET /v1/racecards?date={YYYY-MM-DD}` with `region=HK` filter
- Returns: HK racecards with RPR, draw, trainer/jockey, class
- Going: Standard text (Good to Firm, Good, etc.)
- OR coverage: 97-100% populated — HK uses its own rating scale (0-140), maps closely to UK OR
- Worker: `archive/dead_workers/hk_daily_ingest.py` — fix `os` import + reactivate
- Verdict: **START HERE alongside FR. Zero marginal cost.**

**Priority 2 — HKJC Official Website (Free, stable)**
- Sectional times: `https://racing.hkjc.com/en-us/local/information/displaysectionaltime?racedate={DD/MM/YYYY}&RaceNo={N}`
- Returns: Official 400m split times, pace maps, sectional rankings
- Draw statistics: `https://racing.hkjc.com/en-us/local/horse-racing/draw-statistics`
- Returns: By-draw win%, place%, earnings by course and distance
- Barrier trial results: Listed on HKJC site — critical for debutants (Griffin class)
- Verdict: **Phase 2. Build HKJC sectional scraper. This is the highest-value free signal in HK racing.**

**Priority 3 — Renavon (Commercial, $99+/month)**
- Service: `renavon.com` — HK-specific historical database
- Contains: Results from 1970s, odds time-series (pre-race), odds combinations table `hkjc_odds_combinations`
- Key value: **Opening odds + late odds time-series** — the single most predictive feature in HK racing after fundamental ratings
- Schema: Relational, API access
- Verdict: **Phase 3 — when we are ready to build the Benter odds-time-series layer.**

**Priority 4 — Apify HKJC Scraper**
- `https://apify.com/hkjc-racing` — maintained Apify actor for HKJC data
- Contains: Race cards, results, horse profiles, sectionals
- Cost: ~$10-30/month depending on runs
- Verdict: **Phase 2 fallback if HKJC direct scraping proves brittle.**

**Priority 5 — Racing and Sports (Australia)**
- Covers HK extensively for Australian bettors
- Contains: Form, trainer/jockey stats, weight data
- Verdict: **Phase 3 optional — if Racing API HK runner depth is insufficient.**

---

## 3. Jurisdiction Feature Engineering — What Must Change

### 3A. France — Feature Adaptations

| Feature | UK Behaviour | FR Adaptation Required |
|---|---|---|
| `or_rating` | Official Handicap Rating (0-140) | **0 for French-trained horses** — replace with `rpr` as primary rating |
| `mark_compression_score` | OR delta from best winning OR | **Recompute using rpr_delta_to_best** — if OR=0, use RPR as anchor |
| `curr_or_minus_best_or` | Requires OR history | **Use rpr_vs_field as proxy** — already computed, correlates 0.3363 |
| `going_fit_score` | UK going scale (Firm→Heavy) | **Add penetrometer → UK going mapping table** — French "Bon" ≠ UK "Good" (systematically firmer by ~0.5 GoingStick units) |
| `distance_fit_score` | Furlongs | FR uses metres. **Conversion: metres / 201.168 = furlongs** |
| `class_delta` | UK handicap class (0-7) | **FR class system is entirely different (Group 1-3, Listed, Conditions, Claiming).** Map to tier: 1=G1, 2=G2, 3=G3, 4=Listed, 5=Conditions, 6=Claiming |
| `trainer_timing_score` | UK form cycle patterns | **FR trainers operate differently** — retrain at country level using FR-only history |
| `handicap_plot_score` | UK mark compression | **Conditional: only meaningful for FR handicaps.** Most FR racing is conditions |
| `release_window_score` | Days since win + mark | **Apply to FR handicaps only.** Not applicable to conditions/group races |
| `valeur_rating` | Not in UK system | **NEW FEATURE** — French Valeur rating (20-62 scale). Treat as secondary rating alongside RPR. Add to feature dict. |
| `quintet_plus_flag` | Not in UK system | **NEW FEATURE** — QUINTÉ+ races are highest-quality, attract best-rated field. Binary flag. |
| `pmu_morning_odds` | Not systematically captured | **NEW FEATURE** — French morning PMU odds are highly informative (regulated, no exchange volatility) |

**Going Penetrometer Mapping Table (for FR going_fit_score adaptation):**
```
Penetrometer (French)  →  UK Going Equivalent
< 2.5                  →  Firm
2.5 – 3.4              →  Good to Firm
3.5 – 4.4              →  Good
4.5 – 5.5              →  Good to Soft
5.6 – 6.5              →  Soft
> 6.5                  →  Heavy
```

---

### 3B. Hong Kong — Feature Adaptations

| Feature | UK Behaviour | HK Adaptation Required |
|---|---|---|
| `or_rating` | UK OR (0-140) | **HK rating (0-140) uses same scale by convention.** Maps directly. Use as-is. |
| `class_delta` | UK class system | **HK class = 1 (elite) → 5 (bottom) + Griffin (0).** Class transitions are highly informative — Class 5→4 is a positive signal. Map: griffin=0, class5=1...class1=5 |
| `griffin_flag` | Not in UK system | **NEW FEATURE** — Griffins (debut HK horses) have barrier trial results only. If griffin_flag=True, use barrier trial RPR as rating substitute. Critical signal. |
| `sectional_pace_rank` | Not computed in UK | **NEW FEATURE** — HKJC publishes official 400m splits. Compute: where did horse rank in the first 400m vs field? Horses that run prominent in HK win at higher rates. |
| `draw_bias_score` | UK course/draw adjustment | **HK draw is more deterministic than UK** — especially at Sha Tin (low draws dominate on short-course configurations). Build per-course per-distance draw table from historical data. |
| `barrier_trial_rpr` | Not applicable | **NEW FEATURE** — for Griffin horses, barrier trial performance is the only form guide. HKJC publishes barrier trial times. Compute relative time rating vs trial field. |
| `ts` (Timeform Speed Figure) | Available for UK | **TS often 0 for HK horses.** Do not use as primary feature. RPR is the primary rating. |
| `distance_fit_score` | Furlongs | **HK uses metres.** Same conversion: metres / 201.168. Sha Tin configurations: 1000m, 1200m, 1400m, 1600m, 1800m, 2000m, 2400m |
| `going_fit_score` | UK going scale | **HK going is well-maintained, standard scale.** Use as-is. Going rarely extreme at Sha Tin/Happy Valley. |
| `course_fit_score` | UK course specialist signal | **HK has only 2 courses (ST + HV).** Replace with: track_preference_score = (wins_at_track / runs_at_track) weighted by recency |
| `odds_contraction_score` | UK odds movement | **In HK (tote-only market), no Betfair.** Use HKJC dividend odds time-series from Renavon. Morning pool → post-time pool ratio as contraction signal. |
| `hk_class_trajectory` | Not in UK system | **NEW FEATURE** — class movement over last 4 runs. Horses dropping 2+ classes are not always positive (often distressed). Class ascending from wins signals readiness. |

---

## 4. Model Architecture — Three Options

### Option A: Jurisdiction Feature Flags (Fastest to Ship)
**Approach:** Keep the existing SQPE_IMPROVEMENT_MDS_V1 pipeline. Add `jurisdiction` as a one-hot feature. Add jurisdiction-specific features (valeur, griffin_flag, sectional_pace_rank) to the feature dict. Retrain on combined dataset with jurisdiction flag.

**Pros:** One model. One scoring pipeline. Fastest to production.  
**Cons:** Model trained primarily on UK data — UK-tuned weights may not transfer. RPR top-20% lift is 7-10x in both FR and HK (encouraging), but local signals like draw bias and class trajectory won't get proper weight.

**Signal quality check from parquet:**  
`rpr_vs_field` already computed for all jurisdictions. Existing features that ARE nonzero for HK and FR:
- `mark_compression_score`: HK 86%, FR 100%
- `course_fit_score`: HK 72%, FR 74%  
- `runs_since_win`: HK 92%, FR 92%
- `or_rating`: HK 97%, FR 0% (FR will need RPR substitution)

**Verdict:** Viable for initial shadow testing. NOT recommended as permanent solution.

---

### Option B: Separate Jurisdiction Models (Recommended)
**Approach:** Train three separate SQPE models: UK (existing), FR, HK. Each model is trained on its own jurisdiction's data, with jurisdiction-specific features included. Shared feature engineering layer extracts common features (RPR, form, market) but each model has jurisdiction-specific features appended.

**Architecture:**
```
RP PDF / Racing API
    |
feature_extractor_v17.py (shared — RPR, form, market)
    |
jurisdiction_adapter.py (NEW)
    ├── FR: add valeur, penetrometer going, quintet_plus, PMU odds
    └── HK: add class_trajectory, draw_bias, griffin_flag, sectional_pace_rank
    |
jurisdiction_model_loader.py (NEW)
    ├── UK → sqpe_v17_uk.pkl (existing)
    ├── FR → sqpe_v1_fr.pkl (train from 172K parquet rows)
    └── HK → sqpe_v1_hk.pkl (train from 81K parquet rows + Benter)
    |
shared verdict formatter (existing)
```

**Training plan:**
- FR: 172,329 rows in parquet. Split 2015-2023 train, 2024-2025 holdout. Expected AUC: 0.82-0.88 based on RPR lift.
- HK: 81,533 rows. Split same. Benter model calibration on holdout. Expected AUC: 0.80-0.86.

**Pros:** Each model is tuned to its jurisdiction. Draw bias, class transitions, sectional pace properly weighted. Benter overlay on HK adds market wisdom layer.  
**Cons:** Three models to maintain. Feature engineering split adds complexity.

**Verdict: This is the target architecture. Build toward this.**

---

### Option C: Shared Backbone + Jurisdiction Heads (Most Sophisticated)
**Approach:** Shared lower layers (RPR, form, market) with jurisdiction-specific head layers (final probability estimation). This is the deep-learning equivalent of multi-task learning.

**Structure:**  
```
Shared SQPE backbone (RPR, form, market features) → latent embedding
    ├── UK head → UK probability
    ├── FR head → FR probability (+ valeur, penetrometer)
    └── HK head → HK probability (+ class, draw, sectional)
```

**Verdict:** Overkill for current data volume. Revisit when each jurisdiction has 300K+ rows. **Do not build now.**

---

## 5. Supabase Schema Design

### 5A. France — `fr_research` Schema
Already partially designed in `fr_daily_ingest.py`. Extend with:

```sql
-- Core tables (already in dead worker, create if missing)
CREATE TABLE fr_research.fr_races (
    race_id TEXT PRIMARY KEY,
    meeting_date DATE, course TEXT, region TEXT DEFAULT 'FR',
    off_time TEXT, race_name TEXT, distance_round TEXT,
    distance_f FLOAT, pattern TEXT, race_class TEXT,
    race_type TEXT, age_band TEXT, prize FLOAT, field_size INT,
    going TEXT, going_penetrometer FLOAT,  -- NEW: numeric going
    is_abandoned BOOLEAN DEFAULT FALSE, race_status TEXT,
    quintet_plus BOOLEAN DEFAULT FALSE,    -- NEW: Quinté+ flag
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fr_research.fr_runners (
    race_id TEXT, horse_id TEXT,
    horse_name TEXT, draw INT, weight_kg FLOAT,
    age INT, sex TEXT, jockey_id TEXT, jockey_name TEXT,
    trainer_id TEXT, trainer_name TEXT,
    odds_open FLOAT, odds_live FLOAT, fav_flag BOOLEAN,
    rpr FLOAT, ts FLOAT, or_rating FLOAT,
    valeur_rating FLOAT,                   -- NEW: France Galop Valeur
    form TEXT, comment TEXT,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE fr_research.fr_results (
    race_id TEXT, horse_id TEXT,
    finish_position INT, position_text TEXT,
    beaten_distance FLOAT, sp FLOAT,
    win_flag BOOLEAN, place_flag BOOLEAN,
    jockey_name TEXT, trainer_name TEXT,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE fr_research.fr_verdicts (  -- NEW: FR scoring outputs
    race_id TEXT, horse_id TEXT, horse_name TEXT,
    velo_prime_prob FLOAT, rpr_vs_field FLOAT,
    decision_tier TEXT, verdict_date DATE,
    model_version TEXT DEFAULT 'FR_V1_SHADOW',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE fr_research.fr_sigma_ledger (  -- NEW: FR audit
    race_id TEXT, horse_id TEXT, verdict_date DATE,
    velo_prime_prob FLOAT, decision_tier TEXT,
    outcome TEXT, sp FLOAT, miss_reason TEXT,
    PRIMARY KEY (race_id, horse_id)
);
```

### 5B. Hong Kong — `hk_research` Schema
Already designed in `hk_daily_ingest.py`. Extend:

```sql
-- Core tables (already in dead worker)
CREATE TABLE hk_research.hk_races (...);      -- exists
CREATE TABLE hk_research.hk_results (...);    -- exists
CREATE TABLE hk_research.hk_horse_history (...); -- exists

-- NEW: HK-specific extensions
ALTER TABLE hk_research.hk_races ADD COLUMN IF NOT EXISTS
    hk_class INT;                             -- 1=Class1 (elite) → 5=Class5 + 0=Griffin

ALTER TABLE hk_research.hk_runners (
    race_id TEXT, horse_id TEXT,
    draw INT, hk_class INT,
    griffin_flag BOOLEAN DEFAULT FALSE,        -- NEW
    barrier_trial_rpr FLOAT,                   -- NEW: for Griffins
    class_trajectory INT,                      -- NEW: last 4 run class delta
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE hk_research.hk_sectionals (       -- NEW: HKJC sectional times
    race_id TEXT, horse_id TEXT,
    split_400m FLOAT, split_800m FLOAT,
    split_1200m FLOAT, final_time FLOAT,
    pace_rank_400m INT,                        -- rank within field at 400m
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE hk_research.hk_draw_stats (       -- NEW: historical draw bias
    course TEXT, distance_m INT, draw_position INT,
    win_pct FLOAT, place_pct FLOAT, n_runs INT,
    last_updated DATE,
    PRIMARY KEY (course, distance_m, draw_position)
);

CREATE TABLE hk_research.hk_verdicts (         -- NEW: HK scoring outputs
    race_id TEXT, horse_id TEXT, horse_name TEXT,
    velo_prime_prob FLOAT, benter_prob FLOAT,
    decision_tier TEXT, verdict_date DATE,
    model_version TEXT DEFAULT 'HK_V1_SHADOW',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (race_id, horse_id)
);
```

---

## 6. Daily Pipeline Design

### 6A. France Daily Pipeline

```
05:30 UTC — FR Cold Archive Run
    python -m workers.fr_daily_ingest --date YESTERDAY
    → Writes to fr_research.fr_races, fr_runners, fr_market_snapshots

06:00 UTC — FR Feature Build (after UK RPDC build, parallel)
    PYTHONPATH=. python scripts/intl/build_fr_features.py --date YESTERDAY
    → Reads fr_runners + fr_races
    → Computes: rpr_vs_field, going_penetrometer, quintet_plus_flag, valeur_rating
    → Writes: fr_research.fr_runner_features

06:30 UTC — FR Shadow Scoring
    PYTHONPATH=. python scripts/intl/score_fr_today.py --date YESTERDAY
    → Loads FR model (sqpe_v1_fr.pkl)
    → Scores all FR runners
    → Writes: fr_research.fr_verdicts
    → Model: FR_V1_SHADOW (research only, no Telegram)

21:00 UTC — FR Sigma (after FR results close)
    PYTHONPATH=. python scripts/intl/run_fr_sigma.py --date YESTERDAY
    → Compares fr_verdicts vs fr_results
    → Writes: fr_research.fr_sigma_ledger
    → Outputs SR, Frame rate, VP band breakdown
```

### 6B. Hong Kong Daily Pipeline

HK races on Wed + Sat (Sha Tin). Wed also includes Happy Valley (night).

```
09:00 UTC — HK Cold Archive Run (after HK races close ~08:00 UTC)
    python -m workers.hk_daily_ingest --date YESTERDAY
    → Writes to hk_research.hk_races, hk_results, hk_horse_history

09:30 UTC — HKJC Sectional Scrape
    PYTHONPATH=. python scripts/intl/scrape_hkjc_sectionals.py --date YESTERDAY
    → Fetches: https://racing.hkjc.com/en-us/local/information/displaysectionaltime
    → Writes: hk_research.hk_sectionals

09:45 UTC — HK Feature Build
    PYTHONPATH=. python scripts/intl/build_hk_features.py --date YESTERDAY
    → Reads hk_runners + sectionals + draw_stats
    → Computes: class_trajectory, draw_bias_score, griffin_flag,
                sectional_pace_rank, rpr_vs_field
    → Writes: hk_research.hk_runner_features

10:00 UTC — HK Shadow Scoring
    PYTHONPATH=. python scripts/intl/score_hk_today.py --date YESTERDAY
    → Loads HK model (sqpe_v1_hk.pkl) + Benter overlay
    → Scores all HK runners
    → Benter combines: sqpe_prob × α + market_prob × β
    → Writes: hk_research.hk_verdicts
    → Model: HK_V1_SHADOW (research only, no Telegram)

10:30 UTC — HK Sigma
    PYTHONPATH=. python scripts/intl/run_hk_sigma.py --date YESTERDAY
    → Writes: hk_research.hk_sigma_ledger
```

---

## 7. Model Training Strategy

### 7A. Phase 0 — Baseline Signal Audit (Before Training Anything)

Run these against the existing 255,862 target-course parquet rows to confirm signal before touching a model:

```python
# Already confirmed from parquet analysis:
# FR: rpr_vs_field → target correlation = 0.3363
# HK: rpr_vs_field → target correlation = 0.3257
# Both: sp_rank → target correlation = -0.22 to -0.26
# Both: mark_compression_score → nonzero and correlated

# TO CONFIRM (run before training):
# 1. Does valeur_rating (when proxied from rpr) add lift in FR vs rpr_vs_field alone?
# 2. Does draw position predict winner at Sha Tin consistently?
# 3. Does class_trajectory (last 4) correlate with FR_target at n >= 1000?
```

### 7B. Phase 1 — FR Shadow Model Training

Training data: `data/raceform_v17_features.parquet`, filter `course IN (Chantilly, Deauville, Longchamp, Auteuil, Saint-Cloud)`  
Train period: 2015-01-01 to 2023-12-31 (n≈140K rows)  
Holdout: 2024-01-01 to 2025-12-31 (n≈32K rows)

Features to include:
- All existing v17 features where nonzero >50%
- Drop: `or_rating` (0% coverage in FR), `ts` (low coverage)
- Add: `rpr_vs_field` as primary rating proxy for OR
- Add: `going_penetrometer` mapped from going text
- Add: `quintet_plus_flag` binary

Target: `is_winner` (1/0)  
Algorithm: GradientBoostingClassifier (same as UK SQPE)  
Expected AUC: 0.82-0.86 (RPR lift suggests strong signal)

Output: `models/specialist/sqpe_v1_fr/sqpe_v1_fr.pkl + metadata.json`

### 7C. Phase 2 — HK Shadow Model Training

Training data: same parquet, filter `course IN (Sha Tin, Happy Valley)`  
Train period: 2015-01-01 to 2023-12-31 (n≈66K rows)  
Holdout: 2024-01-01 to 2025-12-31 (n≈15K rows)

Features:
- All v17 features where nonzero >50%
- Add: `class_trajectory` (computed from hk_horse_history)
- Add: `draw_bias_score` (from hk_draw_stats table)
- Add: `griffin_flag` (binary — debut HK horse)
- SQPE output → Benter overlay using HKJC tote odds as market prior

Benter calibration: run `benter.calibrate()` on holdout set to find optimal α/β for HK market.  
Current defaults: α=0.9, β=1.1 (from Benter 1994 paper — will likely differ for HK tote structure)

Output: `models/specialist/sqpe_v1_hk/sqpe_v1_hk.pkl + metadata.json`  
Output: `models/specialist/benter_v1_hk/benter_v1_hk_calibration.json` (α, β, log-loss)

---

## 8. Phased Delivery Plan

### Phase 1 — Cold Archive Activation (1-2 days)
**Goal:** Start collecting live FR and HK data immediately. No scoring yet.

Tasks:
1. Fix `os` import bug in both dead workers (both reference `os.getenv` without importing `os`)
2. Move workers from `archive/dead_workers/` to `workers/`
3. Test ingest for recent date (FR: yesterday, HK: last race day)
4. Verify Supabase `fr_research` and `hk_research` schemas exist; create missing tables
5. Schedule daily crons in Railway (or local cron for now)

Deliverable: Live FR + HK data flowing into cold storage daily.

### Phase 2 — Feature Engineering + Signal Audit (5-7 days)
**Goal:** Build the FR and HK feature adapters. Confirm signal quality on live data.

Tasks:
1. Build `scripts/intl/build_fr_features.py` — FR feature adapter
2. Build HKJC sectional scraper `scripts/intl/scrape_hkjc_sectionals.py`
3. Build `scripts/intl/build_hk_features.py` — HK feature adapter
4. Build penetrometer going mapping table (hardcoded dict, 10 lines)
5. Run signal audit: for 90 days of live FR + HK data, compute feature → target correlations
6. Confirm: draw_bias at Sha Tin, class_trajectory at HV, penetrometer at Chantilly

Deliverable: FR and HK feature dicts comparable to UK v17 output.

### Phase 3 — Shadow Model Training (3-5 days)
**Goal:** Train FR and HK specialist models on existing parquet data.

Tasks:
1. Build `scripts/intl/train_fr_model.py` using parquet FR rows
2. Build `scripts/intl/train_hk_model.py` using parquet HK rows
3. Calibrate Benter model on HK holdout set
4. Validate holdout AUC, VP band monotonicity, favourite SR calibration
5. Compare FR model VP bands vs actual FR results (same methodology as UK evidence audit)

Deliverable: `sqpe_v1_fr.pkl`, `sqpe_v1_hk.pkl`, `benter_v1_hk_calibration.json`

### Phase 4 — Shadow Scoring + Evidence Accumulation (ongoing)
**Goal:** Run shadow scoring daily for both jurisdictions. Accumulate 300+ results per jurisdiction before any promotion discussion.

Tasks:
1. Build `scripts/intl/score_fr_today.py` — FR shadow scorer
2. Build `scripts/intl/score_hk_today.py` — HK shadow scorer + Benter overlay
3. Build `scripts/intl/run_fr_sigma.py` — FR sigma audit
4. Build `scripts/intl/run_hk_sigma.py` — HK sigma audit
5. Extend Mission Control to show FR + HK shadow lanes

Evidence gates (same structure as UK CPU Gate V2):
- Gate 1 (n=150): First review — VP band analysis, SR vs favourite SR, top-decile
- Gate 2 (n=300): Full evidence review — all metrics, Benter calibration check
- No promotion discussion until Gate 2

---

## 9. Governance Rules (International — Permanent)

```
SHADOW ONLY until Gate 2 passed per jurisdiction
No FR or HK verdicts in Telegram morning brief
No fr_research or hk_research tables mixed into public.* or velo_*
No model promotion without operator decision
No staking, no Betfair, no exchange integration
May 20 (SCORING_FLATLINE_CONTAMINATED) exclusion applies only to UK pipeline
FR and HK evidence gates are independent of UK CPU Gate V2
All credentials in .env only
fr_ingestion schema: fr_research.* ONLY
hk_ingestion schema: hk_research.* ONLY
```

---

## 10. The One Thing That Will Make or Break Each Jurisdiction

**France:** The penetrometer going number. French going is systematically firmer than the UK equivalent text label suggests. A horse with a UK going preference for "Good to Firm" that runs on French "Bon (3.8 penetrometer)" is NOT on preferred going — it's on genuine Good to Firm equivalent. Get this mapping table right and the going_fit_score becomes a genuine signal in FR. Get it wrong and it adds noise.

**Hong Kong:** The draw. At Sha Tin on the 1200m course C+3 configuration, draws 1-4 win at 2-3x the rate of draws 9-14. This is the most exploitable structural edge in HK racing and it is publicly available data from HKJC. Build the draw bias table in Phase 2. If sectional times confirm pace shape supports the draw position, the confidence multiplies.

---

## 11. External Data Source Reference Checklist (Updated — Racing API Unavailable)

**Racing API access has been removed as of 2026-05-23. Workers are BLOCKED on Racing API dependency.**

| Source | URL | Auth | Priority | Status | Phase |
|---|---|---|---|---|---|
| PMU API (unofficial) | `online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}` | None | P1 FR | FREE — primary | Phase 1 |
| HKJC Official | `racing.hkjc.com` | None | P1 HK | FREE — primary | Phase 1 |
| HKJC Sectionals | `racing.hkjc.com/en-us/local/information/displaysectionaltime` | None | P1 HK | FREE | Phase 2 |
| HKJC Draw Stats | `racing.hkjc.com/en-us/local/horse-racing/draw-statistics` | None | P1 HK | FREE | Phase 2 |
| France Galop (Valeur) | `france-galop.com/fr/programme-et-resultats` | None (scrape) | P2 FR | FREE | Phase 2 |
| Renavon (HK odds) | `renavon.com` | Subscription $99+/mo | P3 HK | OPTIONAL | Phase 3 |
| Racing & Sports AU | `racingandports.com.au` | Subscription ~$40/mo | P3 FR/HK | OPTIONAL | Phase 3 |
| Apify HKJC | `apify.com` | API key ~$20/mo | P4 HK | FALLBACK | Phase 2 |
| Racing API (FR/HK) | `api.theracingapi.com` | Basic Auth | — | **UNAVAILABLE** | Blocked |

---

## 12. Phase 0 Audit Trail

All Phase 0 documents:

| Document | Purpose | Verdict |
|---|---|---|
| `data/reports/raceform_v17_international_profile.json` | Full parquet coverage profile | 255,862 target rows confirmed |
| `data/reports/raceform_v17_international_profile.md` | Human-readable profile | All 7 courses TRAINING_SAFE |
| `data/reports/international_signal_baselines_latest.json` | Signal correlation audit | RPR primary, OR absent in FR, TS absent in HK |
| `data/reports/international_signal_baselines_latest.md` | Signal audit report | Auteuil classified FR_JUMPS |
| `data/reports/international_row_count_reconciliation_latest.json` | Row count gap explanation | 14,881 gap = Meydan UAE — RECONCILED |
| `data/reports/international_baseline_arena_latest.json` | Offline model viability | All 5 packs VIABLE_SHADOW_CANDIDATE |
| `data/reports/international_baseline_arena_latest.md` | Arena results report | LightGBM AUC 0.90–0.96 across all packs |
| `docs/audit/FR_HK_HISTORICAL_PERFORMANCE_AUDIT.md` | Historical claim check | HISTORICAL_RESULT_CLAIM_UNVERIFIED_BUT_TRAINING_DATA_EXISTS |
| `docs/audit/INTL_INGEST_WORKER_AUDIT.md` | Worker readiness | ARCHIVE_ONLY_NOT_ACTIVATED |
| `docs/audit/INTL_SCHEMA_MIGRATION_PREFLIGHT.md` | Migration review | MIGRATION_READY — not yet applied |
| `docs/audit/INTERNATIONAL_ROW_COUNT_RECONCILIATION.md` | Row count reconciliation | RECONCILIATION_COMPLETE |
| `docs/engineering/INTL_FEATURE_CONTRACT_V1.md` | Feature availability by jurisdiction | HK/FR mandatory + banned features locked |
| `docs/engineering/INTL_SCHEMA_MIGRATION_APPROVAL_PACKET.md` | Migration approval packet | AWAITING_OPERATOR_APPROVAL |
| `docs/engineering/INTL_WORKER_REPLACEMENT_PLAN_V1.md` | Worker replacement strategy | HKJC P1, PMU P2, Parquet P0 done |
| `scripts/audit_international_signal_baselines.py` | Repeatable signal audit | Run anytime to refresh |
| `scripts/audit_international_baseline_arena.py` | Offline model viability test | Repeatable — no live state |

### Phase 1A Offline Baseline Arena Results

Temporal split: Train 2015-2022, Valid 2023, Test 2024-2025. LightGBM best model per pack.

| Pack | Test Rows | Fav SR | Best AUC | Best SR | Beats Fav | Verdict |
|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | 10,451 | 34.7% | **0.9541** | 81.5% | YES | **VIABLE_SHADOW_CANDIDATE** |
| HK_HAPPY_VALLEY_V1 | 5,987 | 26.9% | **0.9591** | 84.3% | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_CHANTILLY_V1 | 8,009 | 29.4% | 0.9072 | 64.5% | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_FLAT_CORE | 23,225 | 29.7% | 0.9076 | 68.6% | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_AUTEUIL_JUMPS_V1 | 4,810 | 27.5% | 0.9051 | 67.3% | YES | **VIABLE_SHADOW_CANDIDATE** |

**Top features confirmed across packs:** `rpr_num`, `rpr_vs_field`, `or_num` (HK only), `ts_num` (FR flat only), `wgt_lbs`, `field_size`.
**Leakage status:** CLEAN — no SP/odds-derived features used.
**Governance:** OFFLINE ONLY — no DB writes, no scoring pipeline, no live state.

---

## 13. Phase 0 Final Classification

```
VELO_INTERNATIONAL_PHASE0_COMPLETE
FR_HK_TRAINING_SUBSTRATE_VERIFIED: 255862 rows, 7 courses, 22122 races
ROW_COUNT_RECONCILIATION_COMPLETE: 14881_gap=Meydan_UAE
JURISDICTION_PACKS_DEFINED: FR_FLAT_CORE, FR_AUTEUIL_JUMPS_V1, HK_SHA_TIN_V1, HK_HAPPY_VALLEY_V1
OFFLINE_BASELINE_ARENA_COMPLETE: ALL_5_PACKS_VIABLE_SHADOW_CANDIDATE
  HK_SHA_TIN_V1: AUC=0.9541
  HK_HAPPY_VALLEY_V1: AUC=0.9591
  FR_CHANTILLY_V1: AUC=0.9072
  FR_FLAT_CORE: AUC=0.9076
  FR_AUTEUIL_JUMPS_V1: AUC=0.9051
FEATURE_CONTRACT_LOCKED: INTL_FEATURE_CONTRACT_V1.md
MIGRATION_READY_NOT_APPLIED: AWAITING_OPERATOR_APPROVAL
WORKERS_ARCHIVE_ONLY_NOT_ACTIVATED
RACING_API_UNAVAILABLE
NO_LIVE_DEPLOYMENT
AUTEUIL_CLASSIFIED_JUMPS_SEPARATE_FROM_FLAT
DRAW_BIAS_CONFIRMED_SHA_TIN
OR_ABSENT_FRANCE
TS_ABSENT_HK_AND_AUTEUIL
RPR_PRIMARY_CROSS_JURISDICTION_SIGNAL
FIRST_PACK_BUILD: HK_SHA_TIN_V1
SECOND_PACK_BUILD: FR_CHANTILLY_V1
```

---

**Generated:** 2026-05-23
**Phase 0 status:** COMPLETE
**Phase 1A status:** COMPLETE — offline arena run, all 5 packs viable
**Phase 1B:** PENDING — operator approval required before migration
**Phase 1C:** NOT STARTED — HKJC + PMU workers not yet built
**Next action:** Operator decision: approve migration + worker builds, or continue offline model development only
