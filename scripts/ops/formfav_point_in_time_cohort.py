"""Point-in-time FormFav training cohort discovery; read-only SQL contract.

The capture table has multiple snapshots per runner. Never fit on each snapshot.
Only final results are candidates for labels, and result payload identity must
be audited before constructing any target column.
"""
POINT_IN_TIME_COHORT_SQL = """
WITH selected AS (
 SELECT DISTINCT ON (c.provider_race_key, c.provider_runner_number)
   c.provider_race_key, c.provider_runner_number, c.provider_runner_name,
   c.captured_at, c.off_time_utc, c.source_payload_sha256,
   c.source_payload
 FROM formfav_factual_captures c
 WHERE c.captured_at < c.off_time_utc - interval '10 minutes'
   AND c.source_payload_sha256 IS NOT NULL
 ORDER BY c.provider_race_key, c.provider_runner_number, c.captured_at DESC, c.id DESC
)
SELECT count(*) runner_snapshots, count(distinct s.provider_race_key) races,
       count(*) FILTER (WHERE r.provider_race_key IS NOT NULL) snapshots_with_final_race_result,
       count(distinct s.provider_race_key) FILTER (WHERE r.provider_race_key IS NOT NULL) races_with_final_result
FROM selected s
LEFT JOIN formfav_results r ON r.provider_race_key=s.provider_race_key
 AND r.result_stage='final' AND r.interim=false;
"""

def validate_training_row(row):
    """Do not silently authorize fitting from race-level results alone."""
    return bool(
        row.get("captured_at") and row.get("off_time_utc")
        and row.get("source_payload_sha256")
        and row.get("final_result_verified")
        and row.get("runner_result_identity_verified")
        and row.get("feature_schema_verified")
        and row.get("pre_off_margin_verified")
        and not row.get("synthetic")
    )
