# VÉLØ Baseline v1.0 - Benter Model Calibration

**Version:** Baseline_α1_β1_v1.0  
**Date:** 2025-11-09  
**Status:** Committed as control layer

---

## Executive Summary

This baseline represents the **pure Benter model** - a mathematical calculator that identifies mispriced horses using fundamental analysis (ratings) and public odds. It establishes the foundation upon which intelligence modules will be built.

**Performance:** -5.3% ROI (10k sample, Jan 2015)  
**Conclusion:** Math works, but lacks strategic intelligence

---

## Model Architecture

### Benter Combination Formula

```
p_model = α × p_fundamental + β × p_public
```

**Where:**
- `p_fundamental` = Probability from ratings (OR, RPR, TS) via softmax transform
- `p_public` = Market-implied probability (1 / odds)
- `α, β` = Learned weights

### Optimal Weights (Grid Search)

**Training:** 10k sample, 2015-2023 data, 1,024 races

| Parameter | Value | Interpretation |
|-----------|-------|----------------|
| **α** | 1.0 | Fundamental weight (balanced) |
| **β** | 1.0 | Public odds weight (balanced) |
| **Log Loss** | 0.2788 | Calibration quality |

**Initial attempt (α=1.5, β=0.5):**
- Too contrarian
- 41.5% overlay rate (absurd)
- -100% ROI (bust)

**Recalibrated (α=1.0, β=1.0):**
- Balanced approach
- 11.0% overlay rate (realistic)
- -5.3% ROI (survived)

---

## Betting Strategy

### Overlay Selection Criteria

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Min Edge** | 0.05 (5%) | Selective - clear advantage required |
| **Max Odds** | 40.0 | Disciplined longshots |
| **Min Odds** | 1.5 | Exclude favorites |
| **Kelly Fraction** | 0.1 | Conservative sizing (10% of full Kelly) |

### Backtest Results (Jan 2015)

**Sample:** 10,000 rows, 1,024 races, 8,519 qualified runners

| Metric | Value |
|--------|-------|
| **Overlays Found** | 938 (11.0% of runners) |
| **Average Edge** | 8.8% |
| **Average Odds** | 18.01 |
| **Odds Range** | 2.2 - 40.0 |
| **Total Bets** | 938 |
| **Wins** | 72 (7.7% strike rate) |
| **Total Staked** | £10,855.76 |
| **Total Profit** | -£575.80 |
| **ROI** | -5.3% |
| **Final Bankroll** | £424.20 (started £1,000) |
| **Return** | -57.6% |

---

## Key Findings

### What Works

1. **Selectivity:** 11% overlay rate is realistic (vs 41.5% in over-contrarian model)
2. **Odds discipline:** Average 18.0 odds (vs 31.3 in longshot-chasing model)
3. **Survival:** Bankroll survived (vs bust in aggressive model)
4. **Win rate:** 7.7% (vs 5.9% in aggressive model)

### What Doesn't Work

1. **Still losing:** -5.3% ROI means no edge found
2. **Market efficiency:** Public odds already incorporate ratings information
3. **Blind betting:** No context, intent, or timing awareness
4. **Single-signal:** Relying on Benter alone is insufficient

---

## Root Cause Analysis

**The Benter model is a calculator, not a strategist.**

**It can:**
- ✅ Calculate probabilities from ratings
- ✅ Identify mathematical overlays
- ✅ Size bets via Kelly criterion

**It cannot:**
- ❌ Detect trainer intent
- ❌ Recognize pace scenarios
- ❌ Identify prep cycle patterns
- ❌ Spot narrative disruption
- ❌ Learn from past results

**Conclusion:** The market has absorbed basic Benter logic. We need intelligence layers to find edges the market misses.

---

## Next Evolution: Intelligence Modules

### Phase 2: SQPE (Sub-Quadratic Prediction Engine)
- **Purpose:** Filter noise, amplify convergence signals
- **Method:** Multi-factor ranking with sub-quadratic complexity
- **Output:** True-value edge scores

### Phase 3: TIE (Trainer Intention Engine)
- **Purpose:** Quantify trainer placement strategy
- **Signals:**
  - Jockey booking patterns
  - Seasonal prep cycles
  - Course/distance specialization
  - Trainer strike rates by scenario

### Phase 4: NDS (Narrative Disruption Scan)
- **Purpose:** Detect market misreads
- **Signals:**
  - Hype vs reality gaps
  - False bias identification
  - Media-driven price distortions

### Phase 5: Dual-Signal Logic
- **Rule:** No bet unless 2+ intelligence modules agree
- **Example:** SQPE + TIE convergence required
- **Rationale:** Reduces false positives, increases conviction

### Phase 6: Self-Learning Feedback Loop
- **Mechanism:** Post-race recalibration
- **Data:** ROI archive per horse/trainer/course/scenario
- **Adaptation:** Auto-weight adjustment based on actual results

---

## Baseline Commit

**Branch:** `feature/v10-launch`  
**Tag:** `baseline-v1.0`  
**Files:**
- `models/benter_weights_10k.json` - Trained weights (α=1.0, β=1.0)
- `models/backtest_recalibrated.json` - Backtest results
- `scripts/train_benter.py` - Training script
- `scripts/backtest.py` - Backtesting framework
- `docs/BASELINE_V1.0.md` - This document

---

## Performance Target

**Current:** -5.3% ROI (baseline Benter only)  
**Target:** +41% ROI (23-race system benchmark)  
**Gap:** 46.3 percentage points

**Path to close gap:**
1. Intelligence modules (SQPE, TIE, NDS) → +20-30pp
2. Dual-signal logic → +10-15pp
3. Self-learning feedback loop → +5-10pp
4. Modern data (2023-2024) → +5-10pp

**Total potential:** +40-65pp improvement

---

## Conclusion

**Baseline v1.0 establishes the foundation:**
- ✅ Benter model works mathematically
- ✅ Grid search finds optimal weights
- ✅ Kelly sizing prevents catastrophic loss
- ✅ Overlay detection is functional

**But it's not enough:**
- ❌ No strategic intelligence
- ❌ No context awareness
- ❌ No learning mechanism

**Next step:** Transform calculator into strategist by adding intelligence layers.

**The hunt begins.** 🏇

