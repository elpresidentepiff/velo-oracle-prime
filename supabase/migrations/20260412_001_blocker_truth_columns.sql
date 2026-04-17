-- Migration: add blocker truth columns to race_truth_audits
-- Apply via: Supabase Dashboard > SQL Editor
-- Context: Layer 4 extension — records whether a promotion blocker fired on each
--   scored race, which blocker, and whether it helped or hurt organism behavior.
--   Allows weekly rollup to answer: "Is each blocker making us better or worse?"
--
-- Design:
--   Top-level columns for fast KPI queries (fire counts, help/hurt rates).
--   Full detail already lives in truth_payload->blocker_truth JSONB (added in code).
--   original_tier = tier from synthesize_decision() before blockers apply.
--   final_tier    = tier that was actually stored (decision_tier = post-blocker).

ALTER TABLE race_truth_audits
    ADD COLUMN IF NOT EXISTS blocker_fired    BOOLEAN  DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS blocker_type     TEXT,
    ADD COLUMN IF NOT EXISTS original_tier    TEXT     CHECK (original_tier IS NULL OR original_tier IN ('A','B','C','D','X')),
    ADD COLUMN IF NOT EXISTS blocker_helped   BOOLEAN  DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS blocker_hurt     BOOLEAN  DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS blocker_neutral  BOOLEAN  DEFAULT FALSE;

-- Index for blocker KPI queries
CREATE INDEX IF NOT EXISTS idx_race_truth_audits_blocker_fired
    ON race_truth_audits (blocker_fired)
    WHERE blocker_fired = TRUE;

CREATE INDEX IF NOT EXISTS idx_race_truth_audits_blocker_type
    ON race_truth_audits (blocker_type)
    WHERE blocker_type IS NOT NULL;

-- ── Updated weekly KPI view (replaces existing) ──────────────────────────────
-- Extends velo_truth_rollup with blocker metrics.

CREATE OR REPLACE VIEW velo_truth_rollup AS
SELECT
    DATE_TRUNC('week', race_date)::date                             AS week_start,

    -- Volume
    COUNT(*)                                                         AS races,
    COUNT(*) FILTER (WHERE result_outcome IS NOT NULL)               AS audited,

    -- Outcomes
    COUNT(*) FILTER (WHERE result_outcome = 'WIN')                   AS wins,
    COUNT(*) FILTER (WHERE result_outcome = 'PLACED')                AS placed,
    COUNT(*) FILTER (WHERE result_outcome = 'MISS')                  AS misses,

    -- Core miss types
    COUNT(*) FILTER (WHERE core_miss_type = 'clean_hit')             AS clean_hits,
    COUNT(*) FILTER (WHERE core_miss_type = 'wrong_top_horse')       AS wrong_top,
    COUNT(*) FILTER (WHERE core_miss_type = 'over_suppressed')       AS over_suppressed,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_public_trap')     AS false_traps,
    COUNT(*) FILTER (WHERE core_miss_type = 'missed_public_trap')    AS missed_traps,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_prep_release')    AS false_preps,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_chaos')           AS false_chaos,
    COUNT(*) FILTER (WHERE core_miss_type = 'missed_chaos')          AS missed_chaos,

    -- Gate performance
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_helped')   AS gate_helped,
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_hurt')     AS gate_hurt,
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_neutral')  AS gate_neutral,
    COUNT(*) FILTER (WHERE gate_fired)                                     AS gate_total_fires,

    -- Archetype performance
    COUNT(*) FILTER (WHERE archetype_match = TRUE)  AS archetype_correct,
    COUNT(*) FILTER (WHERE archetype_match = FALSE) AS archetype_wrong,

    -- Blocker performance (new)
    COUNT(*) FILTER (WHERE blocker_fired = TRUE)                     AS blocker_total_fires,
    COUNT(*) FILTER (WHERE blocker_fired AND blocker_helped)         AS blocker_helped_count,
    COUNT(*) FILTER (WHERE blocker_fired AND blocker_hurt)           AS blocker_hurt_count,
    COUNT(*) FILTER (WHERE blocker_fired AND blocker_neutral)        AS blocker_neutral_count,

    -- Per-blocker fire counts
    COUNT(*) FILTER (WHERE blocker_type = 'macro_chaos_mode')        AS blocker_chaos_fires,
    COUNT(*) FILTER (WHERE blocker_type = 'market_decoy_signal')     AS blocker_mds_fires,
    COUNT(*) FILTER (WHERE blocker_type = 'longshot_risk_flag')      AS blocker_ls_fires

FROM race_truth_audits
WHERE result_outcome IS NOT NULL
GROUP BY DATE_TRUNC('week', race_date)
ORDER BY week_start DESC;
