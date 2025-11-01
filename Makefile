# VÉLØ v10 Makefile
# Standardized build, test, and deployment commands

PY=python3
PIP=pip3

.PHONY: help install lint test run db migrate format clean cli

help:
	@echo "VÉLØ v10 - Oracle of Odds"
	@echo ""
	@echo "Available targets:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
	@echo "  make db         - Apply database migrations"
	@echo "  make migrate    - Generate new migration"
	@echo "  make run        - Run Oracle"
	@echo "  make cli        - Run CLI help"
	@echo "  make clean      - Clean build artifacts"

install:
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

lint:
	@echo "Running flake8..."
	@flake8 src/ tests/ || echo "flake8 not configured yet"

test:
	@echo "Running pytest..."
	pytest -q

run:
	$(PY) src/core/oracle.py

db:
	@echo "Applying database migrations..."
	alembic upgrade head

migrate:
	@echo "Generating new migration..."
	alembic revision --autogenerate -m "schema update"

format:
	@echo "Formatting code with black..."
	@black src/ tests/ || echo "black not configured yet"

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ .coverage htmlcov/

cli:
	$(PY) -m src.cli --help

