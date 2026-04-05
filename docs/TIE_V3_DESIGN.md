# TIE v3 Design — Trainer Intent Engine: Gate/Filter Architecture

## Status
**Design phase.** TIE v1 and v2 both failed as additive probability components.
Do not start training until this design is accepted.

---

## What We Learned from v1 and v2

| Experiment | Label | Model | Ensemble delta |
|---|---|---|---|
| TIE v1 | `is_winner` | LogReg | -1.1 ppts top-1 |
| TIE v2 | `intent` (class drop + rest + market support) | HistGBM | -1.85 ppts top-1 |
| TIE v2 intent AUC | — | HistGBM | 0.87 (good detection) |

**Root cause of failure**: Place model (AUC 0.949) already captures "prepared horse" signal.
TIE as a weighted probability component overlaps Place's signal and dilutes the ranking.
The problem is not feature quality — intent AUC 0.87 is strong. The problem is *role*.

---

## Architectural Principle

> TIE should modify HOW we act on other models' scores, not add another probability.

The ensemble already knows who is fit and well-placed. TIE should answer:
**"Does this horse have a deliberate activation signal behind its entry?"**

If yes: reinforce conviction in high-ranked horses, or expand EW consideration.
If no: do not suppress — absence of intent evidence is not a negative.

---

## Three Candidate Roles

### Role A: Conviction Gate (recommended for v3)

TIE outputs a binary `intent_confirmed` flag (or a soft score 0–1).
It only fires when confidence is high (precision-biased threshold).

**Effect on ensemble:**
- When `intent_confirmed=True` AND horse ranks in top-2 by velo_prime_prob → upgrade to tier B minimum
- When `intent_confirmed=True` AND horse is a longshot (SP > 8) → enable EW consideration
- Otherwise: no effect (TIE is silent)

**Why this works:**
- Avoids the dilution problem — TIE never weakens the Place/SQPE probability signal
- Only acts in cases where it has strong evidence
- Longshot gate is orthogonal to Place (Place doesn't rank longshots highly)

**Key design constraint:** TIE v3 must NOT output a probability that enters the weighted average.

---

### Role B: EW/Place Modifier

TIE outputs `ew_intent_score` (0–1).
Used only to decide whether to recommend EW vs WIN-only on the top pick.

**Effect:**
- If `ew_intent_score > threshold` AND place_prob > 0.35 → flag as EW play
- No effect on velo_prime_prob or ranking

**Why this works:**
- EW decision is genuinely orthogonal to top-1 ranking
- Trainer intent patterns (class drop, fresh from break, quiet run) are predictive of place-or-better
- Doesn't interact with SQPE or Place at all

---

### Role C: Watchlist / Pre-Race Alert

TIE acts as a signal ahead of race day — not in the scoring pipeline at all.
Fires when market conditions + trainer pattern suggests "watch this horse."
Output goes to a `tie_watchlist` table, not into velo_prime_prob.

**Use case:** surfacing horses before the day's scoring run for manual review.

---

## Recommended Path: Role A (Conviction Gate)

Start with Role A. It is the most testable and the most conservative.

**Testable question**: do races where TIE fires AND horse is in top-2 have higher
actual win rate than base rate for tier-A/B verdicts?

If yes: gate is additive with zero probability dilution risk.
If no: disable the gate, try Role B.

---

## TIE v3 Training Spec

### Label
`intent_confirmed`: 1 if horse placed (pos <= 3) AND at least 2 of:
- `class_delta <= 0` (same or lower class)
- `days_since_run >= 14` (proper rest)
- Market support signal (runs_since_mkt_support <= 3)
- Fresh trainer (trainer_timing_score > 0.5 from v17 feature set)

This is a **confirmed outcome label**, not a forward-looking intent label.
We are training on races where intent existed AND paid off.

**Why pos<=3 not is_winner**: intent races tend to be "run into a place" first,
especially at class drop. Using winner label is too sparse and noisy.

### Features
Tier 1 (always available):
- `days_since_run`, `class_delta` (from v18)
- `runs_since_win`, `runs_since_place`, `runs_since_mkt_support` (from v17)
- `trainer_timing_score`, `quiet_run_score` (from v17)
- `sp_dec`, `sp_rank` (market position)
- `field_size`, `class_num`

Tier 2 (if RPD features available):
- `setup_run_flag`, `cash_run_flag` (from v17 — currently zero-variance in live)

### Model
HistGradientBoostingClassifier (same as v2 — fast, handles NaN natively).
Target: **precision over recall** — we want few false positives.
Tune threshold for precision >= 0.60 on holdout (not default 0.5).

### Evaluation
Primary: **precision at threshold** (not AUC)
Secondary: win/place rate when gate fires vs base rate
NOT: ensemble top-1 delta (gate doesn't enter ensemble)

---

## Integration Points

### In `velo_prime_ensemble.py`
Add `tie_gate: Optional[float] = None` field to `VeloPrimeEnsembleInput`.

In `predict()`:
```python
if self.tie_gate is not None and self.tie_gate > TIE_GATE_THRESHOLD:
    # Boost tier if horse is in top-2 and gate fires
    result.tie_gate_fired = True
    if result.decision_tier in ("C", "D"):
        result.decision_tier = "B"  # upgrade
    # EW flag
    if self.sp_dec and self.sp_dec > 8.0 and self.place_prob > 0.30:
        result.ew_recommended = True
```

### In `v17_feature_extractor.py`
Already has `days_since_run` and `class_delta`. TIE v3 features are a subset.
No new live features needed for Tier 1.

### In `velo_verdicts` DB schema
Add columns: `tie_gate_score FLOAT`, `tie_gate_fired BOOL`, `ew_recommended BOOL`

---

## Decision Criteria for Enabling in Production

1. Precision >= 0.60 at chosen threshold on holdout
2. Races where gate fires: actual win rate >= 1.3x field base rate
3. No ensemble AUC regression (gate must not touch velo_prime_prob)
4. At least 200 gate-fire events in test set to have stable statistics

---

## What NOT To Do

- Do NOT add TIE score as a weighted component in `_WEIGHTS`
- Do NOT train on `is_winner` — too sparse, collapses to trainer quality (v1 lesson)
- Do NOT set gate threshold at 0.5 — use precision-biased threshold (v2 lesson: 0.87 AUC still hurt ensemble)
- Do NOT enable until SQPE v18 is in production (need `days_since_run` + `class_delta` live)

---

## Timeline

1. **Now**: SQPE v18 training (provides `days_since_run` + `class_delta` in live extractor)
2. **After v18 deploys**: Train TIE v3 with Role A gate
3. **Ablation**: backtest gate-only (no ensemble weight change) vs no gate
4. **Deploy**: add `tie_gate_score` to live pipeline after ablation confirms lift
