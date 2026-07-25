# July 07 — Sigma Input Audit (Task 1)
Generated: 2026-07-07T21:45:00Z | Mission: JULY07-OFFICIAL-SIGMA-AND-FULL-LEARNING

## Verdict source confirmed
- Supabase `velo_verdicts` (matched via `race_id LIKE '%20260707%'`): **35 rows, 35 unique race_ids**.
- Local `data/velo_prime_verdicts_2026_07_07.json`: **35 rows**.
- Supabase ↔ local race_id sets: **identical (35/35 match, 0 supabase-only, 0 local-only)**.
- `predicted_field_size` summed across all 35 Supabase rows: **289** — matches the
  `runners_processed: 289` figure in `velo_daily_run_truth_2026_07_07.md` exactly.

## Race count / runner count
- Expected race count: 35 — **actual: 35 — MATCH**.
- Expected runner count: 289 — **actual (sum of predicted_field_size): 289 — MATCH**.

## RP results capture
- Capture directory: `data/racing_post_account_raw/rp-results-2026-07-07/`
- HTML pages captured: **35/35**, all `http_status: 200`, all titled `Full Result ... | 7 July 2026 | Racing Post` (confirmed real result pages, not login walls).
- Captured across two passes (batch dedup via `manifest.json` against already-PASS URLs) using the existing saved browser profile (`data/browser_profiles/racing_post_account`, headless Chromium).
- Courses: Tramore (IRE, 7 races), Pontefract (7), Wolverhampton AW (8), Brighton (6), Uttoxeter (7).

## Verdict — inputs ready
This is the normal live route, not a runtime-fallback day: Supabase `velo_verdicts` has a full, matched 35-row set for 2026-07-07, and RP result pages are now fully captured.

## Classification
`JULY07_INPUTS_READY_FOR_OFFICIAL_SIGMA`
