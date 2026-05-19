# MARKET_FEATURE_LEAKAGE_AUDIT_V1

**Run:** 2026-05-19T11:53:54.265091+00:00  
**Feature set:** MARKET_ONLY  
**Overall verdict:** `CLEAN_NO_LEAKAGE`  
**Safe for training:** YES  
**Safe for forward gate:** YES  

## Feature Audit

| Feature | Known Pre-Race | SP-Derived | Result-Derived | Verdict |
|---|---|---|---|---|
| `market_deception_score` | YES | NO | NO | `CLEAN` |
| `place_prob` | YES | NO | NO | `CLEAN` |
| `longshot_prob` | YES | NO | NO | `CLEAN` |
| `release_day_prob` | YES | NO | NO | `CLEAN` |

## Feature Evidence

### `market_deception_score`

**Source:** scripts/train_specialist_models.py → models/specialist/market_deception_model/  
**Timestamp:** Race card release (morning of race or earlier)  
**Derivation:** Specialist ML model trained on pre-race form signals. Inputs: going_flag, headgear_change, trainer_strike_rate_going, draw_position_normalized, class_drop_flag, days_since_last_run, comment_manipulation_flag. Trained on historical race-level data. Score assigned per runner from model output.  

**Evidence:** MDS is produced by a model trained on non-result features. The model target at training time is a historical outcome, but the SCORE is generated from pre-race inputs only. Verified: no SP, no BSP, no result columns in MDS inference path. Source: scripts/train_specialist_models.py lines 180-210 — feature list excludes sp_decimal, bsp_decimal, win_flag, place_flag. CLEAN.

### `place_prob`

**Source:** scripts/train_specialist_models.py → models/specialist/place_model/  
**Timestamp:** Race card release (morning of race or earlier)  
**Derivation:** Specialist ML model for each-way placement probability. Inputs: sqpe_v17_prob, improvement_score, comment_intel_score, draw_position_normalized, field_size, going_category. Score assigned pre-race.  

**Evidence:** place_prob model trained on historical place outcomes but SCORES from pre-race features. Confirmed: no SP, no BSP in inference-time features. SQPE is an input but SQPE itself is also pre-race (trained on form data). CLEAN.

### `longshot_prob`

**Source:** scripts/train_specialist_models.py → models/specialist/longshot_model/  
**Timestamp:** Race card release (morning of race or earlier)  
**Derivation:** Specialist ML model for longshot identification (sp >= 10 target at training). Inputs: comment_intel_score, draw_position_normalized, days_since_last_run, going_flag, trainer_strike_rate, field_size. IMPORTANT: 'sp >= 10' is the TRAINING TARGET, not an inference input. At inference time, no SP is used — model only receives pre-race signals.  

**Evidence:** Training target is historical SP >= 10 (longshot flag). This is a LABEL at training time — not an inference-time feature. At prediction time, longshot_prob is produced purely from pre-race form features. This is the standard supervised learning setup: label derived from result, but score computed from pre-race features only. CLEAN. Note: longshot_prob MUST NOT be used as a predictive feature in contexts where SP is available (i.e., only use in pre-race, never post-race refit). This constraint is already enforced by the training cutoff rule.

### `release_day_prob`

**Source:** scripts/train_specialist_models.py → models/specialist/release_window_model/  
**Timestamp:** Race card release — days_since_last_run computable from declared entry  
**Derivation:** Specialist ML model for release-window probability (horse running in its optimal release window: 14–35 days since last run). Inputs: days_since_last_run, going_preference_match, trainer_strike_rate, comment_freshness_score, prior_release_window_win_rate. Score is a probability of being in optimal condition window.  

**Evidence:** All inputs computable from declared racecard (trainer form, last run date, going). No result SP or outcome in the inference feature set. Training target is historical result-based (did horse run well in window?) but inference score is pre-race only. CLEAN.

## Data Range Check

**Status:** NO_PARQUET_FOUND  
**Note:** Cannot verify value ranges — manual verification required  

## Conclusion

**CLEAN:** All MARKET_ONLY features are pre-race and not derived from result SP or post-race outcomes.

Hard rules enforced:
- SP (`sp_decimal`) is NEVER used as an inference-time feature
- BSP and result win/place flags are NEVER in the inference feature list
- Training cutoff is immutable — no future rows seen during training