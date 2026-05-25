# New Build VELO — Data Feed Plan V1

Document date: 2026-05-25
Status: AUDIT COMPLETE — pre-engine run feed classification
Trust policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING

---

## Classification Legend

| Label | Meaning |
|-------|---------|
| **KEEP_NOW** | Clean, available, accepted, low leakage risk — ready for V0 model |
| **KEEP_LATER** | Useful but needs more parsing, linkage, or volume work |
| **ARCHIVE_ONLY** | Store and report — never enters predictor |
| **BANNED** | Hard no — RPR boundary, post-race leakage, or scoring prohibition |
| **MISSING** | Known to exist somewhere, parser does not extract it yet |

---

## KEEP_NOW — Ready for V0 Model

These fields are in the New Build spine, passed the RPR boundary audit, and are available for the first model training run.

| Field | Source | Notes |
|-------|--------|-------|
| horse_key (normalized name) | Racing API racecard | Identity |
| trainer_key | Racing API racecard | Entity key |
| jockey_key | Racing API racecard | Entity key |
| course_key | Racing API racecard | |
| age | Racing API racecard | |
| draw | Racing API racecard | |
| days_since_run | Racing API racecard | Freshness signal |
| has_headgear | Racing API racecard | Boolean flag |
| headgear_first_time | RP racecard injection | First-time equipment |
| gelding_first_time | RP racecard injection | First-time gelding |
| wind_surgery | RP racecard injection | |
| form_figures | Racing API racecard | Last 6 form string |
| race_class | Racing API racecard | |
| race_type | Racing API racecard | |
| distance | Racing API racecard | |
| going | Racing API racecard | |
| surface | Racing API racecard | |
| trainer_win_rate | Derived from results history | |
| trainer_frame_rate | Derived from results history | |
| jockey_win_rate | Derived from results history | |
| jockey_frame_rate | Derived from results history | |
| rpdc_release_score_avg | RPDC backfill (18,554 rows) | |
| rpdc_tag_count | RPDC backfill | |
| rpdc_cash_window_count | RPDC backfill | |
| newspaper_tip_count | RP racecard injection | |
| spotlight_comment_present | RP racecard injection | Boolean |
| has_human_context flag | RP context flags | Derived from spotlight/diomed |
| tip_heat_flag | RP context flags | >6 tips threshold |
| pedigree_context_flag | RP context flags | Sire/dam present |
| archive_flag_count | RP context flags | Total flags |
| outcome_linked (result) | Racing API results | Training label |
| won | Racing API results | Primary training label |
| framed (top 3) | Racing API results | Secondary label |

**Count: ~32 KEEP_NOW fields**

---

## KEEP_LATER — Useful, Needs More Work

### RP Form History Fields (161 horses, 2,228 runs — May 26-27 only)
These exist in `data/race_shape/form_history_*.json` but are not yet connected to the New Build spine. The pipeline to join form history to racecard runners needs to be built (matching on horse_rp_uid or normalized name).

| Field | Upgrade Signal |
|-------|---------------|
| sp_dec (career SP per run) | SP trajectory, historical market confidence |
| position (career all runs) | Win/place/loss pattern beyond last 6 |
| field_size (career) | Competitive context profile |
| course_name per run | Course affinity / specialist detection |
| distance per run | Distance preference derivation |
| going per run | Going preference derivation |
| jockey_rp_uid per run | Career jockey continuity/change signal |
| beaten_margin | Run quality quantification |
| result_type (WIN/PLACED/LOSS) | Clean career classification |
| ts_rating (career TS sequence) | Speed figure trajectory |
| or_rating (career OR progression) | Class level movement |
| weight_lbs per run | Weight pattern |
| gear per run | Equipment usage history |

**Blocker**: No form_history_2026-05-24.json or form_history_2026-05-25.json yet built. Only May 26-27 processed. Also need ingest pipeline to join to New Build spine.

### RP Horse Profile Fields (not yet extracted into spine)

| Field | Upgrade Signal |
|-------|---------------|
| trainer_last_14_runs/wins/percent | Trainer live form (captured per race day) |
| sire_avg_flat_win_distance | Pedigree distance specialization |
| dam_sire_avg_win_distance | Maternal pedigree context |

### Large Parquet Files

| File | Status | Notes |
|------|--------|-------|
| raceform_clean.parquet (~374K rows) | EXISTS, not wired | Major historical resource — needs parquet-to-New-Build pipeline |
| raceform_v17_features.parquet (~200K rows) | EXISTS, not wired | Contains derived features — leakage risk audit required before use |

### Derived Signals (from form history, not yet built)

| Signal | How Built |
|--------|-----------|
| run_frequency (runs per year) | Derivable from form history date sequence |
| layoff_days_histogram | Derivable from inter-run date gaps |
| course_affinity_score | Win rate at specific course from career history |
| distance_preference_score | Win/place rate by distance band |
| going_preference_score | Win/place rate by going category |
| jockey_continuity_flag | Same jockey as last n runs |
| sp_drift_direction | Is horse being backed or drifting vs career average |

---

## ARCHIVE_ONLY — Store and Report, Never Enter Predictor

| Field | Source | Reason |
|-------|--------|--------|
| official_rating (OR) | Racing API card | Archive-only label — stored in spine as official_rating_archive_only |
| topspeed (TS) | Racing API card | Archive-only label — stored as topspeed_archive_only |
| ts from results (tsr) | Racing API results | Archive-only |
| post-race comment | Racing API results | Archive-only |
| video_url | RP form history | No predictor value, archive reference only |
| rpr_rating (form history) | RP form history | RPR boundary — see BANNED |
| trainer quotes text | RP horse profile | Raw text — archival signal, may derive flags later |
| stable tour quotes text | RP horse profile | Raw text — archival signal |
| rpPostmark | RP quotes | Racing Post market postmark — archive |

**Note on OR and TS**: These are labeled archive-only in the current implementation as a conservative initial stance. They could potentially be promoted to KEEP_LATER (as pre-race context features) in a future review, since OR and TS are available before race time. The current labeling reflects the RPR boundary principle that ratings require careful handling. This should be reviewed explicitly before V0 model training.

---

## BANNED — Hard No

| Field | Reason | Code Location |
|-------|--------|---------------|
| rpr (all sources) | RPR_ARCHIVE_ONLY boundary — Racing Post Rating is excluded from all VELO predictors | features.py BANNED_FEATURE_KEYS, spine.py RPR_POLICY, rpr_feature_allowed=False always |
| rp_rpr_archive_only | Same RPR boundary | spine.py rp_rpr_velo_allowed=False |
| rpr_rating from form history | Same RPR boundary | Parser stores it in JSON (archive context) but never wires to predictor |
| sp (pre-race SP) | Post-race leakage risk — SP is only known at race time, not before | features.py BANNED_FEATURE_KEYS |
| position (as feature) | Post-race leakage — finishing position is the target, not a feature | features.py BANNED_FEATURE_KEYS |
| finishing_position | Same | features.py BANNED_FEATURE_KEYS |
| won (as feature) | Same — training label only, not feature | features.py BANNED_FEATURE_KEYS |
| framed (as feature) | Same | features.py BANNED_FEATURE_KEYS |

---

## MISSING — Known but Not Extracted

| Field | Where It Should Come From | Gap |
|-------|--------------------------|-----|
| trainer per run (career history) | RP form history table | hp-formTable does not include trainer — would need additional scrape |
| race class per historical run | Racing API results join | RP form table lacks class data |
| prize money per run | Racing API results | Not in current schema |
| OR per historical run (from Racing API) | Racing API results | Would need Racing API Pro plan for horse result history |
| going detail (soft, yielding etc.) | RP form history | going cell has short codes only |
| form history for May 24 (Bow Echo) | parse_rp_form_history.py --date 2026-05-24 | Parser not yet run for May 24 |
| form history for May 25 (59 horses) | parse_rp_form_history.py --date 2026-05-25 | Parser not yet run for May 25 |
| form history join to New Build spine | New ingest pipeline needed | No connector between race_shape/ and New Build normalized/ |

---

## Feed Plan Summary — Counts

| Category | Count |
|----------|-------|
| KEEP_NOW | ~32 fields |
| KEEP_LATER | ~30 fields (form history + derived signals + parquet) |
| ARCHIVE_ONLY | ~9 fields |
| BANNED | 8 fields |
| MISSING | 9 items |

---

## Pre-Engine Run Verdict

The New Build V0 model can be trained using KEEP_NOW fields immediately. The spine has:
- 17,464 runners (36 racecard files)
- 25,987 results (62 result files)
- 9 fully outcome-linked rows (tight identity match)
- 473 outcome bridge rows (working toward full linkage)
- 18,554 RPDC memory rows
- Zero RPR violations

**Blockers before V0 engine run**:
1. Outcome linkage is only 9 fully confirmed rows — need to expand to >100 for meaningful model training (expand identity bridge coverage)
2. Form history is not yet connected to spine (KEEP_LATER items currently unavailable to predictor)

**Not blockers**:
- Parser is clean and working
- RPR boundary confirmed enforced
- No live/shadow VELO touched
- Feature coverage report shows 17,937 feature rows exist

No live VELO, Shadow VELO, scoring, or model promotion touched.
All New Build outputs: trust_policy=ARCHIVE_CONTEXT_ONLY_NOT_SCORING, velo_scoring_allowed=False
