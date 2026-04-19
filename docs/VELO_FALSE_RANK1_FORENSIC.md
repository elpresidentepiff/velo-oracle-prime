# VÉLØ False Rank-1 Forensic

**Status:** COMPLETE | **Count:** 108 Races

This document investigates the `false_rank1_overcommit` failure class, where the model expressed HIGH confidence but lacked mathematical margin.

---

## 1. The Anatomy of an Overcommit
A "False Rank-1" occurs when the model forces a selection in a **Competitive Cluster**. 
- **Average Prob Gap:** $< 0.05$ (Rank-1 and Rank-2 are virtually tied).
- **SP Band:** Heavily concentrated in the 3.0 - 8.0 SP zone.

## 2. The Feature Illusion
Why does the model vote for Rank-1 in these clusters?
- **The Tie-Breaker:** When baseline stats are tied, the model defaults to the horse with the lower `market_deception_score` (the safer market play). 
- **The Reality:** In clustered races, the safer market play is often a decaying favourite, while the true winner is the Rank-2 or Rank-3 horse showing late `improvement_score` momentum.

## 3. Correction Law
We must stop forcing the model to pick a winner in a cluster. 
If `prob_gap < 0.08`, the race is automatically stripped of `WIN_ONLY` status and re-routed to `FRAME_ONLY` or `PASS`.
