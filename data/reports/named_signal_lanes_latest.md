# VELO NAMED SIGNAL LANES — TRACKING REPORT
**Run:** 2026-05-17 13:12 UTC
**Training rows:** 1310
**Date:** 2026-05-17

---

## 2K Milestone Progress

| Metric | Value |
|---|---|
| Training-safe rows | **1310** |
| Target (2K milestone) | 2000 |
| Rows remaining | 690 |
| Progress | 65.5% |
| Growth path | daily_clean_accumulation |

---

## Lane Performance — Historical Corpus

| Lane | n | SR | Frame | ROI | SR Δ | Frame Δ | Avg SP | Med SP | Status |
|---|---|---|---|---|---|---|---|---|---|
| MDS_HIGH_LANE ⚠️ | 39 | 69.2% | 92.3% | -7.2% | +49.5pp | +40.6pp | 1.58 | 1.44 | **PROVEN** |
| IMPROVER_LANE ⚠️ | 38 | 42.1% | 76.3% | -36.3% | +22.4pp | +24.6pp | 2.49 | 1.92 | **PROVEN** |
| VP40_LANE | 150 | 45.3% | 80.7% | +8.2% | +25.6pp | +29.0pp | 3.45 | 2.25 | **PROVEN** |
| VP40_TIER_A_LANE | 132 | 44.7% | 80.3% | +9.4% | +25.0pp | +28.6pp | 3.32 | 2.0 | **PROVEN** |
| SHORTFAV_VP30 | 186 | 52.2% | 84.9% | -9.5% | +32.5pp | +33.2pp | 1.89 | 1.81 | **PROVEN** |
| MIDPRICE_ROUTER_QUAL ⚠️ | 18 | 33.3% | 72.2% | +12.5% | +13.6pp | +20.5pp | 3.44 | 3.5 | **INSUFFICIENT_SAMPLE** |
| MIDPRICE_SUPPRESS | 545 | 16.0% | 52.1% | -23.1% | -3.7pp | +0.4pp | 5.21 | 5.0 | **SUPPRESS_CONFIRMED** |
| LONGSHOT_SUPPRESS | 413 | 6.3% | 24.5% | -11.7% | -13.4pp | -27.2pp | 20.38 | 15.0 | **SUPPRESS_CONFIRMED** |

---

## Today's Lane Candidates (2026-05-17)

### IMPROVER_LANE

| Horse | Race | VP | MDS | IMP | SP | Tier |
|---|---|---|---|---|---|---|
| Ride The Thunder | Hamilton 16:45 | 0.382 | 0.308 | 0.411 | ? | low |

### VP40_LANE

| Horse | Race | VP | MDS | IMP | SP | Tier |
|---|---|---|---|---|---|---|
| Plaid | Hamilton 17:45 | 0.448 | 0.279 | 0.34 | ? | low |
| Trojan Soldier | Ripon 14:17 | 0.467 | 0.232 | 0.311 | ? | low |
| Cawthorne Cracker | Stratford 15:05 | 0.554 | 0.053 | 0.116 | ? | low |
| A Little Something | Stratford 16:05 | 0.457 | 0.28 | 0.2 | ? | low |
| Arrycan | Stratford 17:05 | 0.673 | 0.243 | 0.182 | ? | low |
| Lightsoutandaway | Stratford 17:35 | 0.522 | 0.015 | 0.087 | ? | low |

---

## Lane Definitions

| Lane | Definition | Promotion Target |
|---|---|---|
| MDS_HIGH_LANE | VP>=0.30 AND MDS>0.50 — crown jewel signal | SHADOW_LANE_TRACKING |
| IMPROVER_LANE | VP>=0.30 AND improvement_score>0.40 | SHADOW_LANE_TRACKING |
| VP40_LANE | VP>=0.40 | WATCH |
| VP40_TIER_A_LANE | VP>=0.40 AND tier A | WATCH |
| SHORTFAV_VP30 | SP<3.0 AND VP>=0.30 — short-price + high conviction | WATCH |
| MIDPRICE_ROUTER_QUAL | SP 3.0–8.5 AND router qualified (V1/V2/V6) | SHADOW_LANE_TRACKING |
| MIDPRICE_SUPPRESS | SP 3.0–8.5 AND no router — advisory suppression | SUPPRESS_ADVISORY |
| LONGSHOT_SUPPRESS | SP>8.5 — confirmed dead zone | SUPPRESS |

---

## Governance

Advisory only. No scoring / model / router / staking / Telegram changes.

*BUILD_NAMED_SIGNAL_LANES_V1 — build_named_signal_lanes.py*