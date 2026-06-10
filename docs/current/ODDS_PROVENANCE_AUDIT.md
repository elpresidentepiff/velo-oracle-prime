# ODDS PROVENANCE AUDIT

**Date:** 2026-06-10 · Rule: no ROI/CLV number is presented without its price source declared.

| Odds field | Source | Captured | Pre/post race | Safe for ROI | Safe for CLV | Null rate / range |
|---|---|---|---|---|---|---|
| `sp_dec` / `sp_decimal` (results, horse_runs, innovation rows) | RP results pages, parsed post-race | Evening capture | **Post-race official SP record** | **YES** — official starting price is the industry-standard settlement price | **NO** — SP is recorded after the off; CLV needs a price you could have actually taken pre-off | ~99% coverage on starters since RP pipeline (June); earlier via legacy results |
| `actual_winner_sp` (sigma_audits) | Same RP results parse | Evening | Post-race record | YES (winner rows; 529/551 WIN rows covered) | NO | 22 unpriced wins excluded from economics |
| `best_odds_decimal` (normalized runners) | RP **betting forecast** (newspaper-style morning line) | Morning capture | Pre-race forecast — not a tradeable quote | NO (forecast ≠ obtainable price) | NO | Used for sp_rank/differentiation only |
| Morning/live bookmaker odds | not captured | — | — | — | — | ABSENT |
| BSP (Betfair Starting Price) | not captured | — | — | — | — | **ABSENT — this is the gap** |
| Exchange near-off snapshots | `market_snapshots`/`odds_snapshots` tables exist, **0 rows ever** | — | — | — | — | ABSENT |

## Verdicts
- **ROI: PROVEN-METHOD** — flat-stake at official SP is computable and honest across layers A/B/F/G. Caveat: SP is a settlement price; a real bettor taking morning/exchange prices would do somewhat better or worse — SP-ROI is the conservative standard and we state it as such.
- **CLV: UNPROVEN — at every layer.** Closing-line value requires a timestamped pre-off price (BSP or exchange last-traded). VÉLØ has never captured one. Any CLV claim today would be invented.

## The one capture worth adding (small, high value)
Record **BSP per runner per day** (available publicly after racing from Betfair's BSP files) plus, when automation returns, a single near-off exchange snapshot per race. Cost: one small evening fetch + one table/file. Benefit: unlocks CLV — the professional-grade edge proof — for every day going forward. Recommend adding to the post-June-11 queue; not before the clean-chain target.
