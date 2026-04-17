# VÉLØ — Lessons Learned

## 2026-03-16

### L001 — Model metrics require realism audit before celebration
AUC 0.94 / Top-1 73.7% triggered suspicion. Full audit ran. Passed: chronological split, zero label leakage, race-level confirmed. Mode A (ratings only, no SP): Top-1 75.9% — model is genuine horse intelligence, not market echo. Rule: any AUC > 0.85 or Top-1 > 50% must go through the 9-check audit protocol before production claim.

### L002 — Cache expensive doctrine features immediately
v17 doctrine computation across 195k horses = 30-40 min. We recomputed it twice (training + audit attempt) before caching to parquet. Rule: after any full-corpus feature engineering, save to data/raceform_v17_features.parquet before anything else. Never recompute from scratch unless source data changes.

### L003 — O(n²) per-horse lookback stalls on long-career horses
The course/going/distance fit inner loop (for j in range(i)) is O(n²) per horse. A horse with 200 career runs = 20,000 comparisons. Multiplied across 195k horses it can stall for 4+ hours. Rule: vectorise or limit lookback window to last N runs (e.g. last 20) for any O(n²) per-horse operation.

### L004 — rpr_vs_field dominates (37.7% importance)
RPR relative to the field is by far the most predictive single feature. implied_prob is third (10.9%). SP features add noise, not signal — Mode A outperforms Mode C by 2.1pp. Rule: ratings-first architecture. Market features are supplementary, not primary.

### L005 — Model is underconfident at the high end
When model assigns 56.7% probability, actual win rate is 61.6%. Gap: +4.9pp. Rule: high-confidence signals can be trusted even more than stated. Consider upward calibration adjustment for top-decile predictions.

### L006 — 1.7M row corpus (raceform.csv) is the primary training asset
34x more data than backtest_50k.csv. 2015-2025. RPScrape format. Encoding: latin-1/utf-8 with replace. Already converted to data/raceform_clean.parquet (131MB). Rule: all new model training uses this corpus first.

### L007 — SP/market features should be excluded from pre-race live models
Final SP is not available at prediction time. Mode B (no raw SP) = Top-1 71.9%. Mode A (no market at all) = 75.9%. Rule: production live models use ratings + doctrine features only. SP/implied_prob reserved for research-only or post-race analysis.

### L008 — CPU-first architecture is correct
GradientBoostingClassifier (sklearn) is sequential, CPU-only. For 240 predictions/day, this is correct. No GPU dependency. Runs on Railway free tier, any laptop. Rule: never introduce GPU-dependent models without explicit justification.

### L009 — BHA JSON field names differ from assumed names
The avg_field_size_by_code section uses 'flat_turf' and 'flat_awt', NOT 'flat' and 'aw'. The favourite_market section has no 'win_pct' — it has 'pct_odds_on_and_evens' and 'pct_odds_against' sub-sections. Rule: when reading bha_industry_stats.json, always verify actual field names first (python -c "print(list(d[section]['data'][0].keys()))") before assuming.

### L010 — Abandonment normalisation triggers false chaos on normal weather years
Normalising abandonment rate to [0,1] vs worst year causes 2019 and 2023 (6% abandon rate) to appear near-chaotic. These are normal racing seasons. Rule: chaos_mode must use structured criteria (covid_year flag + fixture_strain_index < 0.72), not a raw abandonment rate threshold.

### L011 — BHA macro data loaded in 3 Supabase tables (Phase A, 2026-03-16)
bha_industry_stats (246 rows), bha_yearly_summary (13 rows), bha_macro_specialty_metrics (132 rows). Raw parquet cache: data/bha_macro_features.parquet (39 rows, 3 codes x 13 years). Load script: scripts/load_bha_to_supabase.py. Cache script: scripts/cache_bha_macro_features.py.

### L012 — Specialist model standalone AUC is misleading
release_window (0.703), comment_intelligence (0.670), draw_bias (0.614) look weak as standalone models. This is expected: they capture regime-specific signals (timing, NLP, draw) that are deliberately excluded from SQPE to prevent washing out. Rule: evaluate specialist models by their ADDITIVE contribution to VELO_PRIME_prob, not standalone Top-1.

### L013 — Place and longshot models are unexpectedly strong
place_model (AUC 0.949, Top-1 75.6%) and longshot_model (AUC 0.936, Top-1 80.6%) outperform SQPE v17 on their respective targets. This makes sense: place_model uses same feature set but with 20% positive rate (vs 10% for win), giving cleaner calibration. Longshot_model works on a pre-filtered subset (sp>=10) where ratings dominate over market. Rule: these two models carry real each-way and big-price betting value.

### L014 — CalibratedClassifierCV + GBM300 takes ~20min per model on 1.4M rows (CPU)
With cv=3 and n_estimators=300, each specialist model trains 4 full GBMs (3 CV folds + 1 final). On 1.4M rows, each GBM takes ~5min CPU → 20min total per model. Rule: for future specialist models, start training in background immediately. Never train sequentially in a blocking call during interactive sessions.
