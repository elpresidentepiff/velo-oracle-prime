# Race Day 15 — Cron and Control-Plane Autopsy (Phase 8, v2 — CORRECTED)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. **Revision v2** — corrects an overclaim in v1 (P0-23). v1 stated the WSL cron "fired late" at 14:08 while, in the same document, also stating standard cron does not catch up missed jobs — those two statements conflict and the "fired late" claim was not actually supported by evidence. This revision replaces both trigger-origin claims with the evidence-supported classification and keeps only what the evidence proves.

## What was investigated

1. Why did no `07:00`-window scoring run appear in `pipeline_runs`?
2. What produced the 08:45 morning run and the 14:08 afternoon run, given both are `pipeline_runs.trigger_source = manual`, not `scheduled`?
3. Where does the `pipeline_runs.target_date does not exist` error originate?
4. What is `pipeline_runs_terminal_only_rule_phase2`?

## Finding 1 — the GitHub Actions scheduler is disabled, not misconfigured

```
gh api repos/{owner}/{repo}/actions/workflows/score-daily.yml
  "state": "disabled_manually"
  "updated_at": "2026-06-10T16:09:52-07:00"
```

`.github/workflows/score-daily.yml` is the **source-controlled scheduler** — its own header comment says "Railway cron is intentionally NOT configured — this file IS the schedule," with cron entries at `0 9 * * 1-6` (scoring) and `0 21 * * 1-6` (sigma). It was manually disabled on 2026-06-10, over five weeks before 2026-07-15, and has not produced a single workflow run since (`gh api .../runs?created=>2026-07-10` returns `total_count: 0`). Every run visible in `gh run list` for this workflow is from early June and all failed. This is the primary reason there is no automated 09:00 UTC scoring trigger at all on 2026-07-15 — the mechanism that was supposed to fire it has been switched off for over a month, and nothing detected or alerted on that.

## Finding 2 — the local WSL crontab's wrapper log proves the WRAPPER ran at 14:08-14:09 UTC; it does NOT prove the cron daemon triggered it

```
crontab -l:
CRON_TZ=Europe/London
0 7 * * * cd <primary-repo-root> && PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py --date $(date +\%Y-\%m-\%d) --execute >> data/reports/run_full_raceday_cron.log 2>&1
```

`0 7 * * *` with `CRON_TZ=Europe/London` in July (BST, UTC+1) means the job is scheduled for 06:00 UTC. The append-only log file `data/reports/run_full_raceday_cron.log` (136,029 lines, spanning multiple days) contains **exactly one** `run_full_raceday.py` invocation block for `2026-07-15` (`RUN_FULL_RACEDAY SUMMARY — 2026-07-15` at line 136006), and the file's own last-modified timestamp is `2026-07-15 14:09:41 UTC` — matching, to the second, the generation timestamps of New Build's and Champion Intent's 14:09 output files.

**Correction from v1**: v1 of this report stated the cron "fired late" at 14:08. That is not supported by the evidence and is withdrawn. What the log proves is only that `scripts/ops/run_full_raceday.py` executed with its stdout/stderr redirected into `data/reports/run_full_raceday_cron.log`, ending 14:09:41Z — that redirection pattern (`>> data/reports/run_full_raceday_cron.log 2>&1`) is identical whether the process was launched by the cron daemon at its scheduled time (after a delayed wake, if such a thing occurred), or by a human running the exact same shell command manually and reusing the same log path. There is no cron-daemon log, syslog entry, process-parent record, or PID trace available in this mission's evidence set that distinguishes the two. **Corrected classification: `AFTERNOON_TRIGGER_ORIGIN_UNPROVEN`.**

## Finding 3 — the 08:45 morning run's origin is equally unproven, not merely "third path, most plausibly X"

The morning `pipeline_runs` row (`54fee6ec-...`, started 08:45:22Z, races_processed=47, runners_processed=400) has **no corresponding entry anywhere in `run_full_raceday_cron.log`** for 2026-07-15 — that log shows only the single 14:08-14:09 full-pipeline run. It was therefore not produced by an invocation that redirected output into that log file. Beyond that, this mission's evidence set does not contain shell history, a process list, or any other record that identifies what launched the 08:45 run. **Corrected classification: `MORNING_TRIGGER_ORIGIN_UNPROVEN`** — v1's language ("most plausibly a direct standalone call ... consistent with the orchestrating session's own account") oversold a plausibility judgment as if it were evidence; it is withdrawn as a specific attribution and replaced with the honest "unproven" label. What remains provable without qualification: (a) it was not the GH Actions scheduler (confirmed `disabled_manually` since June 10), (b) it does not match the local crontab's only logged 2026-07-15 firing (that entry maps to the 14:08-14:09 window, not 08:45), and (c) `pipeline_runs.trigger_source = manual` for BOTH rows confirms neither run self-reports as a scheduled/automated firing.

**The structural root cause of the whole incident is unaffected by this correction and remains fully supported by evidence**: there is no single owner of "today's scoring run," regardless of which specific mechanism triggered either run. Two runs fired against the same `source_date` roughly 5.5 hours apart, both reported `status=PASS`, both self-report `trigger_source=manual`, and the second silently overwrote every mutable artifact the first had produced, with nothing in the system flagging the collision. **Retained classification: `NO_SINGLE_DAILY_RUN_OWNER_AND_NO_RUN_LOCK`.**

## Finding 4 — `pipeline_runs.target_date` schema drift, confirmed still live in code

```
app/main.py:1249
    status_code, _ = _pipeline_request("GET", f"/pipeline_runs?target_date=eq.{target_date}&limit=1")
```

The actual `pipeline_runs` table column is `source_date` (confirmed directly: `pipeline_runs.select('source_date')` succeeds; `.select('target_date')` throws `column pipeline_runs.target_date does not exist`, error code `42703`). This exact query, at `app/main.py:1249`, inside a Supabase-status health check block (`# 4. Supabase Status`), is still present at commit `aef63056` (the anchor SHA both this mission and the primary dirty worktree's `HEAD` share) and would fail every time this code path executes, silently degrading `res["supabase_persistence_status"]` to `"DISCONNECTED"` even when Supabase is fully reachable and pipeline_runs rows exist. This is a genuine, currently-live schema-drift bug, separate from the missing-trigger problem — it corrupts a *status/health-check read*, it does not itself block writes. There is no evidence in this repository's git history (not investigated in depth this mission; out of scope to trace blame) of a schema migration event that renamed the column without updating this call site; the drift was not caught by any test, since `pytest` coverage for `app/main.py`'s health-check block appears absent from CI (consistent with the memory note "pytest env broken. CI covers only ingestion_spine").

## `pipeline_runs_terminal_only_rule_phase2` constraint

Not independently reproduced with a failing write in this read-only mission (writes were out of scope). Named-constraint search in the codebase for a Phase-2 terminal-state rule was not conclusive within the time budget of this evidence pass; flagged as an open item for the next investigative pass — do not treat this section as resolved.

## Who/what triggered the 14:08 run and the 08:45 run — corrected, evidence-bound conclusion

Both origins are **unproven** by the evidence available to this mission:

- **08:45 morning run**: `MORNING_TRIGGER_ORIGIN_UNPROVEN`.
- **14:08 afternoon run**: `AFTERNOON_TRIGGER_ORIGIN_UNPROVEN`.

What IS supported by hard evidence for the 14:08 run: `scripts/ops/run_full_raceday.py` executed end-to-end (19/19 steps PASS) with its output redirected into `data/reports/run_full_raceday_cron.log`, ending 14:09:41Z, and this is the only invocation of that wrapper script logged for 2026-07-15. Neither `pipeline_runs` row carries any metadata distinguishing an automated trigger from a manual one (no `github_actions_scheduled`-style `trigger_source` value, matching `score-daily.yml`'s own convention for what an automated trigger would look like — both rows instead say plain `manual`). Establishing definitive origin for either run would require evidence this mission does not have access to: cron-daemon/syslog records, shell history for the relevant time windows, Railway process logs, or an audit trail on the `/api/trigger/score-daily` endpoint (which was not investigated in this mission — it exists in `app/main.py` but no request log for 2026-07-15 was located in the evidence set).

**The structural finding stands regardless of unresolved origin**: no locking, idempotence check, or "already scored today" guard exists anywhere in the pipeline to have prevented or even flagged two independent runs firing against the same `source_date`, 5.5 hours apart.

## Repair specification (NOT implemented in this evidence mission)

1. Re-enable and repair the `score-daily.yml` GitHub Actions scheduler, or replace it with a single authoritative scheduler (see `race_day_controller_design.md`) — do not run two parallel scheduling mechanisms (GH Actions + local WSL cron) that can both independently fire the same pipeline.
2. Add a `run_prime_today.py`-level guard: refuse to start a new `daily_scoring` run for a `source_date` that already has a `PASS` pipeline_runs row, unless explicitly invoked with a `--force-diagnostic-rerun` flag that writes to a clearly separate, non-authoritative artifact namespace.
3. Fix `app/main.py:1249` to query `source_date` instead of `target_date` (out of scope to implement in this evidence mission per the hard boundaries; flagged for the repair PR).
4. Add an alert if the daily scheduled scoring run has not produced a `pipeline_runs` row by a fixed cutoff (e.g. 10:00 UTC), so a missed 06:00/07:00 firing is caught same-day instead of discovered retroactively.
5. Investigate and document `pipeline_runs_terminal_only_rule_phase2` in a follow-up pass with write-path testing (out of scope here — read-only mission).
6. Add cron-daemon/syslog logging (or equivalent process-launch provenance capture) so a future mission CAN distinguish scheduled-but-delayed firings from manual invocations — this mission could not, and neither could v1's now-withdrawn "fired late" claim.
7. Add request logging on `/api/trigger/score-daily` (and any equivalent scoring-trigger endpoint) capturing caller IP/auth-context/timestamp, so manual API-triggered runs are distinguishable from cron/GH-Actions-triggered runs after the fact.
