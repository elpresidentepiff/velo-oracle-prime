# Global Clean Spine Audit v2

## Summary
- **A_accepted_clean_race_event_count**: `1671`
- **B_accepted_historical_runner_count**: `18331`
- **C_accepted_hfs_row_count**: `18331`
- **F_duplicate_race_id_count**: `0`
- **G_duplicate_event_key_count**: `0`
- **H_duplicate_race_id_horse_id_count**: `0`
- **I_missing_hfs_rows**: `0`
- **J_orphan_hfs_rows**: `0`
- **N_macro_year_mismatch_count**: `0`
- **R_race_date_min_max**: `2017-01-01 -> 2024-11-23`
- **S_jurisdiction_breakdown**: `{'HK': 1022, 'FR': 630, 'JPN': 19}`
- **T_year_breakdown**: `{'2017': 294, '2018': 280, '2019': 292, '2020': 194, '2021': 321, '2022': 202, '2023': 47, '2024': 41}`
- **course_breakdown_top_50**: `{'Sha Tin (HK)': 579, 'Chantilly (FR)': 511, 'Happy Valley (HK)': 443, 'Compiegne (FR)': 119, 'Kokura (JPN)': 11, 'Sapporo (JPN)': 8}`

## Parity
- `D_race_results_runner_results_hfs_parity`: `{'accepted_race_events': 1671, 'accepted_race_results_rows': 1671, 'accepted_runner_rows': 18331, 'accepted_hfs_rows': 18331, 'runner_hfs_match': True, 'missing_hfs_rows': 0, 'orphan_hfs_rows': 0, 'race_results_match': True}`
- `E_winner_parity`: `{'ok': True, 'bad_race_count': 0, 'bad_races_sample': {}}`

## Signal
- `K_vector_dimension_distribution`: `{'37': 18331}`
- `L_MPI_stats`: `{'null_count': 0, 'min': 0.1277, 'max': 100.0, 'variance': 893.9245739245306}`
- `M_chaos_bloom_stats`: `{'null_count': 0, 'min': 37.3413, 'max': 97.3157, 'variance': 59.86141074220885}`
- `story_anchor_narrative_null_classification`: `{'expected_historical_nulls': 18331}`

## Completeness
- `O_doctrine_tag_completeness`: `{'signal_contract_version_complete_hfs': '18331/18331', 'mpi_source_complete_hfs': '18331/18331', 'chaos_bloom_source_complete_hfs': '18331/18331', 'signal_contract_version_complete_races': '1671/1671'}`
- `P_provenance_tag_completeness`: `{'event_identity_contract_complete_hfs': '18331/18331', 'data_owner_confirmed_true_hfs': '18331/18331', 'training_eligible_pending_hfs': '18331/18331', 'source_historical_raceform_hfs': '18331/18331', 'bridge_version_complete_hfs': '18331/18331', 'discovery_version_complete_hfs': '18331/18331', 'event_identity_contract_complete_races': '1671/1671', 'data_owner_confirmed_true_races': '1671/1671', 'training_eligible_pending_races': '1671/1671', 'source_historical_raceform_races': '1671/1671', 'bridge_version_complete_races': '1671/1671', 'discovery_version_complete_races': '1671/1671'}`
- `Q_training_eligible_distribution`: `{'pending_global_training_gate': 18331}`

## Block 025
- `{'bridge_block': 'OASIS_BLOCK_025', 'status': 'rolled_back', 'race_events': 26, 'runner_rows': 244, 'reason': 'macro_year_mismatch', 'race_year': 2025, 'macro_layer_support': '2012-2024', 'scorer_fallback': '2025 -> 2024', 'archive_exhausted': True}`

## Decision Gate
- `parity_holds`: `True`
- `winner_parity_100`: `True`
- `duplicates_zero`: `True`
- `missing_vectors_zero`: `True`
- `vector_length_37_only`: `True`
- `MPI_nulls_zero`: `True`
- `chaos_bloom_nulls_zero`: `True`
- `MPI_variance_gt_zero`: `True`
- `chaos_bloom_variance_gt_zero`: `True`
- `macro_year_mismatch_zero`: `True`
- `doctrine_tags_complete`: `True`
- `provenance_tags_complete`: `True`
- `training_eligible_pending_only`: `True`
- `pass`: `True`