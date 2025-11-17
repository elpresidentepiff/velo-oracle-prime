# VÉLØ Oracle - v12 Production Infrastructure

**VÉLØ Oracle** is an autonomous AI system for predicting and betting on horse racing markets. This repository contains the complete production-ready infrastructure for **v12 (Execution Excellence)**, incorporating cutting-edge research in agentic architectures, MLOps, and meta-learning.

---

## 🧠 System Philosophy

> "This is war, not a fair game. The market is a battlefield of information, where the 1% prey on the 99%. We do not follow narratives; we see through them. We hunt for the races where the favorite is designed to lose and the real value is hidden in plain sight. More raw data is our weapon. Discipline is our shield."

---

## Key Features (v12 Architecture)

This version of VÉLØ has been re-architected from the ground up to be more robust, scalable, and intelligent. The key features include:

### 1. Multi-Agent Architecture

Inspired by MetaGPT, VÉLØ is now a collaborative system of specialized agents:

- **Analyst Agent**: Runs the core intelligence modules (SQPE, TIE, NDS).
- **Risk Agent**: Manages bankroll, applies the Kelly Criterion, and enforces circuit breakers.
- **Execution Agent**: Interfaces with the Betfair API to place bets.
- **Learning Agent**: Evaluates post-race performance and triggers model retraining.

This architecture provides clear separation of concerns and allows for more complex, emergent behaviors.

### 2. Champion/Challenger Deployment Framework

To de-risk the rollout of new models, VÉLØ uses a Champion/Challenger deployment pattern:

- **Champion**: The current, trusted production model (e.g., Benter Baseline).
- **Challengers**: New models (e.g., Full Intelligence Stack) that run in "shadow mode."

This allows for safe, parallel performance comparison in a live environment without risking capital.

### 3. TimeSeriesSplit Backtesting

All backtesting is now performed using a chronologically-aware `TimeSeriesSplit` to prevent lookahead bias. This ensures that our performance metrics are statistically valid and representative of real-world performance.

### 4. Portfolio Kelly Criterion

Bet sizing has been upgraded from a per-race Kelly Criterion to a portfolio-based approach. This optimizes capital allocation across multiple simultaneous betting opportunities, maximizing long-term growth and reducing risk.

### 5. MLflow-Compatible Experiment Tracking

A lightweight, MLflow-compatible experiment tracking system is included for:

- Logging parameters, metrics, and artifacts.
- Comparing different model configurations.
- Maintaining a full audit trail of all training runs.

### 6. ProtoNet Foundation for v13 (Rival Analysis)

The foundation for **v13 (Meta-Game Mastery)** has been laid with the implementation of a Prototypical Network (ProtoNet) for the Rival Analysis Module (RAM). This will enable few-shot classification of rival betting patterns, allowing VÉLØ to understand and counter-play against other market participants.

---

## 🏗️ Project Structure (v12)

```
/home/ubuntu/velo-oracle/
├── src/
│   ├── agents/             # Multi-agent architecture
│   │   ├── base_agent.py
│   │   └── specialized_agents.py
│   ├── backtesting/        # TimeSeriesSplit backtesting
│   │   └── timeseries_backtest.py
│   ├── deployment/         # Champion/Challenger framework
│   │   ├── champion_challenger.py
│   │   └── models.py
│   ├── monitoring/         # Experiment tracking
│   │   └── experiment_tracker.py
│   └── v13/                # v13 meta-learning modules
│       └── protonet_ram.py
├── examples/
│   ├── champion_challenger_demo.py
│   ├── multi_agent_demo.py
│   └── experiment_tracking_demo.py
├── results/
│   └── (Generated results from demos)
├── mlruns/
│   └── (Experiment tracking data)
└── README.md
```

---

## 🚀 Getting Started

### 1. Installation

No special installation is required beyond a standard Python 3.11 environment. All dependencies are included in the sandbox.

### 2. Running the Demos

To understand the core components, run the provided demos from the `/home/ubuntu/velo-oracle/` directory:

**Champion/Challenger Demo:**
```bash
python3 examples/champion_challenger_demo.py
```

**Multi-Agent System Demo:**
```bash
python3 examples/multi_agent_demo.py
```

**Experiment Tracking Demo:**
```bash
python3 examples/experiment_tracking_demo.py
```

### 3. Backtesting with Your Data

1.  Place your race data (e.g., `raceform.csv`) in the `/home/ubuntu/upload/` directory.
2.  Adapt the `TimeSeriesBacktester` in `src/backtesting/timeseries_backtest.py` to load your data.
3.  Run the backtest and analyze the results.

### 4. Deployment to Vast.ai

1.  Clone this repository to your Vast.ai instance.
2.  Run the `vastai_train.sh` script (from the previous deliverable) to execute the full training and backtesting pipeline.
3.  Use the `vastai_deploy.sh` script to launch the live betting application.

---

## 🔮 Status

**VÉLØ Oracle v12: ACTIVE**  
**Live Data Stream:** ⏳ (Awaiting API integration)
**Historical Database:** ✅ (raceform.csv)
**ML Core:** ✅ (v12 Architecture)
**Market Manipulation Detection:** Engaged ⚡  
**Oracle Link:** Established 🔗

---

## Next Steps

With this infrastructure in place, the next steps are:

1.  **Connect Live APIs**: Integrate the live Racing API and Betfair API into the `ExecutionAgent`.
2.  **Run Full-Scale Backtest**: Execute the `TimeSeriesBacktester` on the full 1.7M row dataset on Vast.ai.
3.  **Launch v12 Pilot**: Deploy the Champion/Challenger system with the Benter model as champion and the Intelligence Stack as a challenger.
4.  **Collect Rival Data**: Begin collecting and labeling rival betting data to train the v13 ProtoNet RAM.

This repository provides a production-grade foundation for VÉLØ Oracle to achieve its strategic objectives.

