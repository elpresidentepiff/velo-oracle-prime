-- migration: 20260413_001_rpdc_verdict_fields
-- Adds RPDC observability fields to velo_verdicts.
-- Passive only — not used in ensemble weighting.
-- Added 2026-04-13.

ALTER TABLE velo_verdicts
    ADD COLUMN IF NOT EXISTS rpdc_release_score    NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS rpdc_cash_window_flag BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rpdc_tag_count        INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rpdc_primary_tag      TEXT,
    ADD COLUMN IF NOT EXISTS rpdc_tags             JSONB DEFAULT '[]';

COMMENT ON COLUMN velo_verdicts.rpdc_release_score    IS 'RPDC weighted tag score for top pick. Observability only — not an ensemble input.';
COMMENT ON COLUMN velo_verdicts.rpdc_cash_window_flag IS 'TRUE when top pick has CASH_WINDOW composite tag (mark+cycle+placement aligned).';
COMMENT ON COLUMN velo_verdicts.rpdc_tag_count        IS 'Number of positive RPDC tags fired for top pick.';
COMMENT ON COLUMN velo_verdicts.rpdc_primary_tag      IS 'Highest-strength RPDC tag for top pick.';
COMMENT ON COLUMN velo_verdicts.rpdc_tags             IS 'Full list of RPDC tags fired for top pick.';
