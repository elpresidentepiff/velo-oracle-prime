# VÉLØ Ingestion Sequencing Hardening

**Status:** ACTIVE MITIGATION | **Revision:** 2026-04-18.01

This document defines the "Structural Ingestion Sequencing Bug" and the implemented mitigation path to ensure VÉLØ truth remains current.

---

## 1. The Measured Risk: 06:00 UTC Divergence
Audit performed on 2026-04-18 on a sample of A/B tier races:
- **Mutation Rate:** **34.0%** (Field size changed between 06:00 UTC and race results).
- **Performance Impact:** 
  - Clean Races: **36.4% Strike Rate**
  - Mutated Races: **23.5% Strike Rate**
- **Conclusion:** Field mutation degrades edge by ~35%. This is a fatal risk for high-stakes execution.

---

## 2. Phase 1: Honesty Labeling (Implemented)
The system now explicitly tracks the "Ground Shift":
- **`fetch_timestamp`**: Persisted in `velo_verdicts` to mark the "Standard" fetch time.
- **`predicted_field_size`**: Persisted at scoring time.
- **`actual_field_size`**: Reconciled by Sigma Loop from official results.
- **`field_mutated` (bool)**: Flagged in `velo_post_race_reviews` for downstream learning.

---

## 3. Phase 2: Smallest Mitigation (Implemented)
**The Mutation Monitor (`workers/mutation_monitor.py`):**
- **Target:** A-STRIKE races only.
- **Trigger:** 15 minutes before the off.
- **Logic:** Re-fetches the field and re-scores.
- **Fail-Fast Alert:** Sends a Telegram `⚠ MUTATION ALERT` only if:
  - The Top Pick has shifted (CRITICAL).
  - The Field Size has changed.
  - The Top Pick probability has materially shifted (> 0.05).

---

## 4. Hardening Ledger Update
- **Ingestion Sequencing Bug:** VERIFIED HONESTY LABELS.
- **Mitigation Status:** ACTIVE (A-Tier Monitor deployed).
