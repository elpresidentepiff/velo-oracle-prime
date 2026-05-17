# SIGMA 2K REGIME AUDIT V1
**Run:** 2026-05-17 12:30 UTC
**Training rows:** 1310
**Global SR (reference):** 19.7%

---

## Classification Key

| Class | Meaning |
|---|---|
| PROVEN | SR lift ≥+15pp, Frame ≥70% |
| PROMISING | SR lift ≥+8pp, Frame ≥60% |
| WATCH | SR lift ≥+2pp |
| SUPPRESS | SR lift <-5pp or SR<12% |
| INSUFFICIENT_SAMPLE | n<20 |

---

## 1. VP Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| VP:VP<0.20 | 463 | 13.4% | 38.4% | -25.0% | 12.26 | 7.5 | 30 | 6.5 | **SUPPRESS** |
| VP:VP0.20-0.30 | 448 | 16.7% | 46.7% | -26.1% | 9.76 | 5.5 | 26 | 5.0 | **WATCH** |
| VP:VP0.30-0.40 | 249 | 27.7% | 64.7% | -2.3% | 5.84 | 3.75 | 13 | 2.6 | **PROMISING** |
| VP:VP>=0.40 | 150 | 45.3% | 80.7% | +8.2% | 3.45 | 2.25 | 7 | 1.2 | **PROVEN** |
| VP:VP>=0.30 | 399 | 34.3% | 70.7% | +1.6% | 4.95 | 3.25 | 12 | 1.9 | **PROMISING** |
| VP:VP>=0.30+TierA | 236 | 37.3% | 72.0% | +9.8% | 4.59 | 2.88 | 8 | 1.7 | **PROVEN** |

---

## 2. MDS Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| MDS:MDS<0.30 | 1196 | 17.7% | 47.7% | -17.2% | 9.85 | 5.5 | 29 | 4.6 | **WATCH** |
| MDS:MDS0.30-0.50 | 71 | 46.5% | 83.1% | -21.7% | 2.14 | 1.8 | 6 | 1.2 | **PROVEN** |
| MDS:MDS>0.50 ⚠️ | 41 | 65.9% | 92.7% | -11.8% | 1.7 | 1.44 | 3 | 0.5 | **PROVEN** |

---

## 3. Improvement Score Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| IMP:IMP<0.20 | 1082 | 18.5% | 48.2% | -14.5% | 10.01 | 5.5 | 34 | 4.4 | **WATCH** |
| IMP:IMP0.20-0.40 | 170 | 30.0% | 61.2% | -26.6% | 5.97 | 3.62 | 16 | 2.3 | **PROMISING** |
| IMP:IMP>0.40 | 56 | 37.5% | 73.2% | -41.6% | 3.0 | 2.0 | 5 | 1.7 | **PROVEN** |

---

## 4. SP Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| SP:SP<3.0 | 330 | 46.4% | 81.2% | -15.0% | 2.03 | 2.0 | 8 | 1.2 | **PROVEN** |
| SP:SP3.0-8.5 | 563 | 16.5% | 52.8% | -22.0% | 5.15 | 5.0 | 31 | 5.1 | **WATCH** |
| SP:SP8.5-16.0 | 235 | 8.9% | 32.8% | -1.9% | 11.67 | 12.0 | 47 | 10.2 | **SUPPRESS** |
| SP:SP>16.0 | 178 | 2.8% | 13.5% | -24.7% | 31.88 | 24.5 | 83 | 34.6 | **SUPPRESS** |

---

## 5. Router Lanes

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| ROUTER:V1_BASE ⚠️ | 32 | 34.4% | 78.1% | +3.5% | 3.03 | 3.0 | 7 | 1.9 | **PROMISING** |
| ROUTER:V2_CLASS4 ⚠️ | 22 | 36.4% | 72.7% | +14.2% | 3.13 | 3.19 | 4 | 1.8 | **PROVEN** |
| ROUTER:V6_GOLD_SEAM ⚠️ | 10 | 40.0% | 70.0% | +37.5% | 3.46 | 3.5 | 2 | 1.5 | **INSUFFICIENT_SAMPLE** |
| ROUTER:Any_Router ⚠️ | 32 | 34.4% | 78.1% | +3.5% | 3.03 | 3.0 | 7 | 1.9 | **PROMISING** |
| ROUTER:No_Router | 1278 | 20.6% | 50.4% | -17.8% | 9.33 | 5.25 | 30 | 3.9 | **WATCH** |

---

## 6. Archetypes

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| ARCH:Compression ⚠️ | 22 | 9.1% | 54.5% | -29.5% | 6.33 | 5.75 | 18 | 10.0 | **SUPPRESS** |
| ARCH:Structure | 130 | 25.4% | 56.9% | -13.5% | 6.6 | 4.33 | 17 | 2.9 | **WATCH** |
| ARCH:Compression+VP<0.30 ⚠️ | 22 | 9.1% | 54.5% | -29.5% | 6.33 | 5.75 | 18 | 10.0 | **SUPPRESS** |

---

## 7. Tiers

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| TIER:A | 236 | 37.3% | 72.0% | +9.8% | 4.59 | 2.88 | 8 | 1.7 | **PROVEN** |
| TIER:B | 622 | 18.8% | 47.6% | -17.9% | 9.09 | 5.5 | 28 | 4.3 | **WATCH** |
| TIER:C | 232 | 14.2% | 46.1% | -43.3% | 9.82 | 6.0 | 39 | 6.0 | **SUPPRESS** |
| TIER:D ⚠️ | 26 | 15.4% | 50.0% | -51.8% | 10.54 | 8.0 | 12 | 5.5 | **WATCH** |
| TIER:X | 157 | 15.3% | 38.9% | -4.4% | 15.94 | 8.5 | 31 | 5.5 | **SUPPRESS** |
| TIER:B_VP>=0.30 | 143 | 30.1% | 68.5% | -5.8% | 5.5 | 3.5 | 12 | 2.3 | **PROMISING** |
| TIER:B_VP<0.30 | 479 | 15.4% | 41.3% | -21.5% | 10.16 | 6.0 | 22 | 5.5 | **SUPPRESS** |

---

## 8. Combo Zones

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| COMBO:MDS>0.5+VP>=0.30 ⚠️ | 39 | 69.2% | 92.3% | -7.2% | 1.58 | 1.44 | 3 | 0.4 | **PROVEN** |
| COMBO:IMP>0.40+VP>=0.30 ⚠️ | 38 | 42.1% | 76.3% | -36.3% | 2.49 | 1.92 | 8 | 1.4 | **PROVEN** |
| COMBO:MidPrice+Router ⚠️ | 18 | 33.3% | 72.2% | +12.5% | 3.44 | 3.5 | 7 | 2.0 | **INSUFFICIENT_SAMPLE** |
| COMBO:MidPrice+NoRouter | 545 | 16.0% | 52.1% | -23.1% | 5.21 | 5.0 | 31 | 5.3 | **WATCH** |
| COMBO:VP>=0.40+TierA | 132 | 44.7% | 80.3% | +9.4% | 3.32 | 2.0 | 6 | 1.2 | **PROVEN** |
| COMBO:VP>=0.30+Router ⚠️ | 32 | 34.4% | 78.1% | +3.5% | 3.03 | 3.0 | 7 | 1.9 | **PROMISING** |
| COMBO:ShortFav+VP>=0.30 | 186 | 52.2% | 84.9% | -9.5% | 1.89 | 1.81 | 6 | 0.9 | **PROVEN** |
| COMBO:Outsider+Router ⚠️ | 0 | 0.0% | 0.0% | — | — | — | 0 | — | **INSUFFICIENT_SAMPLE** |

---

## Governance

Advisory only. No scoring/model/staking/router/Telegram changes.

*SIGMA_2K_REGIME_AUDIT_V1 — sigma_2k_regime_audit.py*