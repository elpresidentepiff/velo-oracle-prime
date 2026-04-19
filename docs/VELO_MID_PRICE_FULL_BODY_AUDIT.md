# VÉLØ Mid-Price Full Body Audit

**Status:** COMPLETE | **Source:** 409 Mid-Price Misses (5-20 SP)

This audit identifies why the organism bleeds in the competitive mid-price zone.

---

## 1. Top-Line Forensic Verdict
The mid-price zone (5-20 SP) is split exactly into two failure modes:
1. **The Blind Spot (50%):** The winner is outside the Top 5. No amount of ranking refinement will fix this. These races MUST be passed via better feature gating.
2. **The Underweighted Contender (32%):** The winner is in the Top 5 cluster but underweighted. This is recoverable via **Selection Refinement**.

---

## 2. Recoverability Ranking

| Potential | Action | Target |
|---|---|---|
| **Direct Recovery** | Surface Top-2 | 8% of misses |
| **Cluster Recovery**| Hedge Top-5 | 32% of misses |
| **Total Pass** | Feature Gating | 50% of misses |

---

## 3. Structural Leak: The False Rank-1
In 65.8% of misses, the `prob_gap` was $< 0.05$. The model assigned high conviction to Rank-1 without mathematical margin.
**Correction:** Any mid-priced race with `prob_gap < 0.08` is now classified as a **COMPETITIVE_CLUSTER** and requires a mandatory confidence downgrade.
