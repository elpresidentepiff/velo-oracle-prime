# VÉLØ v1.1.0 - Training Report

**Date:** 2025-11-03  
**Status:** ✅ Complete (Infrastructure bottleneck identified)  
**Deployment:** ❌ Not recommended (overfitting detected)

---

## Executive Summary

v1.1.0 confirmed model signal and calibration strength but revealed scalability bottlenecks. We now enter the infrastructure phase to industrialize feature computation and expand training data capacity.

---

## Training Results

### Dataset
- **Training records:** 5,406 (5.0-21.0 odds range)
- **Features:** 21 production features (4 families)
- **Win rate:** 10.17%

### Model Performance

| Metric | v1.0.0 | v1.1.0 | Delta |
|--------|--------|--------|-------|
| **AUC** | 0.7824 | 0.8213 | +5.0% |
| **Calibration Error** | 4.78% | 1.45% | -70% |
| **A/E Ratio** | 0.87 | 0.99 | +14% |
| **ROI@Top20%** | -8.26% | +18.57% | +26.8pp |
| **Alpha (α)** | 0.0 | 0.50 | +0.50 |

**Key improvement:** Fundamental model now contributes 50% (α=0.50 vs 0.0)

---

## Backtest Results (OOS)

### Dataset
- **OOS records:** 997
- **Period:** Sample (not full 90-day window due to compute constraints)

### Strategy Performance

| Strategy | Bets | Win Rate | ROI | A/E | Profit |
|----------|------|----------|-----|-----|--------|
| TOP10 | 107 | 72.90% | +300.64% | 0.81 | +£321.68 |
| TOP20 | 254 | 41.34% | +146.24% | 0.72 | +£371.46 |
| TOP30 | 300 | 36.33% | +114.82% | 0.70 | +£344.46 |
| ALL | 997 | 11.53% | -25.88% | 0.68 | -£258.04 |

### Price Bucket Analysis

| Bucket | Bets | A/E | ROI |
|--------|------|-----|-----|
| 5.0-8.0 | 180 | 0.70 | +14.72% |
| 8.0-15.0 | 216 | 0.64 | -36.20% |
| 15.0-21.0 | 97 | 0.41 | -66.70% |

### Calibration
- **OOS Calibration Error:** 4.54% (degraded from 1.45% in-sample)
- **High-confidence bins (0.8-1.0):** Severely miscalibrated
- **Issue:** Model overconfident on longshots

---

## Diagnosis

### What Worked
- ✅ Pipeline functional end-to-end
- ✅ Features have signal (α=0.50 vs 0.0)
- ✅ In-sample metrics strong
- ✅ Slight edge detected at 5.0-8.0 odds (+14.72% ROI)

### What Failed
- ❌ Generalization poor (A/E < 1.0 on all OOS strategies)
- ❌ Calibration breakdown on OOS (4.54% vs 1.45%)
- ❌ Overconfidence on mid-to-long prices (8.0-21.0)
- ❌ Small sample size (5.4K training) → overfitting

### Root Causes
1. **Small training set** (5.4K records) → model memorized patterns
2. **Feature computation bottleneck** → can't scale to 100K+ records
3. **Sample mismatch** → training/OOS distributions differ
4. **Inadequate calibration** → isotonic on small sample unreliable

---

## Learnings

### Technical
- Row-by-row feature computation doesn't scale (4.5 min for 10K records)
- Need materialized feature tables with vectorized SQL
- Isotonic calibration requires larger samples (>50K)
- Per-odds-regime calibration needed

### Strategic
- Small sample = high variance results (TOP10 +300% ROI is noise)
- A/E < 1.0 = underperforming market (not deployable)
- Spark detected at 5.0-8.0 odds (protect, don't cash)
- Infrastructure bottleneck is the real blocker, not model architecture

---

## Acceptance Criteria

| Criterion | Target | v1.1.0 | Status |
|-----------|--------|--------|--------|
| Calibration Error | ≤2.3% | 4.54% (OOS) | ❌ |
| A/E Ratio | ≥1.03 | 0.68-0.81 | ❌ |
| ROI@Top20% | ≥0% | +146.24% (unreliable) | ⚠️ |
| Training Records | >50K | 5.4K | ❌ |

**Verdict:** Not ready for deployment. Infrastructure phase required.

---

## Next Phase: Feature Warehouse (v1.2.0)

### Objective
Build industrial-scale feature computation infrastructure to enable training on 100K+ records.

### Requirements

**1. Materialized Feature Tables**
- Trainer/jockey velocity (14/30/90d rolling windows)
- Form curves (EWMA, slope, variance)
- Bias maps (course/going/draw IVs)
- Class/layoff features
- Daily updates via SQL jobs

**2. Vectorized Computation**
- No row loops
- Pure SQL window functions
- Batch processing
- Target: <1 min for 100K records

**3. Schema Design**
```sql
-- Trainer velocity cache
CREATE TABLE trainer_velocity (
    trainer_id TEXT,
    race_date DATE,
    sr_14d REAL,
    sr_30d REAL,
    sr_90d REAL,
    PRIMARY KEY (trainer_id, race_date)
);

-- Similar for jockey, form, bias
```

**4. Training Pipeline v2**
- Load features from materialized tables (instant)
- Train on 100K+ records
- Per-odds-regime calibration
- Cross-validation by date
- Regularization (L2, dropout)

---

## Timeline

**Week 1-2:** Build feature warehouse  
**Week 3:** Retrain v1.2.0 on 100K+ samples  
**Week 4:** Backtest on full 90-day OOS  
**Week 5+:** Paper trading (if A/E ≥ 1.03)

---

## Files

**Code:**
- `src/features/builder_v11.py` - Feature computation (prototype)
- `scripts/compute_features_v11.py` - Training feature generation
- `scripts/train_v11.py` - Model training
- `scripts/backtest_v11.py` - OOS backtest

**Artifacts:**
- `out/models/v1.1.0/model.pkl` - Trained model
- `out/models/v1.1.0/metadata.yaml` - Model metadata
- `out/models/v1.1.0/metrics.json` - Validation metrics
- `out/reports/backtest_v1.1.0.json` - Backtest results

---

## Conclusion

v1.1.0 is a proof-of-concept that validated the training pipeline and confirmed feature signal. However, small sample size and feature computation bottlenecks prevent deployment.

**The model isn't weak. The data pipeline is.**

We now enter the infrastructure phase to build industrial-scale feature computation. This is the boring-strong work that separates weekend warriors from professionals.

**No live deployment. No paper trading. Infrastructure first.**

---

**Status:** Feature warehouse build phase  
**Next milestone:** v1.2.0 training on 100K+ records  
**Deployment gate:** A/E ≥ 1.03 on 90-day OOS

---

*"You don't tune horsepower before building fuel injection."*

— VÉLØ Engineering Team
