# RACING POST ADAPTER V1

## Purpose

RacingPostAdapter converts merged racecard JSON files (output of `ingest_racecard_pdfs.py`)
into structured, named feature sets consumed by downstream layers: convergence reporting,
CASHRUN, shadow learning, and the operator dashboard.

This is a read-only extraction layer. It does not score horses, does not write to Supabase,
does not modify predictions, and does not interact with the live model pipeline.

## Command

```bash
python scripts/build_racing_post_features.py --date YYYY-MM-DD
```

## Files

| File | Role |
|---|---|
| `app/services/racing_post_adapter.py` | Core extraction logic |
| `scripts/build_racing_post_features.py` | CLI runner |
| `docs/engineering/RACING_POST_ADAPTER_V1.md` | This document |

## Input Files

| Path | Description |
|---|---|
| `data/racecard_merged/racecard_*_YYYY-MM-DD.json` | One file per venue per date, produced by `ingest_racecard_pdfs.py` from RP PDFs (F_0011, F_0012, F_0015, F_0016, F_0032) |

The adapter reads all matching files for the given date. Missing venues produce no rows — coverage is reported.

## Output File

```
data/racing_post_features/YYYY-MM-DD.json
```

Not committed to git. Local operator artifact only.

## Output Schema

```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "<ISO8601 UTC>",
  "coverage": {
    "venues": 7,
    "races": 52,
    "runners": 552,
    "spotlight_present": 52,
    "postdata_present": 42
  },
  "races": [...]
}
```

### Race Object

```json
{
  "venue": "York",
  "off_time": "1:45",
  "race_info": "7f (Class 2) ...",
  "postdata_pick": "Horse Name",
  "topspeed_pick": "Horse Name",
  "spotlight_verdict": "...",
  "runner_count": 8,
  "rp_race_features": { ... },
  "rp_rating_ranks": { "Horse Name": 1, ... },
  "rp_runner_features": [ ... ]
}
```

### `rp_race_features`

Race-level signals derived from RP source coverage.

```json
{
  "has_postdata": true,
  "has_topspeed": true,
  "has_spotlight": true,
  "top_claim_tags": ["HANDICAP_CLAIM", "PROGRESSION_CLAIM"]
}
```

### `rp_rating_ranks`

OR-ranked order of runners in the race.

```json
{ "Horse Name": 1, "Other Horse": 2, ... }
```

### `rp_runner_features`

Per-runner structured features extracted from merged racecard.

| Field | Source | Description |
|---|---|---|
| `horse` | colour card | Horse name |
| `or_rank` | computed | Position by current OR in field |
| `current_or` | OR PDF | Official Rating today |
| `current_ts` | TS PDF | Topspeed master figure |
| `current_rpr` | Postdata | Racing Post Rating |
| `or_trend` | OR history | RISING / FALLING / FLAT / INSUFFICIENT |
| `ts_trend` | TS history | IMPROVING / FLAT_OR_DECLINING / INSUFFICIENT |
| `or_compression` | OR PDF | Compression vs career high |
| `going_flag` | Postdata | Going suitability signal |
| `distance_flag` | Postdata | Distance suitability signal |
| `course_flag` | Postdata | Course suitability signal |
| `draw_flag` | Postdata | Draw suitability signal |
| `ability_flag` | Postdata | Ability suitability signal |
| `trainer_form` | Postdata | positive / neutral / negative |
| `trainer_form_signal` | computed | Trainer recent form string |
| `plot_conviction` | computed | CASHRUN plot conviction label |
| `handicap_plot_score` | computed | Raw CASHRUN handicap score |
| `stall` | colour card | Draw stall number |
| `days_since_last_run` | colour card | Days since last run |
| `headgear` | colour card | Headgear today |
| `spotlight_comment` | Spotlight PDF | Full RP Spotlight text |
| `claim_tags` | extracted | Structured claim tags (see below) |
| `consensus_signals` | computed | Cross-source agreement signals |
| `postdata_pick` | Postdata | True if this horse is Postdata top pick |
| `topspeed_pick` | Topspeed | True if this horse is Topspeed top pick |

### `rp_text_claims` (embedded per runner in `claim_tags`)

Spotlight text is parsed into structured claim tags:

| Tag | Trigger phrases |
|---|---|
| `HANDICAP_CLAIM` | "well handicapped", "good mark", "workable mark", "below last winning mark", "dropped in weights" |
| `PROGRESSION_CLAIM` | "should improve", "open to improvement", "unexposed", "scope for improvement" |
| `TRAINER_INTENT_CLAIM` | "stable fancy", "laid out for", "been freshened", "off a mark" |
| `GROUND_CLAIM` | "ground will suit", "handles the going", "conditions suit" |
| `MARKET_CLAIM` | "market support", "money likely", "heavily backed" |
| `FORM_REVERSAL_CLAIM` | "return to form", "bounce back", "better than bare", "eyecatcher", "not knocked about" |
| `COURSE_CLAIM` | "return to course", "course winner", "loves this track" |
| `TRIP_CLAIM` | "return to trip", "suited by this trip" |
| `NEGATIVE_CLAIM` | "others preferred", "hard to recommend", "needs to raise game", "well beaten" |

### `rp_consensus_signals` (embedded per runner in `consensus_signals`)

Cross-source agreement flags:

| Signal | Meaning |
|---|---|
| `FLAG:GOING_POSITIVE` | Postdata going flag is positive |
| `FLAG:DISTANCE_POSITIVE` | Postdata distance flag is positive |
| `FLAG:COURSE_POSITIVE` | Postdata course flag is positive |
| `FLAG:DRAW_POSITIVE` | Postdata draw flag is positive |
| `FLAG:ABILITY_POSITIVE` | Postdata ability flag is positive |
| `RP_POSTDATA_PICK` | Horse is the Postdata top pick for this race |
| `RP_TOPSPEED_PICK` | Horse is the Topspeed top pick for this race |

Postdata + Topspeed agreement on the same horse is the strongest consensus signal available from RP.

## Provenance Fields

Every output JSON includes:

- `generated_at` — UTC timestamp of extraction
- `date` — race date
- Source traceability: each runner's features map directly to named RP PDF types (OR, TS, Spotlight, Postdata, Colour Card)

## Coverage Fields

`coverage` in the root object reports completeness:

- `venues` — number of venues with merged racecard files
- `races` — total races extracted
- `runners` — total runners extracted
- `spotlight_present` — races with Spotlight coverage
- `postdata_present` — races with Postdata coverage

Missing coverage does not cause failure — the adapter reports what it has.

## Read-Only Contract

This adapter must never:

- Write to Supabase
- Modify `velo_verdicts`, `sigma_audits`, or any prediction table
- Change `data/sentient_state.json`
- Affect SQPE, ensemble weights, or routing rules
- Send Telegram messages
- Trigger EOD or learning consume

## Downstream Consumers (planned)

| Consumer | Usage |
|---|---|
| `build_rp_velo_convergence_report.py` | Compare RP picks to VÉLØ picks |
| `cashrun_detector.py` | Already reads merged racecards directly |
| `cashrun_activation_audit.py` | Cross-references RP signals with results |
| Dashboard | Will surface consensus picks and claim tags |
| Shadow learning | Claim tags become auditable features |

## Version History

| Version | Date | Changes |
|---|---|---|
| V1 | 2026-05-15 | Initial skeleton. Read-only. 9 claim tag types. Consensus signals. OR/TS trend extraction. |
