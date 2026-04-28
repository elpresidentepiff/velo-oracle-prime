# Historical Doctrine Activation Smoke V1

## Dry Run
- Rows evaluated: `244`
- Vector length before: `{"37": 244}`
- Vector length after: `{"37": 244}`
- dist_f before: `{"min": 16.0, "max": 16.0, "variance": 0.0}`
- dist_f after: `{"min": 5.0, "max": 19.0, "variance": 16.59486697124429}`
- Prior coverage: `0=94, 1+=150, 3+=57`
- Leakage audit: `{"same_day_or_future_history_rows_used": 0, "cutoff_rule": "prior_race_date_lt_current_race_date", "rows_with_0_prior_runs": 94, "rows_with_1_plus_prior_runs": 150, "rows_with_3_plus_prior_runs": 57}`
- Outcome exclusion audit: `{"forbidden_current_outcome_fields": ["winner_flag", "is_winner", "placed_flag", "finish_position", "position", "comment", "result_comment", "post_race_ranking", "sqpe_v17_prob", "velo_prime_prob", "g_base_prob", "place_prob", "g_shadow_flags", "g_shadow_horse_id", "g_shadow_mode", "g_shadow_multiplier", "verdict_flags"], "feature_vector_intersection": [], "status": "pass"}`

## Smoke Write
- Rows written: `244`
- Winner parity unchanged: `True`
- Duplicate race_id+horse_id count: `0`
- MPI null count: `0`
- chaos_bloom null count: `0`
- macro-year mismatch count: `0`
- dist_f variance after write: `16.59486697124429`
- doctrine audit active/non-constant count: `35`
