# VÉLØ Refinement Action Board

**Status:** ACTIVE | **Next Action Identified**

This board translates the Post-Training Truth Explainer into surgical engineering tasks.

---

## 1. Priority Refinement Ladder

1. **[IMMEDIATE] Product Routing Engine:** Build the logic layer that reads a verdict and outputs `[WIN_ONLY, FRAME_ONLY, EW_CANDIDATE, PASS]`.
2. **[IMMEDIATE] Geometry & Substrate Blockers:** Hard-code the Chester/Lingfield draw penalties and the Heavy/Soft going blockers.
3. **[DEFERRED] Feature Engineering:** Add `draw_advantage_score` and `going_affinity_index` to the V2 model training data.
4. **[BLOCKED] Shadow Promotion:** `sqpe_v17` remains a donor; it will not be promoted to live execution.

---

## 2. The Single Highest-Value Move
**Deploy the Product Assignment Router.** 
We must stop executing `FRAME_ONLY` races as `WIN_ONLY` bets. Implementing this routing layer will instantly align our execution with our actual vision.
