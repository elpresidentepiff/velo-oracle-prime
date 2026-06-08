# New Build VELO / RP Archive Source Audit - 2026-05-25

Status: `AUDIT_ONLY`

Boundaries:

- Live VELO untouched.
- Shadow VELO untouched.
- No files attached or wired into New Build VELO.
- No scoring change.
- No model change.
- No formula change.
- No Telegram change.
- No Playbook G change.
- No live-state mutation.
- RPR remains archive-only.
- RP data remains database/research/context only.

## A. Where New Build VELO Is

There is no single folder named `new_build_velo` or `New Build VELO`.

The work exists as a governed rebuild/design track across docs, scripts, models, and archive tooling:

- `docs/engineering/VELO_MASTER_ROLLOUT_PLAN_V1.md`
  - master plan for the new operating-system direction.
  - status: design only.
- `docs/engineering/VELO_MASTER_ROLLOUT_INDEX.md`
  - index of committed design phases.
  - says the next safe implementation slice is Agent Harness / Sandbox Runner.
- `docs/engineering/VELO_V14_ARCHITECTURE_TRUTH_MAP.md`
  - path-verified map of live models, shadow models, runtime scripts, and open items.
- `docs/engineering/VELO_AGENT_HARNESS_V1.md`
  - New Build governance boundary for automated agents.
- `docs/engineering/VELO_SANDBOX_RUNNER_V1.md`
  - disposable shadow-only execution design.
- `docs/engineering/VELO_OPERATIONAL_HARNESS_PROTOCOL_V1.md`
  - planner/generator/evaluator discipline.
- `docs/engineering/RP_ARCHIVE_ADVANTAGE_LAYER_V1.md`
  - RP archive advantage layer.
- `docs/engineering/SOURCE_INCLUSION_POLICY_V1.md`
  - source lane policy.
- `docs/engineering/SOURCE_VALUE_MATRIX_V1.md`
  - source value matrix design.
- `docs/engineering/HORSE_IDENTITY_BRIDGE_V1.md`
  - identity bridge governance.
- `docs/engineering/RP_ARCHIVE_OUTCOME_BRIDGE_V1.md`
  - outcome bridge governance.
- `scripts/ops/build_rp_horse_dossiers.py`
  - RP horse dossier builder.
- `scripts/ops/build_rp_race_dossiers.py`
  - RP race dossier builder.
- `scripts/ops/compare_velo_vs_rp_archive_context.py`
  - VELO vs archive context comparator.
- `scripts/ops/build_source_value_matrix.py`
  - source comparison matrix.
- `scripts/ops/build_horse_identity_bridge.py`
  - RP-to-VELO identity bridge.
- `scripts/ops/build_rp_archive_outcome_bridge.py`
  - outcome bridge.
- `scripts/ops/upload_rp_archive_to_supabase.py`
  - Supabase archive-only uploader.
- `scripts/analysis/analyze_rp_archive_advantage.py`
  - archive context analysis.

Current status:

- New Build VELO is a staged design/research/governance track, not a live replacement.
- The RP archive/database lane is the active data foundation for future New Build research.
- Nothing is wired into live or shadow scoring from this lane.

## B. What Newspaper Form / RP Files Give Us

Current parsed racecard fields:

- race id / RP race id
- course
- course id
- country
- race time
- race title
- race type
- race class
- going / going code
- surface
- category
- stalls
- prize money
- rating band
- distance yards
- distance furlongs
- declared runners
- source URL
- raw source file
- html hash
- tabs available
- newspaper form present flag

Current parsed horse/runner fields:

- horse name
- RP horse id
- horse profile URL
- age
- sex / colour
- country
- sire
- dam
- dam sire
- trainer
- trainer id
- trainer recent run-to-form where available
- jockey where available
- jockey id where available
- owner
- draw
- weight stones / pounds / lbs
- headgear
- headgear first-time flag
- wind surgery flag
- days since last run
- form figures
- non-runner flag
- forecast odds where available
- newspaper tip count where available
- Diomed / newspaper-form comment where available
- Spotlight comment where available
- official rating
- Topspeed
- RPR as `rp_rpr_archive_only`
- `rp_rpr_velo_allowed=false`

Captured horse profile fields from the 2026-05-25 form pages:

- horse uid
- horse name
- country
- age
- date of birth
- sex
- colour
- trainer id / name / location
- trainer last 14 days: runs, wins, percent
- owner id / name
- previous owners
- breeder
- sire id / name / country
- dam id / name / country
- dam sire id / name / country
- sire average win distance
- dam-sire average win distance
- tips list and count
- entries list and count
- quotes list and count
- stable-tour quotes
- account logged/subscription metadata
- source URL, final URL, capture hash, raw HTML path

Important limitation:

- Current complete profile extraction is mainly the `form` profile tab.
- Entries/Stats/Quotes/Pedigree/Sales/Notes all-tab collection is prepared but not fully captured/parsed yet.
- Newspaper Form racecard comments exist where Racing Post provides them, but not every runner has comments.

## C. What Racing Post Gives That Racing API Does Not

RP-only / stronger RP fields:

- Newspaper Form / Diomed comments.
- Spotlight-style human comments where present.
- Newspaper tip count / public heat.
- Owner and previous-owner context.
- Pedigree context: sire, dam, dam sire, breeder.
- Sire and dam-sire average winning-distance context.
- Quotes and stable-tour quotes.
- Entries and future intent clues.
- Sales/notes/pedigree tabs once all-tab capture is completed.
- Account-side horse profile pages.
- Rich racecard human interpretation.
- Forecast odds in RP page context.
- RPR archive value, but banned from VELO scoring.

How to use this:

- build horse dossiers.
- build race dossiers.
- detect hype traps.
- detect quiet profiles.
- find unknown/unexposed horses.
- prepare New Build research features.
- compare against VELO after scoring.

Do not use this:

- do not feed RP comments, RPR, tip count, or human selections into live VP.
- do not use RP as truth without Sigma/results.

## D. What Racing API Gives That Racing Post Does Not

Racing API strengths:

- machine-readable race ids.
- runner ids / horse ids where available.
- normalized racecard endpoints.
- structured results endpoint.
- structured odds endpoint where plan allows.
- clean course/result spine.
- easier repeatable API ingestion.
- canonical fallback / cross-check layer.

Racing API is better for:

- identity spine.
- result truth.
- date/race/runner structure.
- standard machine joins.
- cross-checking RP archive rows.

RP is better for:

- human context.
- profile depth.
- newspaper form.
- tips/public heat.
- pedigree/owner/quote/entries intelligence.

## E. What We Already Captured

Parsed archive counts:

| Date | Races | Runners | Horse Profiles | Horse Dossiers | Race Dossiers | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-05-24 | 0 | 0 | 1 | 0 | 0 | Bow Echo/profile pilot and racecard index capture. |
| 2026-05-25 | 8 | 59 | 59 | 59 | 8 | Today archive parsed, 59 horse form profiles captured. |
| 2026-05-26 | 8 | 70 | 0 | 70 | 8 | Racecards/dossiers parsed. |
| 2026-05-27 | 7 | 91 | 0 | 91 | 7 | Racecards/dossiers parsed. |
| 2026-05-28 | 7 | 150 | 0 | 146 | 7 | Duplicate/blank identities deduped in dossiers. |
| 2026-05-29 | 7 | 109 | 0 | 106 | 7 | Duplicate/blank identities deduped in dossiers. |
| 2026-05-30 | 0 | 0 | 0 | 0 | 0 | Race pages captured, runner payload not useful yet. |

Totals:

- parsed races: `37`
- parsed runners: `479`
- captured horse profiles: `60` including Bow Echo
- horse dossiers: `472`
- race dossiers: `37`
- identity bridge rows: `473`
- outcome bridge rows: `473`

Raw capture inventory:

- 2026-05-24: `1` racecard/index capture plus Bow Echo/statistics profile work.
- 2026-05-25: `14` racecard captures, `59` horse profile captures, `1` US Racing capture.
- 2026-05-26: `8` racecard captures.
- 2026-05-27: `7` racecard captures.
- 2026-05-28: `7` racecard captures.
- 2026-05-29: `7` racecard captures.
- 2026-05-30: `7` racecard captures.

Supabase archive load completed:

- `rp_meetings`: `7`
- `rp_racecards`: `37`
- `rp_runner_profiles`: `479`
- `rp_runner_signals`: `479`
- `rp_entity_aliases`: `952` upserts
- `raw_payload_archive`: `17`
- verification: `PASS`
- forbidden table touches: `0`
- RPR scoring leaks: `0`

## F. What Still Needs Capture

High priority:

- all profile tabs for captured horses:
  - form
  - entries
  - stats
  - quotes
  - pedigree
  - sales
  - notes
- May 30 re-capture once runner payloads are present.
- Big Race Entries.
- US Racing race pages and runner profile links.
- full future-card profile capture for 2026-05-26 through 2026-05-29, not just racecard dossiers.

Medium priority:

- repeat capture cadence for tomorrow / Tue / Wed / Thu / Fri / Sat.
- missing newspaper comments where pages do not expose them.
- profile URL list expansion from all racecard runner links.
- raw manifests for every section, including source URL, final URL, hash, and timestamp.

## G. What Needs Modifying

Parsers:

- extend profile parser to all tabs, not just form pages.
- normalize entries/stats/quotes/pedigree/sales/notes into stable fields.
- separate newspaper comments, Spotlight, Postdata, tips, and ratings into explicit source-labelled fields.
- keep RPR as `rp_rpr_archive_only`.

File organisation:

- split raw account captures by date and section:
  - racecards
  - horse_profiles_form
  - horse_profiles_entries
  - horse_profiles_stats
  - horse_profiles_quotes
  - horse_profiles_pedigree
  - horse_profiles_sales
  - horse_profiles_notes
  - us_racing
  - big_race_entries

Identity bridge:

- improve RP horse id to Racing API/Velo runner matching.
- resolve the `2` ambiguous identities.
- upgrade RPDC name-only matches using trainer/sire/age/country/race date/course.

Outcome bridge:

- connect RP archive rows to Sigma and horse_runs as results arrive.
- keep rows without result as `OUTCOME_MISSING` or `PREDICTION_ONLY_NO_RESULT`.
- do not claim edge until outcome overlap exists.

Supabase/archive tables:

- archive tables are usable now.
- consider adding date/source columns to runner profile/signal archive tables later for easier verification.
- keep forbidden scoring tables out of archive loaders.

Reports:

- add a compact daily RP capture board.
- add missing-profile report.
- add RP-only vs VELO-linked report.
- add outcome bridge closeout after each result day.

Future New Build test harness:

- build read-only tests that consume archive data and produce research labels.
- run source value tests only on confirmed identity + confirmed outcome rows.
- block every field from scoring until separately promoted through shadow evidence.

## H. Useful For Future New Build VELO Research

Useful candidates:

- trainer recent form.
- owner/trainer/pedigree clusters.
- sire / dam-sire distance fit.
- entries / future intent.
- quotes / stable-tour intent.
- first-time headgear.
- wind surgery return.
- days since run.
- unexposed horse count.
- tip heat / public overload.
- newspaper comment sentiment as context only.
- RP-only unknown-horse warnings.
- VELO-hot / RP-silent quiet profile lane.
- RP-hyped / VELO-cold trap lane.

Research workflow:

`RP archive -> identity bridge -> outcome bridge -> source value matrix -> shadow research -> promotion audit`

No shortcut into live scoring.

## I. Banned / Archive-Only

Must stay banned from live VELO scoring:

- RPR.
- RP comments.
- Spotlight/Newspaper Form/Diomed comments.
- newspaper tip count.
- RP human selections.
- forecast odds as a direct selection override.
- owner/trainer/pedigree context unless separately proven in shadow.
- any field that leaks post-result truth.

Explicit policy:

- RPR = `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`.
- RP data = `ARCHIVE_CONTEXT_ONLY_NOT_SCORING`.
- `velo_scoring_allowed=false`.
- `rp_rpr_velo_allowed=false`.

## J. Live VELO Confirmation

Live VELO was not touched.

No changes were made to:

- `velo_verdicts`
- predictions
- runner prediction snapshots
- scoring code
- model files
- formulas
- router/staking
- Telegram
- Playbook G
- `data/sentient_state.json`

## K. Shadow VELO Confirmation

Shadow VELO was not touched.

No changes were made to:

- shadow learning targets
- shadow state files
- shadow consume flags
- `shadow_full_train_v1`
- `shadow_full_train_v2`
- `consumed_live`
- learning event consumption

Final classification:

- `NEW_BUILD_FOUND_AS_DESIGN_AND_RESEARCH_TRACK`
- `RP_ARCHIVE_DATABASE_WORK_CONTINUES`
- `NEWSPAPER_FORM_FIELDS_MAPPED`
- `RP_VS_RACING_API_DIFFERENCE_CLEAR`
- `ALL_TAB_PROFILE_CAPTURE_STILL_REQUIRED`
- `OUTCOME_LINK_REQUIRED_BEFORE_EDGE_CLAIMS`
- `RPR_ARCHIVE_ONLY`
- `LIVE_VELO_UNTOUCHED`
- `SHADOW_VELO_UNTOUCHED`
