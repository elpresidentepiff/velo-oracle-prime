# VP Opportunity Panel — 2026-06-04

**Gate Label: GREEN**

Reason: avg VP=0.440 (>=0.35), 16 picks VP>=0.40 (>=5), 14 picks VP>=0.45 (>=2)

## Warnings
- FALSE_GREEN_POSSIBLE: Jun 09 2026 had VP_avg=0.355 / 10 VP>=0.40 picks / 0 wins from 33 — this gate is an opportunity signal, not a staking permission

## Metrics
| Field | Value |
|---|---|
| Total picks | 34 |
| Avg VP | 0.4396 |
| Median VP | 0.3844 |
| VP >= 0.30 | 28 |
| VP >= 0.40 | 16 (47%) |
| VP >= 0.45 | 14 (41%) |
| VP >= 0.50 | 11 |
| SP 1.5-4.0 window % | 0.3235 |
| SP 6.0+ dead zone % | 0.3824 |
| Drain course picks | 0 (0%) |
| Excelling course picks | 6 |

## Top 10 Picks by VP
| Horse | Course | Off | VP | Improve | MDS | Outcome |
|---|---|---|---|---|---|---|
| Loriko | Uttoxeter | 2.00 | 0.7921 | 0.0000 | 0.0000 | WIN |
| Ron's Angel | Lingfield (AW) | 8.10 | 0.7255 | 0.0000 | 0.0000 | WIN |
| Pearl Eye | Hamilton | 3.21 | 0.6861 | 0.0000 | 0.0000 | WIN |
| Ziggy Starshine | Wetherby | 2.12 | 0.6586 | 0.0000 | 0.0000 | PLACED |
| Raspoutine | Lingfield (AW) | 6.40 | 0.6550 | 0.0000 | 0.0000 | PLACED |
| Coumeenoole | Uttoxeter | 2.30 | 0.6460 | 0.0000 | 0.0000 | WIN |
| Ghost Story | Ffos Las | 8.50 | 0.6066 | 0.0000 | 0.0000 | PLACED |
| Real Trouble | Ffos Las | 6.50 | 0.5830 | 0.0000 | 0.0000 | WIN |
| Fire Thunder | Lingfield (AW) | 7.40 | 0.5766 | 0.0000 | 0.0000 | PLACED |
| Sunshine Star | Lingfield (AW) | 6.10 | 0.5428 | 0.0000 | 0.0000 | WIN |

## Course Mix
| Course | Count | Drain? |
|---|---|---|
| Wetherby | 8 |  |
| Hamilton | 7 |  |
| Lingfield (AW) | 7 |  |
| Ffos Las | 6 |  |
| Uttoxeter | 6 | EXCELLING |

---

## Gate Rules (VP_OPPORTUNITY_GATE_V1)
| Label | Criteria |
|---|---|
| GREEN | avg VP >= 0.35, VP40 count >= 5, VP45 count >= 2 |
| AMBER | avg VP >= 0.25, VP40 count >= 1 |
| RED | avg VP < 0.25 OR zero VP>=0.40 picks |

**Evidence base**: corrected row-bearing Sigma universe, 711 rows, May 23–Jun 13.
**Supabase written**: NO | **Live scoring changed**: NO | **Staking enabled**: NO