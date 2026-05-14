# Racing API Final Harvest Plan V1

## Decision

Use the remaining Racing API window for extraction and audit only.

- raw first
- normalize second
- audit always

Do not spend the remaining time on prediction experiments.

## Current Actual DB Spine

These are the current exposed table counts from the live canonical DB, measured via PostgREST exact counts.

Important correction:

- `public.horses = 37` is a lightweight Racing API profile/cache table
- `public.racing_horses = 182846` is the canonical horse registry
- `public.raceform = 1387120` is the live Supabase historical runner spine
- the older `183k` number was real, but it mapped to `horse_profiles` / `racing_horses`, not `public.horses`

Core live counts:

- `public.horses` = `37`
- `public.racing_horses` = `182846`
- `public.raceform` = `1387120`
- `public.races` = `3675`
- `public.runners` = `17386`
- `public.runner_results` = `33430`
- `public.historical_feature_store` = `31936`
- `velo_verdicts` = `2222`
- `sigma_audits` = `1910`

Supporting side tables currently exposed:

- `racing_api_trainer_analysis_courses` = `39740`
- `racing_api_trainer_analysis_distances` = `32698`
- `racing_api_trainer_analysis_jockeys` = `146395`
- `racing_api_jockey_analysis_courses` = `28391`
- `racing_api_jockey_analysis_distances` = `20573`
- `racing_api_jockey_analysis_trainers` = `106842`
- `rp_racecards` = `129`
- `rp_runner_signals` = `1521`

Empty or absent:

- `results` = `0`
- `race_spotlight_verdict` = `0`
- `runner_form_lines` = `0`
- `rp_entity_aliases` = `0`
- `course_metadata` = absent
- `entity_aliases` = absent
- `non_runners` = absent
- `trainer_stats_history` = absent
- `jockey_stats_history` = absent
- `trainer_jockey_combinations` = absent

Current race date span in `races`:

- min date = `2017-01-01`
- max date = `2026-05-06`

That means the machine spine is more current than earlier assumptions in some places. The earlier `183k` inventory was not wrong, but it referred to the canonical registry layer, not the small `public.horses` cache table.

## Racing Data Table Truth Map

### `public.horses`

- role: small Racing API profile/cache table
- count: `37`
- not canonical

### `public.racing_horses`

- role: canonical horse registry
- count: `182846`
- canonical identity layer

### `public.raceform`

- role: historical runner spine
- count: `1387120`
- live Supabase archive, filtered from `2017+`

### `data/raceform_clean.parquet`

- role: larger local archive
- count: `1702741`
- date range: `2015-01-01` to `2025-07-05`

### `data/raceform_v17_features.parquet`

- role: local V17 feature archive
- count: `1702741`
- date range: `2015-01-01` to `2025-07-05`

### `public.historical_feature_store`

- role: derived training/feature layer
- count: `31936`
- not raw source of truth

## Local Archive Gap Note

The local parquet archive is materially larger than live `public.raceform`.

- local archive rows: `1702741`
- live `public.raceform` rows: `1387120`
- delta: `315621`

This is consistent with the archived loader path filtering live Supabase ingestion to `2017-01-01+`, while the local parquet archive still contains `2015-2016` rows.

Do not load that gap yet.

Proposed separate controlled task:

- `2015–2016 raceform live-load audit`
  - raw row count
  - exact date range
  - duplicate checks
  - DB impact estimate
  - no automatic load

## Official Schema / Capability Probe

Live official schema:

- `https://api.theracingapi.com/openapi.json`
- reachable now
- `58` documented paths

Light Standard-plan probe results:

- `/v1/racecards/free` = `200`
- `/v1/racecards/basic` = `200`
- `/v1/racecards/standard` = `200`
- `/v1/racecards/pro` = `401 Pro Plan required`
- `/v1/results` = `200` when using `start_date` and `end_date`
- `/v1/results/today` = `200`
- `/v1/results/today/free` = `200`
- `/v1/horses/search` = `200`
- `/v1/horses/{horse_id}/standard` = `200`
- `/v1/horses/{horse_id}/results` = `401 Pro Plan required`
- `/v1/jockeys/search` = `200`
- `/v1/jockeys/{jockey_id}/analysis/courses` = `200`
- `/v1/trainers/search` = `200`
- `/v1/trainers/{trainer_id}/analysis/courses` = `200`
- `/v1/courses` = `200`
- `/v1/courses/regions` = `200`
- `/v1/odds/{race_id}/{horse_id}` = `401 Pro Plan required`

Important contract corrections from the live schema:

- `/v1/results` does **not** accept `date`
- it uses `start_date` and `end_date`
- `/v1/results` `limit` max is `100`
- `/v1/racecards/standard` uses `day`, `region_codes`, `course_ids`, `limit`, `skip`

## What Still Matters To Harvest

### Highest-value remaining extraction

1. endpoint capability map from the live OpenAPI contract
2. results gap-fill after `2026-05-06`
3. current and future racecards via free/basic/standard
4. courses and regions reference set
5. targeted trainer/jockey analysis refresh for current runners
6. any Standard-plan accessible profile enrichment

### Deprioritized or blocked on Standard

- odds snapshots: blocked by plan
- horse results history endpoint: blocked by plan
- pro racecards: blocked by plan

## Request Volume Estimate

### Minimal 48-hour useful harvest

- capability map probe: `20-40` requests
- results gap-fill for `2026-05-07` onward: roughly `1-3` requests per date depending on pagination
- current/future racecards:
  - free/basic/standard for current day and next day
  - roughly `6-12` requests
- courses/regions: `2` requests

Estimated useful total:

- `50-120` requests for the essential harvest

### Expanded but still reasonable harvest

- targeted trainer/jockey analysis refresh for current/future cards
- recent/current horse standard profiles

Estimated broader total:

- `300-1200` requests depending on entity breadth

### Not worth planning under Standard

- odds endpoint sweep
- horse results bulk sweep

Those are plan-blocked and should not consume the remaining window.

## Rate-Limit Plan

Honor Standard plan constraint:

- max `3 requests/sec`

Practical operating rule:

- use `2.5 requests/sec` target
- sleep `0.40s` between requests
- checkpoint every batch
- persist raw response before normalization
- exponential backoff on `429`, `5xx`, and transport failures
- resume by request-hash and endpoint/param checkpoint

## Raw Landing Zone

Proposed raw-first archive:

- `data/racing_api_raw/final_harvest/schema/`
- `data/racing_api_raw/final_harvest/racecards/`
- `data/racing_api_raw/final_harvest/results/`
- `data/racing_api_raw/final_harvest/courses/`
- `data/racing_api_raw/final_harvest/analysis/`
- `data/racing_api_raw/final_harvest/horses/`
- `data/racing_api_raw/final_harvest/errors/`

Every raw file should preserve:

- endpoint
- params
- fetched_at
- status_code
- request_hash
- response_json
- rate_limit_wait
- error if any

## What Can Finish Inside 48 Hours

Realistically finishable:

- live capability map
- results gap-fill after current max date
- current/future racecards free/basic/standard
- courses and regions
- targeted trainer/jockey analysis checks for current runners
- any Standard-plan accessible profile enrichment

Likely not worth forcing:

- full horse enrichment universe
- odds sweep
- full international coverage proof beyond light spot checks

## What Should Be Left To Racing Post

Racing API should **not** remain the main pre-race intelligence source.

Racing Post should replace it for:

- OR/TS/RPR decision context
- last-6 form intelligence
- Spotlight
- Postdata
- Topspeed
- comment language
- human consensus and preview context

Racing API should remain responsible for:

- race IDs
- horse/jockey/trainer/course IDs
- standardized racecard structure
- results endpoint
- analysis endpoints that remain accessible
- fallback and cross-check validation

## Execution Order

1. capability map from official live schema
2. results gap-fill after latest stored date
3. current and future racecards
4. courses and regions
5. targeted trainer/jockey analysis refresh
6. recent/current horse standard profile capture where Standard still allows it
7. international spot-check only if time remains

## Operating Call

Do not waste the remaining API window pretending it is still the racing brain.

Use it to finish the machine-readable spine.
Then let Racing Post take the intelligence lead.
