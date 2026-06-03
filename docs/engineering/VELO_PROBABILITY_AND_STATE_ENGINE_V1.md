# VÉLØ PROBABILITY AND STATE ENGINE V1

This document specifies the architecture for the Markov Hidden-State Engine and Latent Concept Learning.

## 1. State Taxonomy

Defines the core horse racing states and their associated evidence signatures.

| State | Evidence Signature |
| :--- | :--- |
| **SETUP_RUN** | First run back from layoff, slight market drift, trainer known for patient placing, OR protected. |
| **CASH_RUN** | 2nd/3rd run back, sharp market move, jockey upgrade, OR unchanged or dropped. |
| **MARK_PROTECTION** | Running in below-peak class, OR hasn't moved despite wins, jockey retained. |
| **MARK_RELEASE** | Step up in class after long mark-freeze period, syndicate change or trainer intent signal. |
| **BOUNCE_RISK** | Career-best effort last run, heavy going, top weight, no rest. |
| **CONCEALED_FORM** | Poor finishing position but close-up early, ground excuse, barrier trouble. |
| **MARKET_TRAP** | Heavy SP shortening with low improvement score, public horse, class-level mismatch. |

## 2. Transition Rules

governs the valid sequence of latent states across a horse's campaign.

*   **SETUP_RUN → CASH_RUN:** Valid. Primary intent sequence.
*   **CASH_RUN → CASH_RUN:** Suspicious. Typically indicates a failure in the previous intent run or a "second string" attempt.
*   **BOUNCE_RISK → SETUP_RUN:** Valid. Campaign reset following peak effort.
*   **CONCEALED_FORM → CASH_RUN:** High Edge. The classic "hidden" winner sequence.

## 3. Latent Concept Targets

Defines the raw feature signals and sidecar output for unmodeled domain intelligence.

**MARK_READY_WITH_CONNECTION_INTENT**
*   **Signals:** `or_change_last3` flat + `jockey_continuity`=1 + `days_since_last` 30-60 + `class_moved_down`.
*   **Sidecar Output:** `latent_concept_mark_ready_flag`.

**DRIFT_TRAP**
*   **Signals:** `pp_avg_sp_last5` falling + `improvement_score` < 0.20 + `market_deception_score` < 0.10.
*   **Sidecar Output:** `latent_concept_drift_trap_flag`.

**CASH_RUN_CANDIDATE**
*   **Signals:** `setup_run_candidate`=True in previous race passport + current `pp_days_since_last` 14-28 + jockey retained.
*   **Sidecar Output:** `latent_concept_cash_candidate_flag`.

## 4. Validation Gate

```text
- No state or latent concept enters scoring until it has 30+ closed-outcome examples.
- All new concepts go to sidecar evaluation first.
- Statistical significance must be confirmed against the Calibration Baseline.
```
