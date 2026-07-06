# July 06 Sigma Runtime Learning Summary

Classification: **SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS**
(NOT OFFICIAL_LIVE_VERDICT_SIGMA)

Generated: 2026-07-06T21:54:32.282870Z

## Why runtime artifacts, not velo_verdicts

July 06 did not have pre-race Supabase `velo_verdicts` rows — no live production
scorer run happened for this date. Sigma was run from existing raceday runtime
artifacts (Old VELO report-only scorer, New Build two-lane readiness, Champion
Intent Shadow scorecard, dashboard model-suggestions join) and parsed RP
results instead. This is valid learning evidence. It is not live-staking proof.
Promotion remains gated.

## Result

- Top-pick events evaluated: 324
- Hits: 55
- Races with parsed results: 35/36
- Match audit: {"ID_MATCH": 1215, "NAME_FALLBACK_MATCH": 301, "NO_RESULT_MATCH": 131}
- Models available: CHAMPION_INTENT_SHADOW, MAIN_VELO_PRIME, NEW_BUILD_LANE_A, NEW_BUILD_LANE_B, NEW_BUILD_LANE_C, OLD_VELO_LONGSHOT, OLD_VELO_PLACE, OLD_VELO_WIN, SQPE_NO_RPR_SHADOW
- Models missing: NEW_BUILD_POLICY_V1
