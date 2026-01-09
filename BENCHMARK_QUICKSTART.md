# Benchmark Quick Start Guide

## For Manus (One-Time Setup)

### Generate Baseline Files

```bash
# Set environment variables
export SUPABASE_URL="your_supabase_url"
export SUPABASE_SERVICE_ROLE_KEY="your_service_key"

# 1. Freeze manifest (2,000 races from last 36 months)
python -m benchmark.cli freeze \
  --as-of-date 2026-01-09 \
  --months 36 \
  --n-races 2000 \
  --out benchmark/manifest_2000.json

# 2. Run baseline benchmark
python -m benchmark.cli run \
  --manifest benchmark/manifest_2000.json \
  --as-of-date 2026-01-09 \
  --out /tmp/baseline_run.json

# 3. Calculate metrics
python -m benchmark.cli metrics \
  --input /tmp/baseline_run.json \
  --out benchmark/baseline_metrics.json

# 4. Calculate hash
python -m benchmark.cli metrics \
  --input /tmp/baseline_run.json \
  --hash \
  --out benchmark/baseline_hash.txt

# 5. Commit (replace placeholders)
git add benchmark/manifest_2000.json benchmark/baseline_metrics.json benchmark/baseline_hash.txt
git commit -m "Add benchmark baseline files (2,000 races, 2026-01-09)"
git push
```

## For Developers (Local Testing)

### Run Local Benchmark

```bash
# Run full benchmark locally
python -m benchmark.cli run \
  --manifest benchmark/manifest_2000.json \
  --as-of-date 2026-01-09 \
  --out /tmp/my_run.json

# Calculate metrics
python -m benchmark.cli metrics \
  --input /tmp/my_run.json \
  --out /tmp/my_metrics.json

# Generate report
python -m benchmark.cli report \
  --current /tmp/my_run.json \
  --baseline benchmark/baseline_metrics.json \
  --out /tmp/my_report.json

# Check regression (exit 1 on fail)
python -m benchmark.cli check \
  --report /tmp/my_report.json \
  --fail-on-violation
```

### Run Specific Shard

```bash
# Run just shard 1 of 10 for faster iteration
python -m benchmark.cli run \
  --manifest benchmark/manifest_2000.json \
  --as-of-date 2026-01-09 \
  --shard 1 \
  --total-shards 10 \
  --out /tmp/shard_1.json
```

## CI Workflow

### Automatic Triggers

Benchmark runs automatically on PRs affecting:
- `app/engine/**`
- `app/strategy/**`
- `app/ml/**`
- `workers/ingestion_spine/**`
- `benchmark/**`

### Manual Trigger

```bash
# Trigger via GitHub CLI
gh workflow run benchmark.yml
```

### Expected Output

```
📊 Benchmark Results

### Metrics
- Coverage: 99.8% (15,234/15,264 runners)
- Races Processed: 2000
- Runtime: 245.3s (0.123s/race)

### Regression Check: ✅ PASS

✅ No violations detected

#### Deltas vs Baseline
- Coverage: +0.1%
- Runtime: -0.005s/race
```

## Quality Gates

### Hard Gates (Fail CI)
- ❌ Coverage < 99.5%
- ❌ Any all-zero scores
- ❌ Any placeholder names
- ❌ Runtime > baseline × 1.30

### Soft Gates (Warning)
- ⚠️ ROI < baseline - 2.0pp
- ⚠️ Log-loss > baseline × 1.05

## Troubleshooting

### Hash Mismatch
Non-deterministic behavior detected. Check:
- Feature queries use `as_of_date` parameter
- No `NOW()` in queries
- Stable `ORDER BY` clauses
- Fixed random seeds

### Coverage Regression
Pipeline scoring fewer runners. Investigate:
- Feature extraction changes
- Scoring logic changes
- Missing test data

### CI Timeout
Shard taking > 30 minutes:
- Check database performance
- Review query efficiency
- Verify batch filtering

## Commands Cheat Sheet

```bash
# Freeze manifest
benchmark.cli freeze --as-of-date YYYY-MM-DD --out FILE

# Run benchmark
benchmark.cli run --manifest FILE --as-of-date YYYY-MM-DD --out FILE

# Run with sharding
benchmark.cli run --manifest FILE --as-of-date YYYY-MM-DD --shard N --total-shards M --out FILE

# Calculate metrics
benchmark.cli metrics --input FILE --out FILE

# Calculate hash
benchmark.cli metrics --input FILE --hash --out FILE

# Merge shards
benchmark.cli merge --shards-dir DIR --out FILE

# Generate report
benchmark.cli report --current FILE --baseline FILE --out FILE

# Check regression
benchmark.cli check --report FILE --fail-on-violation
```

## Files & Locations

```
benchmark/
  ├── manifest_2000.json          # 2,000 frozen races
  ├── baseline_metrics.json       # Baseline metrics
  ├── baseline_hash.txt           # Baseline hash
  └── README.md                   # Full documentation

.github/workflows/
  └── benchmark.yml               # CI workflow

tests/
  └── test_benchmark.py           # Unit tests (8 tests)
```

## Support

- Full docs: `benchmark/README.md`
- Implementation: `BENCHMARK_IMPLEMENTATION.md`
- Tests: `pytest tests/test_benchmark.py -v`
