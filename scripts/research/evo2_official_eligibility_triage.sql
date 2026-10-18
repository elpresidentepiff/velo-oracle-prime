-- Evo2 / Velo result-eligibility evidence triage (READ-ONLY).
-- Do not UPDATE, certify, reflag, or fabricate official result provenance.
-- Evidence is grouped at race-day identity and model row; multiple models per race.

-- 1. Root cause: how many rows and races require each repair category?
SELECT
    COALESCE(evaluation_ineligible_reason, 'UNCLASSIFIED') AS reason,
    COUNT(*) AS model_rows,
    COUNT(DISTINCT (run_date, race_id)) AS race_days,
    COUNT(*) FILTER (WHERE result_source_complete IS TRUE) AS complete_source_rows,
    COUNT(*) FILTER (WHERE result_source_hash IS NOT NULL) AS hashed_source_rows
FROM public.canonical_model_scorecards
WHERE official_evaluation_eligible IS NOT TRUE
GROUP BY 1
ORDER BY model_rows DESC;

-- 2. Prioritize recovery dates: missing source vs hashed but uncertified.
SELECT
    run_date,
    COUNT(DISTINCT race_id) AS race_count,
    COUNT(*) FILTER (
        WHERE evaluation_ineligible_reason = 'GOVERNED_REBUILD_REQUIRED'
    ) AS governed_rebuild_rows,
    COUNT(*) FILTER (
        WHERE evaluation_ineligible_reason = 'RESULT_SOURCE_INCOMPLETE'
          AND result_source_hash IS NOT NULL
    ) AS incomplete_with_source_hash_rows,
    COUNT(*) FILTER (WHERE official_evaluation_eligible IS TRUE) AS eligible_rows
FROM public.canonical_model_scorecards
GROUP BY run_date
ORDER BY run_date DESC;

-- 3. Identify distinct races requiring independently-sourced official truth
-- verification, without interpreting model rows as extra races.
SELECT
    run_date,
    race_id,
    COUNT(*) AS affected_model_rows,
    COUNT(DISTINCT model_name) AS model_count,
    COUNT(DISTINCT result_source_hash)
        FILTER (WHERE result_source_hash IS NOT NULL) AS distinct_result_hashes,
    BOOL_OR(evaluation_ineligible_reason = 'GOVERNED_REBUILD_REQUIRED') AS needs_rebuild,
    BOOL_OR(
        evaluation_ineligible_reason = 'RESULT_SOURCE_INCOMPLETE'
        AND result_source_hash IS NOT NULL
    ) AS has_incomplete_hashed_source
FROM public.canonical_model_scorecards
WHERE official_evaluation_eligible IS NOT TRUE
GROUP BY run_date, race_id
ORDER BY run_date DESC, race_id;

-- IMPORTANT: A present hash is NOT proof the result is complete or official.
-- Reconcile original provider payloads, complete finishers, non-runners, dead
-- heats, voids, actual_winner_id, and timestamp/provenance before the crosswalk.
