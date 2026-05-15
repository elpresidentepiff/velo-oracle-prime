# VELO Scoring Dirty Diff Audit — 2026-05-15

Status: `SCORING_DIFF_REQUIRES_HUMAN_REVIEW`

Sentinel should remain: `BLOCK`

Live ops may resume: `NO`

## Scope

Read-only audit of:

- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`

Staged diff check:

- `git diff --cached -- app/services/velo_prime_service.py scripts/run_prime_today.py`
- Result: no staged changes for either file

## File Audit

### `app/services/velo_prime_service.py`

- Changed line summary:
  - adds `subprocess` import
  - adds `_runtime_commit_sha()` helper
  - persists `git_commit_sha`
  - persists `decision_tier`
  - changes RPDC persistence fields from `plot_conviction`-derived values to explicit `rpdc_*` fields
  - adds `decision_tier` into `full_analysis.governance`
  - extends schema warning list with `git_commit_sha`
- Purpose of change:
  - improve persistence truth and schema visibility
  - correct RPDC field mapping so persisted verdicts reflect dedicated RPDC values instead of inferred PDF plot signals
- Risk level:
  - `HIGH`
- Affects scoring:
  - `YES`
- Affects official prediction output:
  - `YES`
- Affects dashboard only:
  - `NO`
- Affects Supabase writes:
  - `YES`
- Safe action:
  - `BLOCKING_LIVE_OPS`

Assessment:

This is partly defensive and partly correctness-oriented, but it is still in the official verdict persistence path. It changes what metadata is written to `velo_verdicts`, changes RPDC column semantics, and changes governance fields that downstream tools read. It should not be reverted casually, and it should not be committed casually without explicit review of schema expectations and downstream consumers.

Recommended action:

- keep blocked
- require human review
- review together with any migration/schema assumptions before deciding whether to keep or revert

### `scripts/run_prime_today.py`

- Changed line summary:
  - adds UTF-8 stdout/stderr reconfigure guard
  - adds a persistence hard block when a stale/date-mismatched card would otherwise be written as current-day truth
  - on mismatch, closes pipeline run as `FAIL`, emits daily truth packet, and returns `BLOCKED`
- Purpose of change:
  - prevent stale racecard persistence from being written as current-day official truth
  - improve Windows console resilience
- Risk level:
  - `HIGH`
- Affects scoring:
  - `YES`
- Affects official prediction output:
  - `YES`
- Affects dashboard only:
  - `NO`
- Affects Supabase writes:
  - `YES`
- Safe action:
  - `BLOCKING_LIVE_OPS`

Assessment:

This looks like a defensive safeguard, and the intent is good. But it directly changes official scoring control flow, persistence behavior, pipeline status reporting, and early-return behavior. Because it gates official day writes, reverting it blindly would also be unsafe. It belongs in reviewed scoring-path change control, not dirty-worktree limbo.

Recommended action:

- keep blocked
- require human review
- decide explicitly whether this safeguard is production doctrine and should be committed in a reviewed scoring-path patch

## Overall Recommendation

Both files affect official scoring/persistence behavior and Supabase write outcomes.

Neither file qualifies as:

- `REVERT_SAFE`
- `COMMIT_SAFE`

Both should remain classified as:

- `BLOCKING_LIVE_OPS`

## Sentinel Outcome

Sentinel should remain `BLOCK` because the current dirty scoring-path files are:

- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`

## Resume Condition

Live ops should remain blocked until one of the following happens:

1. both files are reviewed and intentionally committed as a controlled scoring-path patch, or
2. both files are intentionally reverted after confirming the protections are either obsolete or implemented elsewhere

Until then:

- no live scoring execute
- no `daily-eod --execute`
- no learning consume
- no Telegram send
- no merge to `main`
