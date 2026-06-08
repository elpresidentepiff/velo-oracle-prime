# New Build VELO Continuation Map - 2026-05-25

## Operating line

There are three lanes and they must stay separate.

- Live VELO: operational system. Do not refactor, dismantle, or change scoring/model/router/staking/Telegram/Playbook G/live state from this lane.
- Shadow VELO: protected learning/evaluation system. Do not consume learning, promote, or mutate unless explicitly requested.
- New Build VELO: current database/research/build lane inside `velo-oracle-prime`, using proven archive and bridge work as the foundation.

`velo-oracle-prime` remains the source quarry and current New Build working lane. The accidental standalone `C:\Users\puror\new_velo` repo is not the authority and is ignored unless the operator explicitly asks to quarantine or delete it.

## Current repo truth

- Repo: `C:\Users\puror\velo-oracle-prime`
- Branch: `codex/rp-archive-rpr-boundary`
- Current HEAD when mapped: `84612ec`
- Latest source audit: `docs/engineering/NEW_BUILD_RP_ARCHIVE_SOURCE_AUDIT_2026_05_25.md`

The worktree is noisy. This map does not clean, revert, stage, or mutate unrelated dirty files.

## Established New Build lane

New Build VELO is not one folder yet. It exists as a governed rebuild/database track made from:

- Racing Post account capture
- Racing Post racecard parsing
- Newspaper Form extraction
- Horse profile parsing
- Horse and race dossier generation
- Source Value Matrix
- Horse Identity Bridge
- Outcome Bridge
- RPR archive-only boundary audit
- Supabase archive upload and verification
- RP archive deeper analysis
- RP versus Racing API comparison

This is the useful foundation. It is not Live VELO scoring and it is not Shadow VELO learning.

## Useful assets to keep

These are useful New Build assets and should be carried forward carefully:

- `scripts/ops/racing_post_account_collector.py`
- `scripts/ops/parse_racing_post_account_capture.py`
- `scripts/ops/parse_racing_post_racecard_capture.py`
- `scripts/ops/build_racing_post_racecard_url_list.py`
- `scripts/ops/build_racing_post_profile_url_list.py`
- `scripts/ops/build_rp_horse_dossiers.py`
- `scripts/ops/build_rp_race_dossiers.py`
- `scripts/ops/build_source_value_matrix.py`
- `scripts/ops/build_horse_identity_bridge.py`
- `scripts/ops/build_rp_archive_outcome_bridge.py`
- `scripts/ops/review_horse_identity_bridge.py`
- `scripts/audit_rpr_scoring_boundary.py`
- `scripts/ops/audit_rp_supabase_targets.py`
- `scripts/ops/upload_rp_archive_to_supabase.py`
- `scripts/ops/verify_rp_supabase_archive_load.py`
- `scripts/analysis/analyze_rp_archive_advantage.py`
- `scripts/audit_archive_context_value.py`

Useful data spine:

- `data/racing_post_account_parsed/`
- `data/racing_post_account_parsed/horse_identity_bridge.json`
- `data/racing_post_account_parsed/rp_archive_outcome_bridge.json`
- `data/reports/source_value_matrix_latest.*`
- `data/reports/horse_identity_bridge_latest.*`
- `data/reports/rp_archive_outcome_bridge_latest.*`
- `data/reports/rpr_scoring_boundary_latest.*`
- `data/reports/rp_archive_deeper_analysis_latest.*`

## Useful but needs hardening

These are useful, but should stay supervised because they sit near old operational paths or need cleaner interfaces:

- `scripts/ops/ingest_racecard_pdfs.py`: useful parser history, but old PDF/CASHRUN path is noisy.
- `scripts/ops/build_rp_runner_signals.py`: useful archive signal builder, must remain archive-only.
- `scripts/ops/build_rp_velo_convergence_report.py`: useful comparison layer, not scoring.
- `scripts/ops/compare_velo_vs_rp_archive_context.py`: useful archive-context comparator, not scoring.
- `scripts/ops/build_rp_next_week_watchlist.py`: useful watchlist, archive-only.

## Reject from New Build V1

Do not copy this old noise into New Build V1 unless separately approved:

- Live scoring engine and old VP formula
- Model artifacts
- Shadow consume code
- Playbook G promotion/runtime
- Telegram runtime
- Router/staking/execution code
- Old Council sprawl
- Duplicate runtime reports
- Anything writing `velo_verdicts`, `runner_prediction_snapshots`, live prediction tables, learned patterns, or live state
- Anything that lets RPR enter scoring/model inputs

## Current capture truth

Parsed RP archive currently contains:

| Date | Races | Runners | Horse dossiers | Race dossiers | Captured horse profiles |
|---|---:|---:|---:|---:|---:|
| 2026-05-24 | 0 | 0 | 0 | 0 | 1 |
| 2026-05-25 | 8 | 59 | 59 | 8 | 59 |
| 2026-05-26 | 8 | 70 | 70 | 8 | 0 |
| 2026-05-27 | 7 | 91 | 91 | 7 | 0 |
| 2026-05-28 | 7 | 150 | 146 | 7 | 0 |
| 2026-05-29 | 7 | 109 | 106 | 7 | 0 |
| 2026-05-30 | 0 | 0 | 0 | 0 | 0 |

Totals:

- Races: 37
- Runners: 479
- Horse dossiers: 472
- Race dossiers: 37
- Captured horse profiles: 60
- Outcome bridge rows: 473

Supabase archive load already passed for the archive tables only. It did not touch Live VELO scoring tables.

## Boundary locks

- RPR is archive-only.
- RP comments are archive/context only.
- Newspaper Form and Diomed comments are archive/context only.
- Tip counts are archive/context and hype-warning only.
- Forecast odds are archive/context only and must not override VELO price logic.
- No RP archive field is promoted into scoring without a controlled future approval.

## What still needs doing

Immediate practical work:

1. Create one clean New Build runbook/entrypoint for the archive pipeline.
2. Complete all-tabs horse profile capture for May 25.
3. Capture profile tabs for May 26-29.
4. Re-capture May 30 when pages have real racecard payload.
5. Add Big Race Entries archive capture.
6. Add US Racing racecard and horse profile extraction.
7. Re-run identity bridge after more profile coverage.
8. Re-run outcome bridge once results/Sigma overlap exists.
9. Keep Source Value Matrix honest: no edge claim until identity plus outcome overlap exists.
10. Keep Supabase archive tables as archive/research only.

## Next build slice

The next clean slice should be:

`New Build Archive Pipeline V1`

It should provide one supervised command path that runs:

1. Build RP racecard URL list.
2. Capture RP account pages.
3. Parse racecards and Newspaper Form.
4. Build profile URL list.
5. Capture profile tabs.
6. Parse horse profiles.
7. Build horse/race dossiers.
8. Build identity bridge.
9. Build outcome bridge.
10. Upload archive rows to Supabase archive tables.
11. Verify RPR boundary and archive load.
12. Write a plain operator summary.

This pipeline must not run Live VELO scoring, Shadow learning, Telegram, Playbook G, router/staking, or live-state mutation.

## Final classification

- NEW_BUILD_LANE_IDENTIFIED
- VELO_ORACLE_PRIME_SOURCE_AND_BUILD_LANE
- LIVE_VELO_UNTOUCHED_BY_THIS_MAP
- SHADOW_VELO_UNTOUCHED_BY_THIS_MAP
- RPR_ARCHIVE_ONLY_BOUNDARY_LOCKED
- OLD_NOISE_REJECTED_FOR_NEW_BUILD_V1
- NEXT_SLICE_ARCHIVE_PIPELINE_V1
