# VÉLØ RL POLICY SIMULATOR V1

**Status:** SPEC — not yet built  
**Purpose:** RL is for action policy only. Not for raw winner prediction.

---

## What RL Is NOT in VÉLØ

RL does **not** decide "this horse wins." Raw winner prediction stays with SQPE/VeloPrimeEnsemble tabular models.

Predicting outcomes from covariates is a supervised problem. RL solves a different problem: given a state, what action maximises long-term cumulative reward?

---

## What RL IS in VÉLØ

RL controls the **policy layer** — the decision to act on a prediction:

```
Given:
  VÉLØ probability (VP)
  Decision tier (A/B/C/X)
  Assigned lane (V1_BASE, V2_CLASS4, V6_GOLD_SEAM)
  SP band
  Daily exposure state
  Drawdown state
  Rolling SR / frame rate

Choose action:
  BET_WIN
  BET_FRAME
  HOLD
  SUPPRESS
  ESCALATE_LANE
  ADJUST_THRESHOLD
```

The RL agent learns which action maximises long-term expected return, not just single-race accuracy.

---

## Environment Specification

### State space
```python
state = {
    # Prediction signals
    "vp": float,                    # VÉLØ prime probability 0.0–1.0
    "sqpe": float,                  # SQPE base probability
    "mds": float,                   # market deception score
    "improvement_score": float,
    "place_prob": float,
    "tier": int,                    # A=0, B=1, C=2, X=3
    "sp_band": int,                 # <2.0, 2-4, 4-8, 8-16, >16

    # Race context
    "field_size": int,
    "race_class": int,
    "going_code": int,
    "course_id": int,               # encoded
    "distance_band": int,

    # Session state
    "daily_pl": float,              # running P&L today
    "rolling_sr_7d": float,         # 7-day strike rate
    "rolling_roi_30d": float,       # 30-day ROI
    "consecutive_misses": int,
    "daily_exposure": float,        # total staked today

    # Router state
    "lane": int,                    # encoded lane
    "candidate_exec_allowed": bool,
}
```

### Action space
```python
actions = [
    "BET_WIN",       # back to win, 1 unit
    "BET_FRAME",     # back for place, 0.5 units
    "HOLD",          # no bet, observe
    "SUPPRESS",      # explicit suppress signal
]
```

### Reward function
```python
def reward(action, outcome, sp, stake=1.0):
    if action == "HOLD":
        return 0.0  # neutral — no loss, no gain

    if action == "BET_WIN":
        if outcome == "WIN":
            return (sp - 1.0) * stake    # profit at SP
        else:
            return -stake                 # loss

    if action == "BET_FRAME":
        place_sp = max(1.0, (sp - 1.0) / 4 + 1.0)  # approx place terms
        if outcome in ("WIN", "PLACED"):
            return (place_sp - 1.0) * stake
        else:
            return -stake

    if action == "SUPPRESS":
        return 0.0  # neutral — suppress is a no-bet
```

Reward shaping: small negative for excessive HOLD (promotes decisive policy). Large negative for SUPPRESS on a WIN (penalises over-suppression).

---

## Training Protocol

### Dataset
- Source: `data/velo_unified_evidence_corpus_v1.csv` (1310 rows, time-split)
- Minimum required before training: 1000 clean rows with SP, outcome, and full signal vector
- Expand with daily closed results from Sigma pipeline

### Algorithm
- **Stable-Baselines3 PPO** — proximal policy optimization, stable, well-tested
- Offline RL: train on historical (state, action=HOLD, reward) tuples, then simulate BET actions
- Evaluate against counterfactual: "what if we had bet every predicted winner?"

### Time split rule
- Training: all rows before validation cutoff
- Validation: last 20% of dates (never randomised — time-ordered only)
- No lookahead: SP is available at training time (it is historical), but RL must not use it as a real-time action feature (it won't know SP pre-race)

---

## Promotion Gates

| Gate | Threshold | Action |
|---|---|---|
| n_training_races | >= 1000 | Begin RL simulator training |
| simulator_ROI | > +15% on val set | Eligible for paper ledger test |
| paper_ledger_n | >= 100 | Begin WATCH review |
| paper_ledger_ROI | > 0% at n>=100 | Eligible for shadow discussion |
| shadow_n | >= 300 | Eligible for operator promotion decision |

No automatic promotion. Operator decision required at every gate.

---

## Hard Rules (Permanent)

```
NO_LIVE_STAKING             = TRUE (unconditional)
NO_LIVE_EXECUTION           = TRUE
NO_TELEGRAM_TRIGGERED       = TRUE
NO_MODEL_OVERRIDE           = TRUE
NO_SCORING_CHANGE           = TRUE
SIMULATOR_ONLY              = TRUE (until paper_ledger_n >= 100)
SP_AS_PRE_RACE_FEATURE      = NEVER (historical training only)
VELO_EXECUTION_MODE_LIVE    = RUNTIME_ERROR (hard gate)
```
