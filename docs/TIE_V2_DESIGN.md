# TIE v2 Design — Trainer Intent Engine

**Status:** Design phase. Do NOT train until label is confirmed.
**Last updated:** 2026-04-05

---

## Why v1 failed

TIE v1 trained on `is_winner` with LogisticRegression.

Results (parquet ablation, 25,883 races, 2024+ hold-out):
- CORE (Place+MktDecep): 71.37% top-1
- CORE+TIE v1: 70.27% top-1  **(-1.1 ppts)**

Root causes:
1. **Wrong label.** `is_winner` is "which horse was best today" — not "which horse was deliberately targeted today." These correlate but are not the same thing. The model learned trainer quality (trainer_win_rate coeff=+9.48) not trainer intent.
2. **Wrong model.** LogisticRegression cannot capture intent — intent is fundamentally a multi-way interaction (class drop AND rest AND trainer form AND jockey signal). Linear models flatten this.
3. **Weak interaction features.** `days_since_run` had near-zero coefficient. `jockey_switch_intent` had negative coefficient (switches may correlate with horses being dropped, not deliberately targeted).

---

## What TIE should answer

> "Is this horse SET today?"

Not: "Is this horse the best horse in the race?"

The distinction is the whole project. A targeted run can happen at any class level, any ability level. What matters is whether the trainer deliberately chose this race and prepared for it.

---

## v2 Label Definition

### Option A — Targeted Win (narrow, clean)
```
y_intent = 1 when ALL of:
  - target = 1 (won)
  - class_delta <= 0  (at same or lower class than last run)
  - days_since_run >= 14  (not thrown in off a quick back-to-back)
  - trainer_win_rate >= 0.10  (trainer that knows what they're doing)
```

This selects wins that look deliberately engineered: class drop, rested horse, capable trainer.

Positives will be ~4-5% of corpus (subset of ~10% winners). Downside: very sparse label.

### Option B — Placement Value (broader)
```
y_intent = 1 when:
  - position <= 3  (placed or won)
  - class_delta <= 0  (not running above last class)
  - implied_prob < 0.15  (not already a short-priced favourite — some surprise)
```

This captures "planned run, unexpected placement" — horses that outperformed their market price after a class drop. Broader signal but noisier.

### Option C — Beaten favourite at class drop
```
y_intent = 1 when:
  - class_delta < 0  (genuine class drop)
  - trainer_win_rate >= 0.12
  - target = 1 OR (position = 2 AND implied_prob < 0.20)
```

**Recommended: Option A for v2.** Cleanest definition of deliberate targeting. Evaluate whether sparse positives are a problem in practice.

---

## v2 Feature Set

### Tier 1 — Already in corpus, high priority
| Feature | Source | Status |
|---|---|---|
| `days_since_run` | Computed from race dates per horse | **In corpus (added Apr 5)** |
| `class_delta` | class_num[t] - class_num[t-1] per horse | **In corpus (added Apr 5)** |
| `trainer_win_rate` | Aggregated from train set | In corpus |
| `trainer_recent_win_rate` | 90-day rolling | In corpus |
| `jockey_switch_intent` | Binary 0/1 from corpus | In corpus |
| `mark_compression_score` | OR compression metric | In corpus |
| `runs_since_win` | Form cycle position | In corpus |

### Tier 2 — Need construction or approximation
| Feature | How to build | Priority |
|---|---|---|
| `class_drop_flag` | `class_delta < 0` binary (derived from class_delta) | HIGH |
| `fresh_flag` | `days_since_run >= 21` binary | HIGH |
| `class_drop_x_fresh` | `class_drop_flag * fresh_flag` interaction | HIGH |
| `trainer_form_x_class_drop` | `trainer_win_rate * class_drop_flag` interaction | HIGH |
| `jockey_upgrade` | New jockey has higher win_rate than previous | MEDIUM |
| `sp_shortening` | SP shorter than last run at similar class | MEDIUM — needs per-race SP comparison |
| `quiet_run_score` | Last run was a heavy beating (already in corpus) | MEDIUM |

### Tier 3 — Not in corpus, complex to build
| Feature | Blocker | Priority |
|---|---|---|
| `jockey_tier_change` | Need jockey rank table | LOW |
| `market_move_pre_race` | Betfair data not available | DEFERRED |

---

## v2 Model

**Use GBM (GradientBoostingClassifier), not LogisticRegression.**

Reasons:
- Intent is interaction-heavy — trees handle this naturally
- Class drop × trainer form × rest pattern is a non-linear combination
- Consistent with all other specialist models in the ensemble

Parameters to use (consistent with specialist models):
```python
GBM_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_samples_leaf=20,
    subsample=0.8,
    random_state=42,
)
```

Add isotonic calibration (CalibratedClassifierCV) same as specialist models.

---

## v2 Evaluation Plan

### Training split
- Train: date < 2024-01-01 (same chronological split as specialist models)
- Test: date >= 2024-01-01

### Metrics
1. AUC on intent label (quality of intent detection)
2. Top-1 accuracy when used as ranker alone (sanity check)
3. **Primary: ablation — CORE vs CORE+TIE v2** (this is the real bar)
   - CORE = Place + Market Deception (current proven ensemble)
   - Must show positive lift to be promoted

### Threshold for promotion
- Top-1 lift > 0 on parquet test set
- Top-1 lift > 0 on live Supabase backtest (real scoring data)
- Both must pass before wiring to live ensemble

---

## What NOT to do

- Do NOT train on raw `is_winner` again
- Do NOT use LogisticRegression
- Do NOT promote until ablation shows positive lift over CORE
- Do NOT add TIE to ensemble weight until lift is proven
- Do NOT treat trainer_win_rate as the primary signal — it's already priced in by the market

---

## Build sequence

1. [ ] Confirm label (Option A recommended)
2. [ ] Build interaction features (`class_drop_flag`, `fresh_flag`, cross terms)
3. [ ] Add to corpus prep script or train script
4. [ ] Train GBM with isotonic calibration
5. [ ] Evaluate AUC on intent label
6. [ ] Run parquet ablation: CORE vs CORE+TIE v2
7. [ ] If lift proven, wire into specialist loader + ensemble weight
8. [ ] Run live Supabase ablation to confirm on real scoring data
9. [ ] Promote only when both tests pass

---

## Interaction with live pipeline

TIE v2 will use the same features as v2 training (class_delta, days_since_run, etc.).
These now exist in `v17_feature_extractor.py` DEFAULTS and `extract()`.

In live scoring (`_build_live_features`), these are filled via DEFAULTS (14.0, 0.0) until
the V17FeatureExtractor is fully wired into the scoring path. TIE v2 should be trained
knowing this — it will see default values for days_since_run and class_delta in live
scoring until the extractor is wired.

This is acceptable for a first live run (trainer stats are the stronger signal anyway).
Wiring the extractor is a separate infrastructure task.
