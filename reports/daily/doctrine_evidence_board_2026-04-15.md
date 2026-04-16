# VÉLØ Doctrine Evidence Board — 2026-04-15
Generated: 2026-04-16T04:24:41.245170+00:00

## Live Results
| races | wins | placed | misses |
| --- | --- | --- | --- |
| 38 | 6 | 11 | 21 |

## Shadow Results
| races | blocker_fired_rows | blocker_helped_rows | blocker_hurt_rows |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |

## Blocker Truth
_No blocker truth rows for this date._

## RPDC Truth
| tagged_rows | cash_window_rows | high_release_score_rows |
| --- | --- | --- |
| 0 | 0 | 0 |

## RPDC Coverage
| reviewed_sigma_rows | reviewed_sigma_rows_with_horse_id | reviewed_sigma_rows_in_rpdc_covered_events | reviewed_sigma_rows_with_exact_event_horse_match |
| --- | --- | --- | --- |
| 38 | 38 | 0 | 0 |

## Weak A Cohort
| weak_a_rows |
| --- |
| 3 |

## Weak A Blocker Split
| cohort | races | win_pct | place_pct | miss_pct |
| --- | --- | --- | --- | --- |
| weak_a_no_blocker | 3 | 33.3 | 33.3 | 33.3 |
| weak_a_with_blocker | 0 | 0.0 | 0.0 | 0.0 |

| blocker_type | count |
| --- | --- |
| none | 0 |

| cohort | top_miss_reasons |
| --- | --- |
| weak_a_no_blocker | mid_priced_won (1) |
| weak_a_with_blocker | none |

| cohort | top_tracks |
| --- | --- |
| weak_a_no_blocker | Southwell (AW) (1), Haydock (1), Newmarket (1) |
| weak_a_with_blocker | none |

| cohort | top_archetypes |
| --- | --- |
| weak_a_no_blocker | unknown (3) |
| weak_a_with_blocker | none |

## Rolling Doctrine Summary
| window | doctrine_family | count | win_pct | place_pct | miss_pct | last_seen | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7d | a_tier_weak_place_support | 33 | 42.4 | 33.3 | 24.2 | 2026-04-15T22:57:54.203658+00:00 | watch |
| 7d | blocker_fired_horse_won | 2 | 100.0 | 0.0 | 0.0 | 2026-04-12T00:44:08.628318+00:00 | review |
| 7d | weak_model_strong_doctrine | 1 | 0.0 | 100.0 | 0.0 | 2026-04-13T21:10:49.218111+00:00 | review |
| 30d | a_tier_weak_place_support | 78 | 30.8 | 38.5 | 30.8 | 2026-04-15T22:57:54.203658+00:00 | watch |
| 30d | blocker_fired_horse_won | 15 | 100.0 | 0.0 | 0.0 | 2026-04-12T00:44:08.628318+00:00 | review |
| 30d | weak_model_strong_doctrine | 1 | 0.0 | 100.0 | 0.0 | 2026-04-13T21:10:49.218111+00:00 | review |

## Blocker Review
| blocker_type | 7d_count | 30d_count | winner_suppression_count | top_tracks | top_archetypes | top_miss_reasons |
| --- | --- | --- | --- | --- | --- | --- |
| longshot_block_allowed | 3 | 18 | 8 | Southwell (AW) (4), Kempton (AW) (2), Dundalk (AW) (IRE) (2) | unknown (18) | outsider_won (1), mid_priced_won (1) |
| market_decoy_signal | 5 | 34 | 7 | unknown (5), Chepstow (3), Ascot (2) | unknown (31), Structure (3) | mid_priced_won (5), market_decoy_followed (4), short_fav_won (3) |

## Longshot Block Allowed Regime Split
| surface | count |
| --- | --- |
| AW | 10 |
| non_AW_or_unknown | 8 |

| actual_winner_sp_bucket | count |
| --- | --- |
| short_<=3.0 | 11 |
| mid_3.01_6.0 | 5 |
| outsider_>6.0 | 2 |

### A-Tier AW Slice
| races | suppressed_winners | win_pct | place_pct | miss_pct |
| --- | --- | --- | --- | --- |
| 10 | 6 | 60.0 | 30.0 | 10.0 |

| suppression_rate_pct | blocked_horse_live_rate_pct | short_priced_actual_winner_share_pct |
| --- | --- | --- |
| 60.0 | 90.0 | 90.0 |

| actual_winner_sp_bucket | count |
| --- | --- |
| short_<=3.0 | 9 |
| outsider_>6.0 | 1 |

| blocked_horse_outcome | count |
| --- | --- |
| WIN | 6 |
| PLACED | 3 |
| MISS | 1 |

## Doctrine Candidates
| doctrine_key | family | rule_type | status | sample_size | win_pct | place_pct | next_review_date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| class_drop_requires_trainer_authority | rpdc_class_drop | promoter | proposed | — | — | — | 2026-04-22 |
| a_tier_weak_place_watch | a_tier_quality | watch | watch | — | — | — | 2026-04-22 |
| longshot_block_allowed_watch_only | blocker_truth | watch | watch | — | — | — | 2026-04-22 |
| market_decoy_signal_active | market_decoy | blocker | active | — | — | — | 2026-04-22 |
| longshot_block_allowed_aw_watch | blocker_regime | watch | watch | — | — | — | 2026-04-23 |
| longshot_block_allowed_shortfav_aw_relax_candidate | blocker_regime | watch | proposed | — | — | — | 2026-04-23 |
| mark_ready_requires_trainer_authority | rpdc_readiness | promoter | proposed | — | — | — | 2026-04-22 |
| headgear_intro_low_authority_suppressor | rpdc_headgear | suppressor | proposed | — | — | — | 2026-04-22 |

## Doctrine Contradictions
| contradiction_count |
| --- |
| 3 |

## Review Clock Notes
- doctrine review clock: `sigma_audits.created_at`
- truth rows are mapped onto the sigma review set with `doctrine_event_id` first; `race_id` fallback is used only when doctrine lineage is missing.
- RPDC release rows are mapped onto the sigma review set with `(doctrine_event_id, horse_id)` first; `(race_id, horse_id)` fallback is used only when doctrine lineage is missing.
- RPDC is currently a sparse candidate surface, not full reviewed-selection coverage.
- `today_rpdc_tags` has no `generated_at`; tag counts are therefore approximated by intersecting sigma review `race_id`s with `run_date = review_date`.
- truth lineage matches: event_id=3436 fallback_race_id=0 unmatched=1019
- RPDC lineage matches: event_id+horse=58 fallback_race_id+horse=0 unmatched=1148
- RPDC coverage: reviewed_sigma_rows=38 with_horse_id=38 in_rpdc_covered_events=0 exact_event_horse_matches=0
