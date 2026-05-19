# VELO Horse Memory Arena Join — V1

**Status:** ACTIVE  
**Commit:** feat(memory): join horse career memory into model arena features  
**Date:** 2026-05-18

---

## What Was Done

Horse career memory was joined into the model arena V2 training pipeline as a leakage-free rolling feature set (`HORSE_MEMORY`). The join is implemented in `scripts/train_velo_model_arena_v2.py` via `build_rolling_horse_memory()`.

---

## Leakage-Free Rolling Construction

For each row at race date D, career statistics are computed using only races with date < D (strictly prior). No current-race data is used to compute prior stats.

**Rolling features produced per runner:**

| Feature | Description |
|---|---|
| `prior_starts` | Count of starts before this race |
| `prior_win_rate` | Win rate (wins / starts) before this race |
| `prior_frame_rate` | Frame rate (frame / starts) before this race |
| `prior_avg_vp` | Mean velo_prime_prob from prior races |
| `prior_avg_mds` | Mean market_deception_score from prior races |
| `prior_avg_improvement` | Mean improvement_score from prior races |
| `prior_mds_high_events` | Count of races where MDS ≥ 0.5 |
| `prior_vp_ge_30_events` | Count of races where VP ≥ 0.30 |
| `prior_vp_ge_40_events` | Count of races where VP ≥ 0.40 |
| `prior_improvement_high_events` | Count of races where improvement_score ≥ 0.4 |

Rows with zero prior starts receive NaN for rate features (filled with 0 for training). All values are computed at expansion time — no look-ahead possible.

---

## V2 Arena Results — HORSE_MEMORY Feature Set (win target)

| Model | Brier | AUC |
|---|---|---|
| logistic | 0.173405 | 0.509 |
| xgboost | 0.173684 | 0.486 |
| catboost | 0.173989 | 0.513 |
| lightgbm | 0.175243 | 0.510 |
| random_forest | 0.175602 | 0.516 |

**Verdict:** All AUC near 0.50 — no signal at current corpus size.

---

## Expected Behaviour

The corpus averages ~1.05 prior starts per horse (seed layer). With so few observations per horse, rolling career stats carry no discriminative signal. This is the expected result.

**At 2K corpus milestone:** Re-run arena. Horse memory feature set expected to gain predictive power as careers deepen (3–5+ starts per horse average). Monitor `prior_starts` distribution at next retraining.

---

## Source Scripts

- **Rolling join:** `scripts/train_velo_model_arena_v2.py` → `build_rolling_horse_memory()`  
- **Standalone memory build:** `scripts/build_horse_career_memory.py` (V2 extended with `best_vp_seen`, `latest_rpdc_tags`, `third_run_candidate_flag`, etc.)  
- **RPDC tagger:** `scripts/build_rpdc_horse_tags.py`

---

## Hard Rules

- `prior_*` features may NOT include data from the current race row.
- Training cutoff must be respected: features are computed on train split only.
- SP (`sp_decimal`) must NOT appear in any feature set — historical context only.
