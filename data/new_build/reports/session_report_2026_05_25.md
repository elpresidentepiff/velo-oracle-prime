# New Build VÉLØ — Session Report
**Date:** 2026-05-25
**Branch:** codex/rp-archive-rpr-boundary
**Commits:** 25659a7 → 4357c65

---

## What This Session Did

Three promotions. One leakage catch. Full unseen-data proof pack for the new engine.

---

## 1. Core V0_OR Promoted to Champion

**Script:** `scripts/ops/new_build_promote_core_v0_or.py`
**Commit:** 25659a7

Previous champion was Core V0 (17 features, AUC=0.6735). Challenger Core V0_OR had already passed its gate in the previous session with decision `OR_FIX_CONFIRMED_AND_IMPROVES`.

**What changed:**
- Added `official_rating` (numeric OR, 0 for unrated horses)
- Added `is_rated` (binary flag)
- These fix the `or_rating = '–'` issue for ~41% of Flat runners (maidens, novices who are genuinely unrated)

**Result (val set, 11,650 races):**

| Metric | Core V0 | Core V0_OR | Delta |
|---|---|---|---|
| AUC | 0.6735 | 0.6777 | +0.0042 |
| Brier | 0.0861 | 0.0859 | −0.0002 |
| SR | 21.8% | 21.9% | +0.1% |
| Frame | 50.3% | 50.8% | +0.5% |

**Champion registry:** `data/new_build/models/champion/champion_registry.json`
**Report:** `data/new_build/reports/champion_promotion_latest.md`

---

## 2. Horse Passport Features Built

**Script:** `scripts/ops/new_build_passport_features.py`
**Input:** `data/raceform_v17_features.parquet` (1,702,741 rows)
**Output:** `data/new_build/training/passport_features.parquet`

Computed 11 horse-level lag features from sorted career history. All features use prior races only — no current-race leakage.

| Feature | Coverage | What it reads |
|---|---|---|
| `pp_career_runs` | 100.0% | Number of prior starts |
| `pp_win_rate` | 88.5% | Career win rate up to this race |
| `pp_place_rate` | 88.5% | Career place rate up to this race |
| `pp_days_since_last` | 88.5% | Days since previous race |
| `pp_layoff` | 88.5% | 1 if layoff >90 days |
| `pp_avg_sp_last5` | 88.5% | Mean SP of last 5 prior runs (historical) |
| `pp_jockey_continuity` | 88.5% | 1 if same jockey as last race |
| `pp_course_seen` | 100.0% | 1 if horse has run here before |
| `pp_or_change_3` | 44.7% | OR change over last 3 races |
| `pp_class_moved_up` | 88.5% | 1 if stepped up in class vs last run |
| `pp_class_moved_down` | 88.5% | 1 if dropped in class vs last run |

11.5% debut horses have NaN for most passport fields — expected and correct.

---

## 3. Four-Way Ablation: V0 / V0_OR / Passport-only / V0_OR+Passport

**Script:** `scripts/ops/new_build_ablation.py`
**Test set:** val split (11,650 races)

| Variant | Features | AUC | AUC Δ | SR | Frame |
|---|---|---|---|---|---|
| V0 | 17 | 0.6735 | −0.0042 | 21.8% | 50.3% |
| V0_OR (champion) | 19 | 0.6777 | +0.0000 | 21.9% | 50.8% |
| Passport-only | 11 | 0.6441 | −0.0336 | 21.4% | 50.2% |
| **V0_OR+Passport** | **30** | **0.6901** | **+0.0124** | **22.5%** | **52.8%** |

**Key finding:** Passport-only is weaker than Core V0. Horse history without race context is not enough. Horse history + race context is where the edge lives.

**Verdict:** `PASSPORT_ADDS_SIGNAL`

---

## 4. 2025 Unseen Test — Passport Challenger

**Script:** `scripts/ops/new_build_passport_2025_test.py`
**Test set:** 2025-01-01 → 2025-07-05 | 5,775 races | 57,221 runners (completely unseen)
**Commit:** 25659a7
**Report:** `data/new_build/reports/v0_or_passport_2025_unseen_test_latest.md`

| Variant | AUC | AUC Δ | Brier | SR | Frame |
|---|---|---|---|---|---|
| V0 | 0.6745 | −0.0043 | 0.0871 | 22.0% | 51.2% |
| **V0_OR (champion)** | 0.6788 | +0.0000 | 0.0869 | 22.2% | 51.5% |
| Passport-only | 0.6457 | −0.0331 | 0.0881 | 23.1% | 51.3% |
| **V0_OR+Passport** | **0.6922** | **+0.0134** | **0.0862** | **24.2%** | **54.0%** |

**Promotion gates (V0_OR+Passport vs V0_OR):**

| Gate | Result |
|---|---|
| AUC | PASS |
| Brier | PASS |
| SR | PASS |
| Frame | PASS |

**Classification: `PASSPORT_CHALLENGER_PROMOTE` — 4/4 gates passed**

Note: The AUC lift on unseen test (+0.0134) was larger than on validation (+0.0124). The passport features generalize cleanly.

---

## 5. V0_OR+Passport Promoted to New Build Champion

**Script:** `scripts/ops/new_build_promote_passport.py`
**Commit:** c5d06f5
**Model:** `data/new_build/models/core_v0_or_passport/core_v0_or_passport_model.pkl`
**Champion registry:** `data/new_build/models/champion/champion_registry.json`
**Model card:** `data/new_build/reports/new_build_model_card_latest.md`

**Classification:**
```
PASSPORT_SIGNAL_CONFIRMED
V0_OR_PASSPORT_BEATS_CHAMPION_ON_UNSEEN_2025
PROMOTE_TO_NEW_BUILD_CHAMPION
HORSE_FIRST_STRATEGY_VALIDATED
```

**Scope:** NEW_BUILD_ONLY — not live, not old VÉLØ.

### Feature Importance

Passport layer accounts for **35.8% of total model importance**.

| Feature | Importance | Layer |
|---|---|---|
| `or_vs_field` | 9.4% | Core V0 |
| `pp_days_since_last` | 8.9% | Passport |
| `pp_avg_sp_last5` | 8.8% | Passport |
| `official_rating` | 8.6% | OR layer |
| `wgt_lbs` | 6.3% | Core V0 |
| `pp_career_runs` | 6.3% | Passport |
| `field_size` | 6.1% | Core V0 |
| `pp_place_rate` | 4.5% | Passport |
| `draw_pct` | 4.3% | Core V0 |
| `trainer_timing_score` | 4.0% | Core V0 |
| `pp_or_change_3` | 3.3% | Passport |

Top passport signals: freshness (`pp_days_since_last`), historical market support (`pp_avg_sp_last5`), experience (`pp_career_runs`), quality profile (`pp_place_rate`), OR trajectory (`pp_or_change_3`).

### Champion Feature Architecture (30 features, frozen)

**Layer 1 — Core V0 Race Context (17 features):**
`dist_f`, `going_code`, `is_aw`, `field_size`, `draw_num`, `draw_pct`, `age_num`, `wgt_lbs`, `or_vs_field`, `release_window_score`, `going_fit_score`, `distance_fit_score`, `quiet_run_score`, `trainer_timing_score`, `jockey_switch_intent`, `setup_run_flag`, `cash_run_flag`

**Layer 2 — Official Rating (2 features):**
`official_rating`, `is_rated`

**Layer 3 — Horse Passport (11 features):**
`pp_career_runs`, `pp_win_rate`, `pp_place_rate`, `pp_days_since_last`, `pp_layoff`, `pp_avg_sp_last5`, `pp_jockey_continuity`, `pp_course_seen`, `pp_or_change_3`, `pp_class_moved_up`, `pp_class_moved_down`

### Calibration (V0_OR+Passport, 2025 unseen test)

| Prob band | n | Predicted | Actual WR | Over/Under |
|---|---|---|---|---|
| 0.00–0.05 | 8,465 | 0.036 | 0.033 | −0.003 |
| 0.05–0.10 | 24,900 | 0.075 | 0.071 | −0.004 |
| 0.10–0.15 | 14,207 | 0.122 | 0.121 | −0.001 |
| 0.15–0.20 | 5,860 | 0.171 | 0.177 | +0.006 |
| 0.20–0.25 | 2,221 | 0.221 | 0.224 | +0.003 |
| 0.25–0.30 | 856 | 0.270 | 0.259 | −0.011 |
| 0.30–0.40 | 561 | 0.339 | 0.348 | +0.009 |
| 0.40–1.01 | 151 | 0.481 | 0.510 | +0.029 |

Calibration is tight. Slight underconfidence at high probability bands (sparse n).

---

## 6. Intent Layer V1 — Features Built, Leakage Caught

**Script:** `scripts/ops/new_build_intent_features.py`
**Commit:** 4357c65
**Output:** `data/new_build/training/intent_features.parquet`

Built 17 intent features in two groups.

### Group A — Existing raceform signals (not in champion)

| Feature | Coverage |
|---|---|
| `mark_compression_score` | 54.5% |
| `curr_or_minus_last_win_or` | 33.9% |
| `curr_or_minus_best_or` | 54.5% |
| `runs_since_win` | 50.1% |
| `runs_since_place` | 69.7% |
| `runs_since_mkt_support` | 38.2% |
| `odds_resilience_score` | 79.6% |

**Banned from Group A (leakage):**
- `odds_contraction_score` — computes `(prev_SP − curr_SP) / prev_SP`, requires current race SP
- `decoy_support_flag` — fires on `is_fav[current_race]`, requires current race favourite status

### Group B — New lag features (computed from horse-sorted history)

| Feature | Coverage | What it reads |
|---|---|---|
| `intent_trip_match` | 49.2% | Today's dist_f == dist_f of last win |
| `intent_course_win_history` | 100.0% | Count of wins at today's course |
| `intent_going_match` | 50.1% | Today's going within 0.5 of last win going |
| `intent_class_drop_vs_best` | 31.3% | Class drop vs best winning class |
| `intent_run_after_break` | 65.1% | Run number since last layoff |
| `intent_sp_shortening` | 71.7% | Avg SP last 3 shorter than avg SP last 6 |
| `intent_wins_last10` | 71.9% | Wins in last 10 races |
| `intent_top3_last6` | 79.6% | Top-3 finishes in last 6 races |

All Group B features are clean (prior races only, no current-race data).

### Leakage Catch — Intent Layer V1 Result INVALIDATED

The initial ablation ran and returned:

```
Champion alone:     AUC=0.6922  SR=24.2%  Frame=54.0%
Champion+Intent:    AUC=0.7544  SR=31.8%  Frame=62.7%  ← INVALID
```

The +0.0622 AUC jump was driven primarily by `odds_contraction_score` (12.5% model importance) and `decoy_support_flag` — both encode current-race market data.

**Both banned. Scripts updated. Intent Layer V1 ablation must be rerun.**

---

## Current State

### Model Registry

| Model | Status | AUC (2025 unseen) | SR | Frame |
|---|---|---|---|---|
| Core V0 | Prior champion | 0.6745 | 22.0% | 51.2% |
| Core V0_OR | Prior champion | 0.6788 | 22.2% | 51.5% |
| **Core V0_OR_Passport_V1** | **CHAMPION** | **0.6922** | **24.2%** | **54.0%** |
| Core V0_OR_Passport_Intent | INVALID — rerun required | — | — | — |

### Files Written This Session

**Scripts:**
- `scripts/ops/new_build_promote_core_v0_or.py`
- `scripts/ops/new_build_passport_features.py`
- `scripts/ops/new_build_ablation.py`
- `scripts/ops/new_build_passport_2025_test.py`
- `scripts/ops/new_build_promote_passport.py`
- `scripts/ops/new_build_intent_features.py`
- `scripts/ops/new_build_intent_layer.py`

**Reports:**
- `data/new_build/reports/champion_promotion_latest.md` — V0_OR promotion
- `data/new_build/reports/ablation_latest.md` — 4-way passport ablation
- `data/new_build/reports/v0_or_passport_2025_unseen_test_latest.md` — unseen proof
- `data/new_build/reports/new_build_model_card_latest.md` — champion model card
- `data/new_build/reports/intent_layer_v1_latest.md` — INVALID, rerun required

**Models:**
- `data/new_build/models/champion/` — V0_OR+Passport champion (registry + pkl)
- `data/new_build/models/core_v0_or_passport/` — challenger promoted to champion
- `data/new_build/models/core_v0_or_passport_intent/` — INVALID, will be overwritten on rerun

---

## Next Session — Immediate Actions

### 1. Rerun Intent Layer V1 (clean)
```bash
source venv/bin/activate
python scripts/ops/new_build_intent_features.py   # already patched
python scripts/ops/new_build_intent_layer.py       # already patched
```
The two leaky features are now banned. The rerun will produce a real number.

### 2. Interpret the clean Intent Layer result
- If `INTENT_ADDS_SIGNAL` (4/4 gates): promote Champion+Intent, update model card
- If `INTENT_MARGINAL`: keep champion frozen, treat intent as a sidecar score only
- If `INTENT_NEUTRAL`: features are not strong enough yet — revisit signal design

### 3. After Intent Layer decision
- Build MDS Historical (prior market behaviour, not current-race odds)
- Then Betfair Live Layer (race-day overlay, not morning model)
- Then Tier Policy Simulator

---

## Strategy Locked

```
HORSE FIRST → ENTRY SECOND → RACE THIRD

Champion: Core_V0_OR_Passport_V1 (frozen)
Trust policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING
Live deployment: NOT YET
Old VÉLØ: untouched
RPR: banned
Current-race SP: banned
```

**Promotion gate (permanent rule):** any challenger must beat the champion on AUC, Brier, SR, and Frame on a held-out unseen test set. 4/4 or no promotion.
