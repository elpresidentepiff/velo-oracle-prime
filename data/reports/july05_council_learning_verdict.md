# LLM Council Learning Verdict — 2026-07-05

**Status:** EVIDENCE_INCOMPLETE
**Verdict:** WATCH_ONLY
**Watch flag:** `SIGMA COVERAGE: SR_BELOW_BASELINE`

## Why WATCH_ONLY, and why a different reason than July 4
On July 4, Council was WATCH_ONLY because `runner_prediction_snapshots` were missing (that day's scoring ran `--verdicts-only`). Today's scoring ran normally (no `--verdicts-only`), so snapshots exist — but Council is still WATCH_ONLY, this time because the day's strike rate (18.2%) sits below the working baseline. Two different gates, same overall caution: Council does not consume a day for learning unless both data completeness *and* performance meet its bar.

## Comparison across the two days on record
| | July 04 | July 05 |
|---|---|---|
| SR | 29.4% | 18.2% |
| Frame rate | 52.9% | 59.1% |
| mid_priced_won misses | 18/24 (75%) | 7/9 (78%) |
| Council verdict | WATCH_ONLY (missing snapshots) | WATCH_ONLY (SR below baseline) |

## What worked
Frame rate held up and even improved day-over-day (59.1% vs 52.9%) despite a lower win rate — VÉLØ is still narrowing races to the right small group of contenders.

## What failed
Win conversion within that narrowed group. 7 of 9 true Sigma misses were `mid_priced_won` — the same dominant pattern from July 4, now confirmed across two consecutive days.

## Strongest pattern
`MIDPRICE_TRAP` — reconfirmed, not newly discovered. Two-day sample: 25 of 33 combined true misses (76%) were mid-priced winners beating VÉLØ's selection.

## Danger pattern
`FAV_VULN_ULTRA_COMPRESSED` — unchanged, still low-sample, still research/watchlist (fav_vuln_ultra_sr=0.1875).

## Promotion eligible
None. V1_BASE and V6_GOLD_SEAM remain `LANE_FROZEN`; V2_CLASS4_ONLY moved to `WATCHLIST` (an improvement) but is explicitly not eligible — needs more days at its current thresholds.

## Data quality / identity
Clean on both metrics. `data_error_count: 0` (vs 1 on July 4, before that day's mid-run Leicester recovery). No identity or RPDC failures reported by Mission Control on either day.

## Is learning shadow-only?
Yes — `shadow_state_touched: true`, `live_sentient_state_touched: false`, `supabase_writes_attempted: false` in the Step 20 status, same as July 4.

## Governance note (unchanged)
"sigma_audits truth writes are never blocked by council." Blocking only affects learning consume, shadow promote, and promotion evidence — none of which occurred on either day.
