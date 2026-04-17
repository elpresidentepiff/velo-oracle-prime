# VELO ARCHITECTURE CLARIFICATION

**"61+ Engines" Explained**

---

## THE QUESTION

"Does VELO have 61 separate prediction models?"

**Answer**: **NO**

---

## THE CORRECT INTERPRETATION

**61+ Feature Engines** (micro-engines producing signals)  
→ **1 Core Predictor** (consumes features, outputs probabilities)  
→ **1 Decision Policy** (chassis logic)  
→ **1 Learning Gate** (ADLG)

---

## WHAT ARE "FEATURE ENGINES"?

A **feature engine** is a **pure function** that transforms raw racing data into a signal.

**Example Feature Engines**:
- `rpr_last_3_avg`: Average RPR over last 3 runs
- `draw_bias_score`: Draw position advantage for this course/distance
- `trainer_strike_rate_14d`: Trainer win rate over last 14 days
- `pace_geometry_score`: Predicted pace shape advantage
- `market_drift_30m`: Odds movement in last 30 minutes

Each feature engine:
- Takes **raw inputs** (race card, market data, historical data)
- Produces **one signal** (number, flag, or score)
- Is **deterministic** (same inputs → same output)
- Is **ablation-testable** (can be removed to test robustness)

---

## VELO v12 FEATURE COUNT

From `feature_schema_v12.json`:

| Domain | Features | Examples |
|--------|----------|----------|
| Form | 10 | `rpr`, `or`, `ts`, `form_last_3`, `consistency_score` |
| Pace | 8 | `early_pace_score`, `late_pace_score`, `pace_geometry` |
| Draw | 5 | `draw_bias`, `draw_advantage`, `rail_position` |
| Trainer/Jockey | 12 | `trainer_strike_rate`, `jockey_strike_rate`, `combo_win_rate` |
| Course/Going/Distance | 10 | `course_form`, `going_suitability`, `distance_win_rate` |
| Class | 6 | `class_rating`, `class_movement`, `class_drop_flag` |
| Recency | 4 | `days_since_last`, `runs_this_season`, `layoff_flag` |
| Weight/Age | 3 | `weight_carried`, `age`, `weight_for_age` |
| Market | 3 | `odds_decimal`, `odds_drift`, `volume_indicator` |

**Total**: **61 features**

Each feature is a **micro-engine** (pure function).

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│  RAW INPUTS                                                 │
│  ├─ Race card (runners, trainers, jockeys, weights)        │
│  ├─ Market data (odds, volumes, timestamps)                │
│  └─ Historical data (past performances, course records)     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  61+ FEATURE ENGINES (Micro-Engines)                        │
│  ├─ Form engines (10)                                       │
│  ├─ Pace engines (8)                                        │
│  ├─ Draw engines (5)                                        │
│  ├─ Trainer/Jockey engines (12)                             │
│  ├─ Course/Going/Distance engines (10)                      │
│  ├─ Class engines (6)                                       │
│  ├─ Recency engines (4)                                     │
│  ├─ Weight/Age engines (3)                                  │
│  └─ Market engines (3)                                      │
│                                                             │
│  Output: Feature vector (61 dimensions)                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  1 CORE PREDICTOR                                           │
│  └─ Model: Gradient Boosting / Neural Network              │
│     Input: 61 features                                      │
│     Output: p(win), p(top4)                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STRATEGIC INTELLIGENCE PACK V2                             │
│  ├─ Opponent Models (GTI)                                   │
│  ├─ Cognitive Trap Firewall (CTF)                           │
│  └─ Ablation Tests (AAT)                                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  1 DECISION POLICY                                          │
│  └─ Chassis selection:                                      │
│     ├─ Win_Overlay (if Release + Intent + Clean + Stable)  │
│     ├─ Top_4_Structure (default in chaos)                   │
│     ├─ Value_EW (each-way value)                            │
│     └─ Suppress (no bet)                                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  1 LEARNING GATE (ADLG)                                     │
│  └─ Status: committed | quarantined | rejected              │
└─────────────────────────────────────────────────────────────┘
```

---

## WHY THIS ARCHITECTURE IS SANE

### ✅ **Modular**
- Each feature engine is independent
- Can add/remove features without breaking the system
- Ablation tests validate robustness

### ✅ **Testable**
- Each feature engine is a pure function → unit testable
- Ablation tests verify decision doesn't rely on single feature
- Integration tests verify end-to-end flow

### ✅ **Explainable**
- Feature importance shows which signals matter
- Ablation tests show which features are critical
- Decision policy has explicit rules (not black box)

### ✅ **Scalable**
- Adding new features doesn't require retraining entire system
- Feature registry enables feature subsets (no_market, minimal, etc.)
- Parallel feature computation possible

---

## WHAT VELO IS **NOT**

❌ **NOT 61 separate prediction models**  
- That would be overkill and unmanageable
- Would require 61 training loops, 61 calibrations, 61 backtests
- Would be "Benter complicated" without Benter discipline

❌ **NOT an ensemble of 61 models**  
- Ensembles combine multiple models (e.g., 5-10 models)
- VELO has 1 core predictor consuming 61 features
- Strategic Intelligence Pack adds governance, not more models

❌ **NOT a neural network with 61 hidden layers**  
- 61 features = input dimension, not depth
- Core predictor can be gradient boosting, neural net, or logistic regression
- Depth/complexity is separate from feature count

---

## COMPARISON: VELO vs ALTERNATIVES

| System | Feature Engines | Core Predictors | Decision Layers | Learning Gates |
|--------|----------------|-----------------|-----------------|----------------|
| **VELO v12** | 61+ | 1 | 1 (DecisionPolicy) | 1 (ADLG) |
| **Naive Model** | 5-10 | 1 | 0 (no chassis) | 0 (no gate) |
| **Over-Engineered** | 100+ | 10+ | 5+ | 0 (no discipline) |
| **Benter-Style** | 50-100 | 1-3 | 1 (Kelly staking) | 1 (quality filter) |

VELO v12 is **Benter-aligned**: Many signals → Few models → Disciplined decision policy

---

## FEATURE REGISTRY & ABLATION

The **Feature Registry** (`app/ml/feature_registry.py`) groups features by domain:

```python
class FeatureDomain(Enum):
    FORM = "form"
    PACE = "pace"
    DRAW = "draw"
    TRAINER_JOCKEY = "trainer_jockey"
    COURSE_GOING_DISTANCE = "course_going_distance"
    CLASS = "class"
    RECENCY = "recency"
    WEIGHT_AGE = "weight_age"
    MARKET = "market"
```

**Predefined Feature Subsets**:
- `minimal`: Core features only (form + class)
- `no_market`: All features except market
- `form_and_pace`: Form + pace features only
- `ability_only`: Form + class + trainer/jockey

**Ablation Tests** (`app/ml/ablation_tests.py`):
- Remove one domain at a time
- Re-run prediction
- Check if top selection flips
- If flip_count >= 2 → decision is **fragile** → quarantine learning

---

## SUMMARY

**"61+ engines"** = **61+ feature engines** (pure functions producing signals)

**NOT** 61 models, NOT 61 training loops, NOT overkill.

**This is standard ML practice**: Many features → One model → Disciplined policy.

**VELO's innovation** is the **Strategic Intelligence Pack v2**:
- Learning Gate (ADLG) prevents training on garbage
- Ablation Tests (AAT) ensure robustness
- Opponent Models (GTI) treat market as adversary
- Cognitive Trap Firewall (CTF) protects from biases
- Decision Policy enforces chassis discipline

**Result**: A system that exploits structural incentives without needing perfect information.

---

**Version**: 1.0  
**Date**: December 17, 2025  
**Author**: VELO Team
