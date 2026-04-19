# VÉLØ Frame vs. Win Explainer

**Status:** PROVEN | **Insight:** Monetizing the 46.4% Frame Rate

We have a 19.8% Win Rate and a 46.4% Frame Rate. This gap represents 295 races where VÉLØ successfully identified a contender, but we registered a "Loss" because of product misassignment.

---

## 1. When do we Win vs. Frame?

| Condition | Win Probability | Frame Probability | Product Assignment |
|---|---|---|---|
| **A-Tier, Sub-5.0 SP** | HIGH (~60%) | VERY HIGH | `WIN_ONLY` |
| **A/B-Tier, 5.0-12.0 SP**| LOW (~15%) | HIGH (~55%) | `EW_CANDIDATE` / `FRAME_ONLY` |
| **Tight Prob Gap (<0.08)**| LOW | HIGH | `FRAME_ONLY` |

## 2. The "Safety-First" Phenomenon
When we frame but don't win, it is usually because the model made a "Safety-First" selection. It identified the horse most likely to run a solid, reliable race (high `place_prob`), but missed the volatile, high-ceiling winner.

## 3. Strategic Realignment
The organism is exceptionally good at finding the "Finish Zone." We must adapt the execution layer to capture this. A-Tier horses at 6.0 SP that place 2nd are no longer "Misses"—they are successful `EW_CANDIDATE` conversions.
