# STASH-01 — Local Stash Inventory — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | no stash applied/popped/dropped/created | inspected read-only via `git stash show`

---

## Q1. How many stashes exist?

**11**, spanning `stash@{0}` (2026-06-16, newest) to `stash@{10}` (2026-03-24, oldest — over 3 months old). None were touched, applied, popped, or dropped in this audit.

## Q2. Which are likely duplicates of merged work?

- **`stash@{2}`** (Jun 12, WIP on `stabilization/prime-hardening-v1`): a 1-line fix adding `main` to `.github/workflows/governed-safety.yml`'s trigger branches. **Confirmed already present in the current committed workflow file** — the fix landed some other way. This stash is now redundant.
- **`stash@{3}`**'s `.gitignore` addition (`.agents/`) is likewise already present in the current `.gitignore` (line 139) — redundant, though the rest of that stash (a test-file deletion) is not.

No stash overlaps with the VCP/LOCAL-01/REPO-01/DATA-01 work merged in PRs #92-98 — all 11 stashes predate that entire reconciliation effort (newest is Jun 16; the reconciliation work started Jun 29).

## Q3. Which might contain real unmerged work?

Three stand out:
- **`stash@{5}`** (May 7, message literally: *"pre-merge tracked runtime/doc work — review required"*) — the stash's own author flagged it as needing review and it was never resolved. Touches `app/main.py` (+90 lines), the dashboard (+242 lines), `run_prime_today.py`, and **`run_results_sigma.py`** — the Sigma script this project's doctrine says is LOCKED and must never change casually. This needs a human look before anything happens to it.
- **`stash@{4}`** (May 19) adds a whole new "Daily Run Truth Duty" section to `docs/engineering/VELO_LLM_COUNCIL_V1.md` (confirmed absent from the current file) plus real code changes to `cashrun_detector.py`, `velo_morning_cockpit.py`, `sync_verdicts_from_supabase.py` — but those three script paths no longer exist (moved to `scripts/audit/` and `scripts/ops/` during the May 20 repo reorg), so the code portion is orphaned and can't be cleanly reapplied; the doc addition could likely be salvaged directly.
- **`stash@{6}`** (Apr 27) contains substantial, never-committed business documents: `docs/company/VELO_COMPANY_MASTER_PLAN_V1.md` (+730 lines), `VELO_FUNDING_PACK_OUTLINE_V1.md`, `VELO_WHITEPAPER_OUTLINE_V1.md`, plus evidence docs (`VELO_49_DAY_SIGNAL_DISCOVERY_REPORT_V1.md`, `VELO_SIGNAL_RANKINGS_V1.md`). These read like real strategic/investor material that may exist nowhere else in this form.
- **`stash@{8}`** (Apr 12) modifies `app/services/security_validator.py` by +218 lines — the file still exists at that path today, so this diff may still be directly relevant. Worth a security-focused review before dismissing.
- **`stash@{10}`** (Mar 24, oldest) proposes deleting 5 files (`app/ml/stability_clusters.py`, `app/ml/v11_signal_engines.py`, `app/strategy/gti_game_theory.py`, `tests/test_phase2a_integration.py`, `tests/test_stability_clusters.py`) — all 5 **still exist in the repo today**, over 3 months later. Either this cleanup was correct and simply never executed, or it was abandoned for a reason. Needs an operator decision either way.

## Q4. Which are safe-to-drop candidates, pending operator approval?

- **`stash@{2}`** — duplicate of already-merged workflow fix, trivial timestamp diff otherwise.
- **`stash@{7}`** (Apr 16) — 35 files, almost entirely "oasis" pipeline candidate/rejection window data with near-equal insertions/deletions (11,894+ / 11,897-), suggesting reordering/reformatting rather than new content. Old experimental pipeline, low apparent value.
- **`stash@{9}`** (Apr 12, earliest same day) — the largest stash (52 files, ~146K changed lines), but almost entirely modifications to files that **already exist committed in git history** (presentation deck HTML, LICENSE, Makefile, huge CSV training sets, deprecated Cloudflare Worker deployment scripts). Balanced insert/delete counts suggest reformatting, not new content. Touches infrastructure (Cloudflare Workers) the project has since moved away from.

None are marked `safe_to_drop_now: true` — per instruction, that flag is reserved for operator sign-off, not something this audit grants itself.

## Q5. Which should become GitHub PRs?

Only after manual review resolves what's real: the "Daily Run Truth Duty" doc addition in `stash@{4}` and the business docs in `stash@{6}` are the most likely candidates for a future docs-only PR, since they're additive and don't touch orphaned code paths.

## Q6. Which should become data-backfill candidates?

`stash@{0}` and `stash@{1}` — pure data-snapshot deltas (May 1 and mid-June `new_build`/passport-feed refreshes), same shape as the PRs #92-98 data-backfill lane, just older and likely superseded by more recent committed snapshots already. Low priority.

## Q7. Which must stay local-only?

None of the 11 stashes touch `.env`, `data/browser_profiles/`, `data/racing_post_account_raw/`, or `data/current/` — confirmed via the file lists above. This entire stash population is a source-control hygiene problem, not a secrets problem.

## Q8. What must not be touched?

All 11 stashes, until the operator reviews `stash@{4}`, `stash@{5}`, `stash@{6}`, `stash@{8}`, and `stash@{10}` specifically — these five carry a non-trivial chance of real, otherwise-unrecoverable work. No stash was applied, popped, or dropped in this pass.

## Q9. What is the safest next step?

Manual, one-at-a-time review of the five flagged stashes (`4`, `5`, `6`, `8`, `10`), oldest-risk-first. For each: either recover the salvageable piece into a small dedicated PR (via the same clean-worktree pattern used for PRs #92-98), or get explicit operator sign-off to drop. The remaining six (`0`, `1`, `2`, `3`, `7`, `9`) are lower-risk and can likely be dropped after a much shorter confirmation pass, since their content is either already duplicated, already committed elsewhere, or clearly stale data churn.

---
## Final Classifications
STASH_01_INVENTORY_COMPLETE
NO_STASH_APPLIED
NO_STASH_POPPED
NO_STASH_DROPPED
NO_STASH_CREATED
NO_FILES_MOVED
NO_FILES_DELETED
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
REPORT_ONLY
