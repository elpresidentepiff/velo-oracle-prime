# SIMPLIFICATION AUDIT — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · **Nothing deleted. Classifications only. Deletions require operator approval.**

## Root-level files

| Item | Finding | Classification |
|---|---|---|
| `THE_ONE_TRUTH.md` | Best doc in the repo (2026-06-06/07, 20-step contract, all 21 entrypoints verified present in git) | KEEP_CURRENT — referenced by `docs/current/ONE_TRUTH.md` |
| `THE_NEW_TRUTH.md` | June 9 architecture/math notes; formula table lists place 0.08 + longshot 0.07 as if live — they are disabled in the active profile (misleading) | MERGE_INTO_ONE_TRUTH then ARCHIVE |
| `CURRENT_RUNTIME_TRUTH.md` | Names `scrape_results_atr.py` (does not exist) and `app/pipelines/sigma_runner.py` as the evening path — contradicts the locked RP-only sigma path. Stale since ~June 2 | MERGE_INTO_ONE_TRUTH then ARCHIVE |
| `CLAUDE.md` | March-era claims still live: "Racing API CONNECTED" (decommissioned 2026-05-14), 54-table row counts from 2026-03-16, "Known Bugs" list of unverified currency, sqpe table contradicting itself | NEEDS_OPERATOR_DECISION — rewrite to point at `docs/current/ONE_TRUTH.md` |
| `Makefile` | Entirely Benter v10.1 era (`src.training.train_benter`, `src.pipelines.ingest_racecards`) — no target matches the live chain | DEPRECATED_REFERENCE → ARCHIVE |
| `cron.txt` | `/home/ubuntu/velo-oracle` paths, `run_daily_predictions.py` (dead) | DELETE_AFTER_APPROVAL |
| `COMMAND.json` | One-shot Feb 2026 dashboard deploy command | DELETE_AFTER_APPROVAL |
| `MANDATE.md` | Behavioural mandate, still operative in spirit | KEEP_CURRENT (or merge the 4 hard rules into ONE_TRUTH) |
| `sigma_tonight.sh`, `sigma_workflow_patch.yml` | One-night patch artifacts | DELETE_AFTER_APPROVAL |
| `railway_hermes_env.txt`, `railway_velo_oracle_env.txt` | Env dumps at repo root — check for secrets before anything else | NEEDS_OPERATOR_DECISION (security) |

## Directories

| Item | Finding | Classification |
|---|---|---|
| `docs/` flat (133 .md) | Numbered audits, forensics, superseded plans (VELO_FALSE_RANK1_FORENSIC, TIE_V2/V3_DESIGN, etc.) | ARCHIVE to `docs/archive/` except files referenced by ONE_TRUTH |
| `docs/stabilization/`, `docs/operations/`, `docs/runtime/` | Partially current (SCORING_RUNBOOK, SIGMA_RUNBOOK, ROLLBACK_RUNBOOK overlap the new runbook) | MERGE_INTO_ONE_TRUTH / runbook, then ARCHIVE duplicates |
| `docs/live_state/MASTER_STATE.md` | Yet another "current state" doc | MERGE_INTO_ONE_TRUTH |
| `archive/` (13MB) | Already an archive — contains deleted Racing API scripts pending commit | KEEP_CURRENT (commit the deletions) |
| `moltbook/`, `hackathon/`, `presentation/`, `presentation_assets/`, `examples/`, `benchmark/` | Non-production | ARCHIVE |
| `feast_repo/`, `mlruns/`, `alembic/` + `alembic.ini`, `flows/` | No evidence of live use in the daily chain | NEEDS_OPERATOR_DECISION |
| `new_build_velo/`, `data/new_build/` | Shadow challenger — clearly shadow, correctly labeled | SHADOW_ONLY |
| `tmp/`, `incoming/`, `quarantine/` | Scratch artifacts at repo root | ARCHIVE or DELETE_AFTER_APPROVAL |
| `venv/` in repo tree | Should never be committed; verify gitignore | KEEP (local) — confirm ignored |

## Scripts

| Item | Finding | Classification |
|---|---|---|
| `scripts/ops/velo_race_day_button.py` | THE_ONE_TRUTH explicitly forbids using it as authority | DEPRECATED_REFERENCE — archive or make it print the runbook |
| `scripts/ops/scrape_results_sl.py` | Sporting Life — retired source | DEPRECATED_REFERENCE → ARCHIVE |
| `scripts/audit_international_*` (12 files), `scripts/build_hk_*`, `build_fr_*`, `build_intl_*` | Experimental international lane parked at top level | SHADOW_ONLY → move under `scripts/experimental/` |
| `scripts/audit_20260522_*` and other dated one-offs | Point-in-time audits, superseded | ARCHIVE |
| ~29 dated/patch/recovery scripts in `scripts/ops/` | One-day recovery layers that survived their day | ARCHIVE after each is confirmed absent from the 20-step contract |
| `workers/racing_api_fetcher.py`, `workers/ingestion_spine/` | Racing API era; ingestion_spine is the ONLY thing CI tests | NEEDS_OPERATOR_DECISION — if PDFs/HTML replaced it, retire and repoint CI |

## Models

| Item | Finding | Classification |
|---|---|---|
| `models/sqpe_v17/`, `models/specialist/` | Live | KEEP_CURRENT — never touch |
| `models/sqpe_v14/`, `v1_real/`, `tie_v9/`, `longshot_v6/`, `overlay_v5/`, `sqpe_v17_dev/`, `shadow/` | Old/metadata-only/dev | ARCHIVE (keep on disk, mark non-live in ONE_TRUTH) |
| `models/sqpe_v18/` | Candidate, not promoted | SHADOW_ONLY |

## Misleading references found (docs claiming things code disproves)
1. `CURRENT_RUNTIME_TRUTH.md` evening path (`scrape_results_atr.py` — nonexistent).
2. `CLAUDE.md` "Racing API CONNECTED / MCP active".
3. `THE_NEW_TRUTH.md` ensemble table implying place/longshot are live-weighted.
4. Mission Control `source_truth` output — defaults `RP_MERGED_CLEAN` (code defect, see fix plan).
5. `Makefile help` text describing a pipeline that no longer exists.
