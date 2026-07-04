# SIGMA-23 Regression Audit — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | code audit + reuse of SUPA-02's read-only date data | NO WRITES, NO CODE CHANGES

---

## Correction to the mission premise — read this first

The "June 23" framing undersold the problem. Re-examining the full `sigma_audits` by-date breakdown already captured in SUPA-02 (`supa_02_readonly_truth_audit.json`), the actual last date with **any** `pick_sp` coverage is **2026-04-29**. `field_size` last had coverage on **2026-04-25**. `race_type` last had coverage on **2026-05-01**. `verdict_id` last had coverage on **2026-04-23**. Every date from roughly **late April through June 30 — over two months — has zero coverage for all four fields**, not just the June 23-30 window. This is not a new regression on June 23; it is the same, older gap continuing uninterrupted. The June 23-30 zeros you saw in SUPA-02 were the newest instance of a two-month-old flatline, not a fresh break.

## Q1. What exactly broke?

Nothing broke on a specific date in the sense of a code regression. **The live daily writer never wrote these fields at all.** `scripts/ops/run_results_sigma.py` (the LOCKED sigma reconciliation script, upserting to `/sigma_audits` at line 1086) constructs its `sigma_row` payload (lines 1066-1085) with exactly these keys: `race_id, date, track, off_time, event_type, outcome, decision_tier, miss_reason, top_pick_position, actual_winner_id, actual_winner_name, actual_winner_sp, notes`. **`pick_sp`, `field_size`, `race_type`, and `verdict_id` are not in this payload, full stop.** This script has apparently never sent these fields to Supabase.

## Q2. When did it break?

There is no single "break" event in this script's git history to point to — it never had these fields in its write payload during the period examined. The **historical coverage** that did exist (through late April) must have come from a **separate, one-off enrichment/backfill process**, not from this live writer. That separate process appears to have stopped running regularly after late April.

## Q3. Which fields broke?

`pick_sp`, `field_size`, `race_type`, `verdict_id` — all four, for every sigma row created since roughly 2026-04-25/29/01/23 respectively (each field's own last-good date differs slightly, suggesting they were populated by more than one enrichment pass historically, not a single unified process).

## Q4. Which field stayed alive?

`actual_winner_sp` ("winner_sp") — this field **is** in the live writer's payload (line 1078: `"actual_winner_sp": float(row["winner_sp"]) if row["winner_sp"] else None`) and has been continuously populated through 2026-06-30.

## Q5. Which writer path is responsible?

`scripts/ops/run_results_sigma.py` is the only confirmed live writer to `sigma_audits` (via `sb_upsert("/sigma_audits", sigma_row, "race_id")`). No other script in `scripts/ops/` was found calling insert/upsert against `sigma_audits`. For the historically-populated fields: `scripts/ops/vfu_enrich_pick_sp.py` (VFU-03, last touched 2026-06-14) is a **local-only enrichment tool** — it produces local report/data files, not a Supabase write, based on the grep pass in this audit. `scripts/ops/vfu_21_pick_sp_backfill.py` similarly writes only to local ledger files (confirmed in LOCAL-01/REPO-01: `blocked_from_live_use=True`, local-only artifact). **No script found anywhere in the current repo writes `pick_sp`, `field_size`, `race_type`, or `verdict_id` directly to Supabase's `sigma_audits` table.** The historical coverage through April must predate the current script versions, or was written by a since-removed/since-refactored process, or was set by a manual one-off script run outside the current committed code (e.g. a direct SQL backfill).

## Q6. Is this a missing-source problem or a write/join problem?

**Write-path split (`WRITE_PATH_SPLIT`), not a missing-source problem.** `pick_sp` and `field_size` data plainly exist locally — the VFU-21 ledger alone recovers `pick_sp` for 2,633/3,052 rows through mid-June (86.3% local coverage) purely from local result-archive files. The source data is available; there is simply no committed, live code path that takes that recovered value and writes it into Supabase's `sigma_audits` table. This is a governance/pipeline gap, not a data-availability gap.

## Q7. Does VFU-21 fix any part of it?

**Only the historical piece, and only if someone actually runs a write against Supabase using its ledger — which has never happened.** VFU-21's ledger covers rows through ~2026-06-17. It does **not** cover the ~2 weeks after that (June 18-30) at all, and — per this audit's corrected timeline — the true gap actually starts in **late April**, two months earlier than VFU-21 itself acknowledges as its scope ("recovered pick_sp for 2,197 rows missing it in the VFU-20 ledger" — VFU-20/21 were themselves working from an already-narrower slice of the problem). VFU-21 is a partial historical patch, not a fix for the live write path, and not a complete fix even for history.

## Q8. What is the safest repair sequence?

1. **Do not write anything yet.** This audit found no evidence of imminent data loss — the gap has existed for two months already; one more day of review costs nothing.
2. **Decide, as a design question, whether `pick_sp`/`field_size`/`race_type`/`verdict_id` should be written by `run_results_sigma.py` itself** (the natural place, since it already has access to `row` and prediction/result data at write time) **or by a separate scheduled enrichment step**. This is an architecture decision the operator should make explicitly, not something to infer from old code.
3. Only after that design decision, draft the actual code change (adding fields to the `sigma_row` dict, or building a new enrichment job) — as its own reviewed PR, separate from any historical backfill.
4. Separately, decide whether the VFU-21 local ledger should ever be written to Supabase for the pre-existing historical window it covers — a distinct question from fixing the live pipeline.

## Q9. What must not be written yet?

Nothing. No Supabase write, no code change to `run_results_sigma.py`, and no VFU-21 ledger write were performed or drafted as executable code in this audit.

## Q10. What is the next recommended mission?

A **design-only** mission (still report-only) to decide where the four-field write belongs in the pipeline, followed by a small, reviewed code PR — before any historical backfill write is considered. Do not run VFU-21 live until the live-path fix is designed, since writing stale historical values while the live pipeline still doesn't populate new rows would just recreate the same gap on the next race day.

---
## Scope note
Given context/time budget in this pass, Part C's live per-date Supabase re-query and 5-row samples were **not** re-executed — this audit reused the already-captured, already-verified by-date breakdown from SUPA-02 (`data/reports/supa_02_readonly_truth_audit.json`), which is the same underlying data and was itself gathered read-only via the Supabase REST API minutes earlier. No new Supabase connection was made in this pass. `sigma_23_sample_rows.csv` is therefore empty/placeholder — flagged, not fabricated.

## Required Classifications
- SIGMA_23_REGRESSION_AUDIT_COMPLETE
- ACTIVE_PIPELINE_REGRESSION_CONFIRMED — **but corrected: the gap dates to ~2026-04-25/29, not 2026-06-23**
- WINNER_SP_PATH_ALIVE
- PICK_SP_PATH_BROKEN — **write path never existed in current code, not a regression from a working state**
- FIELD_SIZE_PATH_BROKEN — same as above
- RACE_TYPE_PATH_BROKEN — same as above
- VERDICT_LINKAGE_PATH_BROKEN — same as above; no writer found anywhere in the repo
- VFU_21_NOT_SUFFICIENT_FOR_JUNE23_GAP — confirmed, and insufficient for the true (larger, older) gap too
- NO_SUPABASE_WRITES
- REPORT_ONLY
