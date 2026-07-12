# RACE-DAY-12-EOD-TRUTH-01 — Final Report

Governed, evidence-only results-and-Sigma close for 2026-07-12. No learner state, Playbook G, Supabase, or Telegram were mutated.

## Classifications
- **RACE_DAY_12_RESULTS_CAPTURED**: True
- **RESULT_SOURCE_HASHED**: True
- **RESULT_COMPLETENESS_MEASURED**: True
- **CANONICAL_PREDICTION_RUNS_MEASURED**: True
- **LEARNING_EVENT_V2_2_PACKET_SEALED**: True
- **SIGMA_EVIDENCE_CLOSE_COMPLETE**: True
- **PARTIAL_AND_AMBIGUOUS_RACES_EXCLUDED**: True
- **NO_PLAYBOOK_G_CONSUMPTION**: True
- **NO_STATE_LEARNING**: True
- **NO_MODEL_TRAINING**: True
- **NO_MODEL_PROMOTION**: True
- **NO_LIVE_SCORING_CHANGE**: True
- **NO_HFS_MUTATION**: True
- **NO_SUPABASE_WRITES**: True
- **NO_TELEGRAM_SEND**: True

## Results capture
- Primary source: `data/results/rp_results_2026_07_12.json` (SHA-256 `ee42a19325747c5f7deec54d19077c5fa97518b595c71e1383dc5bb2014b62e3`)
- 28 races captured across ['dundalk-aw', 'perth', 'sligo', 'stratford']
- Dundalk-AW note: Dundalk-AW was absent from this morning's domestic racecard-capture manifest (it lives in the separate _intl racecard URL list, which run_full_raceday.py's standard Steps 1-9 do not currently process). Captured manually via a supplementary results-URL list derived from rp_racecards_2026-07-12_intl.txt and merged into the primary results file with full provenance retained (capture_sources[1] in the results JSON).

## Prediction source
- Selected: `velo_verdicts` (Supabase) — runner_prediction_snapshots has 0 rows for 2026-07-12; velo_verdicts is the actual canonical prediction artifact for this date, confirmed one row per race_id (no run-id pooling problem), all rows generated 09:35-09:43 UTC well before the earliest race off (13:10 local).
- `runner_prediction_snapshots` had 0 rows for this date.

## Identity reconciliation
- Dundalk race_id mapping (numeric → composite): {"924518": "rp_DUN_20260712_2.00", "924519": "rp_DUN_20260712_2.35", "924520": "rp_DUN_20260712_3.10", "924521": "rp_DUN_20260712_3.45", "924522": "rp_DUN_20260712_4.20", "924523": "rp_DUN_20260712_4.55", "924524": "rp_DUN_20260712_5.30"}
- velo_verdicts uses name-slug horse ids (e.g. rp_DUN_collective_power) for Dundalk-AW, not the numeric RP ids used by the result truth. Resolved per-horse via identity_resolver.resolve_horse() (exact id, then normalised name within the race). 5 of 256 predicted horses across all courses could not be resolved and were excluded from shadow-eligibility for their race.

## LearningEventV2.2 packet
- 256 events sealed to `data/reports/learning_events_v2_2_2026_07_12.jsonl`
- Status: **SEALED_NOT_CONSUMED** — for later governed 01B replay only.

## Sigma evidence close (read-only)
- Shadow-eligible races: 23/28
- Top-pick win rate (shadow-eligible only): 0.2174
- Top-pick frame rate (shadow-eligible only): 0.4783

## Next step
LEARNING-LOOP-01B not started. July 12 evidence sealed for later governed consumption. July 13 continues with the existing frozen scorer and weights.
