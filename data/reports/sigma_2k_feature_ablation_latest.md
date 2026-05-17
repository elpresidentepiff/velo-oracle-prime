# SIGMA 2K FEATURE ABLATION AUDIT V1
**Run:** 2026-05-17 12:12 UTC
**Training rows:** 721
**Global SR baseline:** 19.7%

---

## Full Results

| Family | n | SR | Frame | ROI | SR Δ | Frame Δ | Coverage | FP Red | W Lost | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| BASE: All corpus | 721 | 19.7% | 51.7% | -22.2% | +0.0pp | +0.0pp | 100.0% | 0.0% | 0 | **ADVISORY_ONLY** |
| VP>=0.30 only | 210 | 31.4% | 70.5% | -17.6% | +11.7pp | +18.8pp | 29.1% | 75.1% | 76 | **KEEP** |
| VP>=0.30 + MDS>0.50 | 21 | 66.7% | 95.2% | -1.8% | +47.0pp | +43.5pp | 2.9% | 98.8% | 128 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + IMP>0.40 | 22 | 50.0% | 90.9% | -21.4% | +30.3pp | +39.2pp | 3.1% | 98.1% | 131 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + Router | 27 | 37.0% | 85.2% | +11.5% | +17.3pp | +33.5pp | 3.7% | 97.1% | 132 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + RP_Conv_HIGH | 210 | 31.4% | 70.5% | -17.6% | +11.7pp | +18.8pp | 29.1% | 75.1% | 76 | **KEEP** |
| VP>=0.30 + CASHRUN_WATCH | 210 | 31.4% | 70.5% | -17.6% | +11.7pp | +18.8pp | 29.1% | 75.1% | 76 | **KEEP** |
| VP>=0.30 + Midprice_Suppress | 139 | 39.6% | 76.3% | -10.7% | +19.9pp | +24.6pp | 19.3% | 85.5% | 87 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + TierA | 120 | 34.2% | 72.5% | -20.1% | +14.5pp | +20.8pp | 16.6% | 86.4% | 101 | **KEEP** |
| VP>=0.30 + TierA_or_B | 192 | 32.3% | 70.8% | -15.5% | +12.6pp | +19.1pp | 26.6% | 77.5% | 80 | **KEEP** |
| VP>=0.30 + suppress_TierC | 200 | 32.0% | 71.0% | -15.4% | +12.3pp | +19.3pp | 27.7% | 76.5% | 78 | **KEEP** |
| VP>=0.30 + MDS>0.50 + IMP>0.40 | 11 | 63.6% | 100.0% | -6.4% | +43.9pp | +48.3pp | 1.5% | 99.3% | 135 | **INSUFFICIENT_SAMPLE** |
| VP>=0.30 + MDS>0.50 + Router | 1 | 100.0% | 100.0% | +110.0% | +80.3pp | +48.3pp | 0.1% | 100.0% | 141 | **INSUFFICIENT_SAMPLE** |
| VP>=0.30 + Router + TierA | 13 | 38.5% | 92.3% | +12.3% | +18.8pp | +40.6pp | 1.8% | 98.6% | 137 | **INSUFFICIENT_SAMPLE** |
| Full stack: VP30+MDS+IMP+Router | 5 | 20.0% | 100.0% | -58.0% | +0.3pp | +48.3pp | 0.7% | 99.3% | 141 | **INSUFFICIENT_SAMPLE** |
| VP>=0.40 only | 73 | 43.8% | 83.6% | -14.7% | +24.1pp | +31.9pp | 10.1% | 92.9% | 110 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.40 + Router | 8 | 37.5% | 100.0% | -8.1% | +17.8pp | +48.3pp | 1.1% | 99.1% | 139 | **INSUFFICIENT_SAMPLE** |
| VP>=0.40 + TierA | 67 | 44.8% | 85.1% | -11.8% | +25.1pp | +33.4pp | 9.3% | 93.6% | 112 | **SHADOW_POLICY_CANDIDATE** |
| Compression suppress | 721 | 19.7% | 51.7% | -22.2% | +0.0pp | +0.0pp | 100.0% | 0.0% | 0 | **ADVISORY_ONLY** |
| Suppress TierC | 554 | 21.5% | 52.7% | -12.1% | +1.8pp | +1.0pp | 76.8% | 24.9% | 23 | **ADVISORY_ONLY** |
| Suppress VP<0.20 | 472 | 22.9% | 57.0% | -21.0% | +3.2pp | +5.3pp | 65.5% | 37.1% | 34 | **ADVISORY_ONLY** |
| Suppress VP<0.30 | 210 | 31.4% | 70.5% | -17.6% | +11.7pp | +18.8pp | 29.1% | 75.1% | 76 | **KEEP** |
| Suppress midprice noRouter | 417 | 23.5% | 51.1% | -14.8% | +3.8pp | -0.6pp | 57.8% | 44.9% | 44 | **ADVISORY_ONLY** |
| Suppress longshot (SP>16) | 626 | 22.2% | 57.2% | -23.7% | +2.5pp | +5.5pp | 86.8% | 15.9% | 3 | **ADVISORY_ONLY** |

---

## Shadow Policy Candidates

- **VP>=0.30 + MDS>0.50**: SR=66.7% (Δ+47.0pp), n=21
- **VP>=0.30 + IMP>0.40**: SR=50.0% (Δ+30.3pp), n=22
- **VP>=0.30 + Router**: SR=37.0% (Δ+17.3pp), n=27
- **VP>=0.30 + Midprice_Suppress**: SR=39.6% (Δ+19.9pp), n=139
- **VP>=0.40 only**: SR=43.8% (Δ+24.1pp), n=73
- **VP>=0.40 + TierA**: SR=44.8% (Δ+25.1pp), n=67

## Governance

No scoring/model/staking/router changes. Advisory only.

*SIGMA_2K_FEATURE_ABLATION_AUDIT_V1 — sigma_2k_feature_ablation_audit.py*