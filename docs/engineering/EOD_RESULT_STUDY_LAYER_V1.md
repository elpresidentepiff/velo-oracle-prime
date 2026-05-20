# EOD Result Study Layer V1

## Overview
The EOD Result Study Layer transforms VÉLØ's nightly learning outcomes into actionable intelligence. It analyzes the delta between predictions and real-world results to identify performance trends, loss patterns, and model calibration health.

## Core Components

### 1. Sigma Study (Performance Audit)
Focuses on the statistical integrity of the day's racing.
- **Strike Rate / Accuracy**: Measures top-line performance.
- **Brier Score**: Evaluates the quality of probability predictions.
- **Loss Taxonomy**: Categorizes misses into `WRONG_HORSE`, `CALIBRATION_ERROR`, `MARKET_LIED`, and `CHAOS_RACE`.
- **Top Movers**: Identifies the day's strongest and weakest predictions.

### 2. Playbook G Shadow Critique
Analyzes the evolution of the shadow sentient state.
- **Imprinting Success**: Verifies that outcome events were successfully applied to the shadow brain.
- **Pattern Protection**: Monitors for recurring failure patterns.
- **Tomorrow Watchlist**: Flags specific market conditions or behaviors for forensic observation.

### 3. Safety & Continuity Check
The study layer acts as a second-pass validator for the nightly loop:
- Verifies that `sentient_state.json` (Live) was not mutated.
- Verifies that Supabase writes were false.
- Verifies that HFS features were not consumed.
- Ensures the LLM Council Audit was successfully produced.

## Reporting Artifacts
- `data/eod_sigma_study_{YYYYMMDD}.json`: Statistical forensics.
- `data/eod_playbook_g_shadow_critique_{YYYYMMDD}.json`: Intelligence evolution audit.
- `data/eod_result_study_{YYYYMMDD}.json`: Combined data report.
- `data/eod_result_study_{YYYYMMDD}.md`: Human-readable executive summary.

## Trigger Mechanism
Integrated into `scripts/nightly_eod_learning_runner.py`. The study layer executes automatically upon a `PASS` verdict from the learning runner.

## Manual Usage
```bash
PYTHONPATH=. python3 scripts/eod_result_study_layer.py --date YYYY-MM-DD
```
