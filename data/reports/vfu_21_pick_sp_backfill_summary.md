# VFU-21: Pick SP Backfill — Operator Brief

## S01 Mission
Recover pick_sp for 2197 rows missing it in the VFU-20 ledger.

## S02 Coverage
| Source | Rows |
|---|---|
| Already had SP | 855 |
| Recovered (results JSON) | 903 |
| Recovered (sigma WIN) | 49 |
| Unrecovered | 1245 |
| **Total with SP** | **1807/3052 (59.2%)** |

## S03 EW P&L (on 1807 rows with SP)
| Metric | Value |
|---|---|
| Total stake (units) | 3614 |
| Total return (units) | 3203.38 |
| Profit | -410.62 units |
| **ROI** | **-11.4%** |

## S04 Governance
- `blocked_from_live_use = True` on all output rows
- NO VP threshold change
- NO model change
- NO live scoring change
- REPORT ONLY

## STOP
STOP — operator review required before VFU-22 (prospective validation).
