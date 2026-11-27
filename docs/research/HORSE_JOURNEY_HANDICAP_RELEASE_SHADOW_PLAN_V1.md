# Horse Journey / Handicap Release Shadow — V1 Plan

## Purpose

Create a factual, auditable research lane for a horse's route into today's
race. It is not a betting system, model probability, Prime amendment or claim
of trainer intent. The lane emits only repeatable facts and tests them forward
against matched same-race controls.

## Research findings

| Existing source | What it genuinely provides | Constraint |
| --- | --- | --- |
| `racing_horse_runs` | dated result history, OR, position, course, trip, jockey/trainer, SP | must be queried strictly `run_date < race_date` |
| RPDC `build_rpdc_daily.py` | current mark, last-win mark delta, return/course/trip facts and stable heat | existing tags are production context; this shadow must not mutate them |
| RP Spotlight factual packet | timestamped, allowlisted factual prose, with opinion language rejected | current-race comment facts are not a retrospective excuse for prior runs |
| Horse passports | career context | rolling passport builds are not point-in-time replay-safe without a frozen pre-off capture |
| retired V17 extractor | older handicapping calculations | excluded: it calls the retired Racing API live path |

## V1 factual tags

- `JOURNEY_MARK_AT_OR_BELOW_LAST_WIN`
- `JOURNEY_MARK_NEAR_LAST_WIN`
- `JOURNEY_RETURN_TO_WINNING_COURSE`
- `JOURNEY_RETURN_TO_WINNING_DISTANCE`
- `JOURNEY_STANDARD_RETURN_WINDOW`
- `JOURNEY_STABLE_WARM`
- `JOURNEY_JOCKEY_CHANGE` — a factual change, not an upgrade claim
- `JOURNEY_HANDICAP_RELEASE_PATTERN` — requires mark evidence plus at least one independent factual corroborator.

## Delivery phases

1. **Core complete in this change:** pure time-safe evidence builder and tests.
2. **Daily capture:** persist one immutable packet per runner before off, using exact RP IDs and source timestamps.
3. **EOD evaluation:** settle tags only after result ingestion and compare them to same-race non-tagged runners.
4. **Dashboard:** show source coverage, factual tags, settlement and cumulative evidence.
5. **Fitting decision:** only after enough forward races and a registered review; never automatically influence Prime.

## Non-negotiable guards

- Never query or use Racing API in live work.
- Reject history dated on/after the race date.
- No name-only identity fallback for persisted journey packets.
- No provider picks/probabilities/confidence.
- No price/ROI conclusion without a separate price-truth protocol.
- No `intent`, `plot`, `edge`, `release` or recommendation claim without the underlying factual codes displayed.
