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
- Selected: `velo_verdicts` (Supabase) — runner_prediction_snapshots has 0 rows for 2026-07-12; velo_verdicts is the actual canonical prediction artifact for this date.
- `runner_prediction_snapshots` had 0 rows for this date.

## Identity reconciliation
- Dundalk race_id mapping (numeric → composite): {"924518": "rp_DUN_20260712_2.00", "924519": "rp_DUN_20260712_2.35", "924520": "rp_DUN_20260712_3.10", "924521": "rp_DUN_20260712_3.45", "924522": "rp_DUN_20260712_4.20", "924523": "rp_DUN_20260712_4.55", "924524": "rp_DUN_20260712_5.30"}
- Derivation: Derived from committed evidence, not positional ordering: each numeric race_id's off-time comes from the results-capture manifest's own source_url + page title (data/racing_post_account_raw/rp-results-2026-07-12-dundalk/manifest.json, SHA-256 ee8e2f5721ec6c6bb16289ccb1b28c7e55fe32caba4c73fe54e8cb8002089f2a); each composite velo_verdicts race_id's off-time is parsed from its own id string. Matched by exact off-time; the generator fails closed (raises) if either side has a duplicate off-time or the two sides are not a clean 1:1 bijection.
- velo_verdicts uses name-slug horse ids (e.g. rp_DUN_collective_power) for Dundalk-AW, not the numeric RP ids used by the result truth. Resolved per-horse via identity_resolver.resolve_horse() (exact id, then normalised name within the race). 5 of 256 predicted horses across all courses could not be resolved and were excluded from shadow-eligibility for their race.

## Time-safety classification
No event is classified SAFE_* in this close: odds_capture_ts is None for every event because no documented check yet proves velo_verdicts.fetch_timestamp represents the capture time of the exact odds embedded in the frozen prediction row. The 214 events for complete, proven-pre-race races are EXCLUDED_UNTIMED_ODDS (shadow-evaluation still allowed per 01A law, which is independent of odds-timing proof); the 37 events belonging to the 5 partial races are EXCLUDED_INCOMPLETE_RESULT; the 5 unresolved-horse events are EXCLUDED_IDENTITY_AMBIGUOUS.

Distribution: {"EXCLUDED_UNTIMED_ODDS": 214, "EXCLUDED_INCOMPLETE_RESULT": 37, "EXCLUDED_IDENTITY_AMBIGUOUS": 5}

## Manifest assertions
{
  "unresolved_horse_exclusion_count": 5,
  "partial_ambiguous_race_count": 5,
  "every_unresolved_horse_in_csv": true,
  "every_partial_race_has_reason": true,
  "no_excluded_race_shadow_eligible": true
}

## LearningEventV2.2 packet
- 256 events sealed to `data/reports/learning_events_v2_2_2026_07_12.jsonl`
- Status: **SEALED_NOT_CONSUMED** — for later governed 01B replay only.

## Sigma evidence close (read-only)
- Shadow-eligible races: 23/28
- Top-pick win rate (shadow-eligible only): 0.2174
- Top-pick frame rate (shadow-eligible only): 0.4783

## Next step
LEARNING-LOOP-01B not started. July 12 evidence sealed for later governed consumption. July 13 continues with the existing frozen scorer and weights.
