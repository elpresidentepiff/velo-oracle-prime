# RP Archive Supabase Load And Analysis Closeout

Status: closed for `2026-05-25` through `2026-05-29`.

## Scope

Load Racing Post archive/context artifacts into Supabase archive tables only.

Allowed tables:

- `rp_ingestion_runs`
- `rp_meetings`
- `rp_racecards`
- `rp_runner_profiles`
- `rp_runner_signals`
- `rp_entity_aliases`
- `raw_payload_archive`

Forbidden tables:

- `velo_verdicts`
- `predictions`
- `runner_prediction_snapshots`
- `learned_patterns`
- `velo_learning_events`

## Boundary

RPR remains archive-only. RP archive data does not enter VELO scoring, formulas, model inputs, router, staking, Telegram, Playbook G, live state, or learning state.

## Run Pattern

1. Audit targets.
2. Dry-run upload.
3. Execute upload only if dry-run is clean.
4. Verify row counts and guard fields.
5. Run deeper archive analysis.

## Current Closeout

Branch:

- `codex/rp-archive-rpr-boundary`

Supabase project:

- `ltbsxbvfsxtnharjvqcm`

Upload run:

- final ingestion run id: `13`
- dry-run status: `PASS`
- execute status: `PASS`
- verification status: `PASS`

Rows uploaded / updated by archive loader:

- `rp_meetings`: `7`
- `rp_racecards`: `37`
- `rp_runner_profiles`: `479`
- `rp_runner_signals`: `479`
- `rp_entity_aliases`: `952`
- `raw_payload_archive`: `17`

Verified date-range rows:

- `rp_meetings`: `7`
- `rp_racecards`: `37`
- `rp_runner_profiles`: `479`
- `rp_runner_signals`: `479`
- `rp_entity_aliases`: `929` horse aliases visible after natural-key upsert collapse
- `raw_payload_archive`: `17`

Verification checks:

- duplicate critical rows: `0`
- null critical rows: `0`
- raw payloads with `rp_rpr_velo_allowed=false`: `17`
- RPR scoring leaks: `0`
- forbidden table touch count: `0`

Tables touched:

- `rp_ingestion_runs`
- `rp_meetings`
- `rp_racecards`
- `rp_runner_profiles`
- `rp_runner_signals`
- `rp_entity_aliases`
- `raw_payload_archive`

Forbidden tables not touched:

- `velo_verdicts`
- `predictions`
- `runner_prediction_snapshots`
- `learned_patterns`
- `velo_learning_events`

RPR boundary status:

- `PASS_RPR_ARCHIVE_ONLY`
- `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`
- `velo_scoring_allowed=false`
- `rp_rpr_velo_allowed=false`
- scoring impact: `NONE`

Deeper archive analysis:

- horses analyzed: `472`
- candidate flags: `449`
- tip heat candidates: `6`
- headgear flags: `50`
- wind surgery flags: `1`
- promotion status: `OUTCOME_REQUIRED_BEFORE_PROMOTION`

Top trainer clusters:

- Charlie Johnston: `12`
- Joseph Patrick O'Brien: `12`
- David O'Meara: `11`
- Richard Hannon: `9`
- Tim Easterby: `9`

Top sire clusters:

- Mehmas: `16`
- Kodi Bear: `14`
- Showcasing: `11`
- Ghaiyyath: `10`
- Dark Angel: `10`
- Cotai Glory: `10`

Closeout conclusion:

- Supabase archive load is complete for the target window.
- Archive tables are populated and verified.
- RPR remains archive-only.
- VELO scoring tables were not touched.
- No archive signal is promoted to scoring.

Next step:

- Use the loaded archive to link future results through the outcome bridge before making any source-value or edge claim.
