# New Build Archive Pipeline V1

## Purpose

This is the clean front door for the New Build VELO archive/database lane inside `velo-oracle-prime`.

It orchestrates Racing Post archive work only:

- horse dossiers
- race dossiers
- identity bridge
- source value matrix
- outcome bridge
- RPR archive-only audit
- archive advantage analysis
- optional Supabase archive-table upload

It does not run Live VELO scoring and it does not run Shadow VELO learning.

## Command

Plan only:

```powershell
python scripts/ops/new_build_archive_pipeline.py --from-date 2026-05-25 --to-date 2026-05-29
```

Run local archive builders:

```powershell
python scripts/ops/new_build_archive_pipeline.py --from-date 2026-05-25 --to-date 2026-05-29 --execute-local --run
```

Run Supabase archive dry-run:

```powershell
python scripts/ops/new_build_archive_pipeline.py --from-date 2026-05-25 --to-date 2026-05-29 --supabase-dry-run --run
```

## Outputs

- `data/new_build/archive_pipeline_latest.json`
- `data/new_build/archive_pipeline_latest.md`

## Hard boundaries

- RPR remains archive-only.
- RP/Newspaper Form remains archive/context only.
- No Live VELO scoring.
- No Shadow VELO learning.
- No Telegram.
- No Playbook G.
- No router/staking.
- No live-state mutation.

## Classification

- NEW_BUILD_ARCHIVE_PIPELINE_V1
- ARCHIVE_DATABASE_ONLY
- RPR_ARCHIVE_ONLY
- LIVE_VELO_UNTOUCHED
- SHADOW_VELO_UNTOUCHED

## Clean replica loop

The New Build ingest/process/learn replica is:

```powershell
python scripts/ops/new_build_velo.py run-all --from-date 2026-05-25 --to-date 2026-05-29
```

Execute writes only to `data/new_build/`:

```powershell
python scripts/ops/new_build_velo.py run-all --from-date 2026-05-25 --to-date 2026-05-29 --execute
```

Stages:

- `ingest`: parsed Racing Post archive -> normalized New Build runner spine
- `process`: normalized runner spine -> archive context flags
- `learn`: outcome bridge -> `data/new_build/learning/sandbox_state.json` and `sandbox_events.jsonl`

The learning stage is sandbox-only. It does not touch Live VELO, Shadow VELO, Playbook G, Telegram, router/staking, or live state.

## Source inventory

New Build is not limited to the small Racing Post account capture window. It can discover the wider source spine:

```powershell
python scripts/ops/new_build_sources.py inventory --execute
```

Structured archive ingests:

```powershell
python scripts/ops/new_build_sources.py ingest-card --date 2026-05-15 --execute
python scripts/ops/new_build_sources.py ingest-results --date 2026-05-13 --execute
```

These write only under `data/new_build/normalized/` and keep RPR archive-only.
