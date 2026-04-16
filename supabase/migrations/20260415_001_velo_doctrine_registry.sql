-- Migration: create velo_doctrine_registry
-- Purpose: Doctrine Layer sidecar registry for machine-readable findings.
-- Scope: observability / governance only. No scoring-path mutations.

CREATE TABLE IF NOT EXISTS velo_doctrine_registry (
    doctrine_key TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('promoter', 'suppressor', 'blocker', 'watch')),
    status TEXT NOT NULL CHECK (status IN ('proposed', 'active', 'retired', 'watch')),
    condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_summary TEXT,
    sample_size INTEGER,
    win_pct NUMERIC,
    place_pct NUMERIC,
    applies_to TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    effective_from DATE,
    next_review_date DATE,
    owner_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_velo_doctrine_registry_family
    ON velo_doctrine_registry (family);

CREATE INDEX IF NOT EXISTS idx_velo_doctrine_registry_rule_type
    ON velo_doctrine_registry (rule_type);

CREATE INDEX IF NOT EXISTS idx_velo_doctrine_registry_status
    ON velo_doctrine_registry (status);

CREATE INDEX IF NOT EXISTS idx_velo_doctrine_registry_applies_to
    ON velo_doctrine_registry
    USING GIN (applies_to);

CREATE INDEX IF NOT EXISTS idx_velo_doctrine_registry_condition_json
    ON velo_doctrine_registry
    USING GIN (condition_json);

CREATE OR REPLACE FUNCTION set_velo_doctrine_registry_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_velo_doctrine_registry_updated_at ON velo_doctrine_registry;

CREATE TRIGGER trg_velo_doctrine_registry_updated_at
    BEFORE UPDATE ON velo_doctrine_registry
    FOR EACH ROW
    EXECUTE FUNCTION set_velo_doctrine_registry_updated_at();
