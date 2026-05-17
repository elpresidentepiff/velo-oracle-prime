# SIGMA 2K FEATURE ABLATION AUDIT V1
**Run:** 2026-05-17 12:30 UTC
**Training rows:** 1310
**Global SR baseline:** 19.7%

---

## Full Results

| Family | n | SR | Frame | ROI | SR Δ | Frame Δ | Coverage | FP Red | W Lost | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| BASE: All corpus | 1310 | 20.9% | 51.1% | -17.2% | +1.2pp | -0.6pp | 100.0% | 0.0% | 0 | **ADVISORY_ONLY** |
| VP>=0.30 only | 399 | 34.3% | 70.7% | +1.6% | +14.6pp | +19.0pp | 30.5% | 74.7% | 137 | **KEEP** |
| VP>=0.30 + MDS>0.50 | 39 | 69.2% | 92.3% | -7.2% | +49.5pp | +40.6pp | 3.0% | 98.8% | 247 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + IMP>0.40 | 38 | 42.1% | 76.3% | -36.3% | +22.4pp | +24.6pp | 2.9% | 97.9% | 258 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + Router | 32 | 34.4% | 78.1% | +3.5% | +14.7pp | +26.4pp | 2.4% | 98.0% | 263 | **KEEP** |
| VP>=0.30 + RP_Conv_HIGH | 399 | 34.3% | 70.7% | +1.6% | +14.6pp | +19.0pp | 30.5% | 74.7% | 137 | **KEEP** |
| VP>=0.30 + CASHRUN_WATCH | 399 | 34.3% | 70.7% | +1.6% | +14.6pp | +19.0pp | 30.5% | 74.7% | 137 | **KEEP** |
| VP>=0.30 + Midprice_Suppress | 265 | 42.3% | 75.8% | +8.2% | +22.6pp | +24.1pp | 20.2% | 85.2% | 162 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + TierA | 236 | 37.3% | 72.0% | +9.8% | +17.6pp | +20.3pp | 18.0% | 85.7% | 186 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.30 + TierA_or_B | 379 | 34.6% | 70.7% | +3.9% | +14.9pp | +19.0pp | 28.9% | 76.1% | 143 | **KEEP** |
| VP>=0.30 + suppress_TierC | 388 | 34.5% | 70.9% | +3.3% | +14.8pp | +19.2pp | 29.6% | 75.5% | 140 | **KEEP** |
| VP>=0.30 + MDS>0.50 + IMP>0.40 | 17 | 58.8% | 88.2% | -18.9% | +39.1pp | +36.5pp | 1.3% | 99.3% | 264 | **INSUFFICIENT_SAMPLE** |
| VP>=0.30 + MDS>0.50 + Router | 1 | 100.0% | 100.0% | +110.0% | +80.3pp | +48.3pp | 0.1% | 100.0% | 273 | **INSUFFICIENT_SAMPLE** |
| VP>=0.30 + Router + TierA | 16 | 31.2% | 81.2% | -8.8% | +11.5pp | +29.5pp | 1.2% | 98.9% | 269 | **INSUFFICIENT_SAMPLE** |
| Full stack: VP30+MDS+IMP+Router | 6 | 16.7% | 100.0% | -65.0% | -3.0pp | +48.3pp | 0.5% | 99.5% | 273 | **INSUFFICIENT_SAMPLE** |
| VP>=0.40 only | 150 | 45.3% | 80.7% | +8.2% | +25.6pp | +29.0pp | 11.5% | 92.1% | 206 | **SHADOW_POLICY_CANDIDATE** |
| VP>=0.40 + Router | 11 | 36.4% | 81.8% | -5.9% | +16.7pp | +30.1pp | 0.8% | 99.3% | 270 | **INSUFFICIENT_SAMPLE** |
| VP>=0.40 + TierA | 132 | 44.7% | 80.3% | +9.4% | +25.0pp | +28.6pp | 10.1% | 93.0% | 215 | **SHADOW_POLICY_CANDIDATE** |
| Compression suppress | 1288 | 21.1% | 51.0% | -17.0% | +1.4pp | -0.7pp | 98.3% | 1.9% | 2 | **ADVISORY_ONLY** |
| Suppress TierC | 1078 | 22.4% | 52.1% | -11.6% | +2.7pp | +0.4pp | 82.3% | 19.2% | 33 | **ADVISORY_ONLY** |
| Suppress VP<0.20 | 847 | 25.0% | 58.0% | -13.0% | +5.3pp | +6.3pp | 64.7% | 38.7% | 62 | **ADVISORY_ONLY** |
| Suppress VP<0.30 | 399 | 34.3% | 70.7% | +1.6% | +14.6pp | +19.0pp | 30.5% | 74.7% | 137 | **KEEP** |
| Suppress midprice noRouter | 765 | 24.4% | 50.3% | -13.0% | +4.7pp | -1.4pp | 58.4% | 44.2% | 87 | **ADVISORY_ONLY** |
| Suppress longshot (SP>16) | 1128 | 23.7% | 56.9% | -15.8% | +4.0pp | +5.2pp | 86.1% | 16.9% | 7 | **ADVISORY_ONLY** |

---

## Shadow Policy Candidates

- **VP>=0.30 + MDS>0.50**: SR=69.2% (Δ+49.5pp), n=39
- **VP>=0.30 + IMP>0.40**: SR=42.1% (Δ+22.4pp), n=38
- **VP>=0.30 + Midprice_Suppress**: SR=42.3% (Δ+22.6pp), n=265
- **VP>=0.30 + TierA**: SR=37.3% (Δ+17.6pp), n=236
- **VP>=0.40 only**: SR=45.3% (Δ+25.6pp), n=150
- **VP>=0.40 + TierA**: SR=44.7% (Δ+25.0pp), n=132

## Governance

No scoring/model/staking/router changes. Advisory only.

*SIGMA_2K_FEATURE_ABLATION_AUDIT_V1 — sigma_2k_feature_ablation_audit.py*