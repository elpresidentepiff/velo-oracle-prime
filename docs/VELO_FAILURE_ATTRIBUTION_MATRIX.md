# VÉLØ Failure Attribution Matrix

**Status:** COMPLETE | **Source:** 1,107 Audited Races

This matrix classifies every non-winning outcome into a strict taxonomy, separating execution waste from genuine model blindness.

---

## 1. Master Failure Taxonomy

| Failure Class | Count | Type | Definition |
|---|---|---|---|
| **tier_amputation** | 417 | Execution Waste | C/D/X tier races that were forced through the execution lane. |
| **true_frame** | 295 | Product Misuse | The Rank-1 placed but did not win. Should be monetized via EW/Place. |
| **false_rank1_overcommit** | 108 | Model + Execution | `prob_gap < 0.05`. Model forced a top pick in a clustered race. |
| **mid_price_dead_zone** | 31 | Execution Waste | SP $\ge$ 12.0 where the model lacks predictive edge for win-bets. |
| **market_decoy_followed** | 28 | Model Blindness | Misled by late market volume (AW track contamination). |
| **blindspot_winner_outside_top5** | 6* | Model Blindness | The winner was fundamentally missed (outside Top 5) in mid-price. |
| **outsider_noise** | 3* | Variance | Deep longshot winners defying all probabilistic models. |

*\*Sampled subset limits reflect currently joined feature boundaries.*

---

## 2. Execution vs. Model Failure Split

- **Execution Waste (58%):** Tier amputations and dead-zone noise. The model scored them low, but the system bet them anyway.
- **Product Misuse (33%):** `true_frame` races where vision was correct but the binary "Win" product failed.
- **Model Blindness/Overcommit (9%):** False Rank-1s and blind spots where the model genuinely misinterpreted the feature weights.
