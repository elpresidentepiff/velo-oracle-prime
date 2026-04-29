# VELO Signal Glossary V1

## Core Probability Terms

- **VP**: shorthand for `velo_prime_prob`, the live VELO_PRIME race-normalized win probability field.
- **VP30**: the evidence cohort where `velo_prime_prob >= 0.30`.
- **VP30_TIER_A**: `velo_prime_prob >= 0.30` and `decision_tier == 'A'`.
- **Tier A**: the highest live decision tier assigned by the daily scorer.

## Sidecar / Candidate Lane Terms

- **MDS_HIGH / MARKET_DECEPTION_HIGH**: `market_deception_score > 0.50`.
- **IMPROVE_HIGH / IMPROVEMENT_SCORE_HIGH**: `improvement_score > 0.40`.
- **PLACE_HIGH / PLACE_PROB_HIGH**: `place_prob > 0.80`.
- **B_LOW_VP / B_TIER_LOW_VP_SUPPRESS**: `decision_tier == 'B'` and `velo_prime_prob < 0.30`.
- **MID_PRICE_WINNER_FORENSICS**: misses where the actual winner SP landed in the 3.0-8.5 zone.

## Public Definition

These labels are evidence cohorts used for shadow analysis and operator visibility.
They are not auto-execution permissions and not deployment approvals.
