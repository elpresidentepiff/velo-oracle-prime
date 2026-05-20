# VÉLØ Live Weight Profile Comparison

Corpus: 721 usable selections (won + SP confirmed)
Baseline n: 321 (Profile A, VP ≥ 0.25)

## Profile Results

| Profile | n | SR% | FR% | ROI% | Δ ROI vs A | Max DD | Lose Run | Avg SP | MDS>0.5 | IMP>0.3 | Top Sel Δ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A_CURRENT** | 321 | 26.48 | 64.49 | -24.38 | +0.00 | 84.33 | 16 | 6.06 | 6.5% | 15.6% | 0.0% |
| **B_CLEAN_VALUE** | 321 | 26.79 | 62.62 | -26.31 | -1.93 | 90.82 | 13 | 6.00 | 6.9% | 19.6% | 73.5% |
| **C_SQPE_MDS_ONLY** | 321 | 26.79 | 61.06 | -30.13 | -5.75 | 96.73 | 20 | 6.17 | 6.9% | 18.1% | 79.1% |
| **D_SQPE_ONLY** | 321 | 17.13 | 50.78 | -12.28 | +12.10 | 59.87 | 19 | 9.20 | 1.2% | 6.2% | 110.3% |

## Recommendations

- PROFILE_B → HOLD: ROI delta=-1.93pp | frame_ok=True | sr_ok=True
- PROFILE_C → HOLD: SQPE+MDS+place_prob delta=-5.75pp
- PROFILE_D → SQPE_ONLY_DOMINANT: ensemble sidecars collectively damaging — rebuild candidate. Gain +12.10pp

## Decision Rules Applied

- **B = PATCH_CANDIDATE** if: Δ ROI > +2pp AND frame_rate ≥ 70% of current AND |ΔSR| ≤ 3pp
- **C → SIDECAR_REDUCTION_URGENT** if: Δ ROI > +3pp
- **D → SQPE_ONLY_DOMINANT** if: D beats both B and C on ROI

## Hard Rules

- No live code changed.
- No SQPE changed.
- No router changed.
- No staking.
- No Telegram betting alert.
- Output is simulation evidence only.
- Weight changes require 30-day shadow proof before promotion.