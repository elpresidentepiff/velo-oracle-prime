# New Build VÉLØ — Model Card
**Model:** Core V0_OR+Passport V1
**Generated:** 2026-05-25T22:38:32.401164Z
**Status:** NEW_BUILD_CHAMPION — not live, not old VÉLØ

---

## Classification
```
PASSPORT_SIGNAL_CONFIRMED
V0_OR_PASSPORT_BEATS_CHAMPION_ON_UNSEEN_2025
PROMOTE_TO_NEW_BUILD_CHAMPION
HORSE_FIRST_STRATEGY_VALIDATED
```

## Trust Policy
- `ARCHIVE_CONTEXT_ONLY_NOT_SCORING`
- `velo_scoring_allowed = False`
- `rpr_violation = False`
- `sp_violation = False`

## 2025 Unseen Test Results
Test set: 2025-01-01 → 2025-07-05 | 5,775 races | 57,221 runners

| Metric | Previous Champion (V0_OR) | New Champion (V0_OR+Passport) | Delta |
|---|---|---|---|
| AUC | 0.6788 | 0.6922 | +0.0134 |
| Brier | 0.0869 | 0.0862 | -0.0007 |
| Top-pick SR | 22.2% | 24.2% | +1.9% |
| Top-3 Frame | 51.5% | 54.0% | +2.6% |

Promotion gates: **AUC PASS / Brier PASS / SR PASS / Frame PASS — 4/4**

## Feature Architecture
Total features: 30

### Layer 1 — Core V0 Race Context
(17 features)
- `dist_f`
- `going_code`
- `is_aw`
- `field_size`
- `draw_num`
- `draw_pct`
- `age_num`
- `wgt_lbs`
- `or_vs_field`
- `release_window_score`
- `going_fit_score`
- `distance_fit_score`
- `quiet_run_score`
- `trainer_timing_score`
- `jockey_switch_intent`
- `setup_run_flag`
- `cash_run_flag`

### Layer 2 — Official Rating
(2 features)
- `official_rating`
- `is_rated`

### Layer 3 — Horse Passport (NEW)
(11 features | 35.8% of total model importance)
- `pp_career_runs`
- `pp_win_rate`
- `pp_place_rate`
- `pp_days_since_last`
- `pp_layoff`
- `pp_avg_sp_last5`
- `pp_jockey_continuity`
- `pp_course_seen`
- `pp_or_change_3`
- `pp_class_moved_up`
- `pp_class_moved_down`

## Feature Importance (top 20)
| Rank | Feature | Layer | Importance % |
|---|---|---|---|
| 1 | `or_vs_field` | Core V0 | 9.4% |
| 2 | `pp_days_since_last` | Passport | 8.9% |
| 3 | `pp_avg_sp_last5` | Passport | 8.8% |
| 4 | `official_rating` | OR | 8.6% |
| 5 | `wgt_lbs` | Core V0 | 6.3% |
| 6 | `pp_career_runs` | Passport | 6.3% |
| 7 | `field_size` | Core V0 | 6.1% |
| 8 | `pp_place_rate` | Passport | 4.5% |
| 9 | `draw_pct` | Core V0 | 4.3% |
| 10 | `trainer_timing_score` | Core V0 | 4.0% |
| 11 | `age_num` | Core V0 | 3.9% |
| 12 | `distance_fit_score` | Core V0 | 3.9% |
| 13 | `going_fit_score` | Core V0 | 3.9% |
| 14 | `pp_or_change_3` | Passport | 3.3% |
| 15 | `quiet_run_score` | Core V0 | 3.1% |
| 16 | `draw_num` | Core V0 | 2.7% |
| 17 | `dist_f` | Core V0 | 2.6% |
| 18 | `going_code` | Core V0 | 1.6% |
| 19 | `release_window_score` | Core V0 | 1.4% |
| 20 | `pp_class_moved_down` | Passport | 1.0% |

### Passport Feature Importance Detail
| Feature | Importance % | Meaning |
|---|---|---|
| `pp_days_since_last` | 8.9% | Days since previous race (freshness) |
| `pp_avg_sp_last5` | 8.8% | Mean SP over last 5 prior runs (historical market support) |
| `pp_career_runs` | 6.3% | Number of prior career starts (experience) |
| `pp_place_rate` | 4.5% | Career place rate up to this race |
| `pp_or_change_3` | 3.3% | OR change over last 3 races (form direction) |
| `pp_class_moved_down` | 1.0% | 1 if dropped down in class vs last race |
| `pp_course_seen` | 0.8% | 1 if horse has previously run at this course |
| `pp_win_rate` | 0.8% | Career win rate up to this race |
| `pp_class_moved_up` | 0.7% | 1 if stepped up in class vs last race |
| `pp_jockey_continuity` | 0.4% | 1 if same jockey as previous race |
| `pp_layoff` | 0.2% | 1 if layoff >90 days |

## Calibration (V0_OR+Passport champion, 2025 test)
| Prob band | n | Predicted WR | Actual WR | Over/Under |
|---|---|---|---|---|
| 0.00–0.05 | 10,467 | 0.033 | 0.032 | -0.001 |
| 0.05–0.10 | 23,735 | 0.074 | 0.072 | -0.002 |
| 0.10–0.15 | 13,416 | 0.122 | 0.123 | +0.001 |
| 0.15–0.20 | 5,610 | 0.171 | 0.176 | +0.005 |
| 0.20–0.25 | 2,232 | 0.221 | 0.225 | +0.004 |
| 0.25–0.30 | 874 | 0.272 | 0.301 | +0.029 |
| 0.30–0.40 | 629 | 0.338 | 0.348 | +0.011 |
| 0.40–1.01 | 258 | 0.477 | 0.484 | +0.008 |

## Key Findings

**Passport-only is weaker than Core V0.** Horse history alone is not enough —
it requires race context to be meaningful.

**Horse history + race context is where the edge lives.** The combination
adds +0.0134 AUC, +1.9% SR, and +2.6% Frame on completely unseen data.

**Passport features account for 35.8% of total model importance.**
These are not decoration — they are structural contributors.

## Frozen Feature List
```
dist_f
going_code
is_aw
field_size
draw_num
draw_pct
age_num
wgt_lbs
or_vs_field
release_window_score
going_fit_score
distance_fit_score
quiet_run_score
trainer_timing_score
jockey_switch_intent
setup_run_flag
cash_run_flag
official_rating
is_rated
pp_career_runs
pp_win_rate
pp_place_rate
pp_days_since_last
pp_layoff
pp_avg_sp_last5
pp_jockey_continuity
pp_course_seen
pp_or_change_3
pp_class_moved_up
pp_class_moved_down
```

## Scope
- NEW_BUILD_ONLY
- Not wired to old VÉLØ engine
- Not live deployment
- No RPR in any feature
- No current-race SP in any feature
- All passport features use prior-race data only (no leakage)

## Next Layer: Intent
Planned challenger: **Intent Layer V1**
```
CASH_RUN_CANDIDATE
SETUP_RUN
TRAP_PREP
MARK_READY
JOCKEY_INTENT
TRAINER_TIMING
```
Test against this champion. Promote only if it beats on unseen data.