# VELO Step-Back Repair Plan - 2026-06-20

## Why This Exists

VELO has three active faults that must be handled before any new lane is trusted:

- Mid-price wound: too many confident top picks are losing in the 3.0-8.5 zone.
- Ingestion wound: dated passport feeds are not guaranteed, causing fallback to `latest`.
- Source-truth wound: stale Racing API labels still existed in the live harness contract.

The fix direction is not "more confidence". The fix direction is stricter evidence, cleaner source truth, and shadow-only proof before promotion.

## Repairs Applied

- `src/velo/source_truth_enforcer.py`: Racing API aliases now map to `RACING_API_BLOCKED`.
- `scripts/ops/write_velo_run_observability.py`: `API_CLEAN` removed from valid observability source labels; `RACING_API_BLOCKED` added for blocked audit packets.
- Harness tests updated so `api`, `racing_api`, and `API_CLEAN` raise `SourceTruthBlockError`.
- `src/velo/radical/regime_router.py`: invalid decimal odds below `1.01` hard-pass.
- `src/velo/radical/regime_router.py`: mid-price hunter actions now affect Shadow VELO routing.
- `scripts/ops/run_radical_shadow_today.py`: if old verdict files lack `midprice_*`, Shadow VELO calculates the mid-price signal in-memory without writing the ledger.

## June 19 Shadow Replay Truth

Input: `data/velo_prime_verdicts_2026_06_19.json`

Obstacle:

- `PASSPORT_DATED_FEED_MISSING: using latest feed only`

Decision counts after the repair:

- `WIN_CANDIDATE_SHADOW`: 1
- `CASH_RUN`: 21
- `WATCHLIST_SHADOW`: 5
- `PASS_OR_WATCH`: 3
- `NO_BET_SHADOW`: 4
- `PASS`: 22

Mid-price signal counts:

- `MIDPRICE_SUPPRESS_TOP`: 19
- `MIDPRICE_NO_EDGE`: 5
- `MIDPRICE_SPLIT_RACE`: 21
- `MIDPRICE_CLEAN`: 11

Action-level result snapshot:

- `CASH_RUN`: n=21, wins=8, frames=13, win-only P/L=-3.67
- `WIN_CANDIDATE_SHADOW`: n=1, wins=0, frames=0, win-only P/L=-1.00
- `PASS`: n=22, wins=3, frames=15, win-only P/L=-12.92
- `PASS_OR_WATCH`: n=3, wins=0, frames=2, win-only P/L=-3.00
- `WATCHLIST_SHADOW`: n=5, wins=0, frames=1, win-only P/L=-5.00

Interpretation:

- The mid-price guard is doing useful suppression work.
- The cash-run lane is frame-heavy, not proven win-profitable.
- Place/cash ROI cannot be trusted until real place odds or exchange-place proxy odds are ingested.
- Passport fallback to latest is an ingestion downgrade and must block any promotion.

## Next Repair Order

1. Dated passport feed must be mandatory for Shadow VELO promotion tests.
2. Add a race-day preflight that fails if `current_card_passport_feed_YYYY_MM_DD.jsonl` is missing.
3. Build a place/cash return audit using real place odds or a documented proxy, not win SP.
4. Replay all Sigma overlap days with the new mid-price router and dated-passport status recorded.
5. Promote nothing until the replay shows a positive pocket with enough sample size and clean ingestion.

## Law

Racing API is dead for live VELO. Racing Post HTML/RP scraper artifacts are the source of truth.

