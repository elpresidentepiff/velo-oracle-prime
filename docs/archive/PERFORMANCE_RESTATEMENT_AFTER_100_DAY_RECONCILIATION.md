# PERFORMANCE RESTATEMENT — AFTER 100-DAY RECONCILIATION

**Date:** 2026-06-10 · Every number from stored artifacts; recomputable via `build_100_day_truth_ledger.py`.

## Buckets

| # | Bucket | Races/runners | Strike | Frame | Status |
|---|---|---|---|---|---|
| 1 | All historical outputs | 87 race days; 3,390 Supabase verdicts (+local) | not aggregable without per-day sigma | — | HISTORICAL_OUTPUT_ONLY |
| 2 | Sigma-verified (recomputable artifacts) | 19 days, 595 top picks (2026-05-21→06-09) | **155/595 = 26.1%** | 145 placed-not-won (wins+frames 50.4%) | VERIFIED_INTERNAL |
| 3 | Clean-source-proven only | **0 days, 0 runners** | n/a | n/a | Nothing qualifies — every sigma day sits inside the RPDC hijack window, and the observability packets that exist show DEGRADED/FALLBACK/UNKNOWN on most days |
| 4 | Degraded excluded (sigma days minus packet-degraded days) | Honest framing: the strict count is bucket 3; any softer cut is a judgment call, documented as such | — | — | INTERNAL_ONLY until clean days accumulate |
| 5 | RPDC-corrupted excluded | Same as bucket 3 — the hijack window covers all sigma days | — | — | — |
| 6 | Public-safe evidence | **none yet** | — | — | NO_PUBLIC_CLAIM |
| 7 | Shadow-only lanes (flat 1pt paper, results-driven, RPDC-independent) | V1 n=51 SR 45.1% ROI +28.8% · V2 n=41 SR 48.8% ROI +40.7% · V6 n=17 ROI +48.5% | — | — | SHADOW_ONLY |
| 8 | Contaminated excluded | May 20 (flatline) already excluded from corpus; June 10 degraded; both outside bucket 2 or flagged | — | — | — |

**ROI:** no staking ledger exists (no live staking, by rule) — live ROI is not statable at any level. The execution-bridge paper ledger remains `EVIDENCE_INTEGRITY_SUSPECT` (ID chain prevents closure) and is excluded from every bucket.

## Why bucket 2 survives the RPDC corruption
Sigma reconciles **picks against results** by race/horse identity. RPDC is passive metadata that never altered ranks; its corruption poisons *labels about* picks, not the picks or their outcomes. So 26.1% over 595 is real — but it is **internally verified only**: the source-health of those days is not provable to the SIGNED_CLEAN standard, several days' packets read DEGRADED/UNKNOWN, and the window is 19 days.

## What is void
- Every RPDC-tag-conditioned statistic computed from `velo_verdicts` between 2026-04-21 and 2026-06-10 (e.g. "RPDC release score >0.5 → SR 24.1%").
- Any claim seasoned with the paper ledger.
- Any whole-history strike-rate without the per-day classifications attached.

## Public claim ceiling

**`VERIFIED_INTERNAL` — and no higher.**
- `NO_PUBLIC_CLAIM` for any RPDC-conditioned or ledger-derived figure.
- `SHADOW_ONLY` for router lanes, always labelled.
- `PUBLIC_SAFE` requires: clean-day-only series (starts accumulating 2026-06-11 at the earliest), 90+ days, exclusions disclosed.
- `PUBLIC_BENCHMARKED` ("top N UK") additionally requires a named-competitor same-dates benchmark. **Not claimable today, full stop.**
