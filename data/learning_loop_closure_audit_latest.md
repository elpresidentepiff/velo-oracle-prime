# VÉLØ Learning Loop Closure Audit

- Generated at: `2026-05-15T01:28:53.301297Z`

## Verdicts

| Metric | Value |
|---|---|
| Total velo_verdicts | 2222 |
| Verdicts with closed runner_results | 1038 |
| Verdicts WITHOUT results | 1184 |

## Sigma Audits

| Total sigma rows | 1938 |
|---|---|

| Date | Closed | Unclosed | Status |
|---|---|---|---|
| 2026-04-25 | 50 | 0 | PARTIAL |
| 2026-04-26 | 0 | 0 | BROKEN |
| 2026-04-27 | 26 | 0 | PARTIAL |
| 2026-04-28 | 29 | 0 | PARTIAL |
| 2026-04-29 | 33 | 0 | PARTIAL |
| 2026-04-30 | 36 | 0 | PARTIAL |
| 2026-05-01 | 34 | 0 | PARTIAL |
| 2026-05-02 | 40 | 0 | PARTIAL |
| 2026-05-03 | 35 | 0 | PARTIAL |
| 2026-05-04 | 49 | 0 | PARTIAL |
| 2026-05-05 | 31 | 0 | PARTIAL |
| 2026-05-06 | 31 | 0 | PARTIAL |
| 2026-05-07 | 36 | 0 | PARTIAL |
| 2026-05-08 | 44 | 0 | PARTIAL |
| 2026-05-09 | 56 | 0 | PARTIAL |
| 2026-05-10 | 21 | 0 | PARTIAL |
| 2026-05-11 | 0 | 0 | BROKEN |
| 2026-05-12 | 38 | 0 | PARTIAL |
| 2026-05-13 | 34 | 0 | PARTIAL |
| 2026-05-14 | 28 | 0 | PARTIAL |

## Ledger Closure Status

| Ledger | Rows | Outcomes Backfilled |
|---|---|---|
| Racing API Shadow Forward | 638 | 504 |
| Paper Ledger (POWER_ANCHOR) | 8 | 8 |
| Paper Ledger (total) | 325 | — |
| Router Shadow Ledger | 33 | — |

## Results JSON Files

- Files found: `53`
- Total races: `2348`
- Races with positions: `2348`

## Missing Fields

- api_ledger:sp_decimal (139/638 blank)
- paper_ledger:horse_id (1/325 blank)
- paper_ledger:sp_decimal (51/325 blank)

## Daily Summary

| Status | Count |
|---|---|
| CLOSED | 29 |
| PARTIAL | 22 |
| BROKEN | 22 |
| Total | 73 |

## Broken Connectors

- velo_verdicts: 1184/2222 verdicts have no runner_results
- sigma loop broken for 22 dates: ['2026-01-09', '2026-01-15', '2026-01-20', '2026-01-25', '2026-01-30']

## Learning State

- Sentient state status: `FOUND_BOTH`
- Has doctrine_strengths: `True`
- Sidecar ablation audit: `FOUND`
- Sidecar audit generated_at: `2026-05-09T00:08:05.518360Z`
- Sidecar baseline matched: `1113`

---
*Audit only — no mutations.*
