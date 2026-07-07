# July 5 2026 — Raceday State — Operator Brief
Generated: 2026-07-05 | PRE-SIGMA STATE LOCK

---

## 1. What was the final July 05 raceday state?
Fully scored and persisted, clean gate PASS, real identity throughout: `RACEDAY_SCORED_AND_PERSISTED`. Sigma not yet run (pending tonight's results, per standard doctrine).

## 2. How many races/courses/runners?
22 races, 3 courses (Ayr, Market Rasen, Southwell AW), 193 runners.

## 3. Did Southwell AW appear correctly?
Yes, after PR #122. Before the fix, the RP index capture found 14 UK/IRE races (Ayr + Market Rasen only); Southwell AW's 8 races were misclassified as international and silently dropped. After the fix: 22 UK/IRE races across all 3 supplied courses.

## 4. What did PR #122 fix?
Added `southwell-aw` to the hardcoded `UK_IRE_VENUES` allowlist in `build_racing_post_racecard_url_list.py` (its siblings `newcastle-aw`/`kempton-aw` were already present; `southwell-aw` was simply never added). One-line fix + regression test. Merged: commit `1158dfa`.

## 5. What did PR #123 fix?
The deeper structural gap: `build_racecard_merged_from_injection.py` (real race_id, PDF fields at 0.0 placeholders) and `ingest_racecard_pdfs.py` (real PDF fields, no race_id at all) both write to the same output path (`data/racecard_merged/racecard_{VENUE}_{date}.json`) and clobber each other — there was no script that merged them. Added `merge_pdf_intel_into_racecard_merged.py`, which splices PDF-derived fields into the injection-based file by horse-name match, preserving `race_id`/`race_info`/runner membership. Merged: commit `fcce9e1`.

## 6. Did real race_ids survive PDF merge?
Yes, confirmed both before persistence (dry-run scoring showed real numeric race_ids like `922291`) and after (Supabase `velo_verdicts.race_id` sample: `921918`, `921920`, `921916`, etc. — all numeric, 22/22).

## 7. Did synthetic race_ids appear anywhere after fix?
No. Before PR #123's fix, scoring fell back to synthetic IDs (`rp_AYR_20260705_2.11` style). After the fix, 22/22 verdicts carry real numeric RP race_ids.

## 8. What was PDF-intel coverage?
Ayr: 53/62 horses (85.5%). Market Rasen: 55/57 (96.5%). Southwell AW: 65/74 (87.8%). Overall ~90% (173/193).

## 9. What was RPDC coverage?
193/193 runners, 22/22 races. `check_rpdc_integrity.py` reports `RPDC_OK` for all 22 races (previously `RPDC_UNKNOWN`-equivalent 0/22 false-negative before the PDF-merge fix, due to the race_id mismatch, not missing RPDC — RPDC itself was correctly built at Stage 4 the whole time).

## 10. Did cache gate pass cleanly?
Yes, after both fixes. Before: `[FAIL] metadata_coverage: 43/183 (23.5%)`, silently downgraded via an `[OVERRIDE]` path rather than genuinely passing. After: clean `RACECARD CACHE GATE — PASS`, `metadata_coverage: 193/193 (100.0%)`, `sidecar_date_match: RPDC covers 22/22 (100%)`.

## 11. Were 22 verdicts persisted?
Yes. `velo_verdicts`: 22/22 races. Field coverage: `race_type` 22/22 (see PR #124 below — this required a third fix), `predicted_field_size` 22/22, `full_analysis` 22/22, `top_rank_horse_id` 22/22, `rpdc_primary_tag` 22/22.

## 12. Was dashboard published?
Yes, from live Supabase (`SOURCE USED: supabase+local_json`, `supabase:22_rows_loaded`), 22 races / 193 runners published to `data/dashboard_daily_predictions_2026_07_05.json`.

## 13. Was Sigma run?
No. `sigma_audits` rows for 2026-07-05: 0. Pending tonight after results.

## 14. Was Telegram sent?
No. Scoring ran with `--no-notify`. No sigma Telegram report (Sigma not yet run).

## 15. Was learning/promotion touched?
No. No `nightly_eod_learning_runner.py`, no `run_results_sigma.py`, no model training, no promotion decision.

## 16. What is pending tonight?
Standard post-race chain once results are available: capture results → parse → Sigma → horse-run ingest → Mission Control → VP30 → Council → Execution Bridge shadow → Innovation Protocol → Router audit → Nightly EOD shadow learning.

---

## A third fix found and disclosed during this mission (not part of the original 2-PR scope)

While verifying `race_type` coverage during Part C of this mission, found it was null for all 22 races even after PR #123's merge. Root cause: `load_rp_merged_as_racecards()` in `src/velo/racecard_loader.py` never extracted `race_type` from `race_info` (only `going`/`race_class`), and a first attempted fix used the wrong dict key (`race_type` instead of the `type` key that downstream code actually reads, matching the standard-cache convention). Fixed properly, tested, and **opened as PR #124** — not merged yet, awaiting your review separately from #122/#123.

**Also disclosed, not fixed**: while chasing this, found the operational (dirty) repo's `app/services/velo_prime_service.py` and `scripts/ops/run_prime_today.py` were stale relative to `main` — missing the already-merged SIGMA-26 race_type persistence code and SIGMA-28B `--verdicts-only` feature. Synced both files from `main` (already-merged content, no new code) to get today's scoring correct — this is disclosed as an operational-hygiene finding, not something requiring a PR (no new code was introduced, just re-syncing a file that had drifted out of date). Found ~20 other files with large diffs between the dirty repo and main (backtest harness, feature engineering, model loader/registry) that were **not touched** — they look like legitimate in-progress local work, not staleness, and untangling that is a separate decision for you.

## Classifications
PR_122_MERGED · PR_123_MERGED · PR_124_OPEN_AWAITING_REVIEW · JULY05_RACEDAY_SCORED_AND_PERSISTED · SOUTHWELL_AW_CLASSIFICATION_FIXED · PDF_INTEL_MERGE_PRESERVES_RACE_ID · RACE_TYPE_EXTRACTION_FIXED · REAL_RACE_IDS_VERIFIED · REAL_HORSE_IDS_VERIFIED · RPDC_COVERAGE_VERIFIED · DASHBOARD_PUBLISHED · SIGMA_PENDING_NOT_RUN · DIRTY_REPO_CODE_DRIFT_DISCLOSED
