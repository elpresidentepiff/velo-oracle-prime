# LearningEventV2

**Mission:** LEARNING-LOOP-01A (Phase 3)
**Module:** `src/velo/learning/learning_event_v2.py`
**Status:** schema defined, unit-tested. Not yet wired into any learner,
not yet consumed by Playbook G, not yet written to Supabase.

## Why this exists

VÉLØ currently has several competing "learning" outputs (`sigma_audits`,
`learned_patterns`, `velo_learning_events`, `canonical_learning_events`,
Sigma memory JSONL, the Playbook G event ledger and shadow state, the EOD
loss ledger, post-race reviews) that do not share one immutable event
contract. `LearningEventV2` is that one contract. Every learner
(Playbook G V2, Sigma memory distillation, future model-promotion
tribunals) is meant to consume this event — no learner should
reconstruct its own weaker version of it.

## Structure

A `LearningEventV2` has four frozen sub-sections:

- **`PredictionTruth`** — everything known *before* the race: full
  runner universe, every model/shadow score, rank order, top-three,
  odds value + capture timestamp, source commit, input-card hash, model
  versions, and which components were active/excluded.
- **`OutcomeTruth`** — the canonical result: per-horse finishing
  position, non-runners, SP/BSP, winner, frame, and a hash of the result
  source used.
- **`RaceContext`** — race class/type, field size, going/distance/
  surface, pace map, draw, pre-race market rank, RPDC/RPD/TIE/NDS/
  CASHRUN signals, archetype, and the Playbook G state hash that was
  active *before* this race was scored.
- **`SafetyProvenance`** — how identity was resolved, whether the join
  was ambiguous-blocked, the time-safety classification, leakage status,
  `learning_allowed`, `promotion_eligible`, and which result source
  (`RP_LOCAL_JSON` / `SUPABASE_CANONICAL_RESULT` / `SUPABASE_LEGACY_RESULT`
  / `RESULT_SOURCE_UNAVAILABLE`) and classification were used.

## No field defaults to "safe"

`time_safety` and `leakage_status` are **required** constructor
arguments on `SafetyProvenance` with no default value — every event
must be given an explicit, evidenced classification. `__post_init__`
enforces:

- `time_safety` must be one of the eight defined classifications below.
- `leakage_status` must be one of `CLEAN` / `SUSPECTED` / `CONFIRMED` /
  `UNKNOWN`.
- an `ambiguous_join_blocked=True` event cannot also have
  `learning_allowed=True`.
- `promotion_eligible=True` requires a `SAFE_*` time-safety
  classification (`SAFE_PROSPECTIVE` or `SAFE_FROZEN_REPLAY`) — a
  counterfactual replay or any excluded event can never be marked
  promotion-eligible.

### Time-safety classifications

| Classification | Meaning |
|---|---|
| `SAFE_PROSPECTIVE` | Scored live, before the race, with no result-derived input anywhere in the pipeline. |
| `SAFE_FROZEN_REPLAY` | Historical, but proven to have used frozen pre-race data with no leakage. |
| `CURRENT_CODE_COUNTERFACTUAL_REPLAY` | Current code re-run against historical data — informative, but never a "backtest". |
| `EXCLUDED_POST_RACE_LEAKAGE` | Some input was derived from the result itself. |
| `EXCLUDED_UNTIMED_ODDS` | Odds value present but capture timestamp unknown/untrusted. |
| `EXCLUDED_IDENTITY_AMBIGUOUS` | Race or horse identity could not be resolved without guessing. |
| `EXCLUDED_INCOMPLETE_RESULT` | Result source was partial (see `result_source_selector`). |
| `EXCLUDED_FEATURE_PROVENANCE_UNKNOWN` | A feature's pre-race provenance could not be established. |

## Deterministic, idempotent identity

`event_id` and `consumption_id` are **not** random UUIDs — they are
SHA-256 hashes of the event's own content (schema version, race id,
race date, input-card hash, result-source hash). The same reconciled
(prediction, result) pair always produces the same `event_id` on
rerun, so re-processing a date is an idempotent upsert, not a
duplicate-generating append. `consumption_id` is derived from
`event_id` so a consumer can record "I have processed this event"
without blocking a different consumer's independent processing of the
same event.

The dataclasses are `frozen=True` — an event cannot be mutated after
construction.

## What this module does NOT do

- It does not read Supabase or local result files itself. Phase 4's
  corpus builder is responsible for populating a `LearningEventV2` from
  `identity_resolver` (race/horse resolution) and
  `result_source_selector` (which result corpus was used and how
  complete it was).
- It does not write anywhere — no Supabase, no Playbook G state, no
  Telegram.
- It does not decide `learning_allowed` or `promotion_eligible` on its
  own beyond the invariants above — those are policy decisions made by
  the caller building the event, which this schema only prevents from
  being internally inconsistent.
