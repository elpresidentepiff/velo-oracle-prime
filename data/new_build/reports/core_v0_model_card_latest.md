# Core V0 Model Card
Generated: 2026-05-25T21:59:30.127425Z
Trust policy: `ARCHIVE_CONTEXT_ONLY_NOT_SCORING` | `velo_scoring_allowed: false`

## Approval Status: `CORE_V0_VALIDATED_WITH_WEAKNESSES`

---

## A. Dataset
- Total rows: 1,162,031
- Unique races: 116,111
- Unique horses: 148,741
- Date range: 2015-01-01 → 2025-07-05
- Race type: **Flat only**

## B. Features Used
Count: **17**

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

## C. Banned Features
The following are **never** used as model inputs:

| Category | Features |
|---|---|
| RPR (archive only) | `rpr`, `rpr_num`, `rpr_vs_field` |
| SP / market | `sp`, `sp_dec`, `log_sp`, `is_fav`, `implied_prob`, `sp_rank`, `odds_resilience_score`, `odds_contraction_score`, `decoy_support_flag`, `runs_since_mkt_support` |
| Post-race leakage | `pos`, `pos_num`, `ovr_btn`, `btn`, `comment`, `time`, `ts`, `ts_num` |

## D. Splits

| Split | Rows | Period |
|---|---|---|
| Train | 987,511 | 2020–2023 approx |
| Val | 117,299 | 2024 |
| Test | 57,221 | 2025 |

## E. Metrics

### Split Metrics

| Split | AUC | Brier | SR | Frame | Races | Runners |
|---|---|---|---|---|---|---|
| Train *(IN-SAMPLE)* | 0.6894 | 0.0858 | 23.7% | 53.4% | 98,684 | 987,511 |
| Val | 0.6735 | 0.0861 | 21.8% | 50.3% | 11,650 | 117,299 |
| Test | 0.6745 | 0.0871 | 22.0% | 51.2% | 5,775 | 57,221 |

> **Note:** Train-set metrics are in-sample and inflated due to fitting. Test set (2025) is the real signal.

### Baseline Comparison (Val set)

| Baseline | SR | Frame | AUC |
|---|---|---|---|
| Random (1/field_size avg) | 9.9% | 29.8% | N/A |
| OR-rank (top by or_vs_field) | 14.9% | 40.1% | N/A |
| Favourite (is_fav=1) | N/A | N/A | N/A — is_fav absent (MARKET_ONLY banned) |
| **Core V0** | **21.8%** | **50.3%** | **0.6735** |

## F. Year-by-Year Stability

| Year | Races | Runners | AUC | SR | Frame | Brier | Flags |
|---|---|---|---|---|---|---|---|
| 2024 | 11,650 | 117,299 | 0.6735 | 21.8% | 50.3% | 0.0861 | - |
| 2025 | 5,775 | 57,221 | 0.6745 | 22.0% | 51.2% | 0.0871 | - |

## G. Known Weaknesses

1. field_band band=13-16: FRAME_BELOW_40PCT (SR=16.0%, Races=2,206)
2. field_band band=17+: SR_BELOW_15PCT,FRAME_BELOW_40PCT (SR=11.5%, Races=364)
3. Train-set metrics (AUC, SR, Frame) are in-sample and inflated — test set is the real signal
4. release_window_score: SAFE_IF_LAGGED — must confirm OR trajectory uses only prior-race ORs in production

## H. Feature Provenance

| Feature | Source | Pre-race safe | Timestamp risk | Null rate (train) | Leakage verdict | Allowed |
|---|---|---|---|---|---|---|
| `dist_f` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `going_code` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `is_aw` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `field_size` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `draw_num` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `draw_pct` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `age_num` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `wgt_lbs` | racecard | Yes | none | 0.0% | SAFE | Yes |
| `or_vs_field` | racecard/OR | Yes | none | 0.0% | SAFE | Yes |
| `release_window_score` | OR_history | Yes | requires lagged OR trajectory — must use prior-race OR only | 0.0% | SAFE_IF_LAGGED | Yes |
| `going_fit_score` | historical_results | Yes | none | 0.0% | SAFE | Yes |
| `distance_fit_score` | historical_results | Yes | none | 0.0% | SAFE | Yes |
| `quiet_run_score` | form_history | Yes | none | 0.0% | SAFE | Yes |
| `trainer_timing_score` | trainer_history | Yes | none | 0.0% | SAFE | Yes |
| `jockey_switch_intent` | form_history | Yes | none | 0.0% | SAFE | Yes |
| `setup_run_flag` | form_history | Yes | none | 0.0% | SAFE | Yes |
| `cash_run_flag` | form_history | Yes | none | 0.0% | SAFE | Yes |

**Leakage verdict: CLEAN — no features flagged as leakage**

### Subgroup Stability Flags (n > 200 races)

| Group | Band | Races | SR | Frame | Flags |
|---|---|---|---|---|---|
| field_band | 13-16 | 2,206 | 16.0% | 36.9% | FRAME_BELOW_40PCT |
| field_band | 17+ | 364 | 11.5% | 26.7% | SR_BELOW_15PCT, FRAME_BELOW_40PCT |

## I. Approval Status

**`CORE_V0_VALIDATED_WITH_WEAKNESSES`**

| Criterion | Value |
|---|---|
| Test SR vs OR-baseline | 22.0% vs 14.9% — PASS |
| Leakage audit | CLEAN |
| Weak cells (n>200) | 2 |

---
*Shadow-only. `velo_scoring_allowed=False`. No live scoring or model promotion.*
