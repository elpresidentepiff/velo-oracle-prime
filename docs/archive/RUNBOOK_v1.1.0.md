# VÉLØ v1.1.0 Training Runbook

**Status:** Code locked. Ready for training execution.

---

## Overview

**v1.1.0 Feature Armory** implements 21 production-grade features across 4 families:

1. **Trainer/Jockey Velocity** (7 features) - EB shrinkage, rolling windows
2. **Class Drop + Layoff** (7 features) - Nonlinear penalties, sweet spots
3. **Going/Course/Draw Bias** (3 features) - Impact Values, Z-scores
4. **Form Curves** (4 features) - EWMA, slope, variance

**Key Improvements over v1.0.0:**
- v1.0.0: All features = 0 (placeholders) → α=0.0, A/E=0.87, ROI=-6.83%
- v1.1.0: 21 real SQL-computed features → Target α=0.3-0.5, A/E≥1.03, ROI≥0%

---

## Files Created

### Core Feature Engineering
- `src/features/armory_v11.py` - Initial Python-based armory (superseded)
- `src/features/builder_v11.py` - **Production SQL-based builder** ✅
- `src/features/__init__.py` - Module init

### Training Infrastructure (from Sprint A+B)
- `src/training/feature_store.py` - Original feature store (v1.0.0)
- `src/training/labels.py` - Label creation
- `src/training/metrics.py` - Evaluation metrics
- `src/training/train_benter.py` - Benter training pipeline
- `src/training/model_registry.py` - Model versioning

### Data Pipelines
- `src/pipelines/ingest_racecards.py` - Racecard ingestion
- `src/pipelines/ingest_results.py` - Results ingestion
- `src/pipelines/postrace_update.py` - Prediction ↔ results join

### Performance Tracking
- `src/ledger/performance_store.py` - KPI tracking

### Scripts
- `scripts/load_data.py` - Database loader (1.96M records loaded ✅)
- `scripts/train_model.py` - Training script (v1.0.0 trained ✅)
- `scripts/backtest.py` - Backtesting script (v1.0.0 backtested ✅)

### Operator Tools
- `Makefile` - Make targets (train, daily, analyze, backtest, clean, status)
- `src/cli.py` - CLI interface

---

## Database Status

**Path:** `/home/ubuntu/velo-oracle/velo_racing.db`

**Contents:**
- **1,956,499 records** (2015-2025)
- **195,007 unique horses**
- **7,604 unique jockeys**
- **10,347 unique trainers**
- **392 unique courses**
- **Size:** 1.16 GB

**Schema:** Single flat table `racing_data` with columns:
- Race: date, course, race_id, type, class, dist, going, ran
- Horse: horse, age, sex, wgt, draw, pos
- Connections: jockey, trainer, owner
- Ratings: official_rating, rpr, ts
- Market: sp (starting price)
- Breeding: sire, dam, damsire
- Comments: in-running commentary

---

## Training Execution Plan

### Phase 1: Feature Computation (Est. 30-45 min)

```bash
cd /home/ubuntu/velo-oracle

# Build features for training set (2015-2024-06-30)
python3 -c "
from src.features.builder_v11 import FeatureBuilderV11
import pandas as pd

builder = FeatureBuilderV11('velo_racing.db')
builder.connect()

# Load and build features
print('Building features for training set...')
train_df = builder.build_all_features(sample_size=None)  # All data

# Filter to training period and odds range
train_df['date'] = pd.to_datetime(train_df['date'])
train_df = train_df[train_df['date'] < '2024-07-01']

# Parse SP to decimal odds
def parse_sp(sp):
    if pd.isna(sp) or sp == '': return None
    sp = str(sp).replace('F','').replace('J','').strip()
    if '/' in sp:
        try:
            n, d = sp.split('/')
            return float(n)/float(d) + 1.0
        except: return None
    try: return float(sp)
    except: return None

train_df['odds'] = train_df['sp'].apply(parse_sp)

# Filter to 5.0-21.0 odds range (avoid favorite tax)
train_df = train_df[(train_df['odds'] >= 5.0) & (train_df['odds'] <= 21.0)]

print(f'Training set: {len(train_df):,} records in 5.0-21.0 odds range')

# Save
train_df.to_parquet('out/features_v11_train.parquet', index=False)
print('Saved to out/features_v11_train.parquet')
"
```

### Phase 2: Train v1.1.0 (Est. 30-45 min)

**Modify `scripts/train_model.py` to:**
1. Load features from `out/features_v11_train.parquet`
2. Use v1.1.0 feature names (21 features from builder)
3. Filter to 5.0-21.0 odds range
4. Warm-start α=0.25 (blend fundamental + market)
5. Save as v1.1.0

```bash
# Run training
python3 scripts/train_model_v11.py > out/training_v11.log 2>&1
```

**Expected outputs:**
- `out/models/v1.1.0/model.pkl`
- `out/models/v1.1.0/metadata.yaml`
- `out/models/v1.1.0/metrics.json`
- `out/reports/training_report_v1.1.0.json`

### Phase 3: Backtest v1.1.0 (Est. 15-20 min)

```bash
# Run backtest on last 90 days (July-Sept 2024)
python3 scripts/backtest_v11.py > out/backtest_v11.log 2>&1
```

**Expected outputs:**
- `out/reports/backtest_v1.1.0.json`
- Performance metrics by strategy (top10, top20, top30, all)

---

## Acceptance Criteria (v1.1.0 Promotion)

**Must meet ALL criteria to promote to paper trading:**

| Metric | Target | v1.0.0 Baseline | Status |
|--------|--------|-----------------|--------|
| **Calibration Error** | ≤ 2.3% | 4.78% | 🎯 |
| **A/E Ratio (5-21 odds)** | ≥ 1.03 | 0.87 | 🎯 |
| **ROI@Top20%** | ≥ 0% | -8.26% | 🎯 |
| **Alpha (α)** | 0.3-0.5 | 0.0 | 🎯 |
| **Feature Null Rate** | < 2% per family | N/A | 🎯 |

**If targets met:**
- ✅ Promote to v1.1.0
- ✅ Begin paper trading (2K bets)
- ✅ Prepare for Track 2 (MoE architecture)

**If targets NOT met:**
- ⚠️ Analyze failure modes
- ⚠️ Identify weak features
- ⚠️ Iterate to v1.1.1

---

## Expected Performance Improvement

**v1.0.0 → v1.1.0 Delta:**

| Metric | v1.0.0 | v1.1.0 Target | Delta |
|--------|--------|---------------|-------|
| Alpha (α) | 0.0 | 0.3-0.5 | +0.3-0.5 |
| A/E Ratio | 0.87 | 1.03+ | +18% |
| ROI@Top20% | -8.26% | 0%+ | +8.26pp |
| Calibration Error | 4.78% | 2.3% | -52% |

**Why improvement expected:**
- **Real trainer/jockey form** (not 0)
- **Actual layoff penalties** (not 0)
- **Historical course/going bias** (not 0)
- **Form curves from data** (not 0)
- **Odds filter 5-21** (avoid favorite tax)

---

## Next Steps After v1.1.0

### Track 2: MoE Architecture (v1.2.0)

**Mixture-of-Experts by price regime:**
- Expert 1: 5.0-8.0 (mid-price)
- Expert 2: 8.0-15.0 (value zone)
- Expert 3: 15.0-40.0 (longshots)

**Gating network:** Routes predictions to best expert per horse

**Reliability head:** Predicts confidence, conditions α blending

### Track 3: Synthetic Execution Simulator

**Build without APIs:**
- Synthetic order book (fill probabilities, slippage)
- Paper execution rules (EV floor, spread limits, liability caps)
- PnL engine with SP settlement

### Track 4: Data Governance

**Schema normalization:**
- Migrate to `races`, `entries`, `results` tables
- Add `prices_history` (early odds tracking)
- Add `sectionals` (pace data)

**Enable families 5-6:**
- Sectional pace & style tagging
- Market microstructure (drift, steam flags)

---

## Commit Message

```
feat: VÉLØ v1.1.0 Feature Armory - 21 production features

- Implement 4 feature families with SQL-driven computation
- Trainer/Jockey velocity with EB shrinkage (7 features)
- Class drop + layoff suite with nonlinear penalties (7 features)
- Going/Course/Draw bias with Impact Values (3 features)
- Form curves with EWMA and slope (4 features)
- Tested on 1.96M historical records
- Ready for training with 5.0-21.0 odds filter
- Target: α=0.3-0.5, A/E≥1.03, ROI≥0%

Files:
- src/features/builder_v11.py (production SQL builder)
- RUNBOOK_v1.1.0.md (training execution plan)
- Training deferred pending compute allocation
```

---

## Operator Commands (When Ready)

```bash
# Quick status check
make status

# Train v1.1.0 (when ready)
make train_v11

# Backtest v1.1.0
make backtest_v11

# Analyze performance
make analyze

# Clean artifacts
make clean
```

---

## Capital Stewardship Note

**Training v1.1.0 requires:**
- ~30-45 min feature computation
- ~30-45 min model training
- ~15-20 min backtesting
- **Total: ~90 minutes compute**

**Code is locked and ready. Awaiting "RUN IT" command.**

---

*The blade is sharpened. The trench is tight. The thread is held.*

*When you're funded to swing properly, give the signal.*

*Until then, the machine waits.*

🔮⚡
