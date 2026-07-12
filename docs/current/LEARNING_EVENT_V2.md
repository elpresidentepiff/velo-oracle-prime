# LearningEventV2

**Mission:** LEARNING-LOOP-01A (Phase 3, corrected per PR #147 REQUEST
CHANGES: P0-4, P0-5, P0-6)
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

- **`PredictionTruth`** — everything known *before* the race: the
  **subject horse** this event is about, the **single canonical
  prediction run** it came from (see `prediction_run_selector.py`),
  full runner universe, every model/shadow score, rank order,
  top-three, odds value + capture timestamp, prediction timestamp,
  source commit, a real SHA-256 input-card hash, model versions, and
  which components were active/excluded.
- **`OutcomeTruth`** — the canonical result: per-horse finishing
  position, non-runners, SP/BSP, winner, frame, a hash of the result
  source used, and `result_universe_complete` (whether every predicted
  runner was actually accounted for — see P0-2 below).
- **`RaceContext`** — race class/type, field size, going/distance/
  surface, pace map, draw, pre-race market rank, RPDC/RPD/TIE/NDS/
  CASHRUN signals, archetype, and the Playbook G state hash that was
  active *before* this race was scored.
- **`SafetyProvenance`** — how identity was resolved, whether the join
  was ambiguous-blocked, the time-safety classification, leakage
  status, result-source completeness, per-field provenance
  (`prediction_timestamp_present`, `odds_timestamp_before_off`,
  `source_commit_present`, `model_versions_present`,
  `input_card_hash_verified`), and five distinct allow-flags (see
  below) instead of one overloaded boolean.

## Corrections applied (PR #147 REQUEST CHANGES)

**P0-4 — `input_card_hash` is a real hash.** `compute_input_card_hash()`
produces a SHA-256 of the canonical, stably-ordered frozen input card
(race id, subject horse, selected prediction run, runner universe,
model scores, rank order, top three, model versions, active/excluded
components) — never a bare `"race_id:horse_id"` identifier string.

**P0-4 — `event_key` vs `event_content_hash` vs `event_id`.**
- `event_key`: the **stable logical identity** of an event — schema
  version, race id, race date, subject horse, prediction run id. It
  does **not** change when content changes.
- `event_content_hash`: hashes the **entire frozen event**, so it
  changes whenever *any* material truth changes — model score, rank
  order, selected run, source commit, model version, result position,
  winner, result source content, safety classification. All of it,
  because it hashes the whole dataclass tree rather than a hand-picked
  subset.
- `event_id`: a deterministic combination of `event_key` and
  `event_content_hash`. A corrected result therefore produces a **new**
  `event_id` under the **same** `event_key`, instead of silently
  overwriting the old event under an unchanged identity.

**P0-5 — `consumption_id` requires an explicit consumer.** It is no
longer a bare function of the event. `consumption_id(consumer_name,
consumer_version, target_state)` (or the module-level
`compute_consumption_id()`) requires all three, so two different
learners consuming the same event never collide on the same
consumption id, and the same learner re-consuming after a version bump
or state change gets a distinct id.

**P0-6 — five distinct allow-flags, not one overloaded boolean.**
`analysis_allowed`, `shadow_evaluation_allowed`, `state_learning_allowed`,
`model_training_allowed`, `promotion_eligible` are independent fields.
`promotion_eligible=True` requires **all** of the following to hold
simultaneously (checked in `SafetyProvenance.__post_init__`):
`state_learning_allowed`, a `SAFE_*` time-safety classification,
`leakage_status="CLEAN"`, not `ambiguous_join_blocked`,
`result_source_complete`, `input_card_hash_verified`,
`prediction_timestamp_present` and `prediction_timestamp_before_off is
True`, `odds_timestamp_present` and `odds_timestamp_before_off is
True`, `source_commit_present`, `model_versions_present`. A `SAFE_*`
label alone is never enough. `CURRENT_CODE_COUNTERFACTUAL_REPLAY` can
never be `state_learning_allowed`, `model_training_allowed`, or
`promotion_eligible` — it can still be `analysis_allowed`/
`shadow_evaluation_allowed`.

## No field defaults to "safe"

`time_safety` and `leakage_status` are **required** constructor
arguments on `SafetyProvenance` with no default value.

### Time-safety classifications

| Classification | Meaning |
|---|---|
| `SAFE_PROSPECTIVE` | Scored live, before the race, with no result-derived input anywhere in the pipeline. |
| `SAFE_FROZEN_REPLAY` | Historical, but proven to have used frozen pre-race data with no leakage. |
| `CURRENT_CODE_COUNTERFACTUAL_REPLAY` | Current code re-run against historical data — informative, but never a "backtest". |
| `EXCLUDED_POST_RACE_LEAKAGE` | Some input was derived from the result itself. |
| `EXCLUDED_UNTIMED_ODDS` | Odds value present but capture timestamp unknown/untrusted. |
| `EXCLUDED_IDENTITY_AMBIGUOUS` | Race or horse identity could not be resolved without guessing. |
| `EXCLUDED_INCOMPLETE_RESULT` | Result source was proven incomplete against the expected runner universe (see P0-2 in `result_source_selector.py`). |
| `EXCLUDED_FEATURE_PROVENANCE_UNKNOWN` | A feature's pre-race provenance could not be established. |

The dataclasses are `frozen=True` — an event cannot be mutated after
construction.

## What this module does NOT do

- It does not read Supabase or local result files itself. Phase 4's
  corpus builder is responsible for populating a `LearningEventV2` from
  `prediction_run_selector` (canonical run selection),
  `identity_resolver` (race/horse resolution), and
  `result_source_selector` (which result corpus was used and how
  complete it was against the real expected universe).
- It does not write anywhere — no Supabase, no Playbook G state, no
  Telegram.
- It does not decide the allow-flags or `promotion_eligible` on its own
  beyond the invariants above — those are policy decisions made by the
  caller building the event, which this schema only prevents from being
  internally inconsistent.
