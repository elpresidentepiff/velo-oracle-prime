#!/bin/bash
#
# VÉLØ Oracle - Vast.ai Training Execution
#
# Runs full-scale training on Vast.ai instance with 1.7M dataset
#
# Prerequisites:
# - Deployed to Vast.ai (via vastai_deploy.sh)
# - raceform.csv uploaded to /workspace/velo-oracle/data/
#
# Usage: ./scripts/vastai_train.sh
#

set -e

echo "VÉLØ Oracle - Full-Scale Training"
echo "=================================="
echo ""

# Check for data file
DATA_FILE="/workspace/velo-oracle/data/raceform.csv"

if [ ! -f "$DATA_FILE" ]; then
    echo "Error: Data file not found at $DATA_FILE"
    echo ""
    echo "Please upload raceform.csv to /workspace/velo-oracle/data/"
    echo ""
    echo "From local machine:"
    echo "  scp -P <port> raceform.csv root@<host>:/workspace/velo-oracle/data/"
    exit 1
fi

# Get file size
FILE_SIZE=$(du -h "$DATA_FILE" | cut -f1)
ROW_COUNT=$(wc -l < "$DATA_FILE")

echo "Data file found:"
echo "  Path: $DATA_FILE"
echo "  Size: $FILE_SIZE"
echo "  Rows: $ROW_COUNT"
echo ""

# Check available memory
TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}')
AVAIL_MEM=$(free -h | awk '/^Mem:/ {print $7}')

echo "System resources:"
echo "  Total memory: $TOTAL_MEM"
echo "  Available memory: $AVAIL_MEM"
echo "  CPUs: $(nproc)"
echo ""

# Confirm before proceeding
read -p "Proceed with training? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Training cancelled"
    exit 0
fi

echo ""
echo "Starting training..."
echo "===================="
echo ""

# Create output directory
OUTPUT_DIR="/workspace/velo-oracle/results/training_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# Run training with grid search
echo "Phase 1: Grid search for optimal parameters..."
python3 /workspace/velo-oracle/scripts/train_benter_chunked.py \
    --data "$DATA_FILE" \
    --output-dir "$OUTPUT_DIR" \
    --chunk-size 100000 \
    --alpha-range 0.5 1.0 1.5 2.0 \
    --beta-range 0.5 1.0 1.5 2.0 \
    2>&1 | tee "$OUTPUT_DIR/training.log"

echo ""
echo "✓ Training complete"
echo ""

# Run comprehensive backtests
echo "Phase 2: Comprehensive backtests..."
echo "===================================="
echo ""

for YEAR in 2015 2020 2023; do
    echo "Testing year: $YEAR"
    
    python3 /workspace/velo-oracle/scripts/backtest_convergence.py \
        --data "$DATA_FILE" \
        --years $YEAR \
        --output-dir "$OUTPUT_DIR/backtests" \
        --bankroll 1000 \
        2>&1 | tee "$OUTPUT_DIR/backtest_$YEAR.log"
    
    echo ""
done

echo "✓ Backtests complete"
echo ""

# Run error mapping
echo "Phase 3: Error mapping analysis..."
echo "==================================="
echo ""

python3 /workspace/velo-oracle/scripts/error_mapper.py \
    --data "$DATA_FILE" \
    --output-dir "$OUTPUT_DIR/error_maps" \
    --year 2023 \
    2>&1 | tee "$OUTPUT_DIR/error_mapping.log"

echo ""
echo "✓ Error mapping complete"
echo ""

# Generate summary
echo "=================================="
echo "✓ ALL PHASES COMPLETE"
echo "=================================="
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "Key files:"
echo "  - Training log: $OUTPUT_DIR/training.log"
echo "  - Backtest reports: $OUTPUT_DIR/backtests/"
echo "  - Error maps: $OUTPUT_DIR/error_maps/"
echo ""

# List all generated reports
echo "Generated reports:"
find "$OUTPUT_DIR" -name "*.md" -o -name "*.json" | sort

echo ""
echo "To download results to local machine:"
echo "  scp -P <port> -r root@<host>:$OUTPUT_DIR ."
echo ""

