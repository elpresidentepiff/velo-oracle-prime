# SIGMA-28A — Race Type Persistence Proof — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | code-read + read-only Supabase check | NO WRITES PERFORMED

---

## Outcome: PATCH_BLOCKED_FOR_SAFE_VERDICT_PROOF

No safe, isolated path exists to produce a post-PR107 `velo_verdicts` row without also triggering a write this mission explicitly forbids. Stopping here per the mission's own instruction ("If no safe verdict persistence path exists without live scoring side effects, STOP and report PATCH_BLOCKED_FOR_SAFE_VERDICT_PROOF") rather than forcing a workaround.

## 1. Did PR #108 merge?

Yes. Merge commit `99e427ef1823f558b1523e3890dbd662b2b59d1a`. `origin/main` advanced `22dba21 → 99e427e`. CI was confirmed green on head `68ddc33` before merging.

## 2. Was a post-PR107 verdict row produced or found?

No. A read-only check (`SELECT race_id,generated_at,race_type,race_type_raw,race_type_source,race_type_recorded_at,predicted_field_size,top_rank_horse_id FROM velo_verdicts WHERE generated_at > '2026-07-04T00:00:00' ORDER BY generated_at DESC LIMIT 20`) returned **0 rows**. Nobody — operator, cron, or this session — has run the live scoring pipeline with the merged code yet today.

## 3-6. race_type / race_type_raw / race_type_source / race_type_recorded_at persisted?

Not applicable — no row exists to check. This is not a code defect; it's simply that the proof-generating event (one live scoring pass) has not happened.

## 7-8. predicted_field_size / full_analysis remained present?

Not applicable for the same reason.

## 9. Was sigma_audits untouched?

Yes — confirmed by inaction. No script that writes `sigma_audits` was run in this mission. Only read-only `SELECT` calls were made (one to check for post-merge verdicts).

## 10. Is SIGMA-28 live-write rehearsal ready?

**No — blocked on this proof, and this proof is blocked on a safe way to generate one ordinary verdict row.** See "Why this is blocked" below.

---

## Why this is blocked

The only real call site for `persist_race_predictions()` (the function that writes `velo_verdicts`, including the new `race_type` fields from PR #107) anywhere in this repo is `scripts/ops/run_prime_today.py::main()` (confirmed via repo-wide grep — the only other match, in `scripts/audit/audit_vp30_lineage.py:152`, is a string literal in an audit proof list, not a real call).

Running that `main()` to get one ordinary verdict row entangles the desired write with a write this mission explicitly forbids:

- `persistence_enabled` (derived from `not args.dry_run`) is a single flag that gates **both**:
  - `persist_race_predictions(...)` — the write we want (STEP 4)
  - `_write_runner_snapshots(..., supabase_client=db if persistence_enabled else None, ...)` — an **unconditional write to `runner_prediction_snapshots`** whenever any race scores (line ~2390-2397 of `run_prime_today.py`)
- Setting `--dry-run` to avoid the snapshot write also disables `persist_race_predictions` (`persistence_enabled = not args.dry_run` controls both) — so there is no flag combination that writes verdicts without also writing snapshots.
- The mission's forbidden list explicitly includes "Do not write runner_prediction_snapshots," and separately forbids faking/ad-hoc-inserting a Supabase row directly (which would be the only other way to get a `race_type`-bearing row without going through the real pipeline).

Telegram is a non-issue here — `tg()` in `run_prime_today.py` already routes through `_legacy_tg()`, which is a permanent no-op ("CONTAINMENT NO-OP", never sends) regardless of `--notify`. `pipeline_runs` logging (an ordinary run-status insert) is not itself a concern. The blocker is specifically the `runner_prediction_snapshots` coupling.

## Recommended path forward (not executed — proposal only)

A small, reviewed decoupling patch to `run_prime_today.py` — an independent `--skip-runner-snapshots` flag (or splitting `persistence_enabled` into two flags: one for verdict persistence, one for snapshot writes) — would let a future mission produce exactly one ordinary verdict row without the entangled forbidden write. This is a proposal for operator review, not something drafted or applied in this REPORT_ONLY mission.

Alternatively, the operator could simply let the **next normal, already-scheduled live race-day run** happen on its own (no special action needed) and a future SIGMA-28B could re-run this same read-only check afterward — no code change required, just patience for the next ordinary operational cycle.

---

## Scope note
No Supabase write, no sigma_audits write, no runner_prediction_snapshots write, no verdict_id write, no Telegram send, no model training, and no ad-hoc/manual Supabase INSERT were performed or drafted as executable code in this mission. Exactly one read-only SELECT was issued to check for a post-merge verdict row.

## Required Classifications
- PR_108_MERGED
- SIGMA_28A_RACE_TYPE_PERSISTENCE_PROOF_INCOMPLETE
- PATCH_BLOCKED_FOR_SAFE_VERDICT_PROOF
- RACE_TYPE_PERSISTED_UNKNOWN — no post-merge row exists to check
- NO_SIGMA_AUDITS_WRITE
- NO_RUNNER_SNAPSHOT_WRITE
- NO_HISTORICAL_BACKFILL
- NO_VERDICT_ID_WRITE
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- NO_AD_HOC_SUPABASE_INSERT
- SIGMA_28_NOT_READY
- REPORT_ONLY
