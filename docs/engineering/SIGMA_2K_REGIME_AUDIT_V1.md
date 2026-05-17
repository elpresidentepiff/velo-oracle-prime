# SIGMA 2K REGIME AUDIT V1
**Run:** 2026-05-17 12:11 UTC
**Training rows:** 721
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
| VP:VP<0.20 | 249 | 13.7% | 41.8% | -24.6% | 10.15 | 7.0 | 19 | 6.3 | **SUPPRESS** |
| VP:VP0.20-0.30 | 262 | 16.0% | 46.2% | -23.7% | 10.14 | 5.5 | 26 | 5.2 | **WATCH** |
| VP:VP0.30-0.40 | 137 | 24.8% | 63.5% | -19.2% | 5.91 | 3.75 | 13 | 3.0 | **WATCH** |
| VP:VP>=0.40 | 73 | 43.8% | 83.6% | -14.7% | 2.89 | 2.0 | 5 | 1.3 | **PROVEN** |
| VP:VP>=0.30 | 210 | 31.4% | 70.5% | -17.6% | 4.86 | 3.0 | 12 | 2.2 | **PROMISING** |
| VP:VP>=0.30+TierA | 120 | 34.2% | 72.5% | -20.1% | 4.39 | 2.81 | 8 | 1.9 | **PROMISING** |

---

## 2. MDS Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| MDS:MDS<0.30 | 663 | 17.2% | 48.9% | -22.2% | 9.17 | 5.5 | 28 | 4.8 | **WATCH** |
| MDS:MDS0.30-0.50 ⚠️ | 36 | 38.9% | 77.8% | -33.1% | 2.38 | 1.87 | 6 | 1.6 | **PROVEN** |
| MDS:MDS>0.50 ⚠️ | 22 | 63.6% | 95.5% | -6.2% | 1.78 | 1.44 | 3 | 0.6 | **PROVEN** |

---

## 3. Improvement Score Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| IMP:IMP<0.20 | 608 | 17.6% | 49.5% | -21.0% | 9.31 | 5.5 | 33 | 4.7 | **WATCH** |
| IMP:IMP0.20-0.40 | 84 | 27.4% | 57.1% | -27.5% | 5.61 | 3.62 | 16 | 2.7 | **WATCH** |
| IMP:IMP>0.40 ⚠️ | 29 | 41.4% | 82.8% | -34.1% | 2.58 | 2.38 | 5 | 1.4 | **PROVEN** |

---

## 4. SP Bands

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| SP:SP<3.0 | 183 | 44.3% | 78.7% | -16.7% | 2.1 | 2.1 | 7 | 1.3 | **PROVEN** |
| SP:SP3.0-8.5 | 317 | 15.5% | 53.9% | -29.7% | 5.13 | 4.5 | 28 | 5.5 | **WATCH** |
| SP:SP8.5-16.0 | 126 | 7.1% | 34.1% | -18.7% | 11.78 | 12.0 | 47 | 13.0 | **SUPPRESS** |
| SP:SP>16.0 | 95 | 3.2% | 15.8% | -12.6% | 28.53 | 23.0 | 52 | 30.7 | **SUPPRESS** |

---

## 5. Router Lanes

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| ROUTER:V1_BASE ⚠️ | 27 | 37.0% | 85.2% | +11.5% | 2.95 | 2.88 | 7 | 1.7 | **PROVEN** |
| ROUTER:V2_CLASS4 ⚠️ | 17 | 41.2% | 82.4% | +30.2% | 3.04 | 3.0 | 4 | 1.4 | **INSUFFICIENT_SAMPLE** |
| ROUTER:V6_GOLD_SEAM ⚠️ | 5 | 60.0% | 100.0% | +115.0% | 3.47 | 3.5 | 1 | 0.7 | **INSUFFICIENT_SAMPLE** |
| ROUTER:Any_Router ⚠️ | 27 | 37.0% | 85.2% | +11.5% | 2.95 | 2.88 | 7 | 1.7 | **PROVEN** |
| ROUTER:No_Router | 694 | 19.0% | 50.4% | -23.6% | 8.82 | 5.5 | 30 | 4.3 | **WATCH** |

---

## 6. Archetypes

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| ARCH:Compression+VP<0.30 ⚠️ | 0 | 0.0% | 0.0% | — | — | — | 0 | — | **INSUFFICIENT_SAMPLE** |

---

## 7. Tiers

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| TIER:A | 120 | 34.2% | 72.5% | -20.1% | 4.39 | 2.81 | 8 | 1.9 | **PROMISING** |
| TIER:B | 281 | 17.4% | 45.6% | -15.2% | 9.4 | 5.5 | 19 | 4.7 | **WATCH** |
| TIER:C | 167 | 13.8% | 48.5% | -56.0% | 9.1 | 5.5 | 29 | 6.3 | **SUPPRESS** |
| TIER:D ⚠️ | 22 | 18.2% | 54.5% | -43.0% | 9.94 | 8.0 | 8 | 4.5 | **WATCH** |
| TIER:X | 95 | 18.9% | 46.3% | +26.6% | 11.29 | 7.5 | 18 | 4.3 | **WATCH** |
| TIER:B_VP>=0.30 | 72 | 29.2% | 68.1% | -7.9% | 5.5 | 3.5 | 7 | 2.4 | **PROMISING** |
| TIER:B_VP<0.30 | 209 | 13.4% | 37.8% | -17.8% | 10.74 | 6.5 | 22 | 6.5 | **SUPPRESS** |

---

## 8. Combo Zones

| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |
|---|---|---|---|---|---|---|---|---|---|
| COMBO:MDS>0.5+VP>=0.30 ⚠️ | 21 | 66.7% | 95.2% | -1.8% | 1.56 | 1.44 | 3 | 0.5 | **PROVEN** |
| COMBO:IMP>0.40+VP>=0.30 ⚠️ | 22 | 50.0% | 90.9% | -21.4% | 2.17 | 1.86 | 3 | 1.0 | **PROVEN** |
| COMBO:MidPrice+Router ⚠️ | 13 | 38.5% | 84.6% | +32.7% | 3.43 | 3.5 | 7 | 1.6 | **INSUFFICIENT_SAMPLE** |
| COMBO:MidPrice+NoRouter | 304 | 14.5% | 52.6% | -32.4% | 5.2 | 5.0 | 28 | 5.9 | **SUPPRESS** |
| COMBO:VP>=0.40+TierA | 67 | 44.8% | 85.1% | -11.8% | 2.87 | 1.91 | 5 | 1.2 | **PROVEN** |
| COMBO:VP>=0.30+Router ⚠️ | 27 | 37.0% | 85.2% | +11.5% | 2.95 | 2.88 | 7 | 1.7 | **PROVEN** |
| COMBO:ShortFav+VP>=0.30 | 99 | 48.5% | 83.8% | -13.3% | 1.94 | 1.83 | 5 | 1.1 | **PROVEN** |
| COMBO:Outsider+Router ⚠️ | 0 | 0.0% | 0.0% | — | — | — | 0 | — | **INSUFFICIENT_SAMPLE** |

---

## Governance

Advisory only. No scoring/model/staking/router/Telegram changes.

*SIGMA_2K_REGIME_AUDIT_V1 — sigma_2k_regime_audit.py*