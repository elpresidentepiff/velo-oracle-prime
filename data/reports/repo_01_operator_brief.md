# REPO-01 — GitHub Main Reconciliation Plan — Operator Brief
Generated: 2026-07-03 | Branch analyzed: `audit/local-01-truth-reconciliation` vs `origin/main` (018d618)
REPORT_ONLY. No merge. No push to main. No delete. No Supabase write. No Telegram.

---

## The headline finding you need first

The "7 commits ahead" framing undersells the size of this diff. **One single commit — `8753b4f` ("chore(data): raceday 2026-06-29 sigma + learning + June 30 prep") — accounts for 474 of the 555 changed files and the overwhelming majority of the 470,571 inserted lines.** It is a bulk backfill of ~3 weeks of daily operational data (2026-06-09 through 2026-06-29) that had been generated locally but never committed, swept into one commit right before the VCP work started. The other 6 commits combined only touch 82 files, and most of those are the 34 pure doc-renames from the archive sweep.

So the real question isn't "should we merge 7 commits" — it's **"should this 3-week data backlog go to GitHub at all, and if so, how."**

## Q1-3. Compare + classify (see CSVs for full detail)

555 files changed between `origin/main` and the audit branch:
- **474 files** (85%) = `8753b4f`'s bulk daily-data backfill (`data/reports/`, `data/sigma_results/`, `data/learning_inputs/`, `data/sigma_memory/`, `data/mission_control/`, `data/council_*/`, `data/timing_audit/`, `data/race_shape/`, dated racecards, etc.) — mostly `NEEDS_OPERATOR_REVIEW` / `SPLIT_TO_DATA_ARCHIVE`, with 4 clear `DELETE_CANDIDATE` files buried inside it.
- **55 files** = `e5b259b` (VCP-00 + A-3 fix + docs archive). Of these, 51 are the pure `R100` doc renames (`docs/current/*.md` → `docs/archive/*.md`) — safe, mechanical, `MERGE_TO_MAIN`. The remaining 4 (`CLAUDE.md`, `README.md`, `docs/current/ONE_TRUTH.md`, `scripts/ops/new_build_two_lane_score.py` + its test) are the real going_code fix and doc updates — `MERGE_TO_MAIN`.
- **9 files** (VCP-01/VCP-02/VCP-03 code + reports + task contracts) = `MERGE_TO_MAIN`.
- **9 files** = LOCAL-01 report commit (`b0c354f`) — `MERGE_TO_MAIN` (that is the entire point of this reconciliation).
- **2 files** = dashboard fix (`ede88e6`, `app/main.py` + `publish_daily_predictions_to_dashboard.py`) — small, clean, `MERGE_TO_MAIN`.
- **4 files** (buried inside the 8753b4f bulk commit) = `data/_check_passport_coverage.py`, `data/_check_supabase_jun24.py`, `data/_multimodel_june23_tmp.json`, `data/_tmp_fetch.py` — one-off debug scratch scripts accidentally committed **inside `data/`** (wrong location by convention — scripts belong in `scripts/`), hardcoded to an absolute Windows path (`C:\Users\puror\velo-oracle-prime`), not reusable. **`DO_NOT_MERGE` / `DELETE_CANDIDATE`.** Not a secrets risk — they read credentials via `os.getenv()` correctly — but they are disposable debug junk in the wrong place.
- **4 files** = `models/*/feature_importance.csv` — small (52-76 line diffs each), routine model artifact drift, low risk — `NEEDS_OPERATOR_REVIEW` only because model-artifact history on main deserves an explicit yes, not a default merge.

## Q4. Dangerous files inside the 6 commits

Checked for: temp scripts, raw generated data, secrets, stale reports, large binary outputs.
- **Temp scripts:** the 4 named above. Confirmed disposable, not dangerous to run, just don't belong in a merge.
- **Secrets:** ran a pattern scan (`api_key`, `secret`, `password`, `token`, `BEGIN PRIVATE`, `service_role`, `sk-ant`, `sk-proj`, `AKIA`) across the entire diff. **No literal key/token values found.** All hits are either `os.getenv("SUPABASE_SERVICE_ROLE_KEY")`-style references (correct, safe pattern) or false positives from horse-name/comment text in racecard JSON. Two of the removed doc lines (in the archived `docs/current/*` files, now moved to `docs/archive/`) mention "rotate Racing API password" as a to-do note from an old audit — historical text, not a live secret.
- **Large binary/generated outputs:** none found — everything in the diff is text (JSON/JSONL/MD/CSV/PY). The 470K-line size comes from volume of files, not binary bloat.
- **Stale reports:** the 34 `R100` renames are exactly the fix for this — they move stale root-level truth docs into `docs/archive/`, which is correct and desired.

## Q5-7. VCP code, governance docs, dashboard fix

- **VCP code** (`build_velo_living_state.py`, `build_velo_heartbeat.py`, `build_vcp03_burn_in_log.py`) — **safe to merge.** Self-contained REPORT_ONLY generators, no Supabase/Telegram/live-scoring touch, already exercised locally for 2 days without incident.
- **Governance/docs cleanup** (34 renames + `CLAUDE.md`/`README.md`/`ONE_TRUTH.md` updates) — **safe to merge.** Pure reorganization plus accuracy fixes; this is exactly what closes the "GitHub main still shows stale docs" gap ChatGPT flagged.
- **Dashboard fix** (`app/main.py`, `publish_daily_predictions_to_dashboard.py`, `ede88e6`) — **safe to merge**, small diff (9 lines), already live locally since 2026-06-29 with no reported regression.

## Q8. Should the raceday-data commit (8753b4f) merge to main?

**Not as-is, and not blindly.** Recommendation: **split it.** The 4 scratch/tmp files should never go to main. The remaining ~470 files are genuine historical operational record (sigma results, council packets, learning events, mission control snapshots) spanning 3 weeks that GitHub has simply never seen — that's real audit value, not clutter, but 470K lines in one commit makes future `git blame`/review effectively useless and risks masking the 4 junk files inside it forever. **Recommended path: re-stage this data (minus the 4 scratch files) as its own dedicated, clearly-labeled commit** (e.g. `data(backfill): raceday operational history 2026-06-09 to 2026-06-29`) on a clean branch, separate from the VCP/code changes, so it can be reviewed and merged (or explicitly deferred) on its own timeline without blocking the VCP/LOCAL-01 merge.

## Q9. Should the LOCAL-01 report commit merge to main?

**Yes.** That was the entire purpose of publishing it — it needs to be visible on `main` (or at minimum in an easily-discoverable merged PR) for ChatGPT/operator review to be durable, not stuck on a branch that could be deleted or drift.

## Q10. Merge plan decision

**Option C confirmed as the right call** — do not merge the audit branch as-is (Option A) and don't cherry-pick piecemeal onto the messy branch (Option B). Instead:

1. Create a clean branch from `origin/main` (018d618).
2. Cherry-pick / re-apply, in this order:
   - `e5b259b`'s non-rename files (`CLAUDE.md`, `README.md`, `docs/current/ONE_TRUTH.md`, `new_build_two_lane_score.py` + test) + all 34 `R100` doc renames
   - `ff86674`, `5f83fec`, `a8b3e8a` (VCP-01/02/03 code + reports + task contracts)
   - `ede88e6` (dashboard fix)
   - `b0c354f` (LOCAL-01 reports)
3. Open that as a PR to `main` for operator review. This keeps `main`'s history clean and auditable.
4. Handle the `8753b4f` raceday-data backfill as a **separate, explicitly-labeled decision** — not bundled into the same PR. Strip the 4 scratch files first regardless of what's decided.
5. `models/*/feature_importance.csv` — bundle with whichever of the two PRs the operator prefers; low risk either way.

This is a plan, not an executed action. No branch beyond the existing `audit/local-01-truth-reconciliation` was created, and no cherry-picks were performed in this pass.

---
## Final Classifications
REPO_01_MAIN_RECONCILIATION_COMPLETE
AUDIT_BRANCH_REVIEWED
MAIN_NOT_TOUCHED
MERGE_PLAN_WRITTEN
VCP_FILES_IDENTIFIED
RAW_DATA_NOT_PROMOTED
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
REPORT_ONLY

---
STOP — operator reviews this plan before any clean branch, cherry-pick, or PR is created.
