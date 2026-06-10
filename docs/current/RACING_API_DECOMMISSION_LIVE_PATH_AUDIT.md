# RACING API — LIVE PATH DECOMMISSION AUDIT

**Date:** 2026-06-10 · Operator law: `RACING_API_LIVE_PATH_FORBIDDEN`. Racing API may exist only as archived legacy, deleted dependency, sidecar reference, documented history, or non-live experimental adapter.

## Live-path scan result

| Reference | What it actually is | Classification | Action taken |
|---|---|---|---|
| `scripts/ops/run_results_sigma.py` `--source` **defaulted to `"api"`** (argparse line 232 + hardcoded fallback line ~426) | One forgotten flag away from calling the decommissioned API on a live closeout | **LIVE_BLOCKER_REMOVE** | **FIXED 2026-06-10** — default flipped to `cache`; explicit warning printed if `api` is requested. API code path left dormant for later approved removal |
| `scripts/ops/run_prime_today.py:1401` → `workers.racing_api_normalizer.normalize_race` | Misleading name only — pure schema normalizer, **zero network imports**; normalizes RP-merged data into the canonical runner schema | DOC_STALE_FIX | Documented here; rename to `race_normalizer` is a later cosmetic refactor (not done — touches live import on race day) |
| `run_results_sigma.py:54-56` env reads `RACING_API_USERNAME/PASSWORD` | Dormant credentials for the retired `--source api` branch | LEGACY_ARCHIVE (with the api branch) | Left in place; remove with the api branch later |
| `run_prime_today.py --source api` choice | Retired source option in the live scorer | LEGACY_ARCHIVE | Not used (`--source rp` is law); remove with later cleanup |
| `src/velo/execution_bridge.py` `racing_api_*_shadow_score` fields | Shadow ledger columns, evidence only, no API calls | SIDE_CAR_ALLOWED | None |
| `src/velo/racing_api_shadow_enrichment.py` | Read-only shadow enrichment (Phase 5 era) | SIDE_CAR_ALLOWED | None |
| `src/velo/course_identity_resolver.py` → `data/racing_api_courses_cache.json` | Static local cache file (historical reference data, no network) | SIDE_CAR_ALLOWED | None |
| `app/data/racing_api_client.py`, `app/main.py` references, `app/engine/*` agents, `workers/racing_api_fetcher.py`, `workers/ingestion_spine/` | Legacy app-era code, not in the 20-step contract | LEGACY_ARCHIVE | None today (bulk archive needs approval). Note: `app/api/racing_api_client.py` + `app/integrations/racing_api_client.py` deletions already pending in worktree |
| `scripts/audit/*` Racing API references (acca replays, weight labs, evidence corpus) | Historical audit scripts | LEGACY_ARCHIVE / SAFE_UNUSED | None |
| `CLAUDE.md` "Racing API CONNECTED / MCP active" | Stale doc claim | **DOC_STALE_FIX** | **FIXED 2026-06-10** — marked DECOMMISSIONED/REMOVED + ONE_TRUTH banner added |
| `CURRENT_RUNTIME_TRUTH.md` API references | Superseded doc | DOC_STALE_FIX | Subordinated by ONE_TRUTH banner; archive pending approval |
| Tests referencing racing_api (e.g. ingestion_spine CI suite) | Legacy-era test target — the ONLY thing CI currently runs | TEST_STALE_FIX | Repoint CI to `tests/` (NEXT_10 fix #8); decision on ingestion_spine retirement is the operator's |

## Verdict
After the sigma default fix, **no live race-day command requires or contacts Racing API**. Race Day 11 runs entirely on the RP HTML path. Remaining references are dormant legacy, sidecar fields, or audit history — scheduled for the approved archive sweep, not for today.
