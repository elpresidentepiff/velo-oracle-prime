# VFU-21: Pick SP Backfill — Operator Brief

## S01 Mission
Recover pick_sp for 2197 rows missing it in the VFU-20 ledger.

## S02 Coverage
| Source | Rows |
|---|---|
| Already had SP | 855 |
| Recovered (results JSON) | 903 |
| Recovered (sigma WIN) | 2 |
| Unrecovered | 419 |
| **Total with SP** | **2633/3052 (86.3%)** |

## S03 EW P&L (on 2633 rows with SP)
| Metric | Value |
|---|---|
| Total stake (units) | 5266 |
| Total return (units) | 4607.98 |
| Profit | -658.02 units |
| **ROI** | **-12.5%** |

## S04 Governance
- `blocked_from_live_use = True` on all output rows
- NO VP threshold change
- NO model change
- NO live scoring change
- REPORT ONLY

## STOP
STOP — operator review required before VFU-22 (prospective validation).
