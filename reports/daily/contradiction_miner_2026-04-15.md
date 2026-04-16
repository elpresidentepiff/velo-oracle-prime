# VÉLØ Contradiction Miner — 2026-04-15
Generated: 2026-04-16T04:25:22.974703+00:00

Total flagged races: 3

## Contradiction Counts
| contradiction_type | count |
| --- | --- |
| a_tier_weak_place_support | 3 |

## Weak A Blocker Split
| cohort | races | win_pct | place_pct | miss_pct |
| --- | --- | --- | --- | --- |
| weak_a_no_blocker | 3 | 33.3 | 33.3 | 33.3 |
| weak_a_with_blocker | 0 | 0.0 | 0.0 | 0.0 |

| blocker_type | count |
| --- | --- |
| none | 0 |

| cohort | top_miss_reasons | top_tracks | top_archetypes |
| --- | --- | --- | --- |
| weak_a_no_blocker | mid_priced_won (1) | Southwell (AW) (1), Haydock (1), Newmarket (1) | unknown (3) |
| weak_a_with_blocker | none | none | none |

## RPDC Coverage
| reviewed_sigma_rows | reviewed_sigma_rows_with_horse_id | reviewed_sigma_rows_in_rpdc_covered_events | reviewed_sigma_rows_with_exact_event_horse_match |
| --- | --- | --- | --- |
| 38 | 38 | 0 | 0 |

## Flagged Races
| race_id | contradiction_type | tier | confidence | verdict_score | outcome | blocker_type | has_cash_window | max_rpdc_release_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rac_11902917 | a_tier_weak_place_support | A | None | None | MISS | None | False | 0.0 |
| rac_11922261 | a_tier_weak_place_support | A | None | None | WIN | None | False | 0.0 |
| rac_11901019 | a_tier_weak_place_support | A | None | None | PLACED | None | False | 0.0 |

## Review Clock Notes
- doctrine review clock: `sigma_audits.created_at`
- truth rows are mapped onto the reviewed sigma set with `doctrine_event_id` first; `race_id` fallback is used only when doctrine lineage is missing.
- RPDC release rows are mapped onto the reviewed sigma selections with `(doctrine_event_id, horse_id)` first; `(race_id, horse_id)` fallback is used only when doctrine lineage is missing.
- RPDC is currently a sparse candidate surface, not full reviewed-selection coverage.
- truth lineage matches: event_id=0 fallback_race_id=0 unmatched=44
- RPDC lineage matches: event_id+horse=0 fallback_race_id+horse=0 unmatched=38
- RPDC coverage: reviewed_sigma_rows=38 with_horse_id=38 in_rpdc_covered_events=0 exact_event_horse_matches=0