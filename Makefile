# VÉLØ v10.1 - Makefile
# ======================
# Operator commands for training, pipelines, and deployment

.PHONY: help train ingest-racecards ingest-results postrace-update report clean test

# Default target
help:
	@echo "VÉLØ v10.1 - Operator Commands"
	@echo "==============================="
	@echo ""
	@echo "Training:"
	@echo "  make train              - Train Benter model with calibration"
	@echo "  make train-quick        - Quick training (no grid search)"
	@echo ""
	@echo "Daily Pipeline:"
	@echo "  make ingest-racecards   - Ingest today's racecards"
	@echo "  make ingest-results     - Ingest today's results"
	@echo "  make postrace-update    - Update predictions with results"
	@echo "  make report             - Generate daily performance report"
	@echo "  make daily              - Run full daily pipeline"
	@echo ""
	@echo "Analysis:"
	@echo "  make analyze DATE=YYYY-MM-DD  - Analyze races for date"
	@echo "  make backtest START=YYYY-MM-DD END=YYYY-MM-DD  - Backtest model"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean              - Clean output directories"
	@echo "  make test               - Run test suite"
	@echo "  make status             - Show system status"
	@echo ""

# Training commands
train:
	@echo "🔥 Training Benter model..."
	python3 -m src.training.train_benter \
		--cv 5 \
		--calibrate isotonic \
		--registry out/models \
		--version v1.0.0

train-quick:
	@echo "⚡ Quick training (no grid search)..."
	python3 -m src.training.train_benter \
		--cv 3 \
		--calibrate none \
		--registry out/models \
		--version v1.0.0-quick

# Daily pipeline commands
ingest-racecards:
	@echo "📥 Ingesting today's racecards..."
	python3 -m src.pipelines.ingest_racecards --date TODAY

ingest-racecards-date:
	@echo "📥 Ingesting racecards for $(DATE)..."
	python3 -m src.pipelines.ingest_racecards --date $(DATE)

ingest-results:
	@echo "📥 Ingesting today's results..."
	python3 -m src.pipelines.ingest_results --date TODAY

ingest-results-date:
	@echo "📥 Ingesting results for $(DATE)..."
	python3 -m src.pipelines.ingest_results --date $(DATE)

postrace-update:
	@echo "🔄 Updating predictions with results..."
	python3 -m src.pipelines.postrace_update --date TODAY

postrace-update-date:
	@echo "🔄 Updating predictions for $(DATE)..."
	python3 -m src.pipelines.postrace_update --date $(DATE)

report:
	@echo "📊 Generating performance report..."
	python3 -m src.ledger.performance_store --date TODAY --export out/reports/daily_report.json

# Full daily pipeline
daily: ingest-racecards analyze ingest-results postrace-update report
	@echo "✅ Daily pipeline complete"

# Analysis commands
analyze:
	@echo "🔮 Analyzing races..."
	python3 -m src.cli analyze --date TODAY --export out/preds/TODAY.json

analyze-date:
	@echo "🔮 Analyzing races for $(DATE)..."
	python3 -m src.cli analyze --date $(DATE) --export out/preds/$(DATE).json

# Backtest command
backtest:
	@echo "📈 Running backtest from $(START) to $(END)..."
	python3 -m src.cli backtest --start $(START) --end $(END) --export out/reports/backtest.json

# Utility commands
clean:
	@echo "🧹 Cleaning output directories..."
	rm -rf out/models/*
	rm -rf out/preds/*
	rm -rf out/reports/*
	rm -rf out/features/*
	rm -rf out/ledger/*
	@echo "✅ Clean complete"

test:
	@echo "🧪 Running test suite..."
	pytest tests/ -v

status:
	@echo "📊 VÉLØ System Status"
	@echo "====================="
	@echo ""
	@echo "Models:"
	@python3 -c "from src.training.model_registry import ModelRegistry; r = ModelRegistry(); r.print_registry()"
	@echo ""
	@echo "Performance:"
	@python3 -c "from src.ledger.performance_store import PerformanceStore; s = PerformanceStore(); print(s.get_cumulative_performance().tail())"
	@echo ""

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip3 install -r requirements.txt
	@echo "✅ Installation complete"

# Initialize directories
init:
	@echo "🏗️  Initializing directories..."
	mkdir -p out/models out/preds out/reports out/features out/ledger
	mkdir -p src/training src/pipelines src/ledger
	@echo "✅ Initialization complete"
