-- migration: 20260412_002_confidence_level_split
--
-- Splits confidence_level into two stored values so decision logic and
-- stored truth use the same signal:
--
--   confidence_level_raw       : value from ensemble before field normalization
--                                (stale — assigned when probs are un-normalised)
--   confidence_level_effective : recomputed after normalization from final
--                                velo_prime_prob, same boundary as synthesize_decision
--
-- Both columns are nullable TEXT with a CHECK constraint on the canonical
-- three-value set {high, normal, low}.
-- confidence_level (existing column) is preserved unchanged so old queries
-- do not break during the shadow window.

ALTER TABLE velo_verdicts
    ADD COLUMN IF NOT EXISTS confidence_level_raw       TEXT
        CHECK (confidence_level_raw IN ('high', 'normal', 'low')),
    ADD COLUMN IF NOT EXISTS confidence_level_effective TEXT
        CHECK (confidence_level_effective IN ('high', 'normal', 'low'));

-- Backfill: treat existing confidence_level as raw; derive effective from
-- velo_prime_prob using the same boundary as synthesize_decision.
UPDATE velo_verdicts
SET
    confidence_level_raw = confidence_level,
    confidence_level_effective = CASE
        WHEN velo_prime_prob >= 0.45 THEN 'high'
        WHEN velo_prime_prob >= 0.15 THEN 'normal'
        ELSE 'low'
    END
WHERE confidence_level_raw IS NULL;

COMMENT ON COLUMN velo_verdicts.confidence_level_raw IS
    'Ensemble confidence label assigned pre-normalization (may be stale).';
COMMENT ON COLUMN velo_verdicts.confidence_level_effective IS
    'Confidence recomputed from final velo_prime_prob after field normalization. '
    'This is the value used by synthesize_decision() for tier gating.';
