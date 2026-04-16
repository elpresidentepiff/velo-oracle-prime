# Doctrine Review — longshot_block_allowed in A-tier AW short-fav regime

Status: proposed review
Scope: review only
Scoring changes: none in this pass

## Why This Review Exists

The Doctrine Layer sidecar reports now isolate a specific blocker failure regime:

- blocker: `longshot_block_allowed`
- decision tier: `A`
- surface regime: `AW`
- actual winner profile: usually `short_<=3.0`
- blocked horse state: usually still live (`WIN` or `PLACED`)

This is not a global blocker failure claim. It is a regime-specific review target.

## Current Evidence

Source board:
- [doctrine_evidence_board_2026-04-15.md](/C:/Users/puror/velo-oracle-prime/reports/daily/doctrine_evidence_board_2026-04-15.md)

Current 30d read from the board:

- `longshot_block_allowed` fires: `20`
- winner suppression count: `8`
- AW fires: `10`
- A-tier + AW slice:
  - races: `10`
  - suppressed winners: `6`
  - blocked horse outcomes:
    - `WIN`: `6`
    - `PLACED`: `3`
    - `MISS`: `1`
  - actual winner SP bucket:
    - `short_<=3.0`: `9`
    - `outsider_>6.0`: `1`

## Review Questions

1. Is `longshot_block_allowed` over-suppressing real winners specifically in the A-tier AW short-fav regime?
2. Is the blocker still justified outside this regime?
3. Would a regime-specific relaxation outperform the current blocker without introducing broader damage?

## Required Comparison

Compare current blocker behavior against a relaxed simulation for this regime only:

- keep blocker unchanged outside the regime
- relax only when all are true:
  - blocker = `longshot_block_allowed`
  - tier = `A`
  - AW regime
  - actual-winner / market proxy is short-priced

## Guardrails

- no global blocker changes
- no non-AW changes
- no scoring deployment from this review alone
- doctrine remains sidecar-only until simulation evidence is reviewed

## Candidate Doctrine Rows

- `longshot_block_allowed_aw_watch`
- `longshot_block_allowed_shortfav_aw_relax_candidate`

## Outcome Of This Review

One of:

- keep current blocker unchanged
- keep blocker globally, but maintain AW watch-only doctrine
- propose regime-specific relaxation candidate for further simulation
