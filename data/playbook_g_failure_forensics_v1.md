# Playbook G Failure Forensics v1

Generated: `2026-04-27T12:09:43.464724+00:00`

No retraining was performed. This is a forensics-only analysis of the checkpointed offline dry-run.

## Core Diagnosis
- Recommendation: `D`
- Build stronger doctrine features first, then run the V2 ablation dry-run.

## HK Failure
- HK test sample: `29 races / 319 runners`
- HK market log loss: `2.004304`
- HK candidate log loss: `2.413058`
- HK candidate top-1 vs market: `0.551724` vs `0.344828`

## FR Success
- FR test sample: `84 races / 683 runners`
- FR market log loss: `1.629290`
- FR candidate log loss: `1.325495`

## Doctrine Layer
- Combined market + rating importance share: `1.000000`
- Doctrine importance share: `0.000000`
- Constant doctrine features: `["runs_since_win", "runs_since_place", "runs_since_mkt_support", "curr_or_minus_last_win_or", "curr_or_minus_best_or", "mark_compression_score", "release_window_score", "course_fit_score", "going_fit_score", "distance_fit_score", "quiet_run_score", "trainer_timing_score", "jockey_switch_intent", "odds_resilience_score", "odds_contraction_score", "decoy_support_flag", "setup_run_flag", "cash_run_flag"]`

## Overfit
- Overfit status: `high`
- Validation log-loss increase vs train: `0.446161`
- Test log-loss increase vs train: `0.635032`

## Next Move
- Do not promote the current candidate.
- Rebuild the doctrine feature layer with real historical context.
- Then run the required V2 ablation plan under the same offline controls.
