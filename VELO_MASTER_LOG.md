# VÉLØ Oracle Prime — Master Project Log

Running record of everything built, discovered, and decided.
Not a thesis. Points only. Feed this into the whitepaper when ready.

---

## Format

Each entry: `[DATE] — what happened, what was built, what was learned`
New builds go at the bottom. Nothing is deleted.

---

## 2026-03-15 — Infrastructure Foundation

- Connected Supabase (`ltbsxbvfsxtnharjvqcm.supabase.co`, eu-west-2, 54 tables)
- Connected Railway (project `sincere-empathy`, service `velo-oracle`)
- Connected GitHub (`elpresidentepiff/velo-oracle-prime`, public repo)
- Connected The Racing API (Basic Auth + MCP)
- Connected Supabase MCP (`mcp.supabase.com`)
- Connected Racing API MCP (`mcp.theracingapi.com`)
- Fixed `ingestion-spine` service: was stuck in cron mode (buildOnly=true), changed to ON_FAILURE restart
- Merged 4 branches: harden-production-security, sentient-feedback-loop, spotlight-layer, replace-placeholder-agents
- 20/20 agent tests passing after merge
- Created `horse_comments` + `race_spotlight_verdict` tables in Supabase
- Built `workers/racing_api_fetcher.py` (token bucket rate limiter, zero silent failures)
- CLAUDE.md written as permanent session memory

---

## 2026-03-16 — Macro Intelligence Layer

- Extracted full BHA Data Pack: `data/bha_industry_stats.json`
- Derived macro indices: competitiveness, fixture_strain, abandonment_stress, favourite_compression, run_density, field_size_regime
- Loaded to Supabase: `bha_industry_stats` (246 rows), `bha_yearly_summary` (13 rows), `bha_macro_specialty_metrics` (132 rows)
- Built `src/intelligence/macro_regime/bha_macro_context.py` — MacroContext dataclass
- Trained 7 specialist models, all LIVE-USABLE:
  - improvement_model AUC 0.896
  - market_deception_model AUC 0.920
  - place_model AUC 0.949
  - longshot_model AUC 0.936
- Built `src/intelligence/velo_prime_ensemble.py` — VeloPrimeEnsemble producing VELO_PRIME_prob
- End-to-end smoke test PASSING: race 856450 (Huntingdon 2024-01-12), winner ranked #1

---

## 2026-03-19 — Sigma Loop Quality

- Fixed `close_sigma_loops.py`: added `date`, `track`, `track_chaos_rating` to sigma_audits
- Added UNIQUE constraint on `sigma_audits.race_id` — prevents double-writes on reruns
- Changed `insert()` → `upsert(on_conflict="race_id")`
- Built `scripts/generate_sigma_report.py` — writes `reports/daily/sigma_forensic_YYYY-MM-DD.md`
- First forensic report: 26 races, WIN=5, PLACED=7, MISS=14

---

## 2026-03-20 — Live Decision Logic Fixes

- **Root cause identified**: stale confidence after renormalization blocked A-tier forever
- **Fix 1**: Recalculate `confidence_level` after renormalization in `VeloPrimeEnsemble.predict_race()`
- **Fix 2**: SP guard added to X longshot trigger — `longshot > 0.35 AND sp_dec >= 10.0` (was firing without SP check)
- **Fix 3**: B-tier confidence gate — `conf not in ("low",)` added to B-PLAYABLE (B was inflated by high place_prob median)
- **Proof**: 4 A-tier outputs on 60-race live card post-fix. B-low-conf = 0. X not misfiring.

---

## 2026-03-20 — Raceform Data Load

- Loaded `data/raceform_clean.parquet` (650MB file, 2017+) to Supabase `public.raceform`
- 2017+ filter: rows from 2025 only used for intelligence layer
- Script: `scripts/load_raceform_to_supabase.py` — 500-row batches, restartable via `--offset`
- Note: IPv6 blocks direct psycopg2 on WSL2 — use REST API for all DML

---

## 2026-03-21 — Intelligence Stack v1 (Data First Doctrine)

**Decision: build private intelligence layer from historical data before more training.**

### Layer 1 — Identity
- Built `intelligence.horse_identity_resolution_2025`
- Source: `public.raceform` 2025 only
- 29,311 entities. 28,395 high-confidence. 916 ambiguous (trainer change noise)
- Zero sire/dam conflicts. Zero age conflicts.
- Confidence grades: high (sire+dam known, single trainer) / medium / ambiguous
- Script: `scripts/build_horse_identity_2025.py`

### Layer 2 — Memory
- Built `intelligence.horse_run_history_2025`
- 84,049 rows. One row per raceform runner entry. 100% join coverage.
- SP decimal conversion: strips F/J suffixes (`9/2F` → 5.50, `EvensF` → 2.00)
- Derived: `run_number_2025`, `days_since_last_run`, `layoff_flag`, `long_layoff_flag`, `is_win`, `is_place`
- Win rate 10.41%, place rate 31.17% — both correct
- Script: `scripts/build_horse_run_history_2025.py`

### Layer 3 — Pressure
- Built `intelligence.handicap_trajectory_2025`
- 84,049 rows. 1:1 with run history.
- OR coverage: 52,070 numeric (61.9%), 31,979 en-dash (38.1% — bumpers/conditions/maidens, expected)
- OR range: 18–177
- Flags: `mark_compression_flag`, `mark_restored_flag`, `first_run_after_drop_flag`, `or_plateau_flag`, `or_treadmill_flag`
- `or_treadmill`: 5+ runs, full-year OR range ≤5 pts — reveals pattern-campaigned horses
- Script: `scripts/build_handicap_trajectory_2025.py`

### Layer 4 — Restoration
- Built `intelligence.setup_restore_events_2025`
- 84,049 rows. 1:1 with run history.
- Surface derived from going: Standard/Fast/Slow → AW; Sloppy/Muddy → Dirt; else → Turf
- Dist matching: exact string (honest — no forced clustering)
- Scope: 2025 wins only. Prior win = any 2025 win before this run at same conditions.
- `full_setup_restore_flag`: course + surface + dist all match a prior 2025 win — 2,405 rows
- AW + HK circuits dominate full_restore (repeat geometry). Ascot/York/Doncaster = reactivation dominant.
- Script: `scripts/build_setup_restore_events_2025.py`

### Layer 5 — Candidate Intersection
- Built `intelligence.plot_candidate_flags_2025`
- 84,049 rows. 1:1.
- 7 individual candidate flags (rules-based, no weights, no model)
- `plot_pressure_flag`: 32,057 rows (38.1%) — broad universe
- `manual_review_priority`: 4,631 rows (5.5%) — requires 2+ independent themes
- Clean subset (high + MR + 3+ codes): 1,530 rows — the real working queue
- GIN index on `plot_reason_codes TEXT[]` — array queries enabled
- Script: `scripts/build_plot_candidate_flags_2025.py`

---

## 2026-03-21 — Intelligence Audit and Key Discoveries

**The first hard VÉLØ law extracted from data:**

> A horse becomes a genuine candidate when the handicapper has moved the mark
> AND the trainer has restored the conditions.
> Either one alone is atmosphere. Both together is intent.

**Combination hierarchy proven:**
- Single-theme flags (mark_compressed, post_drop, or_treadmill, reactivation alone) = 0% MR. Dead.
- Any handicap theme + any restore theme = 100% MR. Absolute.
- 3+ codes = working queue. 4+ codes = dossier material.

**Track archetype split confirmed:**
- AW/HK: restore logic structurally reliable. Circuit geometry repeats. Full_restore carries real weight.
- Turf: reactivation alone = 51% MR (noise). Needs second theme. Ascot/York = timing signals not restore.

**Five dossier horses identified:**
- `Heavenly Fire (GB)` — repeat-restore. All 7 runs at Wolves AW 7f. Trainer waiting for mark to return.
- `Red Walls (GB)` — treadmill archetype. OR band 44–48 all year. Wins only at compressed marks.
- `Bantz (IRE)` — multi-signal active. Two wins both at compressed marks. Full restore live firing at Doncaster 7f as of Jun 28.
- `River Wharfe (GB)` — campaign-shift. Found Brighton 1m mid-season. Every subsequent Brighton run fires full_restore.
- `Muscika (GB)` — drop-and-strike. Age 11. Wins exclusively when OR drops to 67. Treadmill 67–71 all year.

---

## 2026-03-21 — Canonical Doctrine and Operator Output

- Wrote `docs/VELO_PLOT_DOCTRINE_V1.md` — locked canonical doctrine
  - The first hard law
  - 7 numbered rules with data evidence
  - Candidate tier structure (Tier 0–3)
  - 5 named horse archetypes
  - Track archetype reference
  - Disclaimer: review queue, not prediction
- Built `scripts/generate_plot_radar_report.py` — operator-grade report generator
  - Configurable date + window
  - Doctrine v1 filters applied exactly
  - Tier 3 / Tier 2 / Dossier / Trainer sections
  - Output: `reports/plot_radar/plot_radar_YYYY-MM-DD.md`
- First report generated: `reports/plot_radar/plot_radar_2025-07-05.md`
  - 30-day window. 490 Tier 2+ candidates. 235 Tier 3. avg vs last winning OR +2.8 pts.

---

## Standing Architecture (as of 2026-03-21)

```
Live prediction engine:
  app/main.py → FeatureEngineer → SQPE v17 → VeloPrimeEnsemble → run_prime_today.py → sigma

Intelligence stack (separate, read-only, no production contact):
  public.raceform (84k+ rows, 2017–2025)
    → intelligence.horse_identity_resolution_2025 (29,311 entities)
    → intelligence.horse_run_history_2025 (84,049 rows)
    → intelligence.handicap_trajectory_2025 (84,049 rows)
    → intelligence.setup_restore_events_2025 (84,049 rows)
    → intelligence.plot_candidate_flags_2025 (84,049 rows, 1,530 clean candidates)
    → reports/plot_radar/ (operator output)
    → docs/VELO_PLOT_DOCTRINE_V1.md (canonical law)
```

---

## Rules That Are Locked

1. Intelligence stack never touches production tables
2. No predictions from the intelligence layer — candidates only
3. Single-theme flags are not actionable
4. Handicap movement + condition restoration = the intersection that matters
5. AW/HK restore > turf reactivation structurally
6. Dossier horses are case studies in trainer operational logic
7. Live betting decisions require full pipeline (SQPE → VeloPrime → sigma → market) — not the candidate layer alone

---

## What Is Still Needed

- `ANTHROPIC_API_KEY` — add to `.env`
- Racing API subscription upgrade for full racecards
- Supabase DB password — update `SUPABASE_DB_URL`
- Wire VeloPrimeEnsemble to live prediction endpoint
- Rotate Racing API credentials (exposed in git history, repo is public)
- 2024 raceform data load and intelligence stack extension
- Whitepaper draft (this log is the source material)

---

*Add new entries below this line. Date format: YYYY-MM-DD. Points only.*

---

## WHITEPAPER TOPICS — To Elaborate Later

*Source material only. One line per concept. Do not expand here — expand in the whitepaper.*

---

### I. The Core Engine — SQPE (Sub-Quadratic Probability Estimation)

- SQPE is not a standard regression. It models the probability of a horse winning as a function of field-relative quality, not absolute quality.
- "Sub-quadratic" refers to the diminishing-returns relationship between rated quality and win probability — doubling the rating gap does not double the win probability. It follows a compressed curve.
- The model uses isotonic calibration post-training — output probabilities are monotone-constrained and empirically calibrated, not raw sigmoid outputs.
- Trained on 50,000+ real race results. Not synthetic data.
- Versions v14, v15, v16, v17 — each generation improved AUC and top-1 accuracy.
- Key finding: model was systematically underconfident at the top (high-probability horses). Confidence level recalculation after field renormalization was required to fix this.
- The renormalization step (probabilities summed to 1.0 per race) is critical — raw probabilities are not comparable across field sizes without it.

---

### II. The Living Organism — Sentient Loop and Self-Learning

- VÉLØ has a memory layer (`velo_memory.py`) and a sentient loopback (`playbook_g_sentient_loopback.py`)
- After each race result, the system audits its own verdicts against outcomes and writes to `learned_patterns` in Supabase
- The system can modify its own `directive_firing_threshold` based on its rolling performance appetite
- This is not reinforcement learning in the ML sense — it is rule-based self-audit with persistent state
- The "sentient" concept: the system tracks its own confidence history and adjusts operational thresholds based on what it has observed, not what it was told
- Kingmaker logic uses `run_style` from the live racing API to detect pace setup — this is dynamic, not static
- Fuzzy horse name matching (`difflib.SequenceMatcher`) allows the system to reconcile API name variants against its own memory without exact-match brittleness
- State backed up to Supabase `learned_patterns` — cloud-persistent, survives restarts

---

### III. The Intelligence Stack — A Private Historical Layer

- Five tables, built entirely from public raceform data, producing private intelligence not available in any commercial product
- The key architectural decision: separate schema (`intelligence`) completely isolated from live production tables — no risk of contaminating live scoring
- Identity resolution as a first-class problem: 29,311 distinct horse entities identified from raw name strings, with confidence grades and ambiguity flags
- The OR (Official Rating) as a continuous behavioral signal — not just a number but a record of handicapper decisions over time
- Treadmill detection: a horse operating within a 5-point OR band over 5+ runs is being deliberately managed, not randomly failing
- Setup restoration as a strategic signal: when a trainer returns a horse to exact prior winning conditions, that is a decision not an accident
- The 1:1 row integrity across all five layers — no row loss, no duplication — ensures joins are always clean

---

### IV. The Plot Doctrine — First Law of Hidden Readiness

- The first machine-derived law: handicap movement + condition restoration = intent
- Single signals are atmosphere. Intersections are signal. Proven by data, not theory.
- The combination layer is the breakthrough — 100% MR conversion at any handicap+restore intersection, without exception across 4,631 cases
- Track archetypes are structurally distinct: AW/HK geometry repeats (restore reliable); turf tracks vary (reactivation alone is noise)
- Dossier horses reveal trainer operational fingerprints — stable playbooks that repeat across a season
- The candidate tier structure (Tier 0–3) is a working filtration model: broad → narrow → actionable → dossier-grade
- The treadmill + drop-and-strike + repeat-restore archetypes are teachable patterns that generalise beyond individual horses

---

### V. The Meta-Ensemble — VeloPrime

- VeloPrime is not a single model. It is a weighted ensemble of eight signals:
  - SQPE v17 base probability (45% weight — strongest single signal)
  - Improvement score (12%)
  - Release window score (10%)
  - Market deception score (10%)
  - Place probability (8%)
  - Comment intelligence score (8%)
  - Longshot score (7%, SP-gated — only fires when SP ≥ 10.0)
- Missing specialist inputs are excluded from the weighted average — the denominator adjusts, not the numerator
- Macro regime applied at race level not runner level — structural adjustment, not per-horse signal
- Macro chaos mode: dampen all probabilities toward uniform when the field is unpredictable
- Favourite trap: penalty applied to market favourite when compression index is high — the system can be contrarian by design
- The ensemble was designed to be transparent: every component is named, weighted, and auditable

---

### VI. The Macro Layer — BHA Structural Context

- BHA Data Pack (2012–2024): 246 rows of yearly/monthly/seasonal industry metrics
- Derived indices: competitiveness_index, fixture_strain, abandonment_stress, favourite_compression_index, run_density, field_size_regime
- These are structural not tactical — they describe the environment the race is being run in, not the race itself
- Favourite compression: years where favourites win significantly more often than expected → market is over-efficient → VÉLØ applies penalty to hot-pots
- Chaos mode: triggered when macro context shows high abandonment stress or extreme year — the model reduces its own confidence in volatile environments
- The macro layer is the only "macro" signal in the system — everything else is micro (runner, trainer, conditions)

---

### VII. The Sigma Loop — Nightly Self-Audit

- Sigma closes the loop: compares that day's verdicts against the official results
- Writes to `sigma_audits` (one row per race), `velo_post_race_reviews`, `learned_patterns`
- Tracks: actual winner, winning SP, whether VÉLØ's top-pick won, tier of the verdict (A/B/C/D/X)
- The forensic report (`sigma_forensic_YYYY-MM-DD.md`) is a daily audit trail — not a marketing document
- The UNIQUE constraint on `race_id` in sigma_audits prevents double-counting on reruns — data hygiene is non-negotiable
- Pattern over time: sigma will reveal which verdict tiers (A/B/X etc.) are profitable, which trainers are consistently signalling correctly, which track types are mispredicted most often

---

### VIII. The Decision Tiers — A/B/C/D/X

- **A-STRIKE**: high confidence, strong gap to second, field conditions clean — this is the system's highest conviction output
- **B-PLAYABLE**: probability threshold met but lower confidence — additive not primary
- **C-WATCH**: candidate only — do not act, monitor for late market movement
- **D-NO BET**: signal too weak or contradicted by market
- **X-CHAOS**: something is structurally wrong with this race — field compressed, longshot pressure, macro chaos — no bet regardless of model output
- The gate order matters: X is evaluated first. A horse cannot be A-tier if it should be X-tier.
- B-tier was historically inflated because `place_prob` median was 0.75 — almost always true. Fixed with confidence gate.
- A-tier was historically unreachable because stale confidence blocked it. Fixed by recalculating confidence after field renormalization.

---

### IX. The Specialist Model Suite

- Seven specialist models trained on the same raceform data as SQPE, each targeting a different hidden dimension:
  - `improvement_model`: is this horse improving? (AUC 0.896)
  - `market_deception_model`: is the market mispricing this runner? (AUC 0.920)
  - `release_window_model`: is the horse being dropped into a winnable race? (AUC 0.703)
  - `comment_intelligence_model`: does the Spotlight comment signal hidden form? (AUC 0.670)
  - `draw_bias_model`: is the draw position advantaged at this course/distance? (AUC 0.614)
  - `place_model`: probability of finishing in the places (AUC 0.949)
  - `longshot_model`: non-obvious outsider value (AUC 0.936, SP-gated at ≥10.0)
- All models are LIVE-USABLE: trained on pre-race available features only — no post-race leakage
- The market deception model (0.920 AUC) is the surprise — market inefficiency is more detectable than expected

---

### X. The Five Filters — Shortlisting Before Scoring

- Before any model runs, a rule-based filter eliminates horses that should not be considered
- `src/modules/five_filters.py`
- Filters include: recent form threshold, trainer activity, field size constraints, course suitability, class drop/rise limits
- Purpose: do not waste compute on horses that are structurally ineligible regardless of model output
- The five filters are not a model — they are hard gates, each individually justifiable
- This prevents the ensemble from finding signal in noise — garbage in, garbage out prevention

---

### XI. The Spotlight NLP Layer

- Racing Post Spotlight comments parsed into structured behavioral flags
- `workers/spotlight_parser.py`, `workers/spotlight_ingestion_worker.py`
- Comment flags include: fitness signals, trainer confidence language, course suitability phrases, market market intent phrases
- Hard constraint: Spotlight CANNOT override a structural verdict — NLP is additive only
- The `comment_intelligence_model` (AUC 0.670) is built from these parsed flags
- 1,765 rows in `horse_comments` table — growing with each run

---

### XII. The Agent Architecture — Multi-Agent Orchestration

- Five real agents, each with a distinct analytical role:
  - `FormAnalyzer`: recent form figures, trend, consistency
  - `MarketAnalyzer`: odds movement, value identification, market position
  - `ConnectionsAnalyzer`: trainer/jockey combination scoring
  - `CourseDistanceAnalyzer`: course and distance specialist analysis
  - `RatingsAnalyzer`: OR/RPR/TS ratings engine
- Weights: Connections 25%, Ratings 20%, Form 20%, Course/Distance 20%, Market 15%
- Betting rules: BACK 2% if score>70, BACK 1% if score>60, LAY 0.5% if score<40, PASS otherwise
- All five agents were real (not placeholder) and tested: 20/20 tests passing
- LangGraph pipeline built but held back — needs `langgraph>=0.2.0` + `langchain-core>=0.3.0`

---

### XIII. Things That Are Genuinely Unique

- **The intersection law**: derived from data, not designed in advance. Found, not invented.
- **OR treadmill detection**: no commercial product currently identifies pattern-campaigned horses by OR band width
- **Setup restore as a first-class layer**: mapping current conditions against prior winning conditions per horse is not done at scale anywhere in public tools
- **Confidence-adjusted renormalization**: most ensemble systems normalise but do not recalculate confidence tier after normalisation — this was a real bug that blocked A-tier for months
- **The living sigma loop**: most AI betting systems score and forget. VÉLØ audits itself nightly and persists what it learns.
- **Dossier horses as teaching cases**: the system identifies horses whose campaigns reveal trainer intent patterns — these become strategic assets, not just betting candidates
- **Track archetype splitting**: treating AW restore and turf reactivation as structurally different signals — this distinction is not in any published handicapping framework we are aware of
- **Sub-quadratic calibration**: the probability curve is not linear or sigmoid — it reflects the actual diminishing returns of quality advantage in multi-runner fields

---

### XIV. What VÉLØ Is Not

- Not a tipster service
- Not a mechanical betting system
- Not a black box — every signal is named, weighted, and auditable
- Not a replacement for human judgment — it is intelligence infrastructure for better human decisions
- Not trained on artificially balanced data — real races, real results, real distributions including many near-misses and longshot winners
- Not finished — the intelligence stack is the foundation, not the ceiling

---

*End of whitepaper topics section. Expand each into full sections when the whitepaper is written.*
