# VÉLØ Oracle - Vast.ai Deployment Guide

**Version:** 1.0.0  
**Last Updated:** 2024-01-09

Complete guide for deploying VÉLØ Oracle to Vast.ai for full-scale training on 1.7M race dataset.

---

## Prerequisites

### 1. Vast.ai Account Setup

- **Sign up:** https://vast.ai
- **Add payment method** (credit card or crypto)
- **Install Vast.ai CLI:**
  ```bash
  pip3 install vastai
  vastai set api-key <your_api_key>
  ```

### 2. Instance Requirements

**Minimum specifications:**
- **RAM:** 16GB (32GB recommended)
- **Storage:** 50GB
- **GPU:** Not required (CPU training is fine)
- **OS:** Ubuntu 20.04 or 22.04

**Recommended instance types:**
- CPU-only instances (cheaper for our use case)
- On-demand or interruptible (save costs)

### 3. Local Prerequisites

- **VÉLØ Oracle repository** cloned and up-to-date
- **raceform.csv** (633MB, 1.7M rows) ready to upload
- **Vast.ai CLI** installed and configured
- **SSH access** enabled

---

## Deployment Steps

### Step 1: Rent Vast.ai Instance

```bash
# Search for suitable instances
vastai search offers 'cpu_ram >= 16 disk_space >= 50'

# Rent an instance (replace <offer_id> with actual ID)
vastai create instance <offer_id> \
  --image pytorch/pytorch:latest \
  --disk 50

# Note the instance ID (e.g., 12345)
```

**Expected cost:** $0.10-0.30/hour for 16GB RAM instance

### Step 2: Deploy VÉLØ Oracle

```bash
# From your local machine, in velo-oracle directory
./scripts/vastai_deploy.sh <instance_id>
```

**This script will:**
1. Create deployment package
2. Upload to Vast.ai instance
3. Install dependencies
4. Set up PostgreSQL database
5. Run migrations
6. Create required directories

**Duration:** ~5-10 minutes

### Step 3: Upload Training Data

```bash
# Get SSH connection details
vastai ssh-url <instance_id>

# Upload raceform.csv (replace <host> and <port>)
scp -P <port> /path/to/raceform.csv root@<host>:/workspace/velo-oracle/data/
```

**Upload time:** ~2-5 minutes (depending on connection speed)

### Step 4: Connect to Instance

```bash
# SSH into instance
ssh -p <port> root@<host>

# Navigate to project
cd /workspace/velo-oracle

# Verify setup
ls -lh data/raceform.csv
python3 --version
pip3 list | grep pandas
```

### Step 5: Run Full Training

```bash
# Execute training script
./scripts/vastai_train.sh
```

**This will run:**
1. **Grid search** for optimal α, β parameters (2-4 hours)
2. **Comprehensive backtests** on 2015, 2020, 2023 data (1-2 hours)
3. **Error mapping** analysis (30-60 minutes)

**Total duration:** ~4-7 hours

**Expected output:**
```
results/training_20240109_120000/
├── training.log
├── benter_model_optimal.pkl
├── backtests/
│   ├── BACKTEST_CONVERGENCE_REPORT_*.md
│   └── backtest_results_*.json
└── error_maps/
    ├── ERROR_MAP_V1_*.json
    ├── NDS_TRAINING_NOTES_*.md
    └── MODULE_DRIFT_REPORT_*.md
```

### Step 6: Download Results

```bash
# From local machine
scp -P <port> -r root@<host>:/workspace/velo-oracle/results/training_* ./results/
```

### Step 7: Destroy Instance (Optional)

```bash
# When training is complete
vastai destroy instance <instance_id>
```

**Important:** Don't forget to destroy the instance to avoid ongoing charges!

---

## Training Phases Explained

### Phase 1: Grid Search Training

**What it does:**
- Tests multiple combinations of α (fundamental weight) and β (public weight)
- Evaluates each combination on validation set
- Selects optimal parameters based on log loss

**Parameters tested:**
- α: 0.5, 1.0, 1.5, 2.0
- β: 0.5, 1.0, 1.5, 2.0
- Total: 16 combinations

**Output:**
- `benter_model_optimal.pkl` - Best model
- `training.log` - Full training log with metrics

### Phase 2: Comprehensive Backtests

**What it does:**
- Tests baseline Benter vs Intelligence Stack
- Compares 2-module vs 3-module convergence
- Calculates ROI, Sharpe, win rate, drawdown

**Years tested:**
- 2015 (early period)
- 2020 (mid period)
- 2023 (recent period)

**Output:**
- `BACKTEST_CONVERGENCE_REPORT_*.md` - Detailed analysis
- `backtest_results_*.json` - Raw metrics

### Phase 3: Error Mapping

**What it does:**
- Tracks false positives/negatives per module
- Identifies narrative traps (hype favorites, false form)
- Generates NDS training notes

**Output:**
- `ERROR_MAP_V1_*.json` - Full error ledger
- `NDS_TRAINING_NOTES_*.md` - Refinement suggestions
- `MODULE_DRIFT_REPORT_*.md` - Module performance analysis

---

## Expected Results

### Baseline Performance (from 10k sample)

| Metric | Value |
|--------|-------|
| ROI | -5.3% |
| Win Rate | ~12% |
| Sharpe | -0.15 |
| Max Drawdown | ~35% |

### Target Performance (with Intelligence Stack)

| Metric | Target |
|--------|--------|
| ROI | +41% |
| Win Rate | 18-22% |
| Sharpe | 1.5+ |
| Max Drawdown | <25% |

**Key hypothesis:** Dual-signal convergence (2+ modules agree) should dramatically improve hit rate and reduce volatility.

---

## Troubleshooting

### Issue: Out of Memory

**Symptoms:**
```
MemoryError: Unable to allocate array
```

**Solutions:**
1. Increase chunk size in training script:
   ```bash
   python3 scripts/train_benter_chunked.py --chunk-size 50000
   ```

2. Rent larger instance (32GB RAM)

3. Reduce grid search space:
   ```bash
   python3 scripts/train_benter_chunked.py \
     --alpha-range 1.0 1.5 \
     --beta-range 1.0 1.5
   ```

### Issue: PostgreSQL Connection Failed

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**
```bash
# Start PostgreSQL
service postgresql start

# Check status
service postgresql status

# Verify connection
psql -U velo -d velo_oracle
```

### Issue: Training Stalled

**Symptoms:**
- No progress for >30 minutes
- CPU usage at 0%

**Solutions:**
```bash
# Check process
ps aux | grep python

# Check logs
tail -f results/training_*/training.log

# Restart if needed
pkill python3
./scripts/vastai_train.sh
```

### Issue: Upload Failed

**Symptoms:**
```
scp: Connection refused
```

**Solutions:**
```bash
# Verify instance is running
vastai show instance <instance_id>

# Check SSH details
vastai ssh-url <instance_id>

# Try direct SSH first
ssh -p <port> root@<host>
```

---

## Cost Estimation

### Instance Costs (16GB RAM, CPU-only)

| Duration | Cost (approx) |
|----------|---------------|
| 1 hour | $0.10-0.30 |
| 5 hours (full training) | $0.50-1.50 |
| 24 hours (if left running) | $2.40-7.20 |

**Total expected cost for full training:** **$1-2**

### Tips to Minimize Costs

1. **Use interruptible instances** (50% cheaper)
2. **Destroy immediately after download** (don't leave running)
3. **Run during off-peak hours** (better availability, lower prices)
4. **Use CPU-only instances** (we don't need GPU)

---

## Post-Training Workflow

### 1. Review Results

```bash
# Open backtest report
cat results/training_*/backtests/BACKTEST_CONVERGENCE_REPORT_*.md

# Check error maps
cat results/training_*/error_maps/MODULE_DRIFT_REPORT_*.md

# Review NDS training notes
cat results/training_*/error_maps/NDS_TRAINING_NOTES_*.md
```

### 2. Update Model Weights

If training found better parameters:

```python
# In src/models/benter.py
self.alpha = 1.5  # Update from training results
self.beta = 1.2   # Update from training results
```

### 3. Refine Intelligence Modules

Based on error mapping:

```python
# In src/intelligence/nds.py
# Adjust thresholds based on NDS_TRAINING_NOTES
self.hype_threshold = 0.75  # Increase if too many false positives
```

### 4. Commit and Tag

```bash
git add .
git commit -m "feat: update weights from Vast.ai training (α=1.5, β=1.2)"
git tag -a v10.1-trained -m "Full training on 1.7M dataset"
git push origin feature/v10-launch --tags
```

### 5. Deploy Self-Learning Loop

```bash
# Install cron jobs for continuous learning
./scripts/cron_schedule.sh install

# Verify
./scripts/cron_schedule.sh status
```

---

## Next Steps After Training

1. **Paper trading** (1 month, no real money)
   - Monitor live performance
   - Validate intelligence stack in production
   - Track convergence accuracy

2. **Live deployment** (small stakes)
   - Start with £1,000 bankroll
   - Use fractional Kelly (0.1)
   - Require 3-module convergence initially

3. **Scale up** (if successful)
   - Increase bankroll
   - Relax to 2-module convergence
   - Target +41% ROI

---

## Support

**Issues or questions?**

- **GitHub Issues:** https://github.com/elpresidentepiff/velo-oracle/issues
- **Documentation:** `/docs/` directory
- **Logs:** Check `/var/log/velo/` on instance

**Remember:** This is a sophisticated betting system. Always start with paper trading and small stakes. Never bet more than you can afford to lose.

---

**Good luck! May the convergence be with you.** 🏇⚡

