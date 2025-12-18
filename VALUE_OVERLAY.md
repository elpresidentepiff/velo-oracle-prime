# VELO VALUE OVERLAY IMPLEMENTATION

**Lean Benter-Style Approach**

---

## WHAT'S IMPLEMENTED

### 1. ✅ Probability Calibration

**Method**: Platt Scaling (default)

**Formula**: 
```
p_calibrated = sigmoid(A * logit(p_raw) + B)
```

**Purpose**: Adjust model probabilities to match real-world frequencies

**Status**: Implemented in `app/strategy/value_overlay.py`

**Parameters**:
- `A`: Slope parameter (default: 1.0)
- `B`: Intercept parameter (default: 0.0)

**How to fit**:
1. Collect historical predictions: `{p_model, actual_result}`
2. Fit logistic regression: `actual ~ logit(p_model)`
3. Extract `A` and `B` coefficients
4. Store in config

**Alternative**: Isotonic regression (not yet implemented)

---

### 2. ✅ Value Edge Calculation

**Formula**:
```
edge = p_model - p_market
```

Where:
- `p_model`: Calibrated model probability
- `p_market`: Market implied probability = `1 / odds_decimal`

**Threshold**: `edge >= 0.05` (5% minimum edge)

**Example**:
```
Model: p_win = 0.35 (35%)
Market: odds = 4.0 → p_market = 0.25 (25%)
Edge: 0.35 - 0.25 = 0.10 (10% edge) ✅ VALUE
```

**Status**: Implemented in `ValueOverlay.calculate_value_edges()`

---

### 3. ✅ Capped Fractional Kelly Staking

**Formula**:
```
kelly_full = (b * p - q) / b
kelly_fraction = kelly_full * 0.25  (25% fractional Kelly)
stake_pct = min(kelly_fraction, 0.05)  (capped at 5%)
```

Where:
- `b`: Net odds = `odds_decimal - 1.0`
- `p`: Model probability
- `q`: `1 - p`

**Example**:
```
Edge: 0.10
Odds: 4.0 → b = 3.0
p = 0.35, q = 0.65

kelly_full = (3.0 * 0.35 - 0.65) / 3.0 = 0.133 (13.3%)
kelly_fraction = 0.133 * 0.25 = 0.033 (3.3%)
stake_pct = min(0.033, 0.05) = 0.033 (3.3% of bankroll)
```

**Caps**:
- **Minimum stake**: 1% of bankroll
- **Maximum stake**: 5% of bankroll
- **Fractional Kelly**: 25% of full Kelly

**Status**: Implemented in `ValueOverlay.calculate_stakes()`

---

## WHAT'S **NOT** IMPLEMENTED (Intentionally Postponed)

### ❌ Full Benter Iteration

**What it is**:
- Multi-stage weight re-estimation
- Iterative probability refinement
- Complex optimization loops

**Why postponed**:
- Adds complexity without proven ROI at this stage
- Requires extensive backtesting infrastructure
- Can be added later if needed

**When to add**:
- After v12 baseline is established
- If calibration shows systematic bias
- If edge detection needs refinement

---

### ❌ Multi-Stage Weight Re-Estimation

**What it is**:
- Adjust feature weights based on market feedback
- Re-train model using market-implied probabilities
- Iterative convergence to optimal weights

**Why postponed**:
- Requires large historical dataset
- Risk of overfitting to market noise
- Can be gamed by market manipulation

**When to add**:
- After 1000+ races of clean data
- If model shows consistent calibration error
- If market efficiency is validated

---

### ❌ Complex Optimization Loops

**What it is**:
- Optimize Kelly fraction dynamically
- Adjust edge threshold based on market conditions
- Multi-objective optimization (ROI vs risk)

**Why postponed**:
- Adds computational overhead
- Risk of over-optimization
- Static parameters are easier to debug

**When to add**:
- After baseline performance is stable
- If bankroll management needs refinement
- If market conditions show clear regimes

---

## GOVERNANCE & GATING

### Gated by DecisionPolicy

**Value overlay only applies when**:
- `chassis_type == Win_Overlay` OR `chassis_type == Value_EW`
- `win_suppressed == False`
- `ctf_adjusted == False` (no cognitive trap detected)

**Example**:
```python
if decision.chassis_type == BetChassisType.WIN_OVERLAY:
    edges, stakes = calculate_value_overlay(
        model_probabilities,
        market_odds
    )
    # Apply stakes
else:
    # No value overlay (Top-4 chassis or suppressed)
    pass
```

---

### Gated by ADLG (Learning Gate)

**Value overlay results feed into learning gate**:
- If `learning_status == REJECTED` → no learning commit
- If `learning_status == QUARANTINED` → log but don't train
- If `learning_status == COMMITTED` → update calibration params

**Example**:
```python
if learning_gate_result.learning_status == LearningStatus.COMMITTED:
    # Update calibration parameters
    update_calibration_params(actual_results, model_predictions)
else:
    # Don't update (garbage race)
    pass
```

---

## CONFIGURATION

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `EDGE_THRESHOLD` | 0.05 | Minimum edge to bet (5%) |
| `KELLY_FRACTION` | 0.25 | Fractional Kelly (25%) |
| `MAX_STAKE_PCT` | 0.05 | Maximum stake (5% of bankroll) |
| `MIN_STAKE_PCT` | 0.01 | Minimum stake (1% of bankroll) |
| `CALIBRATION_METHOD` | `PLATT` | Platt scaling |

### How to Adjust

**Edge threshold**:
- Lower (0.03) → More bets, lower selectivity
- Higher (0.08) → Fewer bets, higher selectivity

**Kelly fraction**:
- Lower (0.10) → More conservative
- Higher (0.50) → More aggressive (not recommended)

**Max stake**:
- Lower (0.03) → Lower risk
- Higher (0.10) → Higher risk (not recommended)

---

## CALIBRATION WORKFLOW

### Step 1: Collect Historical Data

```python
historical_data = []
for race in completed_races:
    for runner in race.runners:
        historical_data.append({
            'p_model': runner.p_model,
            'actual': 1 if runner.won else 0
        })
```

---

### Step 2: Fit Platt Scaling

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

# Extract data
X = np.array([np.log(d['p_model'] / (1 - d['p_model'])) for d in historical_data]).reshape(-1, 1)
y = np.array([d['actual'] for d in historical_data])

# Fit logistic regression
lr = LogisticRegression()
lr.fit(X, y)

# Extract parameters
A = lr.coef_[0][0]
B = lr.intercept_[0]

print(f"Platt parameters: A={A:.3f}, B={B:.3f}")
```

---

### Step 3: Apply Calibration

```python
calibration_params = {'A': A, 'B': B}

calibrated_probs = overlay.calibrate_probabilities(
    raw_probabilities,
    calibration_params
)
```

---

### Step 4: Validate Calibration

**Calibration Plot**:
- X-axis: Predicted probability (binned)
- Y-axis: Actual win rate
- Ideal: Points lie on diagonal

**Numeric Summary**:
- Brier score: `mean((p_model - actual)^2)`
- Log loss: `-mean(actual * log(p_model) + (1-actual) * log(1-p_model))`

---

## EXAMPLE USAGE

```python
from app.strategy.value_overlay import calculate_value_overlay

# Model probabilities
model_probabilities = {
    'r1': 0.35,
    'r2': 0.25,
    'r3': 0.15
}

# Market odds
market_odds = {
    'r1': 4.0,  # Implied 25%
    'r2': 5.0,  # Implied 20%
    'r3': 8.0   # Implied 12.5%
}

# Calculate value overlay
edges, stakes = calculate_value_overlay(
    model_probabilities,
    market_odds
)

# Results
for edge in edges:
    if edge.has_value:
        print(f"{edge.runner_id}: {edge.edge:.1%} edge")

for stake in stakes:
    print(f"{stake.runner_id}: Bet {stake.capped_stake_pct:.1%} of bankroll")
```

**Output**:
```
r1: 10.0% edge
r2: 5.0% edge
r3: 2.5% edge (below threshold)

r1: Bet 3.3% of bankroll
r2: Bet 1.7% of bankroll
```

---

## TESTING & VALIDATION

### Unit Tests

```python
def test_value_edge_calculation():
    overlay = ValueOverlay()
    
    model_probs = {'r1': 0.35}
    market_odds = {'r1': 4.0}
    
    edges = overlay.calculate_value_edges(model_probs, market_odds)
    
    assert edges[0].edge == 0.10  # 35% - 25%
    assert edges[0].has_value == True  # > 5% threshold
```

---

### Integration Tests

```python
def test_value_overlay_with_decision_policy():
    # Test that value overlay only applies when chassis allows
    decision = make_decision(...)
    
    if decision.chassis_type == BetChassisType.WIN_OVERLAY:
        edges, stakes = calculate_value_overlay(...)
        assert len(stakes) > 0
    else:
        # No value overlay
        pass
```

---

## MONITORING & ALERTS

### Key Metrics

1. **Edge detection rate**: % of races with value found
2. **Stake distribution**: Average stake size
3. **Calibration error**: Brier score over time
4. **ROI**: Return on investment

### Alerts

- ⚠️ **Edge detection rate > 50%**: Model may be overconfident
- ⚠️ **Average stake > 4%**: Kelly fraction may be too aggressive
- ⚠️ **Calibration error increasing**: Re-fit Platt parameters

---

## SUMMARY

### ✅ Implemented (Lean Benter)

1. **Probability calibration** (Platt scaling)
2. **Value edge calculation** (p_model - p_market)
3. **Capped fractional Kelly** (25% Kelly, max 5% stake)

### ❌ Postponed (Full Benter)

1. Multi-stage weight re-estimation
2. Iterative probability refinement
3. Complex optimization loops

### 🔒 Gated By

1. **DecisionPolicy**: Chassis constraints
2. **ADLG**: Learning gate (prevents training on garbage)

### 📊 Next Steps

1. Collect historical data (1000+ races)
2. Fit Platt scaling parameters
3. Validate calibration plot
4. Backtest value overlay on historical data
5. Deploy with paper trading

---

**Version**: 1.0  
**Date**: December 17, 2025  
**Author**: VELO Team
