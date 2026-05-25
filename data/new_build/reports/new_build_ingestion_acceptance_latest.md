# New Build Ingestion Acceptance Audit

Generated: 2026-05-25 | RPR Boundary: PASS | live_velo_touched: false | shadow_velo_touched: false

---

## Summary

| Category | Count |
|----------|-------|
| Fields accepted into New Build spine | 37 |
| Fields banned (RPR + leakage) | 5 |
| Fields present in source but NOT YET WIRED | 26 |

RPR violations in spine: **0** — boundary confirmed clean.

---

## Currently Accepted Fields (Racing API + RP Racecard + RPDC)

### Racing API Racecard

horse, horse_id, trainer, trainer_id, jockey, jockey_id, owner, owner_id, sire, dam, damsire, age, sex, draw, headgear, wind_surgery, days_since_run, form_figures, race_class, race_type, distance, going, surface, course

**Archive-only labels (stored but not emitted as predictor features)**:
- `official_rating_archive_only` — OR stored, labeled archive
- `topspeed_archive_only` — TS stored, labeled archive

### Racing API Results

position, won (derived), framed (derived), sp (outcome context), ts_archive_only, comment_archive_only

### RP Racecard Injection

All racecard fields plus: headgear_first_time, gelding_first_time, wind_surgery, newspaper_tip_count, spotlight_comment_present, newspaper_comment_present

### RPDC Backfill

rpdc_tags, rpdc_primary_tag, rpdc_release_score_avg, rpdc_cash_window_count

### Derived Feature Flags (assembled in features.py)

trainer_win_rate, trainer_frame_rate, jockey_win_rate, jockey_frame_rate (from runner_results.jsonl history), archive_flag_count, has_human_context, tip_heat_flag, pedigree_context_flag, outcome_linked

---

## Banned Fields (never enter predictor)

| Source | Field | Reason |
|--------|-------|--------|
| Racing API card | rpr | RPR_ARCHIVE_ONLY boundary — rpr_feature_allowed=False |
| Racing API results | rpr | RPR_ARCHIVE_ONLY boundary |
| RP racecard injection | rp_rpr_archive_only | RPR boundary — rp_rpr_velo_allowed=False |
| RP form history | rpr_rating | RPR boundary — stored in JSON, never enters predictor |
| Any source | sp (pre-race) | BANNED_FEATURE_KEYS in features.py — post-race leakage risk |

---

## Fields Present in Source But NOT YET WIRED to New Build

These are available in the data but not yet connected to the New Build spine:

### RP Form History (161 horses, 2,228 runs — May 26-27 captures)

| Field | What It Enables |
|-------|----------------|
| sp_dec (career SP per run) | SP trajectory, market confidence history |
| position (career) | Win/place/loss pattern across career |
| field_size | Competitive context per run |
| course_name / course_rp_uid | Course affinity, specialist detection |
| distance | Distance preference |
| going | Going preference (soft/good/firm) |
| jockey_rp_uid (per run) | Jockey continuity/change signal |
| beaten_margin | Run quality quantification |
| result_type (WIN/PLACED/LOSS) | Clean classification target |
| ts_rating (career TS) | Speed figure trajectory |
| or_rating (career OR) | Class level progression |
| weight_lbs | Weight pattern |
| gear | Equipment history sequence |

### RP Horse Profile (not yet extracted)

| Field | What It Enables |
|-------|----------------|
| trainer_last_14_runs/wins/percent | Trainer current form (live signal) |
| sire_avg_flat_win_distance | Pedigree distance specialization |
| dam_sire_avg_win_distance | Maternal pedigree context |
| trainer quotes / stable tour quotes | Trainer intent (exclusive RP signal) |

### Large Parquets (not yet ingested)

| File | Potential |
|------|-----------|
| raceform_clean.parquet (~374K rows) | Full historical training dataset |
| raceform_v17_features.parquet (~200K rows) | v17 derived features (leakage risk if used as inputs) |

---

## RPR Boundary Statement

RPR (Racing Post Rating) is stored in all sources under archive-only labels. It is **never** emitted as a predictor feature. The `rpr_feature_allowed` and `rp_rpr_velo_allowed` flags are hardcoded `False` on every row in the New Build spine. The `BANNED_FEATURE_KEYS` set in features.py includes `rpr`, `rpr_archive_only`, and `rp_rpr_archive_only`. Audit confirms **zero RPR violations** in the current normalized spine.

No live VELO, Shadow VELO, scoring, or model promotion touched.
