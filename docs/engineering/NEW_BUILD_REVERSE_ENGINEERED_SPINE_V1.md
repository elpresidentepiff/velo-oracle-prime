# New Build Reverse Engineered Spine V1

## What was replicated

New Build now has a clean replica of the useful VELO operating shape:

1. Ingest
2. Process
3. Learn

It does not copy the old noise. It does not run Live VELO. It does not run Shadow VELO.

## Ingest

New Build ingest accepts:

- Racing Post parsed racecards
- Racing Post profile/dossier archive
- Racing API standard racecards
- Racing API results
- future source inventory from raceform, RPDC, Sigma, and runner snapshots

Outputs:

- `data/new_build/normalized/YYYY-MM-DD/runners.json`
- `data/new_build/normalized/racing_api/YYYY-MM-DD/runners.json`
- `data/new_build/normalized/racing_api_results/YYYY-MM-DD/results.json`

All rows carry:

- `trust_policy = ARCHIVE_CONTEXT_ONLY_NOT_SCORING`
- `velo_scoring_allowed = false`
- `rpr_policy = RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`

## Process

New Build process converts normalized runners into archive context flags:

- `FIRST_TIME_HEADGEAR`
- `FIRST_TIME_GELDING`
- `WIND_SURGERY_SIGNAL`
- `LAYOFF_WARNING`
- `TIP_HEAT`
- `PUBLIC_OVERLOAD_CANDIDATE`
- `HUMAN_CONTEXT_AVAILABLE`
- `PEDIGREE_CONTEXT_AVAILABLE`
- `LOW_ARCHIVE_SIGNAL`

Outputs:

- `data/new_build/processed/YYYY-MM-DD/runner_context.json`

These are research/context flags only. They are not scoring signals.

## Learn

New Build learn reads the outcome bridge and writes only to its own sandbox:

- `data/new_build/learning/sandbox_state.json`
- `data/new_build/learning/sandbox_events.jsonl`
- `data/new_build/learning/latest_learn_report.json`

Learning is blocked unless outcome rows are confirmed and identity confidence is high enough.

No live state. No shadow state. No Playbook G.

## Wider source spine discovered

New Build source inventory sees:

- Racing API racecard files: 36
- Racing API racecard races: 1,654
- Racing API result files: 62
- Racing API result races: 2,742
- Runner snapshot files: 9
- Sigma result files: 4
- RP parsed dates: 7
- RP parsed races: 37
- RP parsed runners: 479
- `raceform_clean.parquet`: present
- `raceform_v17_features.parquet`: present
- `rpdc_tags_historical.jsonl`: present

This confirms the build is not limited to the small RP capture window.

## Commands

Inventory:

```powershell
python scripts/ops/new_build_sources.py inventory --execute
```

Racing API card ingest:

```powershell
python scripts/ops/new_build_sources.py ingest-card --date 2026-05-15 --execute
```

Racing API result ingest:

```powershell
python scripts/ops/new_build_sources.py ingest-results --date 2026-05-13 --execute
```

RP archive replica loop:

```powershell
python scripts/ops/new_build_velo.py run-all --from-date 2026-05-25 --to-date 2026-05-29 --execute
```

Archive pipeline front door:

```powershell
python scripts/ops/new_build_archive_pipeline.py --from-date 2026-05-25 --to-date 2026-05-29 --run
```

## What was rejected

Not copied into New Build:

- Live scoring engine
- Old VP formula
- Shadow consume
- Playbook G
- Telegram runtime
- Router/staking
- old model artifacts
- live table writers
- RPR as scoring fuel

## Test proof

Targeted tests:

```powershell
python -m pytest tests/test_new_build_archive_pipeline.py tests/test_new_build_spine.py tests/test_new_build_sources.py
```

Status:

- 9 tests passed

## Boundary confirmation

- Live VELO untouched by this build slice.
- Shadow VELO untouched by this build slice.
- RPR archive-only.
- RP/Newspaper Form archive/context only.
- New Build learning is sandbox-only.

## Final classification

- NEW_BUILD_REVERSE_ENGINEERED_SPINE_READY
- INGEST_PROCESS_LEARN_REPLICATED_CLEANLY
- SOURCE_DISCOVERY_EXPANDED_BEYOND_RP_WINDOW
- RACING_API_STRUCTURE_LAYER_ACTIVE
- RP_ARCHIVE_CONTEXT_LAYER_ACTIVE
- NEW_BUILD_SANDBOX_LEARNING_ACTIVE
- LIVE_VELO_UNTOUCHED
- SHADOW_VELO_UNTOUCHED
- RPR_ARCHIVE_ONLY
