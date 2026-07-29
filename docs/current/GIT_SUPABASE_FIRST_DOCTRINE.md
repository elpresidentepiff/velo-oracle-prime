# GIT + SUPABASE FIRST DOCTRINE

**Status:** ACTIVE
**Established:** 2026-07-04
**Trigger:** REPO-01/REPO-02 reconciliation exposed that VCP-00 through VCP-03, LOCAL-01, and REPO-01 work existed only on the local laptop for days while GitHub main sat at an older commit, and Supabase repair candidates (e.g. the VFU-21 pick_sp ledger) sat unwritten. This doctrine exists to stop that pattern from recurring.

## Core law

1. **GitHub is the canonical home** for code, docs, governance state, tests, operator reports, small audit tables, and any evidence that needs to be reviewable (by the operator, by ChatGPT, or by any future agent) without depending on the state of one laptop.

2. **Supabase is the canonical home** for structured racing data: Sigma rows, verdicts, pipeline runs, runner snapshots, race results, RPDC tags, and repair candidates — once those repairs are explicitly approved by the operator. Supabase is not written to speculatively.

3. **Local disk is temporary scratch only.** Nothing on the laptop should be treated as durable truth. If it matters, it either lands on GitHub, lands in Supabase, or is explicitly declared local-only with a stated reason.

4. **No mission may end with important truth stuck local-only** unless that truth is explicitly classified `LOCAL_ONLY` with a reason (e.g. it's a secret, a raw capture, or genuinely too large/volatile for git).

5. **Every mission's final report to the operator must state:**
   - GitHub status — what was committed, what was pushed, what branch/PR
   - Supabase status — what was written, or confirmation nothing was written
   - Local-only artifacts — named explicitly, with reason
   - What was pushed
   - What was written
   - What is intentionally not pushed/written, and why

6. **Every generated artifact must be classifiable as one of:**
   - `GITHUB_COMMIT` — belongs in git, should be committed and pushed
   - `SUPABASE_WRITE` — belongs in the database, pending operator approval if it's a repair
   - `LOCAL_ONLY_SCRATCH` — working file, safe to discard, not truth
   - `LOCAL_ONLY_SECRET_OR_RAW_CAPTURE` — must never leave the laptop (credentials, cookies, browser profiles, raw HTML captures)
   - `DATA_BACKFILL_CANDIDATE` — legitimate historical data that should become its own dedicated PR or Supabase write, not silently absorbed into an unrelated commit
   - `DO_NOT_KEEP` — disposable debug/scratch output with no lasting value (e.g. the `data/_tmp_fetch.py`-style files found during REPO-01)

7. **Reports and audit CSVs are GitHub evidence** unless they are too large for sane review or contain secrets. Small audit tables (a few KB, human-reviewable) should be committed even if a blanket `.gitignore` rule would otherwise exclude them — force-add with an explicit reason when that happens, as was done for the LOCAL-01 and REPO-01 CSV tables.

8. **Raw RP HTML, cookies, browser profiles, `.env`, secrets, large captures, and volatile `data/current/` files must never go to GitHub.** These stay local or move to object storage later; they are not git-appropriate regardless of size.

9. **Structured historical operational records** (daily sigma results, council reports, learning inputs, mission control snapshots, etc.) that accumulate locally must become either Supabase rows or a dedicated, clearly-labeled data-backfill PR — never silently bundled into an unrelated commit (see: the `8753b4f` bulk sweep found during REPO-01, which buried 470 legitimate files and 4 scratch files together in one commit).

10. **Before claiming "this is the current truth," check GitHub and Supabase, not just the local working tree.** Local state can be stale, ahead, or contain uncommitted work that hasn't been reconciled — GitHub main and Supabase's tables are the only two things another agent or the operator can independently verify.

## Why this exists (evidence)

- LOCAL-01 found local `main` was 6 commits ahead of `origin/main`, with real VCP-00/01/02/03 work sitting unpushed.
- REPO-01 found that one of those "6 commits" (`8753b4f`) alone was 474 of 555 changed files — a silent 3-week local data backlog swept into a single commit, which would have poisoned `main`'s history if merged blind.
- REPO-01 also found 4 scratch/debug files (`data/_check_passport_coverage.py`, `data/_check_supabase_jun24.py`, `data/_tmp_fetch.py`, `data/_multimodel_june23_tmp.json`) that had been committed by accident into `data/` — harmless, but exactly the kind of drift this doctrine prevents.
- Supabase's `pick_sp known: 1,212` was found to be frozen at the same value as a local snapshot from days earlier, despite the table gaining new rows — a repair candidate (`vfu_21_pick_sp_backfill_ledger.jsonl`) existed locally the whole time, unwritten.

## Final classifications

GIT_SUPABASE_FIRST_DOCTRINE_ACTIVE
LOCAL_IS_SCRATCH_NOT_TRUTH
MISSION_FINAL_PACKETS_MUST_DECLARE_STORAGE
NO_SILENT_LOCAL_ONLY_ARTIFACTS
GITHUB_FOR_CODE_DOCS_REPORTS
SUPABASE_FOR_STRUCTURED_RACING_TRUTH
