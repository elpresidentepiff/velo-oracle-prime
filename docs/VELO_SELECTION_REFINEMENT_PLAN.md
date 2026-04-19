# VÉLØ Selection Refinement Plan

**Status:** DEFINED | **Source:** Forensic Audit (1,107 Races)

We are moving from "Best Pick" to "Qualified Selection."

---

## 1. Selection Tier Policy

| Tier | Status | Trusted Condition |
|---|---|---|
| **A** | **GOLD** | Always trustworthy if SP < 5.0. |
| **B** | **SELECTIVE**| Usable only if `prob_gap > 0.10` and `Confidence = HIGH`. |
| **C / X** | **BLOCKED** | Permanent pass until feature engineering refinement. |

## 2. Pass Logic: When the Model is Blind
A race MUST be passed if:
1. **Low Margin:** Rank-1 probability is $< 1.1x$ Rank-2.
2. **Decoy Cluster:** AW track with $> 30\%$ price movement on non-rank runners.
3. **Mid-Price Chaos:** SP between 5.0 and 20.0 with `Confidence < HIGH`.

## 3. The 1 Win 1 Place Hybrid
The data points toward a **Win-Heavy Lane (A-Tier)** and a **Place-Orientation Lane (B-Tier)**. 
- A-Tier: Maximize win capture.
- B-Tier: Maximize frame rate (78.2% in A-Tier, ~55% in B-Tier).
