# Captain Velo Value Challenger

- Classification: **retrospective analysis only; reused holdout**
- Readout: **POSITIVE_POINT_ESTIMATE_NOT_FORWARD_PROVEN**
- Production promotion: **not authorized**
- Bets placed: **none**

## The mechanism

Captain Velo starts with the captured pre-off market as a prior and adds a deliberately small independent SQPE+MDS correction. It abstains unless structural probability is at least 1.20x the market probability and the available quote clears a 10% expected-edge buffer. Improvement score is excluded because the mechanism ablation found that it harmed combinations.

## Chronological diagnostics

| Block | Bets | Wins | Profit | ROI | 95% bootstrap ROI |
|---|---:|---:|---:|---:|---:|
| Calibration | 62 | 11 | 51.50 | 83.06% | -12.90% to 194.35% |
| Reused test | 52 | 7 | 19.00 | 36.54% | -50.00% to 138.46% |

## Same-race comparison on the reused test selections

| Decision | Bets | Wins | Profit | ROI |
|---|---:|---:|---:|---:|
| Captain Velo | 52 | 7 | 19.00 | 36.54% |
| Captured market favourite | 52 | 14 | -14.26 | -27.42% |
| Production G top | 52 | 11 | 8.48 | 16.31% |

## Honest interpretation

The point estimate can beat the comparison policies while still being unproven. The final block is not pristine, the bet count is modest, and long-priced winners create wide variance. Only races strictly after 2026-09-24 can accumulate valid promotion evidence.
