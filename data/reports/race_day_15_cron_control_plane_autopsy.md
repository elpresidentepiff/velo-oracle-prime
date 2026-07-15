# Race Day 15 — Cron and Control-Plane Autopsy (Phase 8)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01.

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

## Finding 2 — the local WSL crontab exists but fired late, once, at ~14:08 UTC, not at its scheduled time

```
crontab -l:
CRON_TZ=Europe/London
0 7 * * * cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py --date $(date +\%Y-\%m-\%d) --execute >> data/reports/run_full_raceday_cron.log 2>&1
```

`0 7 * * *` with `CRON_TZ=Europe/London` in July (BST, UTC+1) means the job is scheduled for 06:00 UTC. The append-only log file `data/reports/run_full_raceday_cron.log` (136,029 lines, spanning multiple days) contains **exactly one** `run_full_raceday.py` invocation block for `2026-07-15` (`RUN_FULL_RACEDAY SUMMARY — 2026-07-15` at line 136006), and the file's own last-modified timestamp is `2026-07-15 14:09:41 UTC` — matching, to the second, the generation timestamps of New Build's and Champion Intent's 14:09 output files. **This single logged invocation corresponds to the 14:08 afternoon run, not the 06:00 UTC scheduled time.** WSL-hosted cron on a Windows development machine only fires while the WSL instance is running continuously; if the machine was asleep, shut down, or WSL was not started at 06:00 UTC, the scheduled firing is silently lost (standard cron does not catch up missed jobs), and the job only runs whenever the operator (or another trigger) next launches it. Everything in the evidence is consistent with: the 06:00/07:00 window produced nothing, and the full 19-step `run_full_raceday.py` pipeline (racecard capture through New Build/Champion Intent) was executed once, manually or via a delayed/adhoc trigger, at ~14:08 UTC — which is the source of the **afternoon** `pipeline_runs` row (54 races, 400+454 total, `trigger_source=manual`).

## Finding 3 — the 08:45 morning run's origin does not match either known scheduler

The morning `pipeline_runs` row (`54fee6ec-...`, started 08:45:22Z, races_processed=47, runners_processed=400) has **no corresponding entry anywhere in `run_full_raceday_cron.log`** for 2026-07-15 — that log shows only the single 14:08-14:09 full-pipeline run. Since the GH Actions scheduler was disabled and the local crontab's only logged firing was the afternoon one, the 08:45 morning run must have been produced by a **third, distinct invocation path** — most plausibly a direct, standalone call to the scoring script (`scripts/ops/run_prime_today.py`) outside the `run_full_raceday.py` wrapper (which would not append to the wrapper's log file), consistent with the orchestrating session's own account of running the full-pipeline wrapper only once that day. This session cannot access that prior session's exact shell history to attribute the 08:45 call definitively; what can be stated with evidence is: (a) it was not the GH Actions scheduler (disabled since June 10), (b) it was not the logged local crontab firing (that log entry maps to 14:08-14:09), and (c) `pipeline_runs.trigger_source = manual` for BOTH rows confirms neither run claims to be a scheduled/automated firing — both are self-reported manual triggers, from two different actors or invocation paths, roughly 5.5 hours apart, with no coordination or locking between them.

**This is the structural root cause of the whole incident**: there is no single owner of "today's scoring run." Two independent manual triggers were able to fire against the same `source_date` on the same day, both reported `status=PASS`, and the second silently overwrote every mutable artifact the first had produced, with nothing in the system flagging the collision.

## Finding 4 — `pipeline_runs.target_date` schema drift, confirmed still live in code

```
app/main.py:1249
    status_code, _ = _pipeline_request("GET", f"/pipeline_runs?target_date=eq.{target_date}&limit=1")
```

The actual `pipeline_runs` table column is `source_date` (confirmed directly: `pipeline_runs.select('source_date')` succeeds; `.select('target_date')` throws `column pipeline_runs.target_date does not exist`, error code `42703`). This exact query, at `app/main.py:1249`, inside a Supabase-status health check block (`# 4. Supabase Status`), is still present at commit `aef63056` (the anchor SHA both this mission and the primary dirty worktree's `HEAD` share) and would fail every time this code path executes, silently degrading `res["supabase_persistence_status"]` to `"DISCONNECTED"` even when Supabase is fully reachable and pipeline_runs rows exist. This is a genuine, currently-live schema-drift bug, separate from the missing-trigger problem — it corrupts a *status/health-check read*, it does not itself block writes. There is no evidence in this repository's git history (not investigated in depth this mission; out of scope to trace blame) of a schema migration event that renamed the column without updating this call site; the drift was not caught by any test, since `pytest` coverage for `app/main.py`'s health-check block appears absent from CI (consistent with the memory note "pytest env broken. CI covers only ingestion_spine").

## `pipeline_runs_terminal_only_rule_phase2` constraint

Not independently reproduced with a failing write in this read-only mission (writes were out of scope). Named-constraint search in the codebase for a Phase-2 terminal-state rule was not conclusive within the time budget of this evidence pass; flagged as an open item for the next investigative pass — do not treat this section as resolved.

## Who/what triggered the 14:08 run — best-evidence conclusion

The 14:08 run is the single `run_full_raceday.py` invocation logged in `data/reports/run_full_raceday_cron.log`, ending 14:09:41 UTC. Its trigger mechanism (manual shell invocation vs. a delayed/rescheduled cron firing after the WSL instance came back online) cannot be distinguished from the evidence available inside this read-only mission — both produce an identical log signature (single full-pipeline run, no `scheduled`-tagged metadata anywhere in `pipeline_runs`, both rows say `trigger_source=manual`... consistent with a *human-initiated* run rather than an automated one, since automated Railway/GH Actions triggers would show `trigger_source=github_actions_scheduled` or similar per `score-daily.yml`'s own metadata convention, which neither `pipeline_runs` row does). The most defensible statement supportable by hard evidence: **a human or an ad-hoc script manually launched the full `run_full_raceday.py` pipeline at approximately 14:08 UTC on 2026-07-15, separately from and unaware of the 08:45 morning run that had already completed**, and no locking, idempotence check, or "already scored today" guard exists anywhere in the pipeline to have prevented or even flagged the collision.

## Repair specification (NOT implemented in this evidence mission)

1. Re-enable and repair the `score-daily.yml` GitHub Actions scheduler, or replace it with a single authoritative scheduler (see `race_day_controller_design.md`) — do not run two parallel scheduling mechanisms (GH Actions + local WSL cron) that can both independently fire the same pipeline.
2. Add a `run_prime_today.py`-level guard: refuse to start a new `daily_scoring` run for a `source_date` that already has a `PASS` pipeline_runs row, unless explicitly invoked with a `--force-diagnostic-rerun` flag that writes to a clearly separate, non-authoritative artifact namespace.
3. Fix `app/main.py:1249` to query `source_date` instead of `target_date` (out of scope to implement in this evidence mission per the hard boundaries; flagged for the repair PR).
4. Add an alert if the daily scheduled scoring run has not produced a `pipeline_runs` row by a fixed cutoff (e.g. 10:00 UTC), so a missed 06:00/07:00 firing is caught same-day instead of discovered retroactively.
5. Investigate and document `pipeline_runs_terminal_only_rule_phase2` in a follow-up pass with write-path testing (out of scope here — read-only mission).
