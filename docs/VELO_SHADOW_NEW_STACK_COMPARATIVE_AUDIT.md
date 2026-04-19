# VÉLØ Shadow vs. Live Comparative Audit

**Revision:** 2026-04-19 | **Source:** 1,107-race Sigma truth vs. sqpe_v17 (Shadow)

This audit answers the adult question: Is the "New Stack" actually better, or just cleaner-looking?

---

## 1. Top-Line Delta (Overlapping Sample)

| Metric | Live (velo_prime_v1) | Shadow (sqpe_v17) | Delta |
|---|---|---|---|
| **Overall Strike Rate** | 20.5% | 16.2% | -4.3% |
| **High-Prob Strike (>0.4)** | 25.0% | 0.0% | -25.0% |
| **A-Tier Conversion** | 41.2% | 38.5% | -2.7% |
| **Frame Rate** | 48.0% | 45.2% | -2.8% |

---

## 2. Forensic Findings: Where Shadow Loses
The "Shadow Stack" (sqpe_v17) currently performs **worse** than the Live organism in every premium category. 
- **Conservative Bias:** Shadow probabilities are consistently lower, leading to fewer HIGH confidence selections.
- **Mid-Price Wound:** Shadow did NOT reduce the 5-20 SP leak. In fact, it underweighted several mid-price winners that Live correctly identified.
- **Flattening:** The "New Stack" has flattened the organism's sharpest edges in A-tier while maintaining the same blind spots in C/D tiers.

---

## 3. Promotion Judgment: **SHADOW-VALUABLE / NOT PROMOTE-READY**
The Shadow Stack is **not the savior**. It provides a "cleaner" data structure but at the cost of the model's "Outsider Eye" and A-tier precision. 

**Recommendation:** 
Keep sqpe_v17 as a **Regime-Specific Donor**. Use its probability as a "sanity check" (Sanity Penalty) for Live selections, but do NOT promote it to primary execution.
