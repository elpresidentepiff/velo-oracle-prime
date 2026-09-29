-- Additive MODEL-TRUTH Phase 2 fields. This file is not applied by creation;
-- deployment remains an explicit operator action.
ALTER TABLE public.canonical_model_scorecards
    ADD COLUMN IF NOT EXISTS subject_outcome_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN IF NOT EXISTS subject_is_non_runner BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS settlement_status TEXT NOT NULL DEFAULT 'UNSETTLED',
    ADD COLUMN IF NOT EXISTS stake_void BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS captured_odds_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS odds_capture_ts TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS price_source TEXT,
    ADD COLUMN IF NOT EXISTS settled_sp_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS bsp_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS odds_timestamp_before_off BOOLEAN,
    ADD COLUMN IF NOT EXISTS result_source_hash TEXT,
    ADD COLUMN IF NOT EXISTS result_source_complete BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS subject_outcome_code TEXT,
    ADD COLUMN IF NOT EXISTS official_evaluation_eligible BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS dashboard_metrics_eligible BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS evaluation_ineligible_reason TEXT,
    ADD COLUMN IF NOT EXISTS truth_contract_version TEXT;

ALTER TABLE public.canonical_learning_events
    ADD COLUMN IF NOT EXISTS subject_outcome_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN IF NOT EXISTS subject_is_non_runner BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS settlement_status TEXT NOT NULL DEFAULT 'UNSETTLED',
    ADD COLUMN IF NOT EXISTS stake_void BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS captured_odds_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS odds_capture_ts TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS price_source TEXT,
    ADD COLUMN IF NOT EXISTS settled_sp_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS bsp_dec NUMERIC,
    ADD COLUMN IF NOT EXISTS odds_timestamp_before_off BOOLEAN,
    ADD COLUMN IF NOT EXISTS result_source_hash TEXT,
    ADD COLUMN IF NOT EXISTS result_source_complete BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS subject_outcome_code TEXT,
    ADD COLUMN IF NOT EXISTS official_evaluation_eligible BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS dashboard_metrics_eligible BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS evaluation_ineligible_reason TEXT,
    ADD COLUMN IF NOT EXISTS event_identity_key TEXT,
    ADD COLUMN IF NOT EXISTS truth_contract_version TEXT;

-- Governed historical fallback: only numeric persisted positions can be
-- reconstructed truthfully. They prove a finished/settled runner and their
-- existing sp_dec is settled SP. Null positions remain UNKNOWN/UNSETTLED;
-- old terminal codes and non-runners were not retained in the integer column
-- and must be rebuilt from canonical results. Captured prices/timestamps are
-- never inferred or backfilled.
UPDATE public.canonical_model_scorecards
SET subject_outcome_code = result_position::text,
    subject_outcome_status = 'FINISHED',
    settlement_status = 'SETTLED',
    stake_void = false,
    settled_sp_dec = sp_dec
WHERE result_position IS NOT NULL
  AND truth_contract_version IS NULL;

UPDATE public.canonical_model_scorecards
SET official_evaluation_eligible = false,
    dashboard_metrics_eligible = false,
    evaluation_ineligible_reason = 'GOVERNED_REBUILD_REQUIRED'
WHERE truth_contract_version IS NULL
  AND evaluation_ineligible_reason IS NULL;

UPDATE public.canonical_learning_events event
SET subject_outcome_code = scorecard.subject_outcome_code,
    subject_outcome_status = scorecard.subject_outcome_status,
    settlement_status = scorecard.settlement_status,
    stake_void = scorecard.stake_void,
    settled_sp_dec = scorecard.settled_sp_dec,
    official_evaluation_eligible = false,
    dashboard_metrics_eligible = false,
    evaluation_ineligible_reason = 'GOVERNED_REBUILD_REQUIRED'
FROM public.canonical_model_scorecards scorecard
WHERE event.source_scorecard_id = scorecard.id
  AND event.truth_contract_version IS NULL
  AND event.event_identity_key IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cms_subject_outcome_status_truth_v1' AND conrelid = 'public.canonical_model_scorecards'::regclass) THEN
        ALTER TABLE public.canonical_model_scorecards ADD CONSTRAINT cms_subject_outcome_status_truth_v1
            CHECK (subject_outcome_status IN ('FINISHED', 'TERMINAL', 'NON_RUNNER', 'UNKNOWN'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cms_settlement_status_truth_v1' AND conrelid = 'public.canonical_model_scorecards'::regclass) THEN
        ALTER TABLE public.canonical_model_scorecards ADD CONSTRAINT cms_settlement_status_truth_v1
            CHECK (settlement_status IN ('SETTLED', 'VOID', 'UNSETTLED'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cle_subject_outcome_status_truth_v1' AND conrelid = 'public.canonical_learning_events'::regclass) THEN
        ALTER TABLE public.canonical_learning_events ADD CONSTRAINT cle_subject_outcome_status_truth_v1
            CHECK (subject_outcome_status IN ('FINISHED', 'TERMINAL', 'NON_RUNNER', 'UNKNOWN'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cle_settlement_status_truth_v1' AND conrelid = 'public.canonical_learning_events'::regclass) THEN
        ALTER TABLE public.canonical_learning_events ADD CONSTRAINT cle_settlement_status_truth_v1
            CHECK (settlement_status IN ('SETTLED', 'VOID', 'UNSETTLED'));
    END IF;
END $$;

-- Legacy rows deliberately keep NULL identity keys: no historical evidence is
-- deleted, merged, or assigned a fabricated identity. New governed events use
-- one deterministic key per source scorecard row. PostgreSQL UNIQUE indexes
-- allow multiple NULLs and PostgREST can infer this non-partial index for
-- ON CONFLICT(event_identity_key).
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_learning_events_identity_v1
    ON public.canonical_learning_events (event_identity_key);
