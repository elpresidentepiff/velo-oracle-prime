-- =============================================================================
-- 20260411_002 — runtime_overrides table
-- =============================================================================
-- Creates the exclusive live-scoring config layer for VÉLØ feedback actuation.
--
-- Architecture (3-tier separation):
--   learned_patterns   = observations only      (close_sigma_loops.py writes)
--   patch_proposals    = candidate changes only  (close_sigma_loops.py writes)
--   runtime_overrides  = live scoring config     (apply_approved_proposals.py writes)
--
-- SQPE/.pkl weights are never touched by this system.
-- Activating an override changes synthesize_decision() threshold behaviour only.
--
-- Seeds 3 INACTIVE v1 keys that mirror current hardcoded constants exactly.
-- INACTIVE = zero behaviour change from baseline.
-- Activate via: scripts/apply_approved_proposals.py (APPROVED_PROPOSAL source)
--           or: UPDATE runtime_overrides SET status='ACTIVE' WHERE override_key='...';
-- =============================================================================

CREATE TABLE IF NOT EXISTS runtime_overrides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    override_key    TEXT NOT NULL UNIQUE,
    scope           TEXT NOT NULL DEFAULT 'global'
                    CHECK (scope IN ('global', 'track', 'race_type', 'archetype')),
    value_json      JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'INACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE')),
    source          TEXT NOT NULL DEFAULT 'MANUAL'
                    CHECK (source IN ('MANUAL', 'APPROVED_PROPOSAL', 'SYSTEM_SEEDED')),
    effective_from  TIMESTAMPTZ,
    effective_to    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes           TEXT
);

-- Fast active-key lookup at scoring time
CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_overrides_key
    ON runtime_overrides (override_key);

CREATE INDEX IF NOT EXISTS idx_runtime_overrides_active
    ON runtime_overrides (status, override_key)
    WHERE status = 'ACTIVE';

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_runtime_overrides_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_runtime_overrides_updated_at ON runtime_overrides;
CREATE TRIGGER trg_runtime_overrides_updated_at
    BEFORE UPDATE ON runtime_overrides
    FOR EACH ROW EXECUTE FUNCTION update_runtime_overrides_updated_at();


-- ── Seed v1 defaults (INACTIVE) ───────────────────────────────────────────────
-- These mirror synthesize_decision() hardcoded constants exactly.
-- No behaviour change until activated.

INSERT INTO runtime_overrides (override_key, scope, value_json, status, source, notes)
VALUES
(
    'tier_thresholds',
    'global',
    '{
        "A": {"min_prob": 0.32, "min_gap": 0.08, "min_place": 0.52},
        "B": {"min_prob": 0.15, "min_gap": 0.03, "min_place": 0.45, "min_improve": 0.18},
        "C": {"min_prob": 0.13, "min_gap": 0.02, "rescue_place": 0.55, "rescue_prob": 0.11},
        "X": {"flat_field_prob_max": 0.10, "max_gap": 0.015, "max_place": 0.40}
    }'::jsonb,
    'INACTIVE',
    'SYSTEM_SEEDED',
    'v1 seed — mirrors synthesize_decision() hardcoded constants. Activate after empirical validation. adjust field values first.'
),
(
    'tier_promotion_blockers',
    'global',
    '{
        "blockers": [
            {"when": {"favourite_trap_risk": "high"}, "max_tier": "B",
             "note": "persistent trap risk caps tier at B"},
            {"when": {"macro_chaos_mode": true}, "max_tier": "C",
             "note": "macro chaos caps tier at C"},
            {"when": {"market_decoy_followed": true}, "max_tier": "B",
             "note": "decoy-followed pattern blocks A promotion"},
            {"when": {"outsider_hedge_omitted": true}, "max_tier": "B",
             "note": "outsider hedge miss blocks A promotion"}
        ]
    }'::jsonb,
    'INACTIVE',
    'SYSTEM_SEEDED',
    'v1 promotion blockers — pattern-based tier caps. favourite_trap_risk and macro_chaos_mode are live fields. market_decoy_followed requires runner enrichment.'
),
(
    'trap_escalation_rules',
    'global',
    '{
        "rules": [
            {"when": {"favourite_trap_risk": "high"}, "action": "block_A_tier",
             "note": "persistent trap evidence → hard block on A"},
            {"when": {"macro_chaos_mode": true}, "action": "cap_C_tier",
             "note": "persistent chaos → cap at C"},
            {"when": {"market_deception_score_lt": 0.25}, "action": "cap_B_tier",
             "note": "very low deception score may indicate decoy — cap at B"}
        ]
    }'::jsonb,
    'INACTIVE',
    'SYSTEM_SEEDED',
    'v1 trap escalation placeholder. Activate after trap/chaos miss patterns accumulate in learned_patterns.'
)
ON CONFLICT (override_key) DO NOTHING;
