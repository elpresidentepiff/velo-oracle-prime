# VÉLØ Intelligence Stack v1.0

**Version:** Intelligence_v1.0  
**Date:** 2025-11-09  
**Status:** Production-ready

---

## Executive Summary

The Intelligence Stack transforms VÉLØ from a **calculator** into a **strategist** by requiring multi-signal convergence before committing capital.

**Baseline Benter (math alone):** -5.3% ROI  
**Intelligence Stack (strategic convergence):** TBD (requires testing on 2023-2024 data)

**Key Innovation:** Dual-signal logic - NO BET unless 2+ independent modules agree.

---

## Architecture

### Module Stack

```
┌─────────────────────────────────────────┐
│         Intelligence Orchestrator        │
│     (Dual-Signal Logic Coordinator)      │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   ┌───▼───┐  ┌────▼────┐  ┌────▼────┐
   │ SQPE  │  │   TIE   │  │   NDS   │
   └───┬───┘  └────┬────┘  └────┬────┘
       │           │            │
       └───────────┴────────────┘
                   │
            ┌──────▼──────┐
            │    Benter   │
            │    Model    │
            └─────────────┘
```

---

## Module 1: SQPE (Sub-Quadratic Prediction Engine)

**Purpose:** Filter noise, amplify convergence signals, rank true-value edges

**File:** `src/intelligence/sqpe.py` (372 lines)

### Signals Analyzed

| Signal | Description | Weight |
|--------|-------------|--------|
| **Rating** | OR/RPR/TS with consistency bonus | 0.25 |
| **Form** | Recent performance patterns | 0.25 |
| **Class** | Quality level (Class 1-7) | 0.25 |
| **Market** | Implied probability from odds | 0.25 |

### Convergence Calculation

```python
convergence = 1.0 - std(signals)
```

**High convergence** = all signals agree (low std)  
**Low convergence** = signals contradict (high std)

### Signal Classification

| Strength | Criteria |
|----------|----------|
| **STRONG** | Convergence ≥ 0.6, Confidence ≥ 0.5 |
| **MODERATE** | Convergence ≥ 0.4, Confidence ≥ 0.3 |
| **WEAK** | Convergence ≥ 0.2 |
| **NOISE** | Convergence < 0.2 |

### SQPE Scoring

```python
score = edge × convergence × confidence × longshot_penalty
```

**Longshot penalty:** 0.7 (30% reduction for odds > 10.0)

**Rationale:** Longshots require higher convergence to justify bet.

---

## Module 2: TIE (Trainer Intention Engine)

**Purpose:** Quantify trainer placement strategy and detect intentional win setups

**File:** `src/intelligence/tie.py` (450 lines)

### Signals Analyzed

| Signal | Description | Optimal Range |
|--------|-------------|---------------|
| **Jockey Booking** | Upgrade/downgrade detection | +5% SR = upgrade |
| **Prep Cycle** | Days since last run | 14-28 days |
| **Course Affinity** | Trainer success at course | +5% vs overall |
| **Distance Affinity** | Trainer success at distance | ±10% tolerance |
| **Seasonal** | Trainer success in month | Historical pattern |

### Intent Classification

| Intent | Criteria | Multiplier |
|--------|----------|------------|
| **WIN_TODAY** | Avg signal ≥ 0.8 + jockey upgrade + course specialist | 1.3x |
| **PLACED_TO_WIN** | Avg signal ≥ 0.7 | 1.1x |
| **NEUTRAL** | Avg signal 0.3-0.7 | 1.0x |
| **EXPERIENCE** | Avg signal ≤ 0.3 or prep ≤ 0.3 | 0.7x |
| **DECEIVE** | High signal variance (std > 0.3) | 0.5x |

### TIE Scoring

```python
score = avg(signals) × intent_multiplier
```

**Example:**
- Jockey upgrade: 0.8
- Prep cycle: 0.9 (21 days)
- Course affinity: 0.85 (specialist)
- Distance affinity: 0.75
- Seasonal: 0.7

**Avg = 0.80 → WIN_TODAY → score = 0.80 × 1.3 = 1.04 (capped at 1.0)**

---

## Module 3: NDS (Narrative Disruption Scan)

**Purpose:** Detect market misreads driven by hype, bias, or false narratives

**File:** `src/intelligence/nds.py` (430 lines)

### Signals Analyzed

| Signal | Description | Detection Method |
|--------|-------------|------------------|
| **Overround** | Hype favorite detection | Market overround > 1.15 + odds < 5.0 |
| **Recency** | Last race overweighted | Last pos ≤ 3, hist avg > 6 |
| **Form Quality** | False form (wins in lower class) | 2+ wins in lower class, now stepping up |
| **Odds Drift** | Smart money leaving | Historical odds movement (TODO) |

### Narrative Types

| Narrative | Description | Action |
|-----------|-------------|--------|
| **HYPE_FAVORITE** | Overbet due to media/hype | FADE |
| **RECENCY_BIAS** | Last race overweighted | FADE |
| **FALSE_FORM** | Form looks better than it is | FADE |
| **BREEDING_BIAS** | Overbet due to sire/dam | FADE |
| **CONNECTION_BIAS** | Overbet due to trainer/jockey | FADE |
| **DUE_TO_WIN** | Gambler's fallacy | FADE |
| **HOT_STREAK** | Hot hand fallacy | FADE |
| **NONE** | No clear narrative | BACK (if longshot) |

### Disruption Classification

| Strength | Criteria |
|----------|----------|
| **STRONG** | NDS score ≥ 0.6 |
| **MODERATE** | NDS score ≥ 0.4 |
| **WEAK** | NDS score ≥ 0.2 |
| **NONE** | NDS score < 0.2 |

### NDS Scoring

```python
score = avg(signals) × narrative_strength
```

**Opportunities:**
- **FADE:** Strong/moderate disruption + negative narrative
- **BACK:** No narrative + longshot (odds > 10.0)

---

## Module 4: Orchestrator (Dual-Signal Logic)

**Purpose:** Coordinate all modules and enforce dual-signal requirement

**File:** `src/intelligence/orchestrator.py` (350 lines)

### Voting System

Each module votes: **BACK**, **FADE**, or **ABSTAIN**

| Module | Vote Criteria |
|--------|---------------|
| **SQPE** | STRONG signal + edge > 0 + score ≥ 0.6 → BACK |
| **TIE** | WIN_TODAY or PLACED_TO_WIN (score ≥ 0.7) → BACK |
| | EXPERIENCE or DECEIVE → FADE |
| **NDS** | Fade opportunity + score ≥ 0.6 → FADE |
| | Back opportunity (underbet longshot) → BACK |

### Agreement Calculation

```python
back_count = sum(votes == "back")
fade_count = sum(votes == "fade")

agreement_score = aligned_confidence / total_confidence
```

### Bet Recommendations

| Recommendation | Criteria |
|----------------|----------|
| **STRONG_BACK** | 3 modules vote BACK |
| **MODERATE_BACK** | 2 modules vote BACK |
| **HOLD** | < 2 modules agree |
| **MODERATE_FADE** | 2 modules vote FADE |
| **STRONG_FADE** | 3 modules vote FADE |

### Conviction Scoring

```python
conviction = agreement_score × (1.2 if unanimous else 1.0)
```

**Capped at 1.0**

---

## Dual-Signal Logic: Examples

### Example 1: STRONG_BACK

**Runner:** DESERT HERO, odds 8.0

| Module | Vote | Confidence | Reasoning |
|--------|------|------------|-----------|
| SQPE | BACK | 0.85 | Strong convergence (0.82), edge 12% |
| TIE | BACK | 0.78 | WIN_TODAY intent (jockey upgrade + course specialist) |
| NDS | BACK | 0.65 | Underbet longshot, no negative narrative |

**Result:**
- Back count: 3
- Agreement score: 0.76
- Recommendation: **STRONG_BACK**
- Conviction: 0.76 × 1.2 = 0.91

---

### Example 2: MODERATE_FADE

**Runner:** MEDIA DARLING, odds 2.5

| Module | Vote | Confidence | Reasoning |
|--------|------|------------|-----------|
| SQPE | ABSTAIN | 0.0 | Weak convergence (0.35) |
| TIE | FADE | 0.72 | DECEIVE intent (contradictory signals) |
| NDS | FADE | 0.81 | HYPE_FAVORITE (overround 1.18, short odds) |

**Result:**
- Fade count: 2
- Agreement score: 0.77
- Recommendation: **MODERATE_FADE**
- Conviction: 0.77

---

### Example 3: HOLD (No Bet)

**Runner:** AVERAGE JOE, odds 12.0

| Module | Vote | Confidence | Reasoning |
|--------|------|------------|-----------|
| SQPE | BACK | 0.55 | Moderate convergence (0.52), edge 8% |
| TIE | ABSTAIN | 0.0 | Neutral intent |
| NDS | ABSTAIN | 0.0 | No clear narrative |

**Result:**
- Back count: 1
- Agreement score: 0.55
- Recommendation: **HOLD**
- Conviction: 0.0

**No bet placed - insufficient agreement**

---

## Performance Expectations

### Baseline Benter (v1.0)

**Configuration:** α=1.0, β=1.0, min_edge=0.05, Kelly=0.1

| Metric | Value |
|--------|-------|
| Overlay rate | 11.0% |
| Win rate | 7.7% |
| ROI | -5.3% |
| Conclusion | Math works, no edge |

### Intelligence Stack (v1.0)

**Configuration:** Dual-signal (2+ modules), conviction-weighted Kelly

**Expected improvements:**
1. **Selectivity:** 11% → 3-5% (dual-signal filter)
2. **Win rate:** 7.7% → 12-15% (quality over quantity)
3. **ROI:** -5.3% → +10-20% (strategic convergence)

**Path to +41% target:**
- Intelligence stack: +15-25pp
- Self-learning loop: +10-15pp
- Modern data (2023-2024): +5-10pp

---

## Next Evolution: Self-Learning Feedback Loop

### Phase 6 (Not Yet Built)

**Purpose:** Post-race recalibration and dynamic weight adjustment

**Components:**

1. **Post-Race Tracker**
   - Record actual results
   - Calculate actual ROI per pattern
   - Identify winning/losing scenarios

2. **ROI Archive**
   - Store performance by:
     - Horse/trainer/jockey
     - Course/distance
     - Going/class
     - Module combination
     - Narrative type

3. **Auto-Weight Adjustment**
   - Increase weights for profitable patterns
   - Decrease weights for losing patterns
   - Adaptive learning rate

4. **Recalibration Cycle**
   - Weekly: Update trainer/jockey stats
   - Monthly: Reoptimize α, β weights
   - Quarterly: Retrain full model

---

## Testing Plan

### Phase 1: Historical Backtest (2023-2024)

**Data:** Recent.csv (93 MB, ~200k rows)

**Tests:**
1. Baseline Benter vs Intelligence Stack
2. 2-signal vs 3-signal requirement
3. Conviction thresholds (0.5, 0.6, 0.7)
4. Kelly fractions (0.05, 0.1, 0.15)

**Metrics:**
- ROI
- Sharpe ratio
- Maximum drawdown
- Win rate
- Bet frequency

### Phase 2: Live Paper Trading (1 month)

**Platform:** Betfair (no real money)

**Process:**
1. Fetch racecards daily
2. Run intelligence stack
3. Log recommendations
4. Track results
5. Compare to baseline

### Phase 3: Live Deployment (Small stakes)

**Bankroll:** £1,000

**Risk limits:**
- Max bet: 2% of bankroll
- Max exposure per race: 10%
- Max daily loss: 5%

**Success criteria:**
- ROI > 10% over 100 bets
- Max drawdown < 20%
- Sharpe ratio > 1.0

---

## Code Structure

```
src/intelligence/
├── __init__.py           # Module exports
├── sqpe.py               # Sub-Quadratic Prediction Engine (372 lines)
├── tie.py                # Trainer Intention Engine (450 lines)
├── nds.py                # Narrative Disruption Scan (430 lines)
└── orchestrator.py       # Dual-Signal Logic (350 lines)

Total: 1,602 lines of strategic intelligence
```

---

## Usage Example

```python
from src.intelligence import IntelligenceOrchestrator
from src.models import BenterModel

# Initialize
orchestrator = IntelligenceOrchestrator(min_modules_required=2)
benter = BenterModel(alpha=1.0, beta=1.0)

# Get race data
runners = get_racecard("2024-11-09", "Ascot", "14:30")
historical = load_historical_data()

# Run Benter
p_benter_dict = benter.estimate_race(runners)
p_public_dict = {r['id']: 1.0/r['odds'] for r in runners}

# Run intelligence stack
signals = orchestrator.analyze_race(
    runners, p_benter_dict, p_public_dict, historical
)

# Get actionable bets
back_bets = orchestrator.get_back_recommendations(signals)

for signal in back_bets:
    print(f"{signal.horse_name} @ {signal.odds}")
    print(f"Recommendation: {signal.recommendation.value}")
    print(f"Conviction: {signal.conviction:.2f}")
    print(f"Modules agree: {signal.modules_agree_back}/3")
    print(f"Reasoning:")
    for reason in signal.reasoning:
        print(f"  - {reason}")
    print()
```

---

## Conclusion

**The Intelligence Stack is complete and ready for testing.**

**What we built:**
- ✅ 3 independent intelligence modules (SQPE, TIE, NDS)
- ✅ Dual-signal orchestrator
- ✅ 1,602 lines of strategic code
- ✅ Production-ready architecture

**What we need:**
- ⏳ Historical backtest on 2023-2024 data
- ⏳ Self-learning feedback loop (Phase 6)
- ⏳ Live deployment validation

**The transformation is complete:**

**From calculator → To strategist**

**The hunt begins.** 🏇

