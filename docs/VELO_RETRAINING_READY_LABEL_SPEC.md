# VÉLØ Retraining-Ready Label Spec

**Status:** SPECIFIED | **Use:** V2 Model Pipeline

When we eventually retrain, we cannot use binary Win/Loss labels on dirty data. We must use the **Honest Truth Labels**.

---

## 1. The V2 Label Schema

For every race in the training corpus, the following labels MUST be attached:

- `execution_quality`: [WASTE, PRODUCT_MISMATCH, OPTIMAL]
- `selection_quality`: [FALSE_RANK1, TRUE_VISION, BLINDSPOT]
- `winner_visibility`: [TOP_2, TOP_5, OUTSIDE]
- `frame_capture_possible`: [BOOLEAN]
- `product_should_have_been`: [WIN, EW, PLACE, PASS]
- `blindspot_type`: [GEOMETRY, SUBSTRATE, INTENT, NONE]
- `retrain_include_yes_no`: [BOOLEAN]

## 2. The Exclusion Law
Any race marked `execution_quality = WASTE` (e.g., C/D tier races we never should have bet) or `blindspot_type = GEOMETRY` MUST BE EXCLUDED from the primary win-prediction training pass. 

*We cannot train the model to predict a winner that was decided by a track bias the model cannot currently see.*
