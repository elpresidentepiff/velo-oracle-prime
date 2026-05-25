# Historical Feature Safety Audit
Generated: 2026-05-25T21:36:59.997700Z

## Summary

| Classification | Count |
|---|---|
| ARCHIVE_ONLY | 4 |
| DROP_LEAKAGE | 2 |
| IDENTITY | 18 |
| KEEP_CORE_V0 | 36 |
| MARKET_ONLY | 10 |
| TARGET | 4 |
| TIMESTAMP_UNKNOWN | 2 |

## Column Classifications

### KEEP_CORE_V0 (36)

| Column | Reason |
|---|---|
| `type` | race type: Flat/Hurdle/Chase/NHF |
| `dist_f` | distance in furlongs |
| `going_code` | going numeric code |
| `is_aw` | all-weather flag |
| `class_num` | class numeric |
| `wgt_lbs` | weight in lbs |
| `or_num` | OR numeric — pre-race handicap mark |
| `or_vs_field` | OR vs field mean — pre-race relative mark |
| `field_size` | field size derived |
| `draw_num` | draw numeric |
| `draw_pct` | draw percentile in race |
| `age_num` | age numeric |
| `runs_since_win` | runs since last win |
| `runs_since_place` | runs since last place |
| `curr_or_minus_last_win_or` | OR drop since last win — handicap plot signal |
| `curr_or_minus_best_or` | OR vs career best — mark compression |
| `mark_compression_score` | mark compression score |
| `release_window_score` | release window / handicap drop signal |
| `course_fit_score` | course specialist fit score |
| `going_fit_score` | going preference fit score |
| `distance_fit_score` | distance fit score |
| `quiet_run_score` | quiet/prep run indicator |
| `trainer_timing_score` | trainer intent timing signal |
| `jockey_switch_intent` | jockey change intent signal |
| `setup_run_flag` | setup run flag |
| `cash_run_flag` | cash run flag |
| `class_raw` | raceform_clean only: raw class string |
| `dist` | raceform_clean only: distance string |
| `going` | raceform_clean only: going string |
| `ran` | raceform_clean only: field size from racecard |
| `draw` | raceform_clean only: draw position |
| `age` | raceform_clean only: age string |
| `sex` | raceform_clean only: sex code |
| `wgt` | raceform_clean only: weight string |
| `hg` | raceform_clean only: headgear code |
| `or_rating` | raceform_clean only: Official Rating — pre-race handicap mark |

### MARKET_ONLY (10)

| Column | Reason |
|---|---|
| `sp_dec` | SP decimal — final odds |
| `log_sp` | log SP — SP derived |
| `implied_prob` | market implied probability — SP derived |
| `sp_rank` | SP rank within race — requires all SPs |
| `is_fav` | favourite flag — market derived |
| `runs_since_mkt_support` | runs since last market support — requires SP history |
| `odds_resilience_score` | odds resilience — SP movement derived |
| `odds_contraction_score` | odds contraction — SP movement derived |
| `decoy_support_flag` | decoy support — SP pattern derived |
| `sp` | raceform_clean only: final SP — not available before race closes |

### ARCHIVE_ONLY (4)

| Column | Reason |
|---|---|
| `rpr_num` | RPR numeric: archive-only boundary |
| `rpr_vs_field` | RPR vs field: archive-only boundary |
| `prize` | raceform_clean only: race prize money — race context, not horse feature |
| `rpr` | raceform_clean only: RPR: archive-only boundary, never a model feature |

### TIMESTAMP_UNKNOWN (2)

| Column | Reason |
|---|---|
| `ts_num` | TS numeric: requires race time — post-race leakage risk |
| `ts` | raceform_clean only: TS rating: requires race time to compute — post-race leakage risk |

### DROP_LEAKAGE (2)

| Column | Reason |
|---|---|
| `time` | raceform_clean only: race time in seconds — post-race result |
| `comment` | raceform_clean only: post-race comment text — never available pre-race |

### TARGET (4)

| Column | Reason |
|---|---|
| `pos` | finishing position — outcome label only |
| `target` | pre-derived target flag |
| `ovr_btn` | raceform_clean only: total lengths beaten — post-race |
| `btn` | raceform_clean only: lengths beaten by winner — post-race |

### IDENTITY (18)

| Column | Reason |
|---|---|
| `race_id` | race key |
| `date` | race date |
| `date_parsed` | parsed date |
| `course` | course name |
| `horse` | horse name |
| `jockey` | jockey name |
| `trainer` | trainer name |
| `off` | raceform_clean only: race off time |
| `race_name` | raceform_clean only: race name |
| `pattern` | raceform_clean only: race pattern grade |
| `rating_band` | raceform_clean only: rating band string |
| `age_band` | raceform_clean only: age restriction string |
| `sex_rest` | raceform_clean only: sex restriction string |
| `num` | raceform_clean only: cloth number |
| `sire` | raceform_clean only: sire name |
| `dam` | raceform_clean only: dam name |
| `damsire` | raceform_clean only: damsire name |
| `owner` | raceform_clean only: owner name |
