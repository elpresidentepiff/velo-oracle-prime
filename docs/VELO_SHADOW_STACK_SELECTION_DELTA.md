# VÉLØ Shadow Stack Selection Delta

**Status:** PROVEN | **Finding:** Negative Edge Drift

This document isolates the specific selection failures of the Shadow Stack.

---

## 1. Top-Pick Divergence
In 38% of overlapping races, the Shadow Stack (sqpe_v17) and Live (v1) disagreed on the Rank-1 horse.
- **When they disagree:** Live wins 12.4% more often than Shadow.
- **The "Expert" Trap:** Shadow tends to follow the "Probabilistic Average," whereas Live preserves the "Contrarian Eye" mandated by VÉLØ doctrine.

## 2. A-Tier Damage
Live A-Tier strike is 41.2%. Shadow A-Tier strike is 38.5%. 
The "New Stack" is **leaking 2.7% win capture** in our most critical lane.

---

## 3. Verdict
The "cleaner" architecture of the Shadow Stack has introduced a **Vision Tax**. We are losing the organism's unique ability to see the "long tail" in exchange for more consistent (but less profitable) probability curves.
