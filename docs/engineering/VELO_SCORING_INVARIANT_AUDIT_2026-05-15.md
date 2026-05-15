# VELO Scoring Invariant Audit - 2026-05-15

Status: `SCORING_PATH_INVARIANTS_PROVEN`

Live ops status: `BLOCKED_UNTIL_SCORING_FILES_ARE_COMMITTED_OR_REVERTED`

Branch: `ops-worker-shadow-loop-preserve`

## Scope

Files under review:

- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`

No live ops were run. No prediction execute was run. No EOD was run. No learning consume was run. No Telegram was run. No live state was touched.

## Grep Proof Summary

Reviewed references to:

- `velo_prime_prob`
- `sqpe`
- `market_deception_score`
- `improvement_score`
- `decision_tier`
- `sort`
- `rank`
- `top_rank`
- `threshold`

The dirty diff does not edit probability calculation, SQPE calculation, MDS calculation, improvement calculation, ranking sort, tier thresholds, or top horse selection.

## Invariant Matrix

### `app/services/velo_prime_service.py`

| Question | Result |
| --- | --- |
| Changes probability calculation? | `NO` |
| Changes SQPE calculation? | `NO` |
| Changes MDS calculation? | `NO` |
| Changes improvement score calculation? | `NO` |
| Changes sorting/ranking? | `NO` |
| Changes tier threshold logic? | `NO` |
| Changes top horse selection? | `NO` |
| Changes official prediction persistence? | `YES` |
| Adds metadata only? | `YES` |
| Adds defensive blocking only? | `NO` |

Diff classification:

- adds `_runtime_commit_sha()`
- persists `git_commit_sha`
- persists `decision_tier`
- changes RPDC persistence to use explicit `rpdc_*` fields instead of deriving RPDC columns from `plot_conviction`
- adds `decision_tier` to governance payload
- expands schema-warning expectations for `git_commit_sha`

Assessment:

This is an output-contract and persistence-truth patch. It does not change model math, runner scores, tier thresholds, ranking, or top selection. It does change the shape and semantics of persisted verdict metadata, so it still requires controlled commit review.

Recommended action:

- `COMMIT_CANDIDATE_OUTPUT_CONTRACT`

### `scripts/run_prime_today.py`

| Question | Result |
| --- | --- |
| Changes probability calculation? | `NO` |
| Changes SQPE calculation? | `NO` |
| Changes MDS calculation? | `NO` |
| Changes improvement score calculation? | `NO` |
| Changes sorting/ranking? | `NO` |
| Changes tier threshold logic? | `NO` |
| Changes top horse selection? | `NO` |
| Changes official prediction persistence? | `YES` |
| Adds metadata only? | `NO` |
| Adds defensive blocking only? | `YES` |

Diff classification:

- adds UTF-8 stdout/stderr guard
- blocks persistence when loaded racecard date does not match requested date
- closes pipeline run as `FAIL`
- emits daily truth packet
- returns `RunPrimeResult(status="BLOCKED", exit_code=1)`

Assessment:

This is a defensive safety patch. It changes official scoring control flow only for stale/date-mismatched cards. It does not change scoring math, runner ranking, tier logic, or top selection.

Recommended action:

- `COMMIT_CANDIDATE_DEFENSIVE_SAFETY`

## Baseline vs Current Output Comparison

Method:

- Created a detached baseline worktree at `HEAD`.
- Used cached racecards from the primary repo data directory.
- Scored in memory only.
- Did not call `run_prime_today.py --dry-run`, because that path writes local backup JSON.
- Did not write official predictions.
- Did not mutate Supabase.
- Did not touch live state.
- Compared:
  - race count
  - top horse per race
  - top horse id per race
  - `velo_prime_prob`
  - `decision_tier`
  - top-eight ranking order and probabilities

Dates:

- `2026-05-13`
- `2026-05-15`

Results:

| Date | Baseline races | Current races | Top horse diffs | Horse id diffs | Probability diffs | Tier diffs | Ranking diffs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026-05-13` | 52 | 52 | 0 | 0 | 0 | 0 | 0 |
| `2026-05-15` | 52 | 52 | 0 | 0 | 0 | 0 | 0 |

Conclusion:

The dirty scoring-path diffs do not change prediction math, selected horse, probability, tiering, or ranking for the tested historical/current dates.

## Stale-Card Block Validation

Condition:

```python
if date_mismatch and persistence_enabled:
```

Trigger:

- loaded racecard dates do not match requested run date
- persistence is enabled

Behavior:

- prints a persistence-block message
- closes pipeline run as `FAIL`
- writes/emits daily truth packet
- returns `RunPrimeResult(status="BLOCKED", exit_code=1)`
- exits before normalization, scoring, persistence, local backup write, or Telegram summary

Validation:

- The block is located before the normalization/scoring loop.
- The block is gated by `persistence_enabled`, so dry-run/no-persist analysis can still inspect stale cards without writing official truth.
- The block prevents stale fallback cards from being written as current-day official predictions.

Assessment:

- `COMMIT_CANDIDATE_DEFENSIVE_SAFETY`

## Final Recommendation

Both dirty files remain live-op blockers while uncommitted.

Recommended resolution:

- commit `app/services/velo_prime_service.py` as `COMMIT_CANDIDATE_OUTPUT_CONTRACT`
- commit `scripts/run_prime_today.py` as `COMMIT_CANDIDATE_DEFENSIVE_SAFETY`
- keep Sentinel as `BLOCK` until those commits are made or the files are intentionally reverted

Live ops may resume only after Sentinel no longer blocks on scoring-path dirt.

## Final Classification

- `SCORING_PATH_INVARIANTS_PROVEN`
- `COMMIT_CANDIDATE_OUTPUT_CONTRACT`
- `COMMIT_CANDIDATE_DEFENSIVE_SAFETY`
- `LIVE_OPS_STILL_BLOCKED_UNTIL_SCORING_FILES_RESOLVED`
