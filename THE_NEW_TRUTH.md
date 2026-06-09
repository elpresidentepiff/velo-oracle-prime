# THE NEW TRUTH — VÉLØ ORACLE PRIME ARCHITECTURE
**Updated:** 2026-06-09  
**Status:** PRODUCTION BYPASS ACTIVE (June 9 Override)

This document details the exact ingestion, feature math, and model logic for the two lanes of the VÉLØ Oracle Prime system: **New Build (Ensemble)** and **Old Velo (RPD-C)**.

---

## 1. INGESTION LAYERS

### Lane A: New Build (Digital/API)
- **Source:** Racing Post HTML / Standard API.
- **Process:** `normalize_race` converts raw JSON/HTML into a canonical schema.
- **Bypass (June 9):** High-integrity PDF data (Brighton, Carlisle, Salisbury, Sligo, Southwell) was converted to `rp_merged` JSON.
- **Validation:** 90% metadata coverage required (Jockey, Trainer, Horse ID).

### Lane B: Old Velo (Paper/HTML Newspaper)
- **Source:** Racing Post "Newspaper Form" and "Postdata" sub-pages.
- **Storage:** `data/racing_post_account_raw/YYYY-MM-DD-newspaper-final/`.
- **Purpose:** Extracts "Spotlight" verdicts and "Postdata" grid signals that are not present in the standard digital card.

---

## 2. THE MATH: NEW BUILD ENSEMBLE (`velo_prime_v1`)

The final prediction score, `velo_prime_prob`, is a weighted average of individual component models, adjusted by macro-environmental factors and governed by the "G" doctrinal layer.

### A. Component Weights (`_WEIGHTS`)
The ensemble blends specialized signals:
| Component | Weight | Description |
| :--- | :--- | :--- |
| **SQPE v17** | **0.45** | Core Probability (The Value Anchor) |
| **Improvement Score** | **0.12** | Likelihood of outperforming current mark |
| **Market Deception (MDS)**| **0.10** | Detection of market manipulation/decoy shapes |
| **Place Prob** | **0.08** | Frame reliability |
| **Longshot Score** | **0.07** | High-odds outlier detection (applied if SP > 10.0) |

**Ensemble Formula:**
```math
Base\_Prob = \frac{\sum (Weight_k \times Score_k)}{\sum Weight_{active}}
```

### B. Specialist Model Features
#### Market Deception Score (MDS)
Calculated via `market_deception_model` using 12 features:
- `odds_resilience_score`, `odds_contraction_score`
- `rpr_vs_field`, `or_vs_field`
- `rating_mkt_gap` (RPR vs Implied Prob)
- `or_mkt_gap` (OR vs Implied Prob)
- `decoy_support_flag`, `mark_compression_score`

#### Improvement Model
Calculated via `improvement_model` using 12 features:
- `curr_or_minus_best_or`, `curr_or_minus_last_win_or`
- `runs_since_win`, `runs_since_place`
- `trainer_timing_score`, `distance_fit_score`, `course_fit_score`

---

## 3. THE MATH: OLD VELO (RPD-C)

The `RPD-C` engine assigns a deterministic Tag (**T, H, S, P, E**) based on the Intelligence Stack.

### A. The Hierarchy
1. **T (Target):** Intent to win. Required: 2+ Target evidence codes.
2. **P (Prep):** Fitness/Education run. Required: 2+ Prep evidence codes. **Blocked** if market is shortening.
3. **S (Speculative):** High uncertainty. Required: 1+ Speculative evidence codes.
4. **E (Exhausted):** Regressive profile. Required: 2+ Exhausted evidence codes. **Blocked** if won last time or market shortening.
5. **H (Honest):** Default. Assign if no other logic fires.

### B. Sample Evidence Rules
- **Campaign Fitness:** `run_number` between 3 and 6.
- **Near Winning Mark:** `current_vs_last_winning_or` between -8 and +5.
- **Post Drop Restore:** First run after a mark drop with winning conditions restored.

---

## 4. MACRO & G-SHADOW ADJUSTMENTS

### Macro Regime
- **Chaos Mode:** If active, probability is dampened by 20% toward a uniform distribution (`uniform = 1/field_size`).
- **Favourite Trap:** If market compression is high, the favourite receives a `-0.05` penalty.

### Playbook G (Doctrine Layer)
G applies multipliers based on historical performance of "Doctrines":
- **Multiplier Logic:** If G detects a `FAVOURITE_LIABILITY` (Story != Power), it applies a `0.93x` multiplier.
- **Pain Rules:** Specific `horse_id` penalties applied if they previously failed in high-pressure scenarios.

---

## 5. GOVERNANCE: PRODUCT ROUTER

Final verdicts are assigned to products via `route_verdict`:
- **Tier A/B + High Conf + Low SP (<5.0):** -> `WIN_ONLY` (Gold Standard).
- **Tier A/B + Mid SP (5-12):** -> `EW_CANDIDATE`.
- **Everything Else:** -> `VISION_ONLY` or `PASS`.

**DAY COMPLETE — TRUTH RECORDED.**
