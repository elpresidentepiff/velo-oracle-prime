-- Bring the durable runner snapshot table into exact alignment with the
-- fields emitted by src/velo/runner_snapshot_store.py.  Additive only: no
-- existing row, scoring value, policy decision, or execution field changes.

ALTER TABLE public.runner_prediction_snapshots
    ADD COLUMN IF NOT EXISTS sqpe_no_rpr_shadow_prob NUMERIC(8,6),
    ADD COLUMN IF NOT EXISTS sqpe_no_rpr_shadow_feature_count INTEGER,
    ADD COLUMN IF NOT EXISTS nds_narrative TEXT,
    ADD COLUMN IF NOT EXISTS nds_score NUMERIC(8,6),
    ADD COLUMN IF NOT EXISTS nds_disruption TEXT,
    ADD COLUMN IF NOT EXISTS nds_is_fade BOOLEAN,
    ADD COLUMN IF NOT EXISTS nds_overround_signal NUMERIC(8,6),
    ADD COLUMN IF NOT EXISTS chain_pace_shape TEXT,
    ADD COLUMN IF NOT EXISTS chain_narrative TEXT,
    ADD COLUMN IF NOT EXISTS chain_market_status TEXT,
    ADD COLUMN IF NOT EXISTS midprice_shadow_action TEXT,
    ADD COLUMN IF NOT EXISTS midprice_shadow_evidence TEXT,
    ADD COLUMN IF NOT EXISTS midprice_shadow_field_band TEXT,
    ADD COLUMN IF NOT EXISTS midprice_shadow_rule_version TEXT;

COMMENT ON COLUMN public.runner_prediction_snapshots.chain_market_status IS
    'Snapshot-only market-chain status emitted after Prime scoring; never changes Prime probability.';
COMMENT ON COLUMN public.runner_prediction_snapshots.midprice_shadow_action IS
    'Paper/shadow-only Mid-Price Hunter action; never authorises execution.';
