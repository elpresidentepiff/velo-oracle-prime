# Ablation Baseline Reconciliation
Generated: 2026-05-28T19:24:26.516647

**Status:** `BASELINE_REPRODUCTION_PASSED`
**Baseline Reproduction (AUC ±0.005):** PASS
**Challenger Promotion Earned:** True

## Metrics
|                                   |    AUC |     SR |   Frame |   Brier |   AUC_lift_vs_champion |   SR_lift_vs_champion |   Frame_lift_vs_champion |
|:----------------------------------|-------:|-------:|--------:|--------:|-----------------------:|----------------------:|-------------------------:|
| A: Core V0_OR (Champion Baseline) | 0.6768 | 0.2173 |  0.5069 |  0.0859 |                 0      |                0      |                   0      |
| B: Passport-only                  | 0.6442 | 0.2124 |  0.5017 |  0.0873 |                -0.0326 |               -0.0049 |                  -0.0052 |
| C: Intent-only                    | 0.6329 | 0.2051 |  0.4928 |  0.0877 |                -0.0439 |               -0.0122 |                  -0.0141 |
| D: Core + Passport                | 0.6895 | 0.2298 |  0.5283 |  0.0854 |                 0.0127 |                0.0125 |                   0.0214 |
| E: Core + Intent                  | 0.6864 | 0.2256 |  0.5228 |  0.0856 |                 0.0096 |                0.0083 |                   0.0159 |
| F: All Combined                   | 0.6945 | 0.2363 |  0.5383 |  0.0852 |                 0.0177 |                0.019  |                   0.0314 |

## Governance
- `rpr_violation`: False
- `sp_violation`: False
- `new_build_scoring_allowed`: True
- `old_live_velo_impact`: False
- `shadow_impact`: False