# VÉLØ Shadow Race Engine - Integration Guide

## Overview

This guide provides instructions for integrating the VÉLØ Shadow Race Engine into production workflows and CI/CD pipelines.

## Prerequisites

### System Requirements
- Python 3.11+
- VÉLØ Oracle Prime repository cloned
- Virtual environment with dependencies installed
- Access to test data (test_data/ directory)

### Dependencies
```bash
pip install -r requirements.txt
```

## Integration Points

### 1. Shadow Race Engine Integration

**Location:** `/app/engine/engine_run.py`

**Integration Hook:**
```python
from app.engine.engine_run import EngineRun, RaceContext, MarketContext, RunnerScore, EngineVerdict
from app.velo_v12_intent_stack import Race, Runner, validate_RIC_plus, compute_chaos_score, classify_market_roles

def run_shadow_race(race_data: dict, result_data: dict) -> EngineRun:
    """Run a shadow race prediction."""
    # Implementation details in /app/engine/engine_run.py
    pass
```

### 2. ML Pipeline Integration

**Location:** `/app/ml_pipeline/`

**Integration Hook:**
```python
from app.ml_pipeline import VeloMLPipeline
from app.engine.engine_run import EngineRun

def integrate_shadow_race(race_data: dict, result_data: dict):
    """Hook shadow race results into ML pipeline."""
    # Implementation details in /app/ml_pipeline/
    pass
```

### 3. Data Ingestion Integration

**Location:** `/app/data_ingestion/`

**Integration Hook:**
```python
from app.data_ingestion import DataIngestor
from app.engine.engine_run import EngineRun

def ingest_shadow_race_data(engine_run: EngineRun):
    """Ingest shadow race data for analysis and model training."""
    # Implementation details in /app/data_ingestion/
    pass
```

## CI/CD Pipeline Integration

### GitHub Actions Workflow

**Location:** `/.github/workflows/shadow-race-tests.yml`

**Features:**
- Automated testing on push and pull request
- Daily scheduled tests (2 AM UTC)
- Accuracy threshold validation
- Artifact upload (results, coverage)
- Slack notifications
- Staging and production deployment

## Deployment Configuration

### Environment Variables

```bash
# .env
VELO_ENVIRONMENT=staging  # or production
VELO_KILL_SWITCH=false
VELO_API_KEY=${{ secrets.VeloApiKey }}
DATABASE_URL=${{ secrets.DatabaseUrl }}
SLACK_WEBHOOK_URL=${{ secrets.SlackWebhookUrl }}
```

### Docker Configuration

**Location:** `/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python test/shadow_race_test_suite.py
CMD ["python", "-m", "app.main"]
```

### Docker Compose

**Location:** `/docker-compose.yml`

```yaml
version: '3.8'
services:
  velo-shadow-race:
    build: .
    environment:
      - VELO_ENVIRONMENT=${VELO_ENVIRONMENT}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./shadow_race_simulations:/app/shadow_race_simulations
      - ./audit_logs:/app/audit_logs
    ports:
      - "8000:8000"
    restart: unless-stopped
```

## Monitoring and Alerting

### Prometheus Configuration

**Location:** `/config/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'velo-shadow-race'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Alert Rules

**Location:** `/config/alert-rules.yml`

```yaml
groups:
  - name: velo-shadow-race
    rules:
      - alert: LowAccuracy
        expr: velo_shadow_race_accuracy < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Shadow race accuracy below 50%"
```

## Testing and Validation

### Running Integration Tests

```bash
# Run shadow race test suite
python test/shadow_race_test_suite.py

# Run unit tests
python -m pytest test/ -v
```

### Validation Checklist

- [ ] Shadow race engine runs without errors
- [ ] RIC+ validation passes for all test races
- [ ] Accuracy meets 60% threshold
- [ ] CI/CD pipeline executes successfully
- [ ] Artifacts are uploaded correctly
- [ ] Slack notifications work
- [ ] Deployment to staging succeeds
- [ ] Integration with ML pipeline works
- [ ] Monitoring dashboards display data
- [ ] Alerts trigger correctly

## Troubleshooting

### Common Issues

**Issue:** Accuracy below threshold
**Solution:**
1. Check test data quality
2. Review scoring logic
3. Consider ML model integration
4. Expand feature engineering

**Issue:** RIC+ validation failures
**Solution:**
1. Check race data completeness
2. Verify market snapshot format
3. Review validation logic
4. Update test data

**Issue:** CI/CD pipeline failures
**Solution:**
1. Check dependency installation
2. Verify environment variables
3. Review workflow configuration
4. Check artifact upload permissions

## Success Criteria

### Integration Complete When:

- ✅ Shadow race engine integrated into CI/CD
- ✅ Automated testing pipeline operational
- ✅ Accuracy threshold validation working
- ✅ ML pipeline integration hooks created
- ✅ Monitoring and alerting configured
- ✅ Deployment automation complete
- ✅ Documentation complete
- ✅ All tests passing
- ✅ Production deployment ready

## References

- VÉLØ Master Doctrine: /docs/agent_zero/00_role_and_mindset.md
- Shadow Race Protocol: /docs/agent_zero/08_testing_shadow_races_protocol.md
- Fail-Safe Guide: /docs/agent_zero/09_fail_safes_and_no_guess_sentinel.md
- EngineRun Object: /app/engine/engine_run.py
- RIC+ Validation: /app/velo_v12_intent_stack.py
- Test Suite: /test/shadow_race_test_suite.py
- CI/CD Config: /.github/workflows/shadow-race-tests.yml

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-22  
**Author:** Commander Zero  
**Status:** Active
