# VÉLØ Strategic Recovery Plan: The Liberal Plot Engine

**Date:** April 20, 2026  
**Author:** Manus AI (CTO Mandate)  
**Context:** Based on the 1,107-race forensic audit, the system is bleeding edge in the mid-price dead zone. The current trainer intent engine is a non-functional stub. We must pivot from narrow, mechanical tier-gating to a liberal, plot-driven operating model that exploits the handicap system, education runs, and release-day signals using daily Spotlight intelligence.

---

## 1. The Core Problem: Why VÉLØ is Narrow and Bleeding

The forensic audit revealed that VÉLØ has a genuine edge (+0.086 probability separation, 41.2% A-tier strike rate), but it is being taxed out of profitability by bookmaker margins and a rigid, mechanical approach to the mid-market. 

The current trainer intent implementation (`feature_engineering.py`) is entirely broken. It relies on a hardcoded stub checking for two Australian jockeys and a generic gear change boolean. The `v9pm.py` intent layer merely divides trainer ROI by 20. While the newer `v17_feature_extractor.py` and `HorseStateEngine` have excellent foundations for detecting class drops, mark compression, and release windows, they are disconnected from the daily narrative intelligence required to confirm a handicap plot.

We need VÉLØ to be more **liberal** — not by betting more random horses, but by aggressively hunting and upgrading horses that fit the "handicap plot" profile, even if their base mechanical score (SQPE) is mediocre.

## 2. The New Strategic Blueprint: The Plot Engine

To achieve a liberal, high-yield operating model, we must fuse the existing `v17` mechanical features with daily natural language intelligence extracted from the Racing Post Spotlight PDFs.

### 2.1. The "Winning Mark" Concept (Handicap Plotting)
The British handicap system is designed to equalize chances, but trainers game it. A horse is given an Official Rating (OR). When it wins, the OR goes up. When it loses, the OR drops. 

A "handicap plot" occurs when a trainer deliberately runs a horse over the wrong distance, on the wrong ground, or half-fit (education runs) to drop its OR back to, or below, its last "winning mark."

**The new logic will track:**
*   **Current OR vs Last Winning OR:** If `current_or <= last_winning_or`, the horse is mathematically capable of winning.
*   **The Drop Sequence:** Detecting 3+ consecutive runs where the horse finished outside the top 4 and its OR dropped.
*   **The Release Trigger:** A sudden return to ideal conditions (distance/going), a jockey upgrade, or a specific gear application (first-time blinkers/visor).

### 2.2. Daily Spotlight Ingestion (The Intelligence Layer)
The Spotlight PDFs you provide contain the exact signals needed to confirm a plot. We will build a daily ingestion pipeline that parses the PDF and extracts these critical NLP flags:

*   **Gear Intent:** "first-time cheekpieces", "blinkers go on now", "hood added".
*   **Physical Intervention:** "gelded since", "returns having been gelded", "breathing surgery".
*   **Mark Confirmation:** "dropped down the weights", "3lb below that winning mark", "ahead of the handicapper".
*   **Education Completion:** "could be sharper for that experience", "open to improvement".

### 2.3. Education Runs vs Release Day
We will classify runs into two distinct categories using the `HorseStateEngine`:

*   **Education Run (`setup_run_flag`):** The horse is running to gain fitness, experience, or to drop its OR. Winning is not the primary objective. The market will often be weak (drifting), and the jockey will not be aggressive.
*   **Release Day (`cash_run_flag`):** The OR has dropped to the target mark. The trainer applies intent (gear, top jockey). The market may show quiet support. This is the day we strike.

## 3. Execution Plan: Rebuilding the Intent Architecture

### Phase 1: Spotlight PDF Parser (The Ingestion Spine)
We will build a dedicated parser for the daily Spotlight PDFs (`workers/ingestion_spine/racingpost_pdf/spotlight_parser.py`). This parser will extract the free-text comments and map them to our intent signals using regex and keyword matching.

### Phase 2: The Plot Feature Extractor
We will upgrade `v17_feature_extractor.py` to calculate the exact OR delta.
*   `or_delta_to_win` = `current_or` - `last_winning_or`
*   If `or_delta_to_win <= 0`, flag as `near_winning_mark`.
*   If `or_delta_to_win <= -3`, flag as `below_winning_mark` (High Plot Risk).

### Phase 3: Overhauling the TIE v3 Gate
We will rewrite `src/intelligence/tie_v3_gate.py` to be the core of our liberal strategy. Instead of relying on rigid mechanical scores, the gate will aggressively upgrade horses (C → B, or D → C) if they possess strong plot signals.

**New TIE v3 Gate Rules:**
1.  **The Classic Plot:** `below_winning_mark` + `gear_change_intent` (from Spotlight) = Immediate Tier Upgrade.
2.  **The Education Graduate:** 2+ recent `setup_run_flags` + `trainer_timing_score > 0.15` + return to ideal distance = Release Day Flag.
3.  **The Physical Reset:** "Gelded since last run" + `class_drop` = Intent Flag.

### Phase 4: Adjusting the Weights (Liberal Operating Model)
To make VÉLØ more liberal, we will adjust the ensemble weights in `config/weights.json` and the `v9pm.py` layer.
*   Decrease reliance on base form (`layer_1_form`). Form is deliberately hidden in a plot.
*   Increase weight on `layer_3_trainer_intent` (now powered by the new Plot Engine).
*   Increase weight on `layer_7_class_movement` and OR dynamics.

## 4. Summary and Next Steps

The old system looked for horses that were obviously good. The new system will look for horses that are deliberately hidden. By ingesting the daily Spotlight PDFs and focusing on the OR vs Winning Mark dynamic, VÉLØ will transition from a mechanical favorite-backer to a sophisticated handicap plot detector.

**Immediate Next Steps for Codebase Implementation:**
1.  Build the Spotlight PDF parser to extract the NLP intent signals.
2.  Implement the `last_winning_or` logic in the feature extractor.
3.  Rewrite the `TIEv3Gate` to upgrade tiers based on these new plot signals.
