# RP Supabase Target Audit

- Project: `ltbsxbvfsxtnharjvqcm`
- All required safe: `True`

## raw_payload_archive
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `id, pipeline_run_id, endpoint, request_params, race_date, pulled_at, payload_json, checksum, parse_status, parser_version`

## rp_entity_aliases
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `id, entity_type, rp_id, alias_type, alias_value, match_score, verified, created_at`

## rp_ingestion_runs
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `id, run_type, target_id, target_name, started_at, finished_at, records_fetched, records_written, status, error_note`

## rp_meetings
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `bundle_key, created_at, updated_at, source_date, venue_code, course_name, parser_version, parse_success, races_count, runners_count, input_files, warnings, errors, raw_report`

## rp_racecards
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `race_key, bundle_key, source_date, venue_code, course_name, off_time, race_name, race_number, race_type, distance_text, distance_yards, distance_furlongs, distance_meters, class_band, going, prize, runners_count, raw_bundle`

## rp_runner_profiles
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `race_key, runner_number, horse_name, cloth_no, age, sex, weight, days_since_run, trainer_name, jockey_name, owner_name, draw, headgear, form_figures, or_current, rpr_current, ts_current, raw_runner_bundle`

## rp_runner_signals
- Exists: `True`
- Safe to insert: `True`
- Missing: `none`
- Columns: `race_key, runner_number, horse_name, recent_finish_positions, true_run_count, has_recent_win, has_recent_place, days_since_run, ts_improving_flag, or_drop_streak, or_compression_score, release_window_flag, cash_run_flag, trainer_positive_flag, spotlight_present_flag, comment_present_flag, signal_summary, signal_version, raw_signal_payload`
