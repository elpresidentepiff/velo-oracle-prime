# VÉLØ CPU SHADOW MODEL PROTOCOL V1

**Created:** 2026-05-18  
**Status:** ACTIVE — GATE_OPEN_ACCUMULATING  
**Classification:** SHADOW_PROTOCOL | EVIDENCE_GATED | NO_LIVE_PROMOTION

---

## What This Is

A protocol for running challenger ML models in shadow — tracking their prospective  
performance against live scoring output — without touching production scoring.

The current active shadow challenger is:

```
VELO_CPU_LOGISTIC_SHADOW_V1
Model:       NO_VP_COMPOSITE logistic
Feature set: NO_VP_COMPOSITE (sqpe_v17_prob + 7 raw sidecars, no velo_prime_prob)
Target:      win
Training:    1048 rows, time-split to 2026-05-10
Brier V1:   0.163990 (vs SQPE 0.210688, delta −22.1%)
```

---

## Why NO_VP_COMPOSITE Matters

The ablation V1 result (2026-05-18) ruled out the meta-calibrator hypothesis:

```
NO_VP_COMPOSITE Brier: 0.163990
FULL_META Brier:       0.164972   ← includes velo_prime_prob

NO_VP_COMPOSITE wins without VP.
```

This means the raw sidecars (SQPE, market deception, improvement, place probability,  
longshot, release day, comment intelligence) carry independent predictive signal  
for win outcomes. The challenger is not just recalibrating VÉLØ's own output.

**What this does not mean:**
- VP is wrong (it is an audited, production-grade composite)
- The challenger should replace VP (it should not)
- Frame prediction is solved (it is not — CURRENT_STACK_BEATS_ALL)

---

## Why This Is Not Production

The challenger is trained on 1,048 historical rows with a 2026-05-10 cutoff.  
Historical Brier improvements are necessary but not sufficient for promotion.

Issues that forward validation must resolve:

| Issue | Status |
|---|---|
| Calibration drift on unseen data | UNKNOWN — needs forward n≥300 |
| Subgroup collapse (class/distance/tier) | NOT YET TESTED |
| Frame layer impact | NOT YET TESTED |
| ROI at forward sample | NOT YET TESTED |
| Stable under corpus expansion | NOT YET TESTED — 2K rerun required |

---

## Training Cutoff Rules (Immutable)

```
TRAINING_CUTOFF_DATE = "2026-05-10"
```

Rules:
- The model pkl loaded by `build_shadow_model_forward_gate.py` is trained  
  on data with `date_parsed <= 2026-05-10` only
- No forward data (after 2026-05-10) was seen during training
- The cutoff is recorded in the model artifact metadata and must not change  
  without a full retraining run and new evaluation
- If the corpus is expanded before the 2K milestone, retraining resets the cutoff  
  to the new split date and the forward gate counter resets to zero

---

## Forward Sample Requirement

```
Minimum forward runners:     300
Minimum top-decile runners:   75
```

These are not targets — they are the minimum sample for the first gate decision.  
All eight promotion conditions must be met simultaneously. Meeting the sample  
requirement only unlocks the ability to have the conversation.

Current progress: tracked in `data/reports/shadow_model_forward_gate_latest.json`.

---

## Promotion Gates (All Eight Required)

Gate 1 — **Beats SQPE Brier on forward 300**  
The challenger Brier on the first 300 unseen runners is lower than SQPE Brier  
computed on the same 300 runners. No training or validation window — forward only.

Gate 2 — **Improves win SR by decile**  
Top-decile win SR under challenger ranking exceeds SQPE top-decile SR on the  
same 300 runners. The ranking must be better, not just calibration.

Gate 3 — **Does not degrade frame layer**  
The frame SR and frame ROI when the challenger is used to rank top-decile runners  
is not worse than current stack frame metrics at comparable n. Frame is owned  
by the current stack. Any challenger that hurts frame is rejected regardless  
of win performance.

Gate 4 — **Positive or neutral ROI after outlier stripping**  
ROI computed at full forward sample after removing top and bottom 5% by SP.  
Specifically: the challenger's top-decile ROI must be ≥ 0 after outlier stripping.  
A challenger that picks winners at short prices only is not sufficient.

Gate 5 — **No subgroup collapse**  
Win SR must be above baseline in at least 3 of the following subgroups:  
Tier A, Tier B, handicap races, non-handicap races, Class 3+, Class 4–6.  
A model that works for one subgroup and fails all others cannot be promoted.

Gate 6 — **Reproducible training**  
Re-running the training script with the same data and random seed produces  
Brier within ±0.001 of the recorded result. Model is deterministic.

Gate 7 — **Sentinel clean**  
No Sentinel flags on the challenger output: no SP leakage, no future data  
contamination, no identity resolution errors, no systematic bias (predicted  
probability > 0.80 on non-Tier A runners, etc.).

Gate 8 — **Human approval required**  
No gate passes automatically. The operator reviews the gate report and issues  
explicit approval before any integration discussion begins. Passing all 7  
prior gates does not trigger promotion — it triggers the conversation.

---

## Failure Gates (Automatic Rejection)

| Condition | Action |
|---|---|
| Forward Brier ≥ SQPE Brier at n=300 | CHALLENGER_FAILS — accumulate more data |
| Frame SR drops > 5pp vs current stack | REJECT — frame protection takes priority |
| ROI < −10% at top decile after stripping | REJECT — negative expected value |
| SP detected in feature set | IMMEDIATE_REJECT — rule violation |
| identity_unresolved rows in training | REJECT — data integrity failure |
| Calibration drift > 0.05 Brier point at n=300 vs training | FLAG — operator review |

---

## Rollback Rules

The shadow challenger is never applied to live scoring. Rollback is:

1. Stop running `build_shadow_model_forward_gate.py`
2. Delete `models/shadow/model_arena_v2/NO_VP_COMPOSITE_logistic_win.pkl`
3. No other action needed — no scoring path was modified

Current stack rollback: `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` (unchanged).

---

## 2K Milestone Protocol

When corpus reaches 2,000 clean, result-matched rows (est. 2026-07):

1. Retrain all V2 arena models with new time-split (recalculate cutoff date)
2. Run full ablation again — confirm NO_VP_COMPOSITE still beats FULL_META
3. Reset forward gate counter to zero
4. New forward sample required before promotion review
5. Promotion gates remain the same

The 2K rerun is mandatory. A model trained on 1,048 rows should not be promoted  
based on forward data accumulated with a corpus that has doubled.

---

## File Map

| File | Purpose |
|---|---|
| `scripts/train_velo_model_arena_v2.py` | Trains arena V2, produces pkl artifacts |
| `models/shadow/model_arena_v2/*.pkl` | Trained shadow challengers (gitignored) |
| `scripts/build_shadow_model_forward_gate.py` | Tracks forward performance |
| `data/reports/shadow_model_forward_gate_latest.json` | Current gate snapshot |
| `data/reports/shadow_model_forward_gate_ledger.csv` | Append-only gate history |
| `data/reports/velo_model_arena_ablation_v2_latest.json` | Arena V2 full results |

---

## Governance (Permanent)

```
CPU_SHADOW_MODEL_ACTIVE         = TRUE
FORWARD_GATE_REQUIRED           = TRUE (300 runners minimum)
NO_LIVE_PROMOTION               = TRUE (until all 8 gates pass + operator approval)
NO_SCORING_CHANGE               = TRUE
NO_VP_WEIGHT_CHANGE             = TRUE
NO_ROUTER_RULE_CHANGE           = TRUE
FRAME_LAYER_PROTECTED           = TRUE (Gate 3 enforces)
TRAINING_CUTOFF_IMMUTABLE       = TRUE
2K_RERUN_REQUIRED               = TRUE (when corpus reaches 2,000 rows)
OPERATOR_DECISION_AT_EVERY_GATE = TRUE
```
