# SIGMA-28C — Controlled Verdict-Only Proof — Operator Brief
Generated: 2026-07-04 | PARTIALLY BLOCKED | read-only checks + code inspection | NO WRITES PERFORMED

---

## Outcome: SIGMA_28C_BLOCKED

PR #110 merged cleanly and preflight checks all ran successfully. The controlled write itself (Part D) was **not executed** — no safe racecard source exists to produce one ordinary verdict row without also overwriting real historical data. Stopping per the mission's own instruction ("If no safe card/source exists, stop and report BLOCKED") rather than forcing a substitute.

## 1. Did PR #110 merge?

Yes. Merge commit `fd65631c871f4a6a954c2e2e2a0559b09a7611d3`. `origin/main` advanced `bd4a533 → fd65631`. CI was confirmed green on head `5dd11f1` (Analyze, safety-audit, test, validate, lint, type-check, CodeQL all `SUCCESS`) before merging.

## 2. What command was run?

None. See "Why this is blocked" below — no command was executed against `run_prime_today.py` in this mission.

## 3-7. Did it create a post-PR110 verdict row / did race_type, race_type_raw, race_type_source, race_type_recorded_at persist?

Not applicable — no command was run.

## 8. Did runner_prediction_snapshots remain untouched?

Yes, trivially — confirmed by inaction. Preflight baseline: 0 rows with `created_at` after 2026-07-04T00:00:00.

## 9. Did sigma_audits remain untouched?

Yes, trivially. Preflight baseline: 0 rows with `date` after 2026-07-03.

## 10. Were local runner snapshot files avoided?

Yes. Preflight found 116 existing `data/runner_snapshots_*.jsonl` files, latest dated 2026-06-30. No new files were created (no command ran).

## 11. Did Telegram remain silent?

Yes, trivially — no command ran. (Also, `tg()` in `run_prime_today.py` routes through a permanent `_legacy_tg()` no-op regardless, per earlier SIGMA-28A findings.)

## 12. Did pure Sigma helper extraction include race_type?

Not exercised on new data this pass — no new verdict row exists. (Unit-tested already in SIGMA-26/27; still valid, just not re-demonstrated here.)

## 13. Is SIGMA-28 live Sigma rehearsal ready?

**No — blocked on this proof, which is blocked on data availability, not code.** The code path (`--verdicts-only`, snapshot-skip guard) is proven correct by unit/AST tests from SIGMA-28B. What's missing is a safe racecard input to exercise it against.

---

## Why this is blocked

`load_racecards()` (`src/velo/racecard_loader.py`) has exactly two non-live sources:
- `--source cache` → reads `data/racecards_{date_tag}_standard.json`. **No such file exists for 2026-07-04** (or any date after 2026-06-29 — confirmed via directory listing).
- `--source rp` → reads `data/racecard_merged/racecard_*_{date}.json`. **No such file exists for 2026-07-04 either** (newest available: 2026-06-30).

The only remaining option, `--source api`, requires a **live network fetch**. Per `docs/current/ONE_TRUTH.md`/`CLAUDE.md` hard law #1, "Racing API is PERMANENTLY DECOMMISSIONED for live use. RP HTML is the only live source" — meaning a live run would require live RP HTML scraping, which this sandboxed session cannot reliably perform (no browser/session credentials confirmed available) and which is explicitly the kind of "broad production" run the mission asked me to avoid in favor of a safer source if one didn't exist.

The other candidate — re-running `--verdicts-only` against an **already-cached older date** (e.g. 2026-06-29, the newest local cache file) — was considered and rejected: `persist_race_predictions()` upserts on `race_id` (a stable RP numeric ID, not date-scoped), so re-scoring an already-verdicted date would **overwrite the existing, already-real verdict rows for that day** with a fresh `generated_at` and re-computed scores. Across this entire multi-week SIGMA-2x sequence, the operator has consistently required a separate, explicit authorization before any action that rewrites historical rows (VFU-21 backfill gating, SIGMA-23/24/25's repeated "historical repair is a separate mission" framing). Silently doing that as a side effect of a "proof" mission would contradict that standing pattern, so it was not attempted.

No single-race/test-card fixture path exists in `run_prime_today.py` or `racecard_loader.py` either (confirmed via grep) — there's no narrower safe option between "use stale/real historical data" and "attempt a live fetch."

## Recommended path forward (not executed — proposal only)

1. **Simplest: wait for today's ordinary racecard capture.** Whatever process normally populates `data/racecards_{date_tag}_standard.json` or `data/racecard_merged/` for a live race day (outside this session) will make a safe `--verdicts-only` run possible without touching historical data. No code change needed.
2. **Alternative, if the operator wants to unblock this sooner:** explicitly authorize re-running `--verdicts-only` against a specific already-cached past date (e.g. 2026-06-29), accepting that it will refresh `generated_at` and re-score that day's existing verdict rows. This is a real, visible side effect and should be a deliberate decision, not a default.

---

## Scope note
No Supabase write, no code execution of `run_prime_today.py`, no `run_results_sigma.py` execution, and no ad-hoc Supabase write were performed in this mission. Only read-only preflight checks (Part C) and code/filesystem inspection were done.

## Required Classifications
- PR_110_MERGED
- SIGMA_28C_BLOCKED
- RACE_TYPE_PERSISTED_UNKNOWN — no command run, no new row to check
- RUNNER_SNAPSHOTS_UNTOUCHED
- SIGMA_AUDITS_UNTOUCHED
- NO_LOCAL_RUNNER_SNAPSHOT_FILES
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- NO_HISTORICAL_BACKFILL
- NO_VERDICT_ID_WRITE
- NO_SAFE_RACECARD_SOURCE_AVAILABLE
- SIGMA_28_LIVE_REHEARSAL_NOT_READY — blocked on data availability, not code
- REPORT_ONLY
