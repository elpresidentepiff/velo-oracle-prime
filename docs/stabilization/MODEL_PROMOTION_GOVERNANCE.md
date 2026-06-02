# MODEL PROMOTION GOVERNANCE

This document outlines the strict criteria and procedures for promoting components from Shadow to Live Production.

## 1. Promotion Criteria

| Metric | Minimum Requirement | Verification Source |
| :--- | :--- | :--- |
| **Sample Size (General)** | n ≥ 300 races (or n ≥ 500 runners). | `sigma_audits` (Supabase) |
| **Sample Size (Policy)** | n ≥ 150 top-pick lane decisions. | `policy_lane_ledger.jsonl` |
| **Sample Quality (Policy)** | n ≥ 50 HIGH confidence outcomes. | `policy_lane_ledger.jsonl` |
| **Lane Specifics** | WIN_TRUST / FRAME_TRUST must show statistically significant lift. | `policy_lane_ledger.jsonl` |
| **Edge Stability** | No `RuntimeError` or `NaN` in 30 days of shadow. | `error_logs` |
| **AUC Improvement** | Challenger AUC > Champion AUC + 0.02. | `challenger_v1_promotion_review` |
| **Calibration** | Predicted vs Empirical SR within 5%. | `sigma_calibration_report` |
| **Safety Guard** | `forbidden_import_check` must PASS. | `app/core/safety_guards.py` |

## 2. Decision Hierarchy

1. **Evidence Accumulation:** Component runs in `SHADOW_ONLY` mode for a full evaluation cycle.
2. **Audit Report:** Forensic audit agent generates a `Promotion Review` document.
3. **Operator Approval:** The System Architect reviews the Audit Report and sets the `VELO_ENSEMBLE_PROFILE` or `VELO_G_SHADOW_MODE` flag.
4. **Promotion Commit:** The ensemble weights are updated in `src/intelligence/velo_prime_ensemble.py`.

## 3. Rollback Procedure

All promotions must be reversible within 15 minutes:
*   **Layer 1 (Config):** Revert the environment variable (e.g., `VELO_ENSEMBLE_PROFILE=LEGACY`).
*   **Layer 2 (Git):** Revert the promotion commit if Config Layer fails.
*   **Verification:** Run the `ROLLBACK_VERIFICATION_CHECKLIST.md`.
