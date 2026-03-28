-- =============================================================================
-- PR 3: velo_race_truth completeness
-- =============================================================================
-- Adds three missing fields to the canonical analytics surface:
--
--   off_time        : race start time (from Racing API results, written by
--                     run_results_sigma.py → sigma_audits.off_time)
--
--   winner_name     : actual winner's name (from Racing API results, written by
--                     run_results_sigma.py → sigma_audits.actual_winner_name)
--
--   persist_status  : was sigma reconciliation written for this race?
--                     DERIVED in view: 'RECONCILED' | 'PENDING'
--                     No separate column — derivable from join truth.
--
-- Also adds:
--   run_state       : pipeline lifecycle field from PR 2 (running | completed)
--
-- Also fixes:
--   LATERAL joins on pipeline_runs and sigma_audits prevent duplicate rows if
--   multiple runs or multiple sigma writes exist for the same date/race.
--
--   Pipeline_runs join filter updated from status IN (...) to run_state = 'completed'
--   to use the PR 2 lifecycle column.
-- =============================================================================


-- ── Step 1: Add off_time to sigma_audits ─────────────────────────────────────

ALTER TABLE sigma_audits
  ADD COLUMN IF NOT EXISTS off_time TEXT;


-- ── Step 2: Add actual_winner_name to sigma_audits ───────────────────────────

ALTER TABLE sigma_audits
  ADD COLUMN IF NOT EXISTS actual_winner_name TEXT;


-- ── Step 3: Rebuild velo_race_truth view ─────────────────────────────────────
-- All KPI views (velo_tier_performance, velo_tier_summary, velo_run_reliability)
-- read exclusively from velo_race_truth — no changes needed to those views.

CREATE OR REPLACE VIEW velo_race_truth AS
SELECT
    -- Identity
    vv.race_id,
    vv.generated_at::date                                    AS race_date,
    sa.track                                                 AS course,
    sa.off_time,

    -- Prediction
    vv.top_rank_horse_id                                     AS predicted_runner_id,
    vv.decision_tier,
    vv.velo_prime_prob,
    vv.confidence_level,

    -- Model provenance (from full_analysis JSON if populated)
    vv.full_analysis                                         AS model_bundle_raw,

    -- Run lifecycle + health (PR 2: run_state separates lifecycle from terminal truth)
    pr.run_state,
    pr.status                                                AS run_status,
    pr.id                                                    AS pipeline_run_id,
    pr.trigger_source,
    pr.started_at                                            AS scored_at,

    -- Outcome (canonical)
    sa.outcome                                               AS result_outcome,
    sa.top_pick_position                                     AS finish_pos,
    sa.actual_winner_id,
    sa.actual_winner_name                                    AS winner_name,
    sa.actual_winner_sp,
    sa.miss_reason,
    sa.date                                                  AS reconciled_date,

    -- Notes (JSON with pred name, RPD evidence etc.)
    sa.notes                                                 AS sigma_notes,

    -- Persist status: did the sigma loop close for this race?
    -- RECONCILED = sigma_audits row exists (outcome written)
    -- PENDING    = verdict exists but no sigma write yet (race pending or not yet run)
    CASE
        WHEN sa.race_id IS NOT NULL THEN 'RECONCILED'
        ELSE 'PENDING'
    END                                                      AS persist_status,

    -- Betting outcome (NULL if no bet was placed)
    bl.result                                                AS bet_result,
    bl.stake                                                 AS bet_stake,
    bl.odds                                                  AS bet_odds,
    bl.profit_loss                                           AS bet_pl,
    bl.bet_type                                              AS bet_tier,

    -- Missingness flags — explicit, never implied
    CASE WHEN sa.outcome IS NULL  THEN TRUE ELSE FALSE END   AS outcome_missing,
    CASE WHEN pr.status  IS NULL  THEN TRUE ELSE FALSE END   AS run_status_missing,
    CASE WHEN bl.race_id IS NULL  THEN TRUE ELSE FALSE END   AS no_bet_placed,

    -- Timestamps
    vv.generated_at                                          AS verdict_generated_at,
    sa.created_at                                            AS sigma_reconciled_at

FROM velo_verdicts vv

-- LATERAL join sigma: picks the latest sigma_reconciliation row per race_id.
-- Prevents duplicates if run_results_sigma.py ran more than once for the same date.
LEFT JOIN LATERAL (
    SELECT *
    FROM sigma_audits
    WHERE race_id   = vv.race_id
      AND event_type = 'sigma_reconciliation'
    ORDER BY created_at DESC
    LIMIT 1
) sa ON TRUE

-- LATERAL join pipeline_runs: picks the latest completed run for the scoring date.
-- Prevents duplicates if multiple runs completed for the same date (e.g. manual re-run).
-- Uses run_state = 'completed' (PR 2) instead of status IN (...).
LEFT JOIN LATERAL (
    SELECT *
    FROM pipeline_runs
    WHERE source_date  = vv.generated_at::date
      AND service_name = 'velo-prime-scoring'
      AND run_state    = 'completed'
    ORDER BY started_at DESC
    LIMIT 1
) pr ON TRUE

-- Left join betting ledger: only B/C tiers get bets
LEFT JOIN betting_ledger bl
    ON  bl.race_id = vv.race_id
;


-- ── Step 4: Validation queries (run these after applying) ─────────────────────
-- All counts in block A should return rows_in_view = distinct_race_ids.
-- Run each SELECT manually in Supabase SQL editor to confirm.

-- A: No duplicate rows
-- SELECT COUNT(*) AS rows_in_view, COUNT(DISTINCT race_id) AS distinct_race_ids
-- FROM velo_race_truth;
-- EXPECT: rows_in_view = distinct_race_ids

-- B: persist_status distribution
-- SELECT persist_status, COUNT(*) AS cnt FROM velo_race_truth GROUP BY persist_status;
-- EXPECT: 'RECONCILED' for all rows with known outcomes, 'PENDING' for future/unreconciled

-- C: off_time and winner_name coverage (after next sigma run)
-- SELECT COUNT(*) AS total,
--        COUNT(off_time) AS has_off_time,
--        COUNT(winner_name) AS has_winner_name
-- FROM velo_race_truth WHERE persist_status = 'RECONCILED';

-- D: KPI views still resolve
-- SELECT * FROM velo_tier_performance LIMIT 5;
-- SELECT * FROM velo_tier_summary;
-- SELECT * FROM velo_run_reliability LIMIT 5;

-- E: run_state present
-- SELECT DISTINCT run_state FROM velo_race_truth;
-- EXPECT: 'completed' (possibly NULL for rows with no matched pipeline_run)
