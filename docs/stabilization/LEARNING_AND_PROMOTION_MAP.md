# LEARNING AND PROMOTION MAP

This document defines the various feedback and evolution loops in the VÉLØ Oracle Prime system, establishing clear boundaries between live production and shadow research.

## 1. Loop Taxonomy

| Loop Name | Purpose | Authority | Status |
| :--- | :--- | :--- | :--- |
| **Scoring Loop** | Real-time generation of probabilities and decision tiers for upcoming races. | `run_prime_today.py` | **ACTIVE (LIVE)** |
| **Results Reconciliation Loop** | Nightly matching of predictions against actual outcomes (Sigma). | `run_results_sigma.py` | **ACTIVE (LIVE)** |
| **Evidence Accumulation Loop** | Persistent logging of shadow model performance and candidate features (Sidecars). | `new_build_sidecar_feed_writer.py` | **ACTIVE (SHADOW)** |
| **Shadow Evaluation Loop** | Long-term tracking of "What-If" scenarios and G-shadow multipliers. | `sigma_audits` (Supabase) | **ACTIVE (SHADOW)** |
| **Promotion Review Loop** | Formal audit and decision gate to move a component from Shadow to Live. | Manual / Operator Review | **ACTIVE (GATED)** |
| **Live Model Update Loop** | Automated re-training or weight adaptation based on recent performance. | `auto_retrain.py` | **DISABLED** |

---

## 2. Component Classification

| Component | Status | Role | Rollback Path |
| :--- | :--- | :--- | :--- |
| **SQPE v17** | `LIVE_WEIGHTED` | Dominant probability anchor (Weight: 0.45). | `VELO_ENSEMBLE_PROFILE=LEGACY_FULL` |
| **Improvement Score**| `LIVE_WEIGHTED` | Specialist intent signal (Weight: 0.12). | `VELO_ENSEMBLE_PROFILE=LEGACY_FULL` |
| **Market Deception** | `LIVE_WEIGHTED` | Deception sidecar (Weight: 0.10). | `VELO_ENSEMBLE_PROFILE=LEGACY_FULL` |
| **Place Prob** | `LIVE_VISIBLE_ONLY` | Frame badge/card only; not weighted in VP. | N/A |
| **Longshot Score** | `FROZEN` | ROI underperformance; exclude from VP. | N/A |
| **Release Window** | `SHADOW_ONLY` | Captured but not applied to live scoring. | N/A |
| **Comment Intel** | `SHADOW_ONLY` | Captured but not applied to live scoring. | N/A |
| **Playbook G** | `SHADOW_ONLY` | Sentient multiplier computed but NOT applied. | N/A |
| **NO_VP Composite** | `SHADOW_ONLY` | Challenger profile under evaluation (n<300). | N/A |

---

## 3. Implementation Honesty
*   **Autonomous Learning:** The system **does not** autonomously update its live weights or models. Learning occurs in shadow "Sentinel" loops and is only promoted after manual operator verification.
*   **Sentient Control:** Playbook G's "Emotion Engine" is an audit/suppression tool currently restricted to shadow evaluation.
