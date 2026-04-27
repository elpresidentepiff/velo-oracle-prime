# Global Clean Spine Audit v1

## Scope
- Accepted historical races are identified by `races.raw.source = historical_raceform` and `races.raw.is_historical_backfill = true`.
- HFS rows are scoped by those accepted `race_id` values and `reconstruction_version = V17_B1`.

## Summary
- **A_accepted_clean_race_event_count**: `1671`
- **B_accepted_historical_runner_count**: `18331`
- **C_accepted_hfs_row_count**: `18331`
- **F_duplicate_race_id_count**: `0`
- **G_duplicate_event_key_count**: `0`
- **H_duplicate_race_id_horse_id_count**: `0`
- **I_missing_hfs_rows**: `0`
- **J_orphan_hfs_rows**: `0`
- **K_vector_null_count**: `0`
- **M_MPI_null_count**: `0`
- **O_chaos_bloom_null_count**: `0`
- **Q_macro_year_mismatch_count**: `0`
- **R_race_date_min_max**: `2017-01-01 -> 2024-11-23`

## Parity
- `accepted_race_events`: `1671`
- `accepted_race_results_rows`: `1671`
- `accepted_runner_rows`: `18331`
- `accepted_hfs_rows`: `18331`
- `runner_hfs_match`: `True`
- `missing_hfs_rows`: `0`
- `orphan_hfs_rows`: `0`
- `race_results_match`: `True`

## Signal
- `MPI min/max/variance`: `{'min': 0.1277, 'max': 100.0, 'variance': 893.9245739245306}`
- `chaos_bloom min/max/variance`: `{'min': 37.3413, 'max': 97.3157, 'variance': 59.86141074220885}`
- `vector dimensions`: `{'37': 18331}`

## Breakdown
- `jurisdiction`: `{'HK': 1022, 'FR': 630, 'JPN': 19}`
- `year`: `{'2017': 294, '2018': 280, '2019': 292, '2020': 194, '2021': 321, '2022': 202, '2023': 47, '2024': 41}`
- `top courses`: `{'Sha Tin (HK)': 579, 'Chantilly (FR)': 511, 'Happy Valley (HK)': 443, 'Compiegne (FR)': 119, 'Kokura (JPN)': 11, 'Sapporo (JPN)': 8}`

## Tag Completeness
- `doctrine`: `{'signal_contract_version_complete': '18331/18331', 'mpi_source_complete': '18331/18331', 'chaos_bloom_source_complete': '18331/18331', 'race_level_signal_contract_complete': '1571/1671'}`
- `provenance`: `{'event_identity_contract_complete_hfs': '10508/18331', 'data_owner_confirmed_true_hfs': '7209/18331', 'training_eligible_pending_hfs': '7209/18331', 'event_identity_contract_complete_races': '961/1671', 'data_owner_confirmed_true_races': '665/1671', 'training_eligible_pending_races': '665/1671', 'source_historical_raceform_races': '1671/1671'}`
- `training_eligible distribution`: `{'pending_global_training_gate': 7209, 'None': 11122}`

## Block 025
- `{'bridge_block': 'OASIS_BLOCK_025', 'status': 'rolled_back', 'race_events': 26, 'runner_rows': 244, 'reason': 'macro_year_mismatch', 'race_year': 2025, 'macro_layer_support': '2012-2024', 'scorer_fallback': '2025 -> 2024', 'archive_exhausted': True}`

## Decision Gate
- `parity_holds`: `True`
- `winner_parity_100`: `True`
- `duplicates_zero`: `True`
- `missing_vectors_zero`: `True`
- `vector_length_37_only`: `True`
- `mpi_nulls_zero`: `True`
- `chaos_nulls_zero`: `True`
- `mpi_variance_gt_zero`: `True`
- `chaos_variance_gt_zero`: `True`
- `macro_year_mismatch_zero`: `True`
- `doctrine_tags_complete`: `True`
- `provenance_tags_complete`: `False`
- `training_eligible_pending_only`: `False`
- `pass`: `False`

## Samples
- `clean_event_keys_sample`: `['778308|Happy Valley (HK)|2021-02-17', '778730|Chantilly (FR)|2021-02-19', '778888|Chantilly (FR)|2021-02-19', '778992|Chantilly (FR)|2021-02-22', '779003|Chantilly (FR)|2021-02-22', '778945|Happy Valley (HK)|2021-02-24', '778950|Happy Valley (HK)|2021-02-24', '778951|Happy Valley (HK)|2021-02-24', '779092|Sha Tin (HK)|2021-02-28', '779095|Sha Tin (HK)|2021-02-28', '779096|Sha Tin (HK)|2021-02-28', '779314|Chantilly (FR)|2021-03-02', '779316|Chantilly (FR)|2021-03-02', '779227|Happy Valley (HK)|2021-03-03', '779229|Happy Valley (HK)|2021-03-03', '779230|Happy Valley (HK)|2021-03-03', '779231|Happy Valley (HK)|2021-03-03', '779232|Happy Valley (HK)|2021-03-03', '779773|Sha Tin (HK)|2021-03-07', '779774|Sha Tin (HK)|2021-03-07', '779775|Sha Tin (HK)|2021-03-07', '779776|Sha Tin (HK)|2021-03-07', '779777|Sha Tin (HK)|2021-03-07', '779778|Sha Tin (HK)|2021-03-07', '779882|Chantilly (FR)|2021-03-09', '780005|Chantilly (FR)|2021-03-09', '779942|Chantilly (FR)|2021-03-10', '780061|Chantilly (FR)|2021-03-10', '779929|Happy Valley (HK)|2021-03-10', '779930|Happy Valley (HK)|2021-03-10', '779933|Happy Valley (HK)|2021-03-10', '779935|Happy Valley (HK)|2021-03-10', '780068|Sha Tin (HK)|2021-03-13', '780076|Sha Tin (HK)|2021-03-13', '780243|Chantilly (FR)|2021-03-15', '780301|Chantilly (FR)|2021-03-16', '780302|Chantilly (FR)|2021-03-16', '780743|Compiegne (FR)|2021-03-17', '780763|Compiegne (FR)|2021-03-17', '780211|Happy Valley (HK)|2021-03-17', '780212|Happy Valley (HK)|2021-03-17', '780266|Chantilly (FR)|2021-03-18', '780267|Chantilly (FR)|2021-03-18', '780831|Chantilly (FR)|2021-03-18', '780770|Sha Tin (HK)|2021-03-21', '780916|Happy Valley (HK)|2021-03-24', '780918|Happy Valley (HK)|2021-03-24', '781060|Sha Tin (HK)|2021-03-28', '781061|Sha Tin (HK)|2021-03-28', '781062|Sha Tin (HK)|2021-03-28']`