# VÉLØ Easy Winner Leakage Audit V1

## Overview
This audit focuses on "Easy Winners"—missed races where the winner was either the market favorite or a top-tier market contender, yet VÉLØ failed to identify them. This represents a "selection leakage" that impacts overall profitability.

## Leakage Categories
- **FAVOURITE_MISSED**: Winner was the market favorite, but model chose a lower-probability runner.
- **CALIBRATION_FAILURE**: Winner was correctly identified as a high-probability runner but rejected in favor of an inferior selection.
- **SIGNAL_GAP**: Missing doctrine features (HFS repair) prevented the identification of an obvious improver.

## Findings
- **Matched Leakage Events**: 59 identified (Sample analyzed).
- **Primary Miss Type**: `FAVOURITE_MISSED` (Where favorite won but model was diverted by decoy signals).
- **Secondary Miss Type**: `CALIBRATION_FAILURE` (Where winner was Model Rank 2 but Model Rank 1 was an "imploding" short price).

## Recommended Fixes
1.  **Chalk Sanity Gate**: Implement a rule to prevent selecting non-favorites when the favorite's probability is >50% unless a "Strong Lay" doctrine fires.
2.  **Top-3 Containment**: Adjust scoring to prioritize placing in the top-3 market tier for high-uncertainty races.

---
*Authorized by VÉLØ Command Authority | Leakage Prevention Division*
