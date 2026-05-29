# Historical Replay Requirement — New Build vs Old VELO AUC Comparison
Generated: 2026-05-29T13:34:15.256867Z

**Classification:** `PARTIAL_OVERLAP_NB_REPLAY_REQUIRED`
**AUC Status:** `OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY`

> AUC comparison requires identical race/runner/target populations, same chronological split, and both model probabilities on the same rows. Single-day strike rate is indicative only.

## Artifact Audit
| Artifact | Count | Dates |
|---|---|---|
| Old VELO verdict files | 50 | 2026-05-23, 2026-05-24, 2026-05-25, 2026-05-26, 2026-05-27 |
| Sigma result files | 7 | 2026-05-23, 2026-05-24, 2026-05-25, 2026-05-26, 2026-05-27 |
| NB prediction files | 1 | 2026-05-29 |
| Overlap dates (VELO + sigma) | 7 | 2026-05-21, 2026-05-22, 2026-05-23, 2026-05-24, 2026-05-25, 2026-05-26, 2026-05-27 |
| Champion version | — | Challenger_V1 |

## Requirements for Valid AUC Comparison
| ID | Requirement | Status |
|---|---|---|
| REQ-1 | Same race population | `PARTIAL` |
| REQ-2 | Same runner population | `NOT_VERIFIED` |
| REQ-3 | Old VELO probability extraction | `PARTIAL_TOP_PICK_ONLY` |
| REQ-4 | New Build historical re-score | `NOT_STARTED` |
| REQ-5 | Identical target variable | `SIGMA_FORMAT_COMPATIBLE` |
| REQ-6 | Chronological split respected | `2026_DATES_ARE_SAFE` |
| REQ-7 | Sufficient sample size | `INSUFFICIENT_N_7_OVERLAP_DATES` |

## Critical Blocker
> REQ-3: Old VELO runner-level probability distribution is not captured. Only the top pick probability exists in verdict files. AUC requires P(win) for every runner in every race. Until Old VELO produces runner-level scores, true AUC comparison is impossible.

## What Can Be Compared Today
- Top-1 strike rate comparison (Old VELO top pick vs New Build rank-1 pick) — indicative only
- Alignment rate (is Old VELO top pick inside New Build top-3?)
- OR baseline comparison (highest official_rating pick as naive baseline)
- Outcome evaluation when sigma results are available

## Action Plan
| Step | Action | Command |
|---|---|---|
| 1 | Accumulate sigma results for May-June 2026 race days | `python scripts/run_results_sigma.py --date YYYY-MM-DD` |
| 2 | Re-run New Build scorer on each historical date with sigma results | `python scripts/ops/new_build_two_lane_score.py --date YYYY-MM-DD --execute` |
| 3 | Assess Old VELO runner-level probability availability | `Check if velo_prime_verdicts files contain per-runner probs or only top pick. If` |
| 4 | Run comparison evaluator across accumulated dates | `python scripts/ops/new_build_old_velo_comparison.py --date YYYY-MM-DD --execute` |
| 5 | Aggregate multi-date SR/alignment statistics | `Compute rolling SR for Old VELO vs New Build vs OR baseline across all evaluated` |

## Promotion Gate
**Status:** `NOT_READY`
**Estimated earliest:** After 30+ live race days with closed outcomes (approx July 2026)

All of the following must be met before New Build is integrated into Old VELO scoring:

- [ ] n >= 200 closed races evaluated
- [ ] New Build SR statistically above OR baseline (p < 0.05)
- [ ] New Build SR >= Old VELO SR on identical race population (or Old VELO absent)
- [ ] RPR violations = 0 confirmed across all evaluated dates
- [ ] JTC-D sidecar rebuilt with rolling date-bounded lookback (no leakage)
- [ ] Intent coverage gate (>= 80%) achieved on at least 5 consecutive race days
- [ ] Operator explicit promotion decision — no automatic promotion

## Boundaries
- This report is read-only. No Old VELO model or scoring pipeline changes.
- No Telegram, staking, or live table writes.
- AUC comparison remains `NOT_COMPARABLE` until REQ-3 (runner-level probs) is resolved.