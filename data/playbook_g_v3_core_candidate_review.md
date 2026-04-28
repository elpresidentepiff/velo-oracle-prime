# Playbook G V3 Core Candidate Review

- V3 suite verdict: `FAIL`
- Core candidate classification: `CANDIDATE_PASS_OFFLINE_RESEARCH_ONLY`
- Final recommendation: `B` - accept V3 core as offline research candidate only

## Core Comparisons
- Core vs market log loss: `1.434518` vs `1.725229`
- Core vs V2 best log loss: `1.434518` vs `1.481028`
- Core vs market+ratings log loss: `1.434518` vs `1.481647`

## Blocks To Promotion
- V3 full suite failed because market-assisted arms violated the market-isolation gate.
- Market calibration arm exceeded top-1 market overlap ceiling.
- Residual-over-market arm exceeded both market correlation and top-1 overlap ceilings.
- Core calibration quality is still weaker than the market baseline and needs repair without recrowding.
- 2025 remains sensitivity-only because the sample is only 26 races.
- No production promotion path has been approved for an offline-only research candidate.

## Next Experiment
- Run a core-only stability audit: bootstrap confidence intervals, year-by-year degradation review, HK/FR split reliability, and calibration repair that does not reintroduce raw market crowding.
