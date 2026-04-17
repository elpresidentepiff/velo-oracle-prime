-- =============================================================================
-- VÉLØ Race Truth Table
-- =============================================================================
-- Single canonical analytics surface: one row per scored race selection.
-- ALL downstream KPI queries (WIN%, ROI, tier performance) run from this view/table.
-- No separate script logic required to interpret truth.
--
-- Source joins (deterministic, documented):
--   velo_verdicts       → prediction metadata (tier, prob, model bundle)
--   sigma_audits        → reconciled outcome (WIN/PLACED/MISS/NO_RESULT)
--   pipeline_runs       → run health status
--   betting_ledger      → bet outcome if exists
--
-- Vocabulary contract:
--   result_outcome  : WIN | PLACED | MISS | NO_RESULT  (canonical, from sigma_audits)
--   run_status      : PASS | DEGRADED | FAIL           (canonical, from pipeline_runs)
--   decision_tier   : A | B | C | D | X                (canonical, from velo_verdicts)
-- =============================================================================

-- ── DB constraints on sigma_audits.outcome ───────────────────────────────────
-- Reject any non-canonical outcome value at the DB layer.
-- This is the last line of defence after application-level validation.

ALTER TABLE sigma_audits
  ADD CONSTRAINT sigma_audits_outcome_enum
  CHECK (outcome IN ('WIN', 'PLACED', 'MISS', 'NO_RESULT'));

ALTER TABLE sigma_audits
  ADD CONSTRAINT sigma_audits_tier_enum
  CHECK (decision_tier IS NULL OR decision_tier IN ('A', 'B', 'C', 'D', 'X'));

-- ── DB constraint on pipeline_runs.status ────────────────────────────────────
ALTER TABLE pipeline_runs
  ADD CONSTRAINT pipeline_runs_status_enum
  CHECK (status IN ('in_progress', 'PASS', 'DEGRADED', 'FAIL', 'abandoned'));

-- ── velo_race_truth view ──────────────────────────────────────────────────────
-- One row per scored race selection per day.
-- Aggregates from canonical source tables only.

CREATE OR REPLACE VIEW velo_race_truth AS
SELECT
    -- Identity
    vv.race_id,
    vv.generated_at::date                              AS race_date,
    sa.track                                           AS course,

    -- Prediction
    vv.top_rank_horse_id                               AS predicted_runner_id,
    vv.decision_tier,
    vv.velo_prime_prob,
    vv.confidence_level,

    -- Model provenance (from full_analysis JSON if populated)
    vv.full_analysis                                   AS model_bundle_raw,

    -- Run health
    pr.status                                          AS run_status,
    pr.id                                              AS pipeline_run_id,
    pr.started_at                                      AS scored_at,

    -- Outcome (canonical)
    sa.outcome                                         AS result_outcome,
    sa.top_pick_position                               AS finish_pos,
    sa.actual_winner_id,
    sa.actual_winner_sp,
    sa.miss_reason,
    sa.date                                            AS reconciled_date,

    -- Notes (JSON with pred name, RPD evidence etc.)
    sa.notes                                           AS sigma_notes,

    -- Betting outcome (NULL if no bet was placed)
    bl.result                                          AS bet_result,
    bl.stake                                           AS bet_stake,
    bl.odds                                            AS bet_odds,
    bl.profit_loss                                     AS bet_pl,
    bl.bet_type                                        AS bet_tier,

    -- Missingness flags — explicit, never implied
    CASE WHEN sa.outcome IS NULL THEN TRUE ELSE FALSE END   AS outcome_missing,
    CASE WHEN pr.status   IS NULL THEN TRUE ELSE FALSE END   AS run_status_missing,
    CASE WHEN bl.race_id  IS NULL THEN TRUE ELSE FALSE END   AS no_bet_placed,

    -- Timestamps
    vv.generated_at                                    AS verdict_generated_at,
    sa.created_at                                      AS sigma_reconciled_at

FROM velo_verdicts vv

-- Left join sigma: outcome may not exist yet (race hasn't run / reconciliation pending)
LEFT JOIN sigma_audits sa
    ON  sa.race_id = vv.race_id
    AND sa.event_type = 'sigma_reconciliation'

-- Left join pipeline_run: match by date and service
LEFT JOIN pipeline_runs pr
    ON  pr.source_date  = vv.generated_at::date::text
    AND pr.service_name = 'velo-prime-scoring'
    AND pr.status IN ('PASS', 'DEGRADED', 'FAIL')

-- Left join betting ledger: only B/C tiers get bets
LEFT JOIN betting_ledger bl
    ON  bl.race_id = vv.race_id
;

-- ── KPI views (read from velo_race_truth only) ────────────────────────────────

-- Daily tier performance
CREATE OR REPLACE VIEW velo_tier_performance AS
SELECT
    race_date,
    decision_tier,
    COUNT(*)                                                        AS races,
    COUNT(*) FILTER (WHERE result_outcome = 'WIN')                  AS wins,
    COUNT(*) FILTER (WHERE result_outcome IN ('WIN','PLACED'))       AS placed,
    COUNT(*) FILTER (WHERE result_outcome = 'MISS')                  AS misses,
    COUNT(*) FILTER (WHERE result_outcome = 'NO_RESULT')             AS no_result,
    COUNT(*) FILTER (WHERE outcome_missing)                          AS outcome_pending,
    ROUND(
        COUNT(*) FILTER (WHERE result_outcome = 'WIN')::numeric
        / NULLIF(COUNT(*) FILTER (WHERE result_outcome IS NOT NULL AND NOT outcome_missing), 0) * 100, 1
    )                                                               AS win_pct,
    ROUND(
        COUNT(*) FILTER (WHERE result_outcome IN ('WIN','PLACED'))::numeric
        / NULLIF(COUNT(*) FILTER (WHERE result_outcome IS NOT NULL AND NOT outcome_missing), 0) * 100, 1
    )                                                               AS place_pct,
    COALESCE(SUM(bet_pl), 0)                                        AS total_pl,
    COUNT(*) FILTER (WHERE run_status = 'DEGRADED')                  AS degraded_runs,
    COUNT(*) FILTER (WHERE run_status = 'FAIL')                      AS failed_runs
FROM velo_race_truth
GROUP BY race_date, decision_tier
ORDER BY race_date DESC, decision_tier;


-- All-time tier summary
CREATE OR REPLACE VIEW velo_tier_summary AS
SELECT
    decision_tier,
    COUNT(*)                                                         AS total_races,
    COUNT(*) FILTER (WHERE result_outcome = 'WIN')                   AS wins,
    COUNT(*) FILTER (WHERE result_outcome IN ('WIN','PLACED'))        AS placed,
    COUNT(*) FILTER (WHERE result_outcome = 'MISS')                   AS misses,
    ROUND(
        COUNT(*) FILTER (WHERE result_outcome = 'WIN')::numeric
        / NULLIF(COUNT(*) FILTER (WHERE NOT outcome_missing), 0) * 100, 1
    )                                                                AS win_pct,
    ROUND(
        COUNT(*) FILTER (WHERE result_outcome IN ('WIN','PLACED'))::numeric
        / NULLIF(COUNT(*) FILTER (WHERE NOT outcome_missing), 0) * 100, 1
    )                                                                AS place_pct,
    COALESCE(SUM(bet_pl), 0)                                         AS total_pl,
    COUNT(*) FILTER (WHERE no_bet_placed = FALSE AND bet_result IS NOT NULL) AS bets_placed,
    COUNT(*) FILTER (WHERE run_status_missing)                        AS runs_with_missing_status
FROM velo_race_truth
GROUP BY decision_tier
ORDER BY decision_tier;


-- Run reliability summary
CREATE OR REPLACE VIEW velo_run_reliability AS
SELECT
    race_date,
    run_status,
    COUNT(DISTINCT pipeline_run_id)  AS pipeline_runs,
    COUNT(*)                          AS races_scored,
    COUNT(*) FILTER (WHERE outcome_missing)   AS outcomes_pending,
    COUNT(*) FILTER (WHERE NOT outcome_missing) AS outcomes_reconciled
FROM velo_race_truth
GROUP BY race_date, run_status
ORDER BY race_date DESC;
