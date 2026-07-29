# SUPA-02 — Read-Only Supabase Truth Map — Operator Brief
Generated: 2026-07-04 | SELECT-only audit via Supabase REST API (direct Postgres port unreachable from this sandbox — used PostgREST instead) | NO WRITES PERFORMED

---

## Q1. What is clean in Supabase?

- **`sigma_audits` win/place/miss counts, row counts, and date range** match the prior LOCAL-01 findings exactly (3,167 rows, 717 WIN, 893 PLACED, 1,520 MISS, 857 `mid_priced_won`) — internally consistent, not corrupted.
- **`sigma_audits.verdict_id` linkage has zero orphans**: all 363 rows that carry a `verdict_id` join cleanly to an existing `velo_verdicts` row. The linkage gap is a coverage problem (only 11.46% of sigma rows have a `verdict_id` at all), not a data-integrity problem.
- **`velo_verdicts` is current**: `generated_at` runs through 2026-07-01T03:52 — verdicts are still being written daily.
- **`course_profiles`**: surface and country are 100% populated (70/70).

## Q2. What is dirty or incomplete?

- **`sigma_audits` price/context fields collapse to zero for the most recent ~2 weeks.** Every date bucket from 2026-06-23 through 2026-06-30 shows `pick_sp_known = 0`, `field_size_known = 0`, `race_type_known = 0`, `verdict_id_known = 0` — while `winner_sp_known` stays populated. This is sharper than the earlier "38% overall coverage" framing: **coverage isn't declining, it's flatlined at zero for the newest data.** Something in the write path stopped populating these four fields specifically, starting around June 23.
- **`historical_feature_store`**: `training_safe` is `false` for all 31,936 rows, and `leakage_status`/`feature_status` are 100% null. Not a partial gap — nothing has ever been labeled.
- **`runner_prediction_snapshots`** stops at `2026-06-19`, while `velo_verdicts` continues to `2026-07-01` — a 12-day gap with no snapshot data.
- **`course_profiles.handedness`**: 0/70 known.
- **`raceform`**: 1.38M rows, date range 2017-01-01 to 2025-07-05. Field-level coverage counts (`draw`, `sp`, `rpr`, `or_rating`) could not be obtained in this pass — count queries against this table returned server errors (likely a timeout on an unindexed filter across 1.38M rows), not a data problem. Flagged as unresolved, not silently skipped.

## Q3. Is VFU-21 still needed?

Yes, and more urgently than previously framed. The VFU-21 ledger (`data/reports/vfu_21_pick_sp_backfill_ledger.jsonl`, already on GitHub) recovers pick_sp for rows through **2026-06-17** — it does not cover the newer June 23-30 rows that now show zero coverage. Two separate problems exist: (1) the pre-existing historical gap VFU-21 was built to fix, and (2) a **new, currently-active** gap in the live write path that VFU-21 was never designed to address.

## Q4. Is VFU-21 safe to write now?

**No — not approved in this pass.** This audit is SELECT-only by design; no write was performed or drafted as executable SQL. Beyond the mode restriction, the VFU-21 ledger's own EW ROI on recovered rows is -12.5%, meaning "repairing coverage" and "trusting the recovered price for staking" remain two separate decisions, as flagged in LOCAL-01/REPO-01.

## Q5. What exact write would be proposed later, if approved?

A conditional `UPDATE sigma_audits SET pick_sp = <ledger value> WHERE id = <matched row> AND pick_sp IS NULL`, scoped only to rows present in the VFU-21 ledger with a confirmed join key (race_id + date, pending confirmation the ledger carries a stable key that maps to `sigma_audits.id` or `race_id`). Nothing more than that single field, on that specific row set. This is a proposal for future design, not a query drafted or run in this pass.

## Q6. What must not be written?

Nothing was written. If a future write is approved: no touching `verdict_id`, no touching `training_safe`/`leakage_status`/`feature_status` without a defined labeling methodology (a data copy alone would be fabricating a training-safety judgment, not repairing one), and no bulk `runner_prediction_snapshots` backfill without first diagnosing why the snapshot pipeline stopped on 2026-06-19.

## Q7. Is training still blocked?

**Yes.** `historical_feature_store.training_safe` is `false` for all 31,936 rows with zero `leakage_status`/`feature_status` labeling. No model training or promotion is possible against this table in its current state, independent of any Supabase write question.

## Q8. Is COURSE-01 still blocked?

**Yes.** `course_profiles.handedness` remains 0/70 known, matching the LOCAL-01/REPO-01 finding — no change since that audit.

## Q9. Is `runner_prediction_snapshots` stale?

**Yes, confirmed: 26,425 rows across 1,360 races, `created_at` range 2026-05-20 to 2026-06-19.** Verdicts continue 12 days past the last snapshot — the freshness gap is real and unresolved.

## Q10. What is the safest next action?

1. **Diagnose the June 23 sigma coverage collapse first** — this is new information from this audit, not previously flagged, and looks like an active pipeline regression rather than historical debt. Find what changed in the write path around that date before touching anything else.
2. Design (don't yet execute) the VFU-21 join-key strategy for the pre-existing gap.
3. Diagnose the `runner_prediction_snapshots` pipeline stall.
4. Leave `historical_feature_store` and `course_profiles.handedness` as documented open gaps requiring new data/methodology, not a database write.

---

## Required Classifications
- SUPA_02_READONLY_COMPLETE
- NO_SUPABASE_WRITES
- PRICE_TRUTH_STATUS: **DEGRADED — RECENT RUNS AT ZERO COVERAGE (2026-06-23 onward)**
- SIGMA_VERDICT_LINKAGE_STATUS: **WEAK COVERAGE (11.46%), ZERO ORPHANS IN EXISTING LINKS**
- HFS_TRAINING_GATE_STATUS: **BLOCKED — 0% training_safe / 0% labeled**
- COURSE_PROFILE_STATUS: **HANDEDNESS BLOCKED (0/70), SURFACE/COUNTRY COMPLETE**
- RUNNER_SNAPSHOT_STATUS: **STALE (12+ days behind verdicts)**
- VFU_21_REPAIR_STATUS: **NEEDED BUT NOT SUFFICIENT — covers only through 2026-06-17, new gap exists beyond it**
- SUPABASE_WRITE_APPROVAL_REQUIRED: **YES — no write performed or approved in this pass**

## Final Classifications
SUPA_02_READONLY_COMPLETE
NO_SUPABASE_WRITES
NO_INSERT
NO_UPDATE
NO_DELETE
NO_ALTER
NO_DROP
NO_TRUNCATE
NO_TELEGRAM_SEND
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
REPORT_ONLY

---
## Methodology note
Direct Postgres connection (`SUPABASE_DB_URL`) was unreachable from this sandbox (IPv6 network egress blocked). Fell back to the Supabase REST API (PostgREST) via `supabase-py` with SELECT-only calls — no INSERT/UPDATE/DELETE/RPC-mutation calls were made. Per-course `raceform` breakdown and a full `velo_verdicts.top_horse` coverage count could not be completed in this pass (query errors/budget) — flagged as open, not fabricated.
