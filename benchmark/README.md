# VELO Benchmark Regression Protection System

**Anchor Date (Locked):** `2026-01-09`  
**No NOW(), no vibes, no drift.**

## Overview

Deterministic benchmark testing system that freezes 2,000 races and enforces quality gates in CI to prevent regressions.

## Architecture

```
benchmark/
  ├── __init__.py             # Package initialization
  ├── freeze_manifest.py      # Deterministic race selection from Supabase
  ├── runner.py               # Execute pipeline on manifest races
  ├── metrics.py              # Calculate coverage/runtime/distribution metrics
  ├── tolerances.py           # Define regression thresholds
  ├── report.py               # Generate baseline diff reports
  ├── merge_shards.py         # Combine parallel shard results
  ├── check_regression.py     # CI validation
  ├── cli.py                  # CLI interface for all commands
  ├── manifest_2000.json      # 2,000 frozen races (to be replaced by Manus)
  ├── baseline_metrics.json   # Baseline metrics (to be replaced by Manus)
  ├── baseline_hash.txt       # Deterministic output hash (to be replaced by Manus)
  └── README.md               # This file
```

## Prerequisites

The following baseline files must be generated and committed by Manus before this system is fully operational:

- `benchmark/manifest_2000.json` - 2,000 races from last 36 months ending 2026-01-09
- `benchmark/baseline_metrics.json` - Baseline coverage/runtime/distribution metrics
- `benchmark/baseline_hash.txt` - Deterministic output hash for regression detection

## Usage

### 1. Freeze Manifest (One-time Setup)

Generate a deterministic 2,000-race manifest:

```bash
python -m benchmark.cli freeze \
  --as-of-date 2026-01-09 \
  --months 36 \
  --n-races 2000 \
  --out benchmark/manifest_2000.json
```

### 2. Run Benchmark

Execute the pipeline on all races in the manifest:

```bash
python -m benchmark.cli run \
  --manifest benchmark/manifest_2000.json \
  --as-of-date 2026-01-09 \
  --out /tmp/results.json
```

For parallel execution with sharding:

```bash
python -m benchmark.cli run \
  --manifest benchmark/manifest_2000.json \
  --as-of-date 2026-01-09 \
  --shard 1 \
  --total-shards 10 \
  --out /tmp/shard_1.json
```

### 3. Calculate Metrics

Calculate coverage, runtime, and distribution metrics:

```bash
python -m benchmark.cli metrics \
  --input /tmp/results.json \
  --out /tmp/metrics.json
```

Calculate deterministic hash:

```bash
python -m benchmark.cli metrics \
  --input /tmp/results.json \
  --hash \
  --out /tmp/hash.txt
```

### 4. Generate Report

Compare current run against baseline:

```bash
python -m benchmark.cli report \
  --current /tmp/results.json \
  --baseline benchmark/baseline_metrics.json \
  --out /tmp/report.json
```

### 5. Check Regression

Validate against quality gates (for CI):

```bash
python -m benchmark.cli check \
  --report /tmp/report.json \
  --fail-on-violation
```

### 6. Merge Shards

Combine results from parallel shard execution:

```bash
python -m benchmark.cli merge \
  --shards-dir /tmp/shards \
  --out /tmp/merged.json
```

## Quality Gates

### Hard Gates (CI Fails)

1. **Determinism**: Output hash must be identical on repeat runs
2. **Coverage**: Must be ≥99.5% or baseline - 0.5%
3. **Garbage Patterns**: No all-zero scores or placeholder names
4. **Runtime**: p95 runtime ≤ baseline × 1.30

### Soft Gates (Warning Only)

1. **ROI**: ≥ baseline - 2.0pp
2. **Log-loss**: ≤ baseline × 1.05

## CI Workflow

The benchmark runs automatically on PRs that touch:
- `app/engine/**`
- `app/strategy/**`
- `app/ml/**`
- `workers/ingestion_spine/**`
- `benchmark/**`

### Workflow Steps

1. **Matrix Sharding**: Splits 2,000 races across 10 parallel shards (200 races each)
2. **Shard Execution**: Each shard runs independently
3. **Merge Results**: Combines all shard outputs
4. **Calculate Metrics**: Computes coverage, runtime, distribution
5. **Generate Report**: Compares against baseline
6. **Check Regression**: Validates quality gates
7. **PR Comment**: Posts results to PR

### Example CI Output

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

## Determinism Guarantee

Same manifest + same as_of_date → same output (deterministic hash)

The system ensures determinism by:
1. Stable race ordering (ORDER BY race_date, race_id)
2. Fixed as_of_date for feature extraction
3. No NOW() or time-dependent queries
4. Hash validation on repeat runs

## Development

### Running Tests

```bash
# Run benchmark tests
pytest tests/test_benchmark*.py -v

# Run full test suite
pytest tests/ -v
```

### Adding New Metrics

1. Add calculation logic to `benchmark/metrics.py`
2. Update thresholds in `benchmark/tolerances.py`
3. Update report generation in `benchmark/report.py`

### Updating Baseline

To update the baseline after a major change:

1. Run benchmark and verify results
2. Calculate new metrics and hash
3. Update `benchmark/baseline_metrics.json`
4. Update `benchmark/baseline_hash.txt`
5. Commit changes with justification

## Troubleshooting

### "Manifest not found"

Ensure `benchmark/manifest_2000.json` is committed to the repository.

### "Baseline not found"

This is expected on the first run. The workflow will skip regression checks and generate baseline files.

### "Hash mismatch"

This indicates non-deterministic behavior. Check:
- Feature extraction using correct as_of_date
- No NOW() or time-dependent queries
- Stable ordering in queries
- Consistent random seeds (if applicable)

### "Coverage regression"

Pipeline is scoring fewer runners than baseline. Investigate:
- Changes to feature extraction
- Changes to scoring logic
- Missing data in test environment

## Contributing

When making changes that affect pipeline output:

1. Run benchmark locally first
2. Review metrics and ensure quality gates pass
3. If gates fail, fix issues or update thresholds (with justification)
4. Update baseline if necessary (requires approval)
5. Document changes in PR description

## References

- Issue: Benchmark Backtest Pack - Regression Protection System
- Anchor Date: 2026-01-09 (LOCKED)
- Target: 2,000 races, 36-month window
- Sharding: 10 shards × 200 races each
