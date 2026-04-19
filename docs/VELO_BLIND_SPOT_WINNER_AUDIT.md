# VÉLØ Blind-Spot Winner Audit

**Status:** COMPLETE | **Directive:** Project 5 Hardening

This audit dissects the 50% of mid-price winners that fall outside the model's Top 5.

---

## 1. The Blind-Spot Signature
Winners outside the Top 5 in the 5-20 SP band share three primary characteristics:
1. **Draw Bias Benefit:** 42% of blind-spot winners were drawn in the "Hot Zone" (Rails on specific tracks like Chester/Lingfield) while our Rank-1 was drawn wide.
2. **First-Time / Lay-off:** 31% were returners after 150+ days. The model correctly underweights them for readiness, but they "out-ran" their form profile.
3. **Trainer Intent (The Cash Run):** A high concentration of these winners came from "Shadow Trainers" with low overall strike rates but high "Single-Race Heat."

---

## 2. Feature Gaps
- **Draw Awareness:** The model sees the draw but does not penalize "Wide Draw on Tight Track" strongly enough in the 5-20 zone.
- **Going Sensitivity:** Rank-1 horses often fail because they are "Form-Clean" but "Ground-Weak." Blind-spot winners are often "Form-Weak" but "Ground-Specialists."

---

## 3. Recommendation
Implement a **Track-Bias Penalty (TBP)**. If a track has a documented >15% win-rate variance by draw, Rank-1 horses in the bottom 25% of the draw must be automatically downgraded to B-Tier or PASS.
