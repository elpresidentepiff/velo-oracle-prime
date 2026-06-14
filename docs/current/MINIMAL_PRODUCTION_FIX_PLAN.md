# MINIMAL PRODUCTION FIX PLAN — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · Build NOTHING until June 10 race day closes. Every fix here is small, testable, and touches no weights, no scoring logic, no verdicts.

## P1 — Make Mission Control truthful (stop CLEAN-by-default)
- **File:** `scripts/ops/update_mission_control.py` `_detect_source_truth()`
- **Defect:** falls through to `return "RP_MERGED_CLEAN"`; never reads the observability packet. June 10 scored `RP_MERGED_DEGRADED`; MC will say CLEAN.
- **Fix:** read `source_truth` from `data/velo_run_observability_{date}_*.json` (latest run id); return `UNKNOWN` — never CLEAN — when no artifact is found. ~15 lines.
- **Test:** unit test feeding a DEGRADED observability file; assert MC gate reasons include the degraded block.

## P2 — Stop silent degraded runs
- **Files:** `scripts/ops/run_prime_today.py` (+ existing `scripts/ops/send_degraded_run_notice.py`)
- **Fix:** when `source_truth_enforcer` returns DEGRADED, (a) print a single unmissable banner with the missing-field percentage, (b) invoke the degraded-run notice (respecting `--no-notify` by writing it into telegram delivery truth as SUPPRESSED, not silently skipping).
- **Test:** run against a stripped injection fixture; assert banner + truth-file entry.

## P3 — Restore same-date ratings source (root cause of DEGRADED days)
- **Defect:** DEGRADED fires when >50% of runners lack `pdf_intel.postdata_score`/`or_compression_score` — i.e. the same-date RP PDF/postdata layer didn't make it into the merged build.
- **Fix:** add a pre-scoring check stage (runbook stage 5) that reports PDF-intel coverage per venue BEFORE scoring, so the operator can re-capture/re-merge while there is still time. Detection only — no new data source.
- **Test:** coverage report on June 9 (CLEAN) vs June 10 (DEGRADED) inputs reproduces the difference.

## P4 — One reliable race-day command (orchestration, not logic)
- **Fix:** a thin `scripts/ops/run_race_day.py --date D --phase morning|evening` that executes the existing Steps 1–9 / 10–20 in order, threads `FINAL_CAPTURE_LABEL` automatically, stops at first non-zero exit, and prints the next command. It calls the same scripts the contract names — nothing else.
- **Why:** the repeated daily mistakes are label-copying and step-ordering, both automatable without touching scoring.
- **Test:** dry-run mode prints the exact 20 commands for a given date.

## P5 — Make Sigma/learning gates impossible to bypass
- **Fix:** `nightly_eod_learning_runner.py` refuses to start unless (a) today's Council verdict file exists with `PASS_TO_LEARNING` and (b) MC learning gate is OPEN — read from artifacts, not flags. Currently ordering is by convention.
- **Test:** runner exits non-zero with `WATCH_ONLY` council file present.

## P6 — Fix the test environment + CI
- **Fix:** pin `pytest>=8.2`, compatible `pytest-asyncio`; repair or delete the 3 import-drifted test modules; add a CI job running `tests/` (the current job only tests `workers/ingestion_spine`).
- **Test:** `pytest tests/` green in CI on this branch.

## P7 — Reduce numbered-doc clutter
- **Fix:** execute SIMPLIFICATION_AUDIT.md classifications: archive THE_NEW_TRUTH / CURRENT_RUNTIME_TRUTH / Makefile / cron.txt / COMMAND.json after merge; rewrite CLAUDE.md to ~40 lines pointing at `docs/current/ONE_TRUTH.md`.
- **Approval:** operator approves each DELETE_AFTER_APPROVAL item individually.

## Explicitly NOT in this plan
Model promotion · weight changes · Railway cron resurrection (decide manual-first vs fix-cron as a separate operator decision) · any rewrite of `run_prime_today.py` · Supabase schema changes.
