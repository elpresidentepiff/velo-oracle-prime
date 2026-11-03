# VÉLØ Learning Loop Closure Audit

- Generated at: `2026-11-03T16:48:20.248261Z`

## Verdicts

| Metric | Value |
|---|---|
| Total velo_verdicts | 6942 |
| Verdicts with closed canonical/legacy results | 5384 |
| Verdicts WITHOUT results | 1558 |
| Canonical racing_horse_runs races | 13476 |
| Legacy runner_results races | 1068 |

## Sigma Audits

| Total sigma rows | 5302 |
|---|---|

| Date | Closed | Unclosed | Status |
|---|---|---|---|
| 2026-10-05 | 47 | 0 | CLOSED |
| 2026-10-06 | 32 | 0 | CLOSED |
| 2026-10-09 | 0 | 0 | BROKEN |
| 2026-10-11 | 0 | 0 | BROKEN |
| 2026-10-12 | 44 | 0 | CLOSED |
| 2026-10-13 | 33 | 0 | PARTIAL |
| 2026-10-14 | 38 | 0 | CLOSED |
| 2026-10-15 | 39 | 0 | CLOSED |
| 2026-10-17 | 58 | 0 | CLOSED |
| 2026-10-21 | 34 | 0 | CLOSED |
| 2026-10-22 | 38 | 0 | CLOSED |
| 2026-10-24 | 0 | 0 | BROKEN |
| 2026-10-25 | 0 | 0 | BROKEN |
| 2026-10-27 | 30 | 0 | CLOSED |
| 2026-10-28 | 37 | 0 | CLOSED |
| 2026-10-29 | 0 | 0 | BROKEN |
| 2026-10-30 | 42 | 0 | CLOSED |
| 2026-10-31 | 38 | 0 | CLOSED |
| 2026-11-01 | 35 | 0 | CLOSED |
| 2026-11-03 | 0 | 0 | BROKEN |

## Ledger Closure Status

| Ledger | Rows | Outcomes Backfilled |
|---|---|---|
| Racing API Shadow Forward | 0 | 0 |
| Paper Ledger (POWER_ANCHOR) | 0 | 0 |
| Paper Ledger (total) | 0 | — |
| Router Shadow Ledger | 0 | — |

## Results JSON Files

- Files found: `35`
- Total races: `1451`
- Races with positions: `1451`

## Missing Fields

- None detected

## Daily Summary

| Status | Count |
|---|---|
| CLOSED | 120 |
| PARTIAL | 27 |
| BROKEN | 39 |
| Total | 186 |

## Broken Connectors

- velo_verdicts: 1558/6942 verdicts have no canonical or legacy result
- sigma loop broken for 39 dates: ['2026-01-09', '2026-01-15', '2026-01-20', '2026-01-25', '2026-01-30']

## Learning State

- Sentient state status: `FOUND_BOTH`
- Has doctrine_strengths: `True`
- Sidecar ablation audit: `FOUND`
- Sidecar audit generated_at: `2026-05-15T01:29:53.152969Z`
- Sidecar baseline matched: `1105`

---
*Audit only — no mutations.*
