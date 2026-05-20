# Racing Post Migration Audit V1

## Decision

Keep the source split explicit:

- Racing Post = primary pre-race intelligence
- Racing API = machine spine, IDs, results, fallback, validator
- VÉLØ DB = canonical truth
- Playbook G = learning memory

Do not delete Racing API. Demote it from the intelligence lead to the structured spine.

## Current Racing Post Footprint

### Raw inputs

- `data/incoming_pdfs/**/*.pdf`
- `data/incoming_pdfs/YYYY-MM-DD/*.pdf`
- common RP file families already in use:
  - `F_0010_XX` = selection box / industry picks
  - `F_0011_XX` = postdata summary
  - `F_0012_XX` = colour card / runner card
  - `F_0015_OR` = official ratings card
  - `F_0016_XX` = spotlight card
  - `F_0032_TS` = topspeed card

### Parsers and processors

- `scripts/ingest_racecard_pdfs.py`
  - main RP merge pipeline
  - classifies PDFs by filename family
  - parses OR, TS, Spotlight, Postdata and merges them into per-race/per-runner JSON
- `scripts/cashrun_detector.py`
  - reads merged RP racecards
  - scores CASHRUN from RP intent, OR compression, TS/RPR hidden form, comment language
- `scripts/parse_industry_selections.py`
  - parses `F_0010_XX` selection-box PDFs into tipster pick JSON
- `scripts/build_industry_comparison.py`
  - compares VÉLØ against parsed industry lanes
- `scripts/audit_racing_post_coverage.py`
  - simple RP field coverage check

### Parsed outputs

- `data/racecard_merged/racecard_*_YYYY-MM-DD.json`
- `data/cashrun_report_YYYY_MM_DD.csv`
- `data/cashrun_report_YYYY_MM_DD.md`
- `data/cashrun_operator_card_YYYY_MM_DD.md`
- `data/racing_post_coverage_YYYY_MM_DD.csv`
- `data/racing_post_coverage_YYYY_MM_DD.md`
- `data/industry_selections_YYYYMMDD.json`

### Current consumers

- CASHRUN reads merged RP cards directly
- dashboard joins CASHRUN output in `app/main.py`
- industry benchmark consumes parsed selection-box outputs
- VÉLØ does not yet read a shared normalized RP adapter output
- learning events do not yet preserve a full RP feature packet

## What CASHRUN Already Extracts

From the merged RP racecards and CASHRUN report, the current live extraction already includes most of the intent spine:

- course
- off_time
- race_name when available
- race_info
- horse
- trainer
- jockey
- trainer_form
- weight
- draw
- headgear
- form_string
- current OR
- current TS
- current RPR
- last winning OR
- OR delta vs last winning mark
- last 6 OR
- last 6 TS
- Spotlight comment evidence
- Postdata presence / pick evidence
- class
- distance
- going when source text exposes it
- mark compression score
- TS hidden form score
- RPR hidden form score
- setup language score
- trainer intent score
- Spotlight/Postdata intent score
- suppression evidence
- VP30 overlap flag
- Racing API positive overlap flag
- metadata completeness flag

The merged RP racecards also already carry runner-level fields that CASHRUN currently reads only partially:

- `spotlight_comment`
- `spotlight_verdict`
- `postdata_pick`
- `topspeed_pick`
- `postdata_score`
- `rpr_master`
- `ts_master`
- `or_run_history`
- `ts_run_history`
- `trainer_form_signal`
- `plot_conviction`
- `intent_signals`

## What VÉLØ Still Needs That CASHRUN Does Not Expose Cleanly

CASHRUN is a scorer, not a reusable adapter. It does not currently emit a normalized RP feature row that VÉLØ, dashboard, and learning can all share.

Important gaps:

- no shared adapter file like `data/racing_post_features/YYYY-MM-DD.json`
- no explicit `spotlight_verdict_flag`
- no explicit `postdata_pick_flag`
- no explicit `topspeed_pick_flag`
- no explicit `rp_ratings_pick_flag`
- no normalized `horse_id if resolvable` output in one canonical RP feature file
- no explicit `course_fit`, `distance_fit`, `going_fit` fields
- no normalized `ability_score` and `recent_form_score`
- no `forecast_price`
- no `non_runner_flag`
- no `wind_surgery` extraction
- no `last_6_rpr` extraction from RP source
- no raw source provenance per runner
- no shared alias-resolution layer for RP horse naming variants

## Proposed RacingPostAdapter Schema

Target file:

- `data/racing_post_features/YYYY-MM-DD.json`

Per runner:

- `source_date`
- `race_id` if resolvable
- `course`
- `off_time`
- `race_name`
- `race_info`
- `horse`
- `horse_id` if resolvable
- `draw`
- `jockey`
- `trainer`
- `trainer_form`
- `weight`
- `age`
- `sex`
- `OR`
- `TS`
- `RPR`
- `last_6_form`
- `last_6_or`
- `last_6_ts`
- `last_6_rpr`
- `spotlight_comment`
- `spotlight_verdict_flag`
- `postdata_pick_flag`
- `topspeed_pick_flag`
- `rp_ratings_pick_flag`
- `course_fit`
- `distance_fit`
- `going_fit`
- `class_move`
- `headgear`
- `wind_surgery`
- `ability_score`
- `recent_form_score`
- `forecast_price`
- `non_runner_flag`
- `raw_source_file`
- `source_bundle_key`

## Consumer Split

### VÉLØ

- read normalized RP sidecars only
- no direct PDF parsing inside scoring path
- attach RP fields as shadow sidecars first

### CASHRUN

- read `RacingPostAdapter` output
- stop owning RP parsing logic
- remain one consumer of RP intent, not the parser owner

### Dashboard

- read normalized RP-derived sidecars
- display Spotlight/Postdata/TS/RPR context from adapter-backed fields

### Learning events

- preserve adapter packet or selected derived fields
- keep RP context available for post-race miss forensics

## No-Code Migration Plan

### RP-0 Inventory

- freeze the current RP footprint
- list raw PDFs, merged cards, CASHRUN reports, selection-box outputs, coverage outputs

### RP-1 Adapter extraction

- move RP parsing ownership out of CASHRUN
- create shared `RacingPostAdapter`

### RP-2 Shadow connect

- write normalized RP feature files per date
- let VÉLØ attach them as sidecars with zero scoring change

### RP-3 Parity audit

- compare RP runner list vs Racing API runner list vs VÉLØ canonical runner list
- resolve alias, duplicate, suffix, and late non-runner gaps

### RP-4 Promotion

- only after parity proof
- RP becomes the primary pre-race intelligence source
- Racing API remains the structured validator and results spine

## Risks

- unauthorized scraping must remain forbidden
- RP race names and comments are richer than machine feeds, but also noisier
- alias resolution will matter more once RP becomes primary
- current merged-card schema is useful but not yet canonical enough for all consumers
- CASHRUN must not remain the de facto owner of RP parsing

## Operating Call

Racing Post already supplies the richer decision layer.
The missing piece is not data access. It is adapter discipline.
