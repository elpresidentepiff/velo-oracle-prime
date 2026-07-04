# SIGMA-24 — Four-Field Write Contract — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | code-read audit only, no patch applied | NO SUPABASE WRITES

---

## Q1. Where should each of the 4 fields come from?

- **`pick_sp`**: the verdict's own selection record (the horse VÉLØ picked, and its price at selection time) already exists in `velo_verdicts` (via `predictions[race_id]`, the same dict `run_results_sigma.py` already reads to get `decision_tier`) — this is the natural live source. For history, the VFU-21 local ledger (`data/reports/vfu_21_pick_sp_backfill_ledger.jsonl`) recovers it from local result-archive files, but that's a historical-repair source, not a live one.
- **`field_size`**: `scripts/ops/run_prime_today.py` already computes and uses `field_size` at scoring time (line 402, `synthesize_decision(top, second_prob, field_size)`), meaning it exists somewhere in the racecard/prediction data pipeline before `run_results_sigma.py` ever runs. The live source should be the same `predictions[race_id]` dict, if the verdict-writing step (`publish_daily_predictions_to_dashboard.py` / `run_prime_today.py`) persists `field_size` into the verdict record. **Not confirmed whether it's already persisted there** — that's the one open question this audit could not close without deeper tracing (see Q3 below).
- **`race_type`**: same pattern — `run_prime_today.py` already uses `race_type` (line 587, `_attach_bha_or_diff(top, race_type)`) for BHA lookups at scoring time. Same recommendation: source from `predictions[race_id]` if persisted there, else fall back to the local `racecard_merged/racecard_<COURSE>_<DATE>.json` files for that date, which are known to carry race metadata.
- **`verdict_id`**: should be a **join**, not a copied value — `sigma_audits.race_id` + `date` against `velo_verdicts.race_id` + `generated_at::date`, since `race_id` alone risks duplicate verdicts per race (re-runs, corrections). Confirmed in SUPA-02: 363/363 existing `verdict_id` links have zero orphans, so whatever join logic produced those was sound — the question is only why it stopped being applied to newer rows, not whether the join concept works.

## Q2. Should `run_results_sigma.py` be patched directly?

**Recommendation: yes, for `pick_sp`/`field_size`/`race_type` — this is `ADD_PREWRITE_ENRICHMENT` *inside* the existing function, not a new job.** The script already reads `predictions[race_id]` before building `sigma_row` (confirmed: `decision_tier` is pulled from the exact same dict at the exact same point in the loop). Adding three more `.get()` calls to the same dict, with `None` defaults, is a minimal, contained change to a LOCKED file — but "minimal" does not mean "unreviewed." Any patch to this file needs explicit operator sign-off per project doctrine before it's applied, and should ship with the tests listed in Q8/Part B.

## Q3. Should `verdict_id` be linked inline or separately?

**Separately — `ADD_POSTWRITE_RECONCILIATION_JOB`, not inline at insert time.** Linking `verdict_id` requires a query against `velo_verdicts` for a match, which is a different operation profile (a lookup/join) than the other three fields (which are same-dict `.get()` calls the script already has in hand). Doing this as a small, separate reconciliation pass — run after `sigma_audits` rows exist, joining on `race_id`+date — keeps the LOCKED writer's core insert logic untouched and isolates the riskier "which verdict matches which sigma row" decision into its own reviewable step.

## Q4. What is safe for live future rows?

Once approved and tested: the three same-dict fields (`pick_sp`, `field_size`, `race_type`) added to future `sigma_row` writes. `verdict_id` via the separate reconciliation job, running after each day's sigma pass, matching only rows where `race_id`+date has exactly one candidate verdict (ambiguous/duplicate matches should be left `NULL`, not guessed).

## Q5. What is safe for historical repair?

The VFU-21 ledger (`pick_sp` only, ~86.3% coverage, covering through roughly mid-June) is the only artifact with real recovered values ready to review — but per SUPA-02/SIGMA-23, the true gap starts **2026-04-23/29**, meaning VFU-21 doesn't even cover the full historical window; a separate backfill covering **late April through the VFU-21 start point** would be needed before any full historical repair is complete. No local artifact currently covers `field_size`, `race_type`, or `verdict_id` historically at scale — those would need to be reconstructed from `racecard_merged/` archives and the verdict-join logic respectively, as new work, not a simple ledger write.

## Q6. What must not be written yet?

Nothing. No Supabase write, no patch to `run_results_sigma.py`, no VFU-21 ledger write, no new reconciliation job code were performed or drafted as executable code in this audit — this is a design document only.

## Q7. What is the next mission?

**A code-patch mission for `run_results_sigma.py`'s live write payload (pick_sp/field_size/race_type only), gated on operator sign-off since it touches the LOCKED script, shipped together with the 7 tests in Part B/Q8.** The `verdict_id` reconciliation job and any historical backfill (VFU-21 write, or the newer April 23-29 gap) should each be their own separate, later missions — not bundled into the first patch.

---
## Scope limitation
This audit did not trace end-to-end whether `field_size`/`race_type` are actually persisted inside `velo_verdicts`/`predictions[race_id]` today, versus only existing transiently in `run_prime_today.py`'s in-memory scoring state. That trace (checking `publish_daily_predictions_to_dashboard.py`'s verdict-write payload for these two keys) is the concrete first task of the next mission, before any patch is drafted — flagged here rather than assumed.

## Required Classifications
- SIGMA_24_FIELD_WRITE_CONTRACT_COMPLETE
- NO_SUPABASE_WRITES
- NO_CODE_CHANGE
- LOCKED_SIGMA_WRITER_NOT_PATCHED
- PICK_SP_SOURCE_IDENTIFIED — `predictions[race_id]` (verdict selection record) for live; VFU-21 ledger for partial history
- FIELD_SIZE_SOURCE_IDENTIFIED (tentative) — likely `predictions[race_id]`, persistence not yet confirmed
- RACE_TYPE_SOURCE_IDENTIFIED (tentative) — likely `predictions[race_id]` or `racecard_merged/`, persistence not yet confirmed
- VERDICT_ID_SOURCE_IDENTIFIED — race_id + date join against `velo_verdicts`, as a separate reconciliation job
- WRITE_ARCHITECTURE_RECOMMENDED — `ADD_PREWRITE_ENRICHMENT` (3 fields, inline) + `ADD_POSTWRITE_RECONCILIATION_JOB` (verdict_id) — a `SPLIT_LIVE_AND_HISTORICAL_REPAIR` for the backfill question
- SUPABASE_WRITE_APPROVAL_REQUIRED
- REPORT_ONLY
