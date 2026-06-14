# Pre-Surgery Sigma Study Plan
## VÉLØ Oracle Prime — Mar–Apr 2026 Archive

**Status**: PLAN ONLY — no execution, no writes, no merge
**Generated**: 2026-06-14

---

## Why Separate

The May 08 2026 Ensemble Surgery v1 changed VP calibration. A VP of 0.40 in March may not equal a VP of 0.40 in June. Blending these eras without validation would corrupt gate threshold calibration.

---

## What We Know

| Field | Value |
|---|---|
| Mar–Apr Supabase rows | 1,271 |
| VP extractable | 1,061 (83.5%) |
| Notes format | Plain string `pred=Horse prob=0.XXXX AT BASELINE — ...` |
| verdict_score column | Present (Mar 19–Apr 23, n=363) — NOT VP |

---

## Era Tag

Every extracted row must carry:
```
era: PRE_SURGERY_ARCHIVE
era_date_range: 2026-03-01 to 2026-04-30
surgery_date: 2026-05-08
```

**No PRE_SURGERY_ARCHIVE row may enter CURRENT_ERA without explicit operator approval.**

---

## Study Steps (Read-Only)

1. Extract VP from Mar–Apr notes via regex `prob=([\d.]+)`
2. Build same VP threshold table as current era
3. Compare to current-era distribution (mean VP, VP>=0.40 pct, baseline SR)
4. Build era-separate course table
5. Declare verdict: ERA_CALIBRATION_COMPATIBLE / MARGINAL / INCOMPATIBLE

---

## Verdict Criteria

| Verdict | Condition |
|---|---|
| ERA_CALIBRATION_COMPATIBLE | VP>=0.40 SR within ±5pp of current-era 41.5% |
| ERA_CALIBRATION_MARGINAL | Diverges 5–10pp — merge with caution |
| ERA_CALIBRATION_INCOMPATIBLE | Diverges >10pp — keep permanently separate |

---

## Trigger Condition

Run ONLY after:
1. Current-era union (1,263 rows) validated in dry-run for 14+ days
2. Operator explicitly approves study

**Do not merge Mar–Apr with current era without completed study and operator sign-off.**

---

*PRE_SURGERY_SIGMA_STUDY_PLAN — Not executed — 2026-06-14*
