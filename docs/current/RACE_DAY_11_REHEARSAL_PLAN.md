# RACE DAY 11 REHEARSAL PLAN — 2026-06-11

**Goal:** run the full chain for June 11 with zero live side effects, prove every stage, and produce the exact command list for the real run. Written 2026-06-10 while Race Day 10 is in progress — nothing here executes today.

## What was already rehearsed today (read-only, June 10 data)

| Probe | Result |
|---|---|
| `velo_session_start_check.py` | RUNS — 3 WARN (14 degraded days, 2 learning blocks, dirty worktree), 0 CRITICAL |
| `validate_rp_injection.py` on June 10 injection | **PASS** — 34 races, 34 unique IDs, 5 courses, 381 runners (matches 34 verdicts + 381 RPDC rows exactly) |
| Supabase read audit | June 10 persistence proven 34/34 |
| `--dry-run` flag inspection | `run_prime_today.py` line 1363–1368: dry-run disables Telegram AND persistence — genuine no-write mode exists (verify pipeline_runs/snapshots are also gated on first use) |

## Rehearsal sequence for June 11 (run the morning of June 11, before the real run)

```bash
# 0. Pre-flight (read-only)
PYTHONPATH=. python scripts/ops/velo_session_start_check.py

# 1-3. Capture + parse (external reads, local writes only — safe)
#    THE_ONE_TRUTH Steps 1-4 with date 2026-06-11; record FINAL_CAPTURE_LABEL once.

# 4. Gate (read-only)
PYTHONPATH=. python scripts/ops/validate_rp_injection.py \
  --injection-path data/racing_post_account_parsed/FINAL_CAPTURE_LABEL/racecard_injection.json

# 5. Merged build (local writes only)
PYTHONPATH=. python scripts/ops/build_racecard_merged_from_injection.py --date 2026-06-11 \
  --injection-path <same>

# 6. Ratings/PDF-intel coverage check (NEW — manual until P-fix lands):
#    count runners with pdf_intel.postdata_score/or_compression_score in the merged files;
#    <50% coverage means the day will score DEGRADED — fix BEFORE scoring, not after.

# 7. RPDC build — WRITES SUPABASE runner_release_candidates (same as every morning).
#    Approved standard operation; run as normal:
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date 2026-06-11 --injection-path <same>

# 8. SCORING REHEARSAL — dry-run first:
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py \
  --date 2026-06-11 --source rp --dry-run
#    Confirm: verdicts JSON written locally, NOTHING in Supabase velo_verdicts for the run,
#    no Telegram. Check observability packet: source_truth, flatline, RPDC attach status.

# 9. If dry-run clean → real run (Supabase write = standard daily operation):
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py \
  --date 2026-06-11 --source rp --no-notify

# 10. Persistence proof (read-only) — count June 11 rows, null decision_tier, null git_sha.

# 11. Dashboard dry-run: run the three dashboard scripts; diff output JSON; DO NOT deploy/publish.
# 12. Telegram: remains DISABLED (--no-notify). Verify telegram_delivery_truth records SUPPRESSED.
# 13. Mission Control: run update_mission_control.py AFTER P1 fix, else cross-check
#     source_truth against the observability packet manually.

# EVENING: Steps 10-20 per RACE_DAY_RUNBOOK.md, with sigma closeout and learning
# eligibility decided by Council verdict, not by hand.
```

## What works today (proven)
Capture→parse→validate→merge→RPDC→score→persist→local backup: all ran for June 10 with 100% coverage. Sigma/ingest ran for June 9 (342 horse_runs rows landed).

## What fails / is fragile
1. RPDC persist severance (attached locally, hijacked columns in Supabase) — fix needs approval.
2. Day scored DEGRADED — PDF-intel coverage was not checked before scoring.
3. Mission Control defaults source to CLEAN.
4. Telegram off, cron unproven, all steps manual, label copied by hand ~10 times.
5. Evening Steps 14–20 frequently skipped (June 9: no learning-proof artifacts).

## What needs operator input
- Approve the RPDC persist fix (changes Supabase write payload).
- Approve `source_truth`/`feature_degraded` columns migration.
- Decide Telegram re-enable criteria.
- Decide cron: fix Railway or formally adopt manual-first.

## Blockers for a clean production day
A day is only clean if: injection PASS · PDF-intel coverage >50% · scoring 100% with CLEAN source · persistence proof query green · evening chain completes Steps 10–20 · Council verdict recorded. June 10 fails on PDF-intel coverage and (pending tonight) the evening chain.
