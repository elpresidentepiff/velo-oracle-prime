# VÉLØ Feature Delta Leaderboard

**Status:** DEFINED | **Scope:** Post-Training Feature Weight Adjustments

This leaderboard ranks the features that repeatedly fool the model (Overtrusted) against the features the model repeatedly ignores on true winners (Underweighted).

---

## 1. Overtrusted Features (Causes of False Rank-1)

These features dominated the Rank-1 profiles in races we lost:
1. **`top_horse_readiness_state` (Recent Run)**: Overvalued in the mid-price zone. The model assumes a recent good run equals current fitness, ignoring regression.
2. **`favourite_trap_risk` (Low Risk)**: The model trusts the market favourite too heavily in 5-8 SP bands when `prob_gap` is tight.
3. **`speed_figure_raw`**: Overtrusted on AW tracks without applying a relative track-bias penalty.

## 2. Underweighted Winner Features (The Blindspot Eyes)

These features were present in the actual winners but under-scored by the model:
1. **`draw_bias_geometry` (Inside Draw on Tight Tracks)**: Consistently present in `blindspot_winner_outside_top5` cases. The model does not penalize wide draws heavily enough.
2. **`substrate_mismatch` (Going Shift)**: Winners often have a proven history on the exact day's going, whereas our false Rank-1 has raw speed but no ground proof.
3. **`trainer_intent_heat` (Shadow Trainers)**: Sudden drops in class or specific jockey bookings by lower-tier trainers that indicate a "Cash Run."

---

## 3. Retraining Priority
In the next model update, **Draw Geometry** and **Substrate Mismatch** must be introduced as explicit penalties (negative multipliers) rather than passive linear features.
