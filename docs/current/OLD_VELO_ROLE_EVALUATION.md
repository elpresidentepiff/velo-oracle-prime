# Old VELO Role Evaluation (ROLE-EVAL-01)

**Status:** SHADOW / OPERATOR ONLY. No live scoring change, no model change,
no router change, no Supabase writes, no Telegram, no promotion, no Racing API.

## The problem this replaces

`scripts/ops/build_old_velo_three_option_card.py` mixed two different jobs in
one script: making the WIN/PLACE/LONGSHOT selections (a morning, pre-race job)
and evaluating them against results (an evening, post-race job). Its own
result join was keyed by RP's raw numeric `race_id` while looking results up
using the `rp_{COURSE_CODE}_{date}_{dot_time}` scheme the runner snapshot
uses — the join always missed, so `role_metrics` stayed at zero regardless of
whether real results existed.

The close harness (`scripts/ops/velo_daily_harness.py`, `run_close`) then
re-ran the same builder after results arrived. Since that script only ever
rebuilds selections from runner snapshots — it never actually reads results
correctly — this just regenerated the same pre-race selections a second time
instead of evaluating them. `_check_results` in the same harness also checked
the wrong paths entirely (`data/results_{date}.json`, and a legacy
`data/racing_api_results_{date}.json` path referencing the decommissioned
Racing API), so the harness's own results-presence check was unreliable too.

## The fix

### 1. The morning card is now frozen

`build_old_velo_three_option_card.py --date YYYY-MM-DD` checks whether a
dated card already exists at `data/reports/old_velo_three_option_card_{tag}.json`.
If it does, the script prints `OLD_VELO_THREE_OPTION_FROZEN` and returns the
existing file unchanged — it does not recompute or reorder the selections.
Use `--force-rebuild` to override this (never do so after results have
arrived; it destroys the frozen selections the evaluator depends on).

### 2. A dedicated evening evaluator

`scripts/ops/evaluate_old_velo_three_option_card.py --date YYYY-MM-DD [--strict]`

Reads the frozen card and the canonical results file
(`data/results/rp_results_YYYY_MM_DD.json`) and joins the two, read-only.
Never mutates the frozen card.

**Race join priority** (first match wins):
1. **Exact `race_id`** — direct match if the card ever carries the same raw
   numeric id the results file uses.
2. **Course code/full-name + exact off_time** — resolved via a shared
   course-name → 3-letter-code table (`COURSE_ABBR`), only applied if exactly
   one result race shares that `(course, minute)` key.
3. **Unique ±3 minute fallback** on the same course code — only applied if
   exactly one candidate falls within the window. Two or more candidates is
   an **ambiguous match** and is blocked, not guessed
   (`AMBIGUOUS_COURSE_TIME` / `AMBIGUOUS_FALLBACK_3MIN`).

**Runner identity** within a matched race: the pick's `horse_id` first (only
works when it's a real RP numeric id — the three-option card can carry a
synthetic `rp_{course}_{slug}` placeholder id that will never match a real
result), then a normalised horse name (country suffix like `(IRE)` and
punctuation stripped) as fallback.

### 3. Real daily role truth

For each of WIN / PLACE / LONGSHOT: evaluated count, wins, frames, strike
rate, frame rate, non-runners, identity misses, £1 level-stake profit, and
ROI. Every race records its `join_method`. Every run records the SHA-256 of
both the frozen card and the results file it read, so any output can be
traced back to the exact inputs that produced it.

Output: `data/reports/old_velo_role_evaluation_{date}.json` /
`.md`.

`--strict` exits non-zero if any race is unresolved or ambiguous — an
incomplete reconciliation cannot silently pass.

### 4. Close harness repaired

- `_check_results` now checks the actual canonical path
  (`data/results/rp_results_YYYY_MM_DD.json`) instead of legacy paths that
  never matched, including a Racing API–sourced path that should never exist
  as a live input at all.
- `run_close` runs `evaluate_old_velo_three_option_card.py --strict` after
  Sigma, and no longer re-invokes the card builder (which would only ever
  return the frozen card unchanged, per point 1 above — but the redundant
  call is removed rather than left as effectively-dead work).

## Usage

```bash
# Morning (idempotent — returns existing card unchanged on rerun)
python scripts/ops/build_old_velo_three_option_card.py --date 2026-07-10

# Evening, after results are captured/parsed
python scripts/ops/evaluate_old_velo_three_option_card.py --date 2026-07-10 --strict
```

## Verified against real data (2026-07-10)

| Role | Evaluated | Wins | Frames | SR | Frame Rate |
|---|---:|---:|---:|---:|---:|
| WIN | 43 | 9 | 23 | 20.9% | 53.5% |
| PLACE | 40 | 4 | 12 | 10.0% | 30.0% |
| LONGSHOT | 37 | 4 | 16 | 10.8% | 43.2% |

0 unresolved races across all 49. Frozen card SHA-256 confirmed unchanged
before and after evaluation.
