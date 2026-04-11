-- Migration: create race_truth_audits table
-- Apply via: Supabase Dashboard > SQL Editor
-- Context: Layer 4 of the VÉLØ organism — post-race truth loop.
--   One row per scored race. Records core miss type, gate truth,
--   archetype truth, and horse-state truth so the organism can identify
--   its own error patterns and correct over time.
--
-- Design principles:
--   - Key summary columns are queryable at the top level (fast KPI queries)
--   - Full truth detail lives in truth_payload JSONB (auditable, extensible)
--   - outcome vocabulary mirrors sigma_audits.outcome constraint

CREATE TABLE IF NOT EXISTS race_truth_audits (
    id                    BIGSERIAL PRIMARY KEY,
    race_id               TEXT        NOT NULL,
    race_date             DATE,
    generated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- ── Prediction snapshot ─────────────────────────────────────────────────
    decision_tier         TEXT,                  -- A | B | C | D | X
    assigned_archetype    TEXT,                  -- Structure | Compression | PrepRelease | PublicTrap | Chaos
    archetype_confidence  TEXT,                  -- high | medium | low
    velo_prime_prob       NUMERIC(6,4),
    top_horse_id          TEXT,
    gate_fired            BOOLEAN,
    gate_upgrade_applied  BOOLEAN,

    -- ── Actual outcome (from sigma_audits) ──────────────────────────────────
    result_outcome        TEXT,                  -- WIN | PLACED | MISS | NO_RESULT
    finish_position       INTEGER,
    actual_winner_id      TEXT,
    actual_winner_sp      NUMERIC(8,2),

    -- ── Core truth (Layer 1 summary) ────────────────────────────────────────
    core_miss_type        TEXT,

    -- ── Gate truth summary ──────────────────────────────────────────────────
    gate_outcome          TEXT,                  -- gate_helped | gate_hurt | gate_neutral

    -- ── Archetype truth summary ─────────────────────────────────────────────
    archetype_match       BOOLEAN,               -- TRUE if race behaved like assigned archetype
    archetype_truth       TEXT,                  -- correct | wrong | insufficient_evidence

    -- ── Full truth payload ──────────────────────────────────────────────────
    -- Contains horse_state_truth, gate_truth, archetype_truth detail, evidence
    truth_payload         JSONB,

    -- ── Constraints ─────────────────────────────────────────────────────────
    CONSTRAINT race_truth_audits_unique_race UNIQUE (race_id),
    CONSTRAINT race_truth_audits_outcome_check
        CHECK (result_outcome IS NULL OR result_outcome IN ('WIN', 'PLACED', 'MISS', 'NO_RESULT')),
    CONSTRAINT race_truth_audits_tier_check
        CHECK (decision_tier IS NULL OR decision_tier IN ('A', 'B', 'C', 'D', 'X'))
);

-- Indexes for KPI queries
CREATE INDEX IF NOT EXISTS idx_race_truth_audits_date
    ON race_truth_audits (race_date DESC);

CREATE INDEX IF NOT EXISTS idx_race_truth_audits_miss_type
    ON race_truth_audits (core_miss_type)
    WHERE core_miss_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_race_truth_audits_archetype
    ON race_truth_audits (assigned_archetype)
    WHERE assigned_archetype IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_race_truth_audits_outcome
    ON race_truth_audits (result_outcome)
    WHERE result_outcome IS NOT NULL;

-- ── Weekly KPI view ──────────────────────────────────────────────────────────
-- Feeds weekly rollup report. Query directly for any date range.

CREATE OR REPLACE VIEW velo_truth_rollup AS
SELECT
    -- Temporal bucket (week)
    DATE_TRUNC('week', race_date)::date                         AS week_start,

    -- Volume
    COUNT(*)                                                     AS races,
    COUNT(*) FILTER (WHERE result_outcome IS NOT NULL)           AS audited,

    -- Outcomes
    COUNT(*) FILTER (WHERE result_outcome = 'WIN')               AS wins,
    COUNT(*) FILTER (WHERE result_outcome = 'PLACED')            AS placed,
    COUNT(*) FILTER (WHERE result_outcome = 'MISS')              AS misses,

    -- Core miss types
    COUNT(*) FILTER (WHERE core_miss_type = 'clean_hit')         AS clean_hits,
    COUNT(*) FILTER (WHERE core_miss_type = 'wrong_top_horse')   AS wrong_top,
    COUNT(*) FILTER (WHERE core_miss_type = 'over_suppressed')   AS over_suppressed,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_public_trap') AS false_traps,
    COUNT(*) FILTER (WHERE core_miss_type = 'missed_public_trap') AS missed_traps,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_prep_release') AS false_preps,
    COUNT(*) FILTER (WHERE core_miss_type = 'false_chaos')       AS false_chaos,
    COUNT(*) FILTER (WHERE core_miss_type = 'missed_chaos')      AS missed_chaos,

    -- Gate performance
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_helped')  AS gate_helped,
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_hurt')    AS gate_hurt,
    COUNT(*) FILTER (WHERE gate_fired AND gate_outcome = 'gate_neutral') AS gate_neutral,
    COUNT(*) FILTER (WHERE gate_fired)                                    AS gate_total_fires,

    -- Archetype performance
    COUNT(*) FILTER (WHERE archetype_match = TRUE)  AS archetype_correct,
    COUNT(*) FILTER (WHERE archetype_match = FALSE) AS archetype_wrong

FROM race_truth_audits
WHERE result_outcome IS NOT NULL
GROUP BY DATE_TRUNC('week', race_date)
ORDER BY week_start DESC;
