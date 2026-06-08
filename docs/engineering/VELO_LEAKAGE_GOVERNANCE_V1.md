# VÉLØ LEAKAGE & BIAS-VARIANCE GOVERNANCE V1

Generated: 2026-06-03 | Status: LOCKED | Author: Operator

This document establishes the permanent banned feature list for all morning models (Old VÉLØ SQPE and New Build Challenger). Any feature matching these criteria is strictly prohibited from entering the training corpus or live scoring vector.

## 1. Permanent Banned Feature List

### A. Outcome Leakage
**Banned Substrings:** `result`, `pos`, `won`, `finish`
**Reason:** These features represent the target variable itself. Including them allows the model to "peek" at the future, resulting in artificially inflated AUC during training (1.0) and catastrophic failure in live execution.

### B. Same-Race Market Leakage (SP-Derived)
**Banned Substrings / Exact Matches:** `sp_dec`, `log_sp`, `implied_prob`, `sp_rank`, `is_fav`, `bsp`
**Reason:** Morning models are scored at 09:00 AM. The Starting Price (SP) and Betfair SP (BSP) are not known until the race starts. Training a morning model on SP creates a severe temporal leak, as the model learns to rely on market information it will not have access to at runtime. 
*(Note: Historical SP features, such as `pp_avg_sp_last5`, are permitted as they represent strictly past market data).*

### C. Third-Party Proprietary Leakage
**Banned Substrings:** `rpr`
**Reason:** Racing Post Ratings (RPR) are generally prohibited from acting as model inputs to prevent intellectual property contamination and to force the model to discover independent edges.
**Old VÉLØ Exception:** `rpr_num` and `rpr_vs_field` are permitted in Old VÉLØ SQPE v17 under the `RPR_ACCEPTED` policy enacted 2026-06-03. This is a deliberate operator decision. These features remain strictly banned from New Build Challenger models.

## 2. Governance Enforcement

To prevent accidental leakage during feature engineering:
1.  **Automated Audit:** `scripts/ops/run_leakage_audit.py` scans all active feature sets (`EXPECTED_FEATURES` in `sqpe_v17_service.py` and `_feature_map` in `new_build_two_lane_score.py`).
2.  **Training Guardrails:** The Challenger V2 training script explicitly checks the feature list against `BANNED_IN_FEATURES` and raises an `AssertionError` if a violation is detected.

## 3. Current Audit Status
*   **New Build (Challenger V2/Lane B):** `CLEAN`
*   **Old VÉLØ (SQPE v17):** Contains legacy `sp_dec`, `log_sp`, `implied_prob`, `sp_rank`, `is_fav`, `rpr_num`, and `rpr_vs_field`. These are currently flagged as `FAIL` in the audit and represent the primary technical debt to be cleared in the next major Old VÉLØ refactor.
