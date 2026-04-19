# VÉLØ Blindspot Winner Regime Map

**Status:** MAPPED | **Source:** `blindspot_winner_outside_top5` Failures

Where is the model genuinely blind? This map identifies the specific regimes where the true winner evades our Top 5 entirely.

---

## 1. The Blindspot Clusters

1. **The Chester/Lingfield Geometry Trap**
   - **Signature:** Tight tracks, high field size.
   - **The Blindspot:** The model ignores the insurmountable disadvantage of a wide draw, selecting a "Fast" horse that gets boxed out, while a "Slower" horse on the rail wins.

2. **The "Mud-Lark" Substrate Anomaly**
   - **Signature:** Heavy/Soft going on Turf.
   - **The Blindspot:** The model highly ranks horses with excellent synthetic/firm form, completely missing the outlier horse whose only historical edge is in deep mud.

3. **The Shadow Trainer "Cash Run"**
   - **Signature:** Unheralded trainer, sudden jockey upgrade, massive SP contraction.
   - **The Blindspot:** The model's long-term rolling averages filter out the sudden, single-race intent of a targeted gamble.

## 2. Hard Blocker Implementation
We cannot "model" our way out of these without new features. We must implement **Hard Handbrakes**:
- Auto-pass wide draws on tight tracks.
- Auto-pass extreme going shifts.
