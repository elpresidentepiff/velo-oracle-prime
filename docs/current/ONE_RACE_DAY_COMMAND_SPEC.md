# ONE RACE DAY COMMAND — SPEC (build pending operator approval)

**Date:** 2026-06-10 · Spec only — no orchestrator code yet. This is the route out of hand-copied daily labels.

## Target

```bash
python scripts/ops/run_race_day.py --date YYYY-MM-DD --mode dry-run
python scripts/ops/run_race_day.py --date YYYY-MM-DD --mode live --notify   # notify only after operator re-enables Telegram
```

## Design constraints (non-negotiable)
- **Zero scoring logic inside.** It subprocesses the existing One Truth scripts, in order, nothing else.
- `FINAL_CAPTURE_LABEL` chosen once, threaded automatically to every stage.
- Stops at the first non-zero exit; prints the failed stage, the artifact to inspect, and the exact rerun command.
- `--mode dry-run` forces `--dry-run`/read-only variants everywhere; refuses any stage that cannot be made write-free, listing what it skipped.
- Every stage appends to `data/reports/race_day_{date}_chain.json` — the chain truth artifact.
- Refuses to run `--mode live` while another live run for the same date is recorded unfinished.

## Stages

| # | Stage | Command (existing scripts) | Expected artifact | Pass condition | Fail condition | Write surface | Rollback |
|---|---|---|---|---|---|---|---|
| 1 | Pre-flight | `velo_session_start_check.py` | console table | 0 CRITICAL | any CRITICAL | none | n/a |
| 2 | Source capture | collector `manual-capture` + `build_racing_post_racecard_url_list` + collector `capture` | raw HTML dirs + URL list | every HTML >500KB, ≥3 courses | 5KB block pages | local only | re-login, recapture missing |
| 3 | Parse | `parse_racing_post_racecard_capture.py` | injection JSON + standard cache | zero null off_times | parse errors | local only | re-parse |
| 4 | Validation | `validate_rp_injection.py` | exit 0 | gate PASS | non-zero | none | fix data, rerun 3 |
| 5 | Feature health | PDF-intel coverage report on merged files (fix #5) | coverage report | >50% coverage → CLEAN-track | ≤50% → declare DEGRADED before scoring | local only | fix source or accept degraded knowingly |
| 6 | RPDC | `build_rpdc_daily.py` | `runner_release_candidates` rows = runner count | 100% race coverage | zero-runner warning | Supabase RPDC table | rerun (idempotent upsert) |
| 7 | Scoring | `run_prime_today.py --source rp` (dry-run first in dry-run mode) | verdicts JSON + observability packet | 100% scored, 0 errors | any score error / SOURCE_UNKNOWN | live: Supabase verdicts+pipeline_runs; dry: local | `VELO_ENSEMBLE_PROFILE` env rollback; verdicts upsert on race_id |
| 8 | Persistence proof | `prove_supabase_persistence.py` | proof JSON/MD | exit 0 | exit 1/2 | local reports | investigate before evening |
| 9 | Dashboard | three dashboard scripts | dashboard JSON | diff sane | missing inputs | local until publish approved | skip stage |
| 10 | Telegram | (disabled) delivery-truth check | telegram truth file | SUPPRESSED recorded | silent skip | none while disabled | n/a |
| 11 | Mission Control | `update_mission_control.py` | MC date file + latest.json | source matches observability | UNKNOWN/missing packet | local MC files | rerun after fix |
| 12 | Evening closeout | Steps 10A→19 per runbook | results, sigma, ingest, corpus, council | each gate green | any gate fails → DAY INCOMPLETE | Supabase sigma/horse_runs; local | rerun failed step only |
| 13 | Learning gate | LEARNING_ADMISSION_GATE evaluation | gate status in MC file | LEARNING_READY + operator approval | any BLOCKED status | none (decision) | n/a |

## Acceptance test for the orchestrator itself
Dry-run over a past date's stored artifacts reproduces the chain truth file without a single network write; `--mode dry-run` then `--mode live` on a fresh date produces identical stage ordering with only the declared write surfaces differing.

## Build approval
Operator approves before any code is written (NEXT_10 fix #9 / plan §4). Estimated size: ~200 lines + tests.
