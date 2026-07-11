# July 5 2026 — Pipeline Fixes — Operator Brief

Three real pipeline bugs were found and fixed live while running the 2026-07-05 raceday, not pre-planned defects.

## Fix 1 — PR #122: Southwell AW venue classification (merged, `1158dfa`)
- **Symptom:** Live index capture found only 14 UK/IRE races (Ayr + Market Rasen); Southwell AW's 8 races were absent.
- **Root cause:** `southwell-aw` slug missing from the hardcoded `UK_IRE_VENUES` set in `build_racing_post_racecard_url_list.py`. Its all-weather siblings `newcastle-aw` and `kempton-aw` were already present — `southwell-aw` was simply never added when Southwell's AW fixture type was introduced.
- **Fix:** One-line addition + regression test (`tests/test_racecard_url_list_venue_classification.py`).
- **Result:** 22 UK/IRE races across all 3 courses.

## Fix 2 — PR #123: PDF-intel merge preserving race_id (merged, `fcce9e1`)
- **Symptom:** After running the operator-supplied PDF ratings through `ingest_racecard_pdfs.py`, scoring showed synthetic race_ids (`rp_AYR_20260705_2.11`), RPDC sidecar coverage read 0/22 (despite RPDC itself being correctly built), and the racecard cache gate's metadata check failed at 23.5% (silently downgraded to a pass via an `[OVERRIDE]` path).
- **Root cause:** Two independent scripts write to the exact same output path (`data/racecard_merged/racecard_{VENUE}_{date}.json`):
  - `build_racecard_merged_from_injection.py` — real `race_id` from the live RP capture, PDF fields left at `0.0` placeholders (no PDF access)
  - `ingest_racecard_pdfs.py` — real PDF-derived fields, but a from-scratch structure with no `race_id` at all (races keyed by time only)
  Running either after the other silently destroys the other's contribution. Neither script merges into the other's existing output.
- **Fix:** New `scripts/ops/merge_pdf_intel_into_racecard_merged.py` — parses the PDFs via `ingest_racecard_pdfs.py`'s own parser functions, then splices only the PDF-derived per-horse fields onto the injection-based file by horse-name match, leaving `race_id`/`race_info`/runner membership untouched. Regression test: `tests/test_merge_pdf_intel_preserves_race_id.py`.
- **Result:** ~90% PDF coverage (Ayr 85.5%, Market Rasen 96.5%, Southwell AW 87.8%), real race_ids preserved throughout, cache gate PASS cleanly, RPDC 22/22.

## Fix 3 — PR #124: race_type extraction (open, not yet merged)
- **Symptom:** Found during this mission's Part C verification — `velo_verdicts.race_type` was null for all 22 races even after PR #123's fix.
- **Root cause:** `load_rp_merged_as_racecards()` extracted `going` and `race_class` from `race_info` but never `race_type`, despite `build_racecard_merged_from_injection.py` writing it into `race_info` and the live injection always carrying a real value. A first attempted fix used the wrong dict key (`race_type` instead of the `type` key that `run_prime_today.py`/`velo_prime_service._build_race_type_fields` actually read — matching the standard-cache convention set by `parse_racing_post_racecard_capture.py`).
- **Fix:** Extract `race_type` from `race_info`, write under the `type` key. Regression test added to `tests/test_racecard_loader.py`.
- **Result:** `race_type` 22/22, real values (`chase`/`hurdle`/`flat`).

## Operational hygiene finding (disclosed, not a PR)
While diagnosing Fix 3, found the operational (dirty) repo's `app/services/velo_prime_service.py` and `scripts/ops/run_prime_today.py` were stale relative to `main` — missing already-merged SIGMA-26 (race_type persistence) and SIGMA-28B (`--verdicts-only`) code entirely. Synced both files from the clean worktree/`main` (no new code — already-reviewed, already-merged content). Did **not** touch ~20 other files with large diffs (backtest harness, feature engineering, model loader/registry) — those look like legitimate in-progress local-only work, not staleness, and require your explicit decision before any sync.

## Doctrine takeaway
**Identity truth beats feature enrichment.** PDF intelligence, ratings, and other enrichment sources must be an overlay onto identity-preserving data (real `race_id`/`horse_id` from the live RP capture), never a replacement source that can silently destroy that identity. All three of today's fixes trace back to this one principle.
