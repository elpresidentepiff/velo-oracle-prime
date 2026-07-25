# LOCAL-SALVAGE-01 — Uncommitted Worktree Preservation Manifest
Generated: 2026-07-07 | REPORT_ONLY. No reset. No rebase. No clean. No stash-pop. No push.

Repo: `/mnt/c/Users/puror/velo-oracle-prime`
Checked-out branch: `audit/local-01-truth-reconciliation` @ `5f269b4` (2026-07-03)
`origin/main` @ `a89e90d` (PR #141, VFU-26)
Divergence: local HEAD is 8 commits ahead / **92 commits behind** origin/main (`git rev-list --left-right --count HEAD...origin/main` = `8  92`).

## What this snapshot captures
- `data/reports/local_salvage_01_git_status_porcelain.txt` — raw `git status --porcelain=v1` (313 lines)
- `data/reports/local_salvage_01_diffstat.txt` — `git diff --stat` for tracked modifications
- `data/reports/local_salvage_01_changed_files.txt` — `git diff --name-only` (64 tracked-modified paths)
- `data/reports/local_salvage_01_untracked_files.txt` — `git ls-files --others --exclude-standard` (257 untracked paths)
- `.local_salvage/local_salvage_01_tracked.diff` — full unified diff of all 64 tracked modifications (182,951 lines), stored outside git tracking
- `.local_salvage/local_salvage_01_untracked_manifest.txt` — path/size/mtime for all 257 untracked files, stored outside git tracking

Combined unique paths (tracked-modified ∪ untracked): **321**. (313 porcelain lines vs 321 combined — the porcelain count folds a small number of renamed/staged-adjacent entries differently than the raw union; the 321 figure is the file-level ground truth used for classification.)

## Working tree state at time of snapshot
No files were moved, deleted, reset, or overwritten to produce this snapshot. The working
tree is exactly as it was when this mission started. `git diff` and `git ls-files` are
read-only operations.

## Next steps
See `data/reports/local_salvage_01_classification.csv` / `_summary.md` for per-file
classification, `data/reports/local_salvage_01_secret_scan.md` for the safety scan result,
and `data/reports/local_salvage_01_split_plan.md` for the proposed future-PR breakdown.
A local-only preservation branch (`salvage/local-313-july04-07-preserve`) commits the
non-cache, non-scratch, non-secret-risk subset to guarantee nothing is lost to an
accidental `checkout`/`reset` before classification-driven PRs are built.

## Classification
`LOCAL_SALVAGE_01_MANIFEST_WRITTEN`
