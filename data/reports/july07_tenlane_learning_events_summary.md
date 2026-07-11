# July 07 — 10-Lane Learning Events (supplementary, not persisted)

This is a supplementary 10-model-lane view using the requested event-class taxonomy (MODEL_HIT_OFFICIAL_SIGMA, SHADOW_SIGNAL_HIT, etc.). The row actually persisted to `public.canonical_learning_events` is the official `canonical_learning_events_2026_07_07.csv` built by `build_canonical_learning_events.py` from Supabase `canonical_model_scorecards` (6-model set, production event-type taxonomy). See that file for the canonical record.

Rows: 250

| Event class | Count |
|---|---|
| MISSING_ARTIFACT | 1 |
| MODEL_HIT_OFFICIAL_SIGMA | 36 |
| MODEL_MISS_OFFICIAL_SIGMA | 80 |
| RESULT_PARSE_GAP | 1 |
| SHADOW_SIGNAL_HIT | 20 |
| SHADOW_SIGNAL_MISS | 82 |
| SHORT_PRICE_TRAP | 25 |
| VALUE_DISCOVERY | 5 |

All rows: promotion_eligible=false, promotion_block_reason=PROMOTION_GATED_PENDING_OPERATOR_REVIEW
