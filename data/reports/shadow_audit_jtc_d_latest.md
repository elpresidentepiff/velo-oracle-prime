# SHADOW AUDIT — JTC-D Full-Field Rank Analysis (V2)

**Date range:** 2026-03-17 → 2026-05-17  |  **Races:** 1704

Full-field rank analysis — all runners per race from results JSONs.
JTC-D signals applied to every runner. VP not included (only sigma horses have VP scores).
Shadow analysis only. No scoring change. No live mutation.

**Field average chance baseline:** 10.1% (1/avg field)
**VÉLØ sigma win rate (reference):** 20.9% (separate test)

---

## JTC-D Method Comparison (full field, min 3 runners/race)

| Method | Races | #1 Hit% | vs Chance | Top-3% | MRR | Flat ROI |
|---|---|---|---|---|---|---|
| `trainer_course_sr` | 1407 | **21.3%** | +11.2pp | 50.0% | 0.4180 | +1.8% |
| `jockey_course_sr` | 1485 | **21.3%** | +11.2pp | 49.9% | 0.4174 | -0.1% |
| `trainer_jockey_sr` | 1186 | **24.9%** | +14.8pp | 57.3% | 0.4632 | +18.6% |
| `tc_jc` | 1603 | **19.9%** | +9.8pp | 48.1% | 0.4053 | -13.8% |
| `tc_jc_tj` | 1608 | **20.3%** | +10.2pp | 47.5% | 0.4059 | -14.3% |
| `full_jtcd` | 1645 | **20.2%** | +10.1pp | 48.0% | 0.4052 | -19.1% |

---

## Signal Lift — VÉLØ Candidates (winners vs non-winners)

n_candidates: 1272 | winners: 264

| Signal | Winner Mean | Non-Winner Mean | Lift | Coverage |
|---|---|---|---|---|
| `velo_prime_prob` | 0.3201 | 0.2453 | **+0.0748** | 100% |
| `trainer_course_sr` | 0.1505 | 0.1278 | **+0.0227** | 76% |
| `jockey_course_sr` | 0.1438 | 0.1223 | **+0.0215** | 87% |
| `trainer_jockey_sr` | 0.1563 | 0.1290 | **+0.0273** | 67% |
| `trainer_dist_sr` | 0.1504 | 0.1239 | **+0.0265** | 78% |
| `jockey_dist_sr` | 0.1349 | 0.1199 | **+0.0149** | 91% |

---

## Breakdown (best signal: `trainer_jockey_sr`)

### By Race Type
| Race Type | Races | #1 Hit% | Top-3% | ROI |
|---|---|---|---|---|
| Chase | 120 | 25.0% | 62.5% | +22.7% |
| Flat | 778 | 24.7% | 54.2% | +19.4% |
| Hurdle | 250 | 23.2% | 60.8% | +13.0% |
| NH Flat | 38 | 39.5% | 81.6% | +25.3% |

### By Distance Category
| Distance | Races | #1 Hit% | Top-3% | ROI |
|---|---|---|---|---|
| sprint | 355 | 22.0% | 53.0% | +13.9% |
| mile | 300 | 25.3% | 54.3% | +10.3% |
| route | 531 | 26.6% | 62.0% | +26.4% |

---

## Summary Verdict

**JTC-D PREDICTIVE — best method (trainer_jockey_sr) at 24.9% vs 10.1% chance (+14.8pp). Consider deeper integration.**

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
SHADOW_AUDIT_ONLY — advisory only
```

*SHADOW_AUDIT_JTC_D_VS_SIGMA_V2 — full-field analysis*