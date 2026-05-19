# VÉLØ SHADOW MODEL FORWARD GATE

**Run at:** 2026-05-19T08:19:24.953662+00:00  
**Model:** NO_VP_COMPOSITE_logistic_win  
**Training cutoff:** 2026-05-10  
**Gate status:** `GATE_OPEN_ACCUMULATING`

---

## Gate Progress

| Gate | Required | Current | Met |
|---|---|---|---|
| Total runners | 300 | 246 | NO |
| Top-decile runners | 75 | 33 | NO |
| Beats SQPE on forward | yes | YES | YES |

---

## Forward Metrics

| Metric | Value |
|---|---|
| Forward runners | 246 |
| Challenger Brier (win) | 0.16866 |
| SQPE Brier (same window) | 0.2140053038571429 |
| Brier delta | -0.045345 |
| Challenger AUC | 0.626786 |
| Top-decile SR | 0.4545 |
| ROI (full) | 0.025 |
| ROI (top decile) | -0.2731 |

---

## Promotion Gate Rules (see VELO_CPU_SHADOW_MODEL_PROTOCOL_V1.md)

1. Beats SQPE Brier on forward 300 runners
2. Improves win SR by decile vs naive
3. Does not degrade frame layer
4. Positive or neutral ROI after outlier stripping
5. No subgroup collapse
6. Reproducible training
7. No Sentinel violations
8. Human approval required

---

## Governance

```
No scoring change. No production promotion.
Training cutoff immutable. Forward data only.
Gate requires operator approval at every threshold.
```