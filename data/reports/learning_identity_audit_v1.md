# Learning Identity Audit V1 (LEARNING-LOOP-01A Phase 1)

Run: 2026-07-11T23:54:12.340561Z

## Table row/race counts

| table | rows | distinct races |
|---|---|---|
| runner_prediction_snapshots | 26425 | 1360 |
| historical_feature_store | 31936 | 3156 |
| races | 3675 | 3675 |
| race_results | 3227 | 3227 |
| runner_results | 33430 | 3321 |
| runners | 17386 | 1707 |
| sigma_audits | 3344 | 3344 |
| velo_verdicts | 4494 | 4494 |

## Race-ID namespace formats

- **runner_prediction_snapshots**: {'rp_<COURSE>_<YYYYMMDD>_<time>': 12112, 'numeric': 13217, 'other': 1096}
- **historical_feature_store**: {'numeric': 19948, 'rac_<digits>': 11988}
- **races**: {'rac_<digits>': 1741, 'other': 10, 'numeric': 1924}
- **race_results**: {'numeric': 1924, 'rac_<digits>': 1303}
- **runner_results**: {'rac_<digits>': 13482, 'numeric': 19948}

## Identity join (runner_prediction_snapshots -> results)

- runner_prediction_snapshots_distinct_races: 1360
- runner_prediction_snapshots_distinct_race_horse_pairs: 14172
- local_result_files_scanned: 44
- local_distinct_races: 1617
- local_distinct_race_horse_pairs: 13116
- exact_race_id_join_to_local_results: 766
- exact_race_id_join_pct: 56.3
- exact_race_horse_pair_join_to_local_results: 5278
- exact_race_horse_pair_join_pct: 37.2
- unresolved_races: 594
- unresolved_by_date: {'2026-05-20': 33, '2026-05-21': 44, '2026-05-22': 43, '2026-05-23': 3, '2026-05-24': 7, '2026-05-25': 7, '2026-05-26': 48, '2026-05-27': 2, '2026-05-29': 11, '2026-05-30': 35, '2026-05-31': 7, '2026-06-01': 42, '2026-06-02': 35, '2026-06-03': 65, '2026-06-05': 56, '2026-06-06': 51, '2026-06-07': 30, '2026-06-08': 35, '2026-06-09': 33, '2026-06-11': 6, '2026-06-18': 1}
- supabase_races_table_coverage_gap: {'races_table_max_date': '2026-05-06', 'runner_prediction_snapshots_min_date': '2026-05-20', 'date_overlap_days': 0, 'note': 'races/race_results/runner_results in Supabase are not populated for the era runner_prediction_snapshots covers. The real result-side source of truth for this era is the local data/results/rp_results_YYYY_MM_DD.json corpus, which uses the SAME rp_<COURSE>_<YYYYMMDD>_<time> race_id scheme as runner_prediction_snapshots.'}

## historical_feature_store non-null coverage

| field | non_null | pct |
|---|---|---|
| sp_dec | 31781 | 99.51% |
| implied_prob | 31781 | 99.51% |
| log_sp | 0 | 0.0% |
| sp_rank | 0 | 0.0% |
| is_fav | 0 | 0.0% |
| or_vs_field | 0 | 0.0% |
| rpr_vs_field | 0 | 0.0% |

## Classifications

- LEARNING_IDENTITY_AUDITED
- NO_HFS_MUTATION
- NO_PLAYBOOK_G_MUTATION
- NO_LIVE_SCORING_CHANGE
- NO_MODEL_TRAINING
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
