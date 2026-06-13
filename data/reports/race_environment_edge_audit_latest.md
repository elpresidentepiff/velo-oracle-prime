# VÉLØ Race-Environment Edge Audit

Generated: 2026-06-11T21:20:45.439490+00:00

## Governing Rule

No Tier A filter. A candidate permission rule must be pre-race observable, have minimum sample, and remain profitable in both chronological train and holdout periods.

## Baselines

| Layer | n | Wins | SR | Frames | Frame Rate | ROI |
|---|---:|---:|---:|---:|---:|---:|
| sigma_history | 2502 | 568 | 22.7% | 1240 | 49.6% | n/a |
| sp_enriched_roi_history | 224 | 73 | 32.6% | 134 | 59.8% | +9.8% |

## Bet-Permission Candidates

| Rule | n | Train ROI | Holdout ROI | Total ROI | Holdout SR | Holdout Frame | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| `country=GB AND vp_bucket=VP_20_30` | 46 | +71.6% | +62.0% | +66.8% | 30.4% | 52.2% | -6.3 |
| `surface=TURF_OR_JUMPS AND field_bucket=FIELD_7_9` | 70 | +63.6% | +48.0% | +57.8% | 38.5% | 76.9% | -10.5 |
| `country=GB AND field_bucket=FIELD_7_9` | 62 | +83.8% | +35.6% | +64.3% | 32.0% | 68.0% | -9.5 |
| `going_bucket=GOOD` | 65 | +19.3% | +30.5% | +25.3% | 40.0% | 68.6% | -16.7 |
| `field_bucket=FIELD_7_9` | 74 | +63.6% | +28.3% | +49.3% | 33.3% | 73.3% | -10.5 |
| `country=GB` | 173 | +30.4% | +10.0% | +21.3% | 31.2% | 62.3% | -24.6 |
| `country=GB AND field_bucket=FIELD_2_6` | 34 | +33.6% | +9.9% | +23.2% | 40.0% | 86.7% | -4.7 |
| `field_bucket=FIELD_2_6` | 40 | +38.7% | +3.1% | +24.4% | 37.5% | 87.5% | -7.7 |
| `surface=TURF_OR_JUMPS AND field_bucket=FIELD_2_6` | 40 | +38.7% | +3.1% | +24.4% | 37.5% | 87.5% | -7.7 |
| `surface=TURF_OR_JUMPS` | 218 | +21.1% | +1.7% | +12.8% | 31.2% | 62.4% | -23.6 |

## Proposed Forward-Paper Policy V1

**Core permission:** `GB AND TURF_OR_JUMPS AND FIELD_7_9 AND NOT WEAK_EXCLUDE_TRACK`

**Bet reduction:** 77.7% (224 historical opportunities reduced to 50).

| Period | n | Wins | SR | Frames | Frame | ROI | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Total | 50 | 22 | 44.0% | 36 | 72.0% | +80.1% | -9.0 |
| Train | 33 | 16 | 48.5% | 24 | 72.7% | +99.2% | -9.0 |
| Test | 17 | 6 | 35.3% | 12 | 70.6% | +42.9% | -4.0 |

**Hard no-bet gates:**

- IRE races: broad Sigma underperforms GB and dated ROI is negative.
- Fields of 10 or more: both 10-12 and 13+ buckets are negative in chronological holdout.
- VP below 0.20: negative overall and zero holdout wins in the dated sample.
- WEAK_EXCLUDE tracks: objective full-Sigma rule of n>=30 and SR<15% or frame<40%.

**Freeze rule:** Freeze after 20 forward-paper bets if ROI < 0% or frame rate < 60%; no live promotion before 50 forward-paper bets.

## Track Evidence

No individual track has earned standalone bet permission. Track labels below are supporting filters only.

| Classification | Track | n | SR | Frame |
|---|---|---:|---:|---:|
| STRONG_SUPPORT | Musselburgh | 39 | 41.0% | 61.5% |
| STRONG_SUPPORT | Newbury | 43 | 32.6% | 51.2% |
| WEAK_EXCLUDE | Beverley | 37 | 2.7% | 35.1% |
| WEAK_EXCLUDE | Perth | 39 | 5.1% | 41.0% |
| WEAK_EXCLUDE | Nottingham | 30 | 10.0% | 40.0% |
| WEAK_EXCLUDE | Thirsk | 33 | 12.1% | 42.4% |
| WEAK_EXCLUDE | Warwick | 35 | 14.3% | 60.0% |
| WEAK_EXCLUDE | Southwell (AW) | 100 | 17.0% | 38.0% |
| WEAK_EXCLUDE | Cork (IRE) | 34 | 17.6% | 35.3% |
| WEAK_EXCLUDE | Leicester | 34 | 20.6% | 38.2% |
| WEAK_EXCLUDE | Kempton (AW) | 71 | 21.1% | 39.4% |
| WEAK_EXCLUDE | Goodwood | 30 | 23.3% | 36.7% |

## Stable Environments From Full Sigma History

| Rule | n | Train SR | Holdout SR | Train Frame | Holdout Frame |
|---|---:|---:|---:|---:|---:|
| `off_bucket=BEFORE_14` | 151 | 32.7% | 39.5% | 64.6% | 57.9% |
| `country=GB AND off_bucket=BEFORE_14` | 116 | 29.5% | 39.3% | 61.4% | 53.6% |
| `surface=TURF_OR_JUMPS AND vp_bucket=VP_40_PLUS` | 917 | 25.5% | 34.0% | 54.0% | 66.0% |
| `country=GB AND vp_bucket=VP_30_40` | 285 | 21.0% | 33.3% | 60.5% | 56.1% |
| `vp_bucket=VP_40_PLUS` | 1127 | 25.1% | 32.6% | 51.8% | 64.9% |
| `surface=TURF_OR_JUMPS AND vp_bucket=VP_30_40` | 304 | 22.2% | 32.1% | 59.3% | 58.4% |
| `country=GB AND vp_bucket=VP_40_PLUS` | 902 | 25.7% | 31.8% | 52.3% | 64.5% |
| `vp_bucket=VP_30_40` | 343 | 22.4% | 31.0% | 59.7% | 56.3% |
| `country=GB AND off_bucket=14_TO_17` | 1033 | 21.2% | 27.7% | 50.1% | 53.1% |

## Operating Interpretation

- `BET_PERMISSION_CANDIDATE` means worthy of forward paper betting, not guaranteed profit and not automatic live staking.
- Rules involving SP were excluded from permission candidates because final SP is not known pre-race.
- Course rules can be volatile even with minimum samples; country/race-type/field-size rules are more transferable.
- Any live permission requires a fresh forward-only sample and a stop-loss/freeze rule.
