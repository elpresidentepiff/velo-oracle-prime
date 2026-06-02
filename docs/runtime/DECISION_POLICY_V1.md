# NEW BUILD DECISION POLICY V1

This policy governs the tactical categorization of runners in the New Build scoring lane, utilizing the Challenger V1 champion and newly validated V3 velocity sidecars.

## 1. Tactical Lanes

| Lane | Criteria | Primary Signal | Expected SR | Expected Frame |
| :--- | :--- | :--- | :--- | :--- |
| **WIN_TRUST** | `VP >= 0.30` AND `pp_career_runs >= 5` | High Probability + Proven Baseline | **38.7%** | 76.7% |
| **FRAME_TRUST** | `VP >= 0.25` AND `place_rate_last3 >= 0.66` | Strong Recency + Medium Probability | 32.5% | **69.0%** |
| **SUPPRESS** | `VP < 0.25` AND `pp_career_runs < 3` | Low Data + Weak Probability | 19.0% | 47.6% |
| **LOW_DATA** | `pp_career_runs == 0` | First-time out or uncaptured history | 13.1% | N/A |
| **NO_EDGE** | All other runners | Default lane | 24.7% | 54.9% |

## 2. Decision Anchors
*   **Anchor:** Challenger V1 `velo_prime_prob` (VP).
*   **Context A:** Passport Coverage (`pp_career_runs`).
*   **Context B:** Form Velocity (`place_rate_last3` - V3 Sidecar).

## 3. Implementation Logic
1.  Score race with Challenger V1.
2.  Join V3 Sidecar features (`win_rate_last3`, `place_rate_last3`, `win_rate_last6`).
3.  Apply thresholds sequentially (WIN_TRUST > FRAME_TRUST > SUPPRESS > LOW_DATA).
4.  Persist `nb_decision_lane` and `nb_policy_notes` to prediction logs.

## 4. Evidence Base (2025 Held-out Test Set)
*   **Total Samples:** 5,935 top-ranked runners.
*   **Baseline SR:** 24.7%
*   **Baseline Frame:** 54.9%
*   **Audit Date:** 2026-06-02
