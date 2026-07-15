# New Build — NO_PRE_RACE_SCORECARD (2026-07-14)

## Classification: `NO_PRE_RACE_SCORECARD`

New Build did **not** produce a per-race prediction/pick with a probability
that can be scored against 2026-07-14 results. This is confirmed directly by
`data/model_comparison_ledger.csv` (copied into `evidence_staging/2026-07-14/`,
SHA-256 verified): every 2026-07-14 row has `nb_top_pick`, `nb_prob`, and
`nb_outcome` empty except `nb_outcome == "NO_DATA"`. All 42 rows are
identical on this point — this is not a partial gap, it is a complete
absence of a New Build betting/prediction card for the day.

## What DID run (evidence found)

Steps 6/7 of the daily pipeline (`new_build_current_card_feed.py`,
`new_build_two_lane_score.py`) executed and produced **readiness/feature**
artifacts, not predictions:

- `data/new_build/current_cards/current_card_passport_feed_2026_07_14.jsonl`
- `data/new_build/current_cards/current_card_intent_features_2026_07_14.jsonl`
- `data/new_build/reports/current_card_passport_feed_2026_07_14.json` / `.md`
- `data/new_build/reports/current_card_intent_features_2026_07_14_audit.json`
- `data/new_build/reports/two_lane_readiness_2026_07_14.json` / `.md`

The readiness report shows:
- `overall_status: READY`, `races_scored: 43`, `runners_scored: 368`
- `operational_lane: LANE_A_CORE_PASSPORT`
- `intent_coverage.status: UNAVAILABLE_BELOW_GATE` (0.0% vs an 80% gate) —
  by design, "Intent features are historical (race_id, horse) pairs.
  Current-card rows never match → 0% is expected for morning reads."
- `quality_gates.passport_coverage_above_50pct: false`

## Operational gap identified

The pipeline confirms the **feature/readiness layer completed** (Lane A
core+passport features were built and gated as READY), but there is no
evidence in this repo of a subsequent step that converts that readiness
artifact into a **scored, per-race New Build top pick with a probability**
for 2026-07-14 — i.e. no `new_build_*_scorecard_2026_07_14*` or equivalent
file exists anywhere under `data/new_build/` for this date, and the
Champion/New Build promotion artifacts under `data/new_build/reports/`
(e.g. `champion_promotion_latest.json`) are stale from 2026-05-25, not
date-specific to 07-14.

This mission does **not** identify the exact missing script invocation with
certainty (that would require shell history beyond what was preserved), but
the artifact trail draws a clean line: readiness-scoring stopped at Lane A
feature gating; no race-level prediction card followed.

## What this mission did NOT do

Per hard boundaries, this mission did **not** run New Build scoring after
the fact and did **not** manufacture a retrospective "citable score" for New
Build on 2026-07-14. The lane is reported as `NO_PRE_RACE_SCORECARD` and
excluded from all win/loss/frame arithmetic in the four-model result book.
