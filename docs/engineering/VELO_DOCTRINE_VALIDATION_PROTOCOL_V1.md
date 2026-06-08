# VÉLØ Doctrine Validation Protocol — V1

**Status:** ACTIVE  
**Date:** 2026-05-29  
**Goal:** Ensure doctrine claims are made only after pre-registered, testable evidence.

---

## 1) Eligibility Gate

Validation starts only when all are true:

1. At least **100 reconciled flag-bearing races**
2. All key doctrine flags are present in the sample (`cash_run_flag`, `setup_run_flag`, `decoy_support_flag`)
3. Reconciliation integrity checks pass (no null-critical audit fields)

---

## 2) Pre-Registered Hypotheses

H1 — **Tier A Advantage**  
Tier A strike rate remains materially above global baseline over the validation window.

H2 — **Decoy Interception Utility**  
High MDS races show actionable interception behavior (WIN or PLACED outcomes at a meaningful rate).

H3 — **Doctrine-vs-Market Edge**  
Doctrine win rate exceeds market-top-pick win rate in the same evaluation window.

H4 — **Confidence Reliability**  
Confidence-band realized win rates remain within acceptable error from target calibration.

---

## 3) Pass/Fail Threshold Template

These values are the minimum declaration layer and can be tightened by future protocol revisions:

- Tier A strike rate: **>= 1.5x global strike rate**
- Doctrine edge: **>= +2.0 percentage points**
- Decoy interception: **>= 55% non-miss rate in MDS>=0.5 subgroup**
- Confidence reliability: **mean absolute calibration error <= 7.5 pp**

Any unmet threshold is a fail for claim issuance.

---

## 4) Confidence Interval Policy

For each headline metric, publish:

- point estimate
- confidence interval
- sample size
- exact window dates

No claim may be presented with point estimates alone.

---

## 5) Bias Controls

1. **No hindsight rule:** thresholds are fixed before analysis.
2. **No cherry-picking rule:** report full window and all key subgroups.
3. **No metric substitution:** if a metric fails, report failure instead of replacing with another metric.

---

## 6) Publication Contract

Every public/internal proof packet must include:

1. Gate status
2. Hypothesis table (Pass/Fail)
3. Metric values with intervals
4. Failure clusters and root-cause notes
5. Action plan before next window

