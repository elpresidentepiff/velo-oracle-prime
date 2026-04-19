# VÉLØ Doctrine Subgroup Audit

**Revision:** 2026-04-18.02 | **Status:** DAY ZERO BASELINE (RESTORED)

This document establishes the initial performance baseline for VÉLØ's doctrine subgroups and evaluates whether restored features are ready for effectiveness auditing.

---

## 1. Restored Feature Census (Honesty Pass)
Audit of the latest 100 reconciled races following the persistence fix:

- **`cash_run_flag` Coverage:** **0%** (n=0)
- **`setup_run_flag` Coverage:** **0%** (n=0)
- **`decoy_support_flag` Coverage:** **0%** (n=0)

**Verdict:** **NOT READY FOR EFFECTIVENESS AUDIT.** 
While end-to-end survival is proven in code, the production corpus lacks sufficient flag-bearing rows to measure signal strength. We are in the "Observation Phase."

---

## 2. Structural Subgroup Baseline (n=784)
Using the current trusted reconciled corpus to anchor future audits.

### Tier Performance (Strike Rates)
- **Tier A (A-STRIKE):** **41.7%** (Gold Standard)
- **Tier B (B-PLAYABLE):** **22.7%**
- **Tier X (X-CHAOS):** **13.8%**

### Calibration (Confidence Brackets)
- **HIGH Confidence:** **30.8%** Win Rate / **84.6%** Place Rate
- **MEDIUM Confidence:** **37.5%** Win Rate / **62.5%** Place Rate
- **LOW Confidence:** **19.6%** Win Rate / **44.9%** Place Rate

---

## 3. High-Risk Pockets (Silent Splits)
Based on miss taxonomy, the following subgroups represent the highest risk to truth:
1. **Market Decoys (n=167):** Top pick followed a false market signal.
2. **Mutation Impact (Est. 34%):** Performance likely degrades by ~35% in mutated fields (to be proven with new honesty labels).

---

## 4. Next Frontier: The 100-Race Gate
The system will transition to an **Effectiveness Audit** only after **100 flag-bearing races** have been reconciled with active `cash_run_flag` data.

### Required Actions:
- **Daily Rebuild:** Execute `scripts/build_training_dataset.py` every 24h to monitor flag arrival.
- **Trigger Check:** Ensure live Railway scoring is actually using the latest `main` to populate these flags.
