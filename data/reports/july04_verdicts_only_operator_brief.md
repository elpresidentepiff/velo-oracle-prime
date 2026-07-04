# July 4 2026 — Controlled Verdicts-Only Persistence — Operator Brief
Generated: 2026-07-04 | ONE AUTHORISED SUPABASE WRITE PERFORMED (public.velo_verdicts only) | NO OTHER TABLES TOUCHED

---

## 1. Was PR #115 merged?

Yes. Merge commit `a70caa40eedae6a25347751b6edf9097601ddd62`. `origin/main` advanced `2a6dc87 → a70caa4`.

## 2. What command ran?

```
PYTHONPATH=. venv/bin/python scripts/ops/run_prime_today.py \
  --date 2026-07-04 \
  --source cache \
  --verdicts-only \
  --no-runner-snapshots \
  --no-notify
```

Run from the clean worktree (`/mnt/c/Users/puror/velo-oracle-prime-clean-data01`) using the merged PR #110/114 code, with Supabase credentials sourced inline from the dirty repo's `.env` into the shell environment for this one invocation only — the `.env` file itself was never copied, per the explicit prohibition.

## 3. Was this the only non-dry-run command?

Yes — the only command executed in this mission that could write to Supabase.

## 4. Did velo_verdicts receive new rows?

Yes — **51 new rows**, one per race, `generated_at` between the run's start and finish on 2026-07-04. Confirmed via read-only `SELECT` against `/rest/v1/velo_verdicts?generated_at=gt.2026-07-04T00:00:00`.

## 5. How many rows/races?

51/51 — every race in today's card.

## 6. Did race_type persist?

**Yes — 51/51 (100%).** This is the first production confirmation that the SIGMA-26 `_build_race_type_fields()` patch actually works end-to-end: sample row shows `race_type: "flat"`, `race_type_raw: "Flat"`, `race_type_source: "scoring_race_dict"`, `race_type_recorded_at` populated with a real timestamp.

## 7. Did predicted_field_size persist?

Yes — 51/51 (100%).

## 8. Did full_analysis persist?

Yes — 51/51 (100%), including nested `predictions`, `plot_intel`, and `governance` blocks.

## 9. Did top_rank_horse_id persist?

Yes — 51/51 (100%), all real RP horse UIDs.

## 10. Did runner_prediction_snapshots remain unchanged?

Yes — 0 rows before, 0 rows after. `--no-runner-snapshots` correctly skipped the writer call entirely (confirmed via `runner_snapshots : 0.000s` in the timing summary — zero time spent, not just a suppressed argument).

## 11. Did sigma_audits remain unchanged?

Yes — 0 rows before, 0 rows after. `run_results_sigma.py` was never invoked; a separate pure-function dry-read (Part F) confirmed extraction correctness without writing anything.

## 12. Were local runner snapshot files avoided?

Yes — 116 files before, 116 after.

## 13. Was Telegram silent?

Yes — every message in STEP 5 is logged with a `[CONTAINMENT NO-OP] TG:` prefix; `_legacy_tg()` never performs a real network send.

## 14. Did any model training/promotion occur?

No — nothing in this run touches model training or promotion code paths.

## 15. Is SIGMA-29 live Sigma rehearsal ready?

**Yes, on the data side.** All three previously-blocked fields (`pick_sp`, `field_size`, `race_type`) are now confirmed both persisted in `velo_verdicts` AND correctly extractable by the pure Sigma helpers (51/51 each in the dry-read). `verdict_id` remains correctly excluded from every dry-built sigma row. The only remaining open item before an actual `run_results_sigma.py` write is operator sign-off to run the LOCKED script itself — nothing else is blocking on the data or code side.

---

## Additional findings (disclosed, not requested but relevant)

- **RPDC coverage was 0/51 this run** — the RPDC local-memory cache was not part of the operator-approved data copy list (only the standard racecard cache and passport bank were copied), so `resolve_runner_rpdc()` found no candidates for any race. This means today's verdicts lack RPDC-derived tags/scores. This does not affect the fields this mission was authorised to verify (`race_type`, `predicted_field_size`, `full_analysis`, `top_rank_horse_id`), but is worth knowing if RPDC-driven signals matter for how these verdicts get used downstream.
- **The dashboard auto-refreshed with materially better data this time.** Because `velo_verdicts` now has real rows, `publish_daily_predictions_to_dashboard.py` (auto-invoked by `run_prime_today.py`'s PASS branch) used `source=supabase+local_json` (51 races loaded from Supabase) instead of the earlier dry-run's `local_json_top_only` fallback. The refreshed dashboard JSON now shows real per-runner `decision_tier` values (A/B/C/D/X, not the earlier placeholder `"?"`) and real `horse_id` for all 453 runners. `sp`/`odds`/`bsp` remain null — a pre-existing, documented gap in the publisher (`_NULL_FIELDS`), not something this run could fix.
- **`data/new_build/passports/horse_passports_v1.jsonl` is git-tracked**, and the dirty repo's copy (used for this run) differs from what's committed on `origin/main` (9,634,377 bytes vs 9,553,714 committed — the passport bank has grown since the last commit). This file now sits modified in the clean worktree's working tree. It was **not staged or committed** in this mission — only the 6 report files listed below were added.

---

## Required Classifications
- PR_115_MERGED
- DATA_COPY_APPROVED_BY_OPERATOR
- DATA_INPUTS_COPIED_TO_CLEAN_WORKTREE
- NO_CODE_COPIED
- NO_FORBIDDEN_FILES_COPIED
- JULY04_VERDICTS_ONLY_PERSISTENCE_COMPLETE
- VELO_VERDICTS_WRITE_AUTHORISED_AND_EXECUTED
- NO_MANUAL_SUPABASE_WRITE
- NO_SIGMA_AUDITS_WRITE
- NO_RUNNER_PREDICTION_SNAPSHOT_WRITE
- NO_LOCAL_RUNNER_SNAPSHOT_FILES
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- NO_HISTORICAL_BACKFILL
- RACE_TYPE_PERSISTENCE_VERIFIED (51/51)
- PREDICTED_FIELD_SIZE_PERSISTENCE_VERIFIED (51/51)
- FULL_ANALYSIS_PERSISTENCE_VERIFIED (51/51)
- SIGMA_HELPER_DRYREAD_COMPLETE (pick_sp 51/51, field_size 51/51, race_type 51/51, verdict_id excluded)
- SIGMA_29_DATA_READY — pending operator sign-off on running the LOCKED script itself
- REPORT_ONLY_AFTER_AUTHORISED_VERDICT_WRITE
