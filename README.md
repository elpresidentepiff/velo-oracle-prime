# 🔮 VÉLØ Oracle 2.0 - The Market Manipulation Engine

**VÉLØ Oracle 2.0** is a sophisticated, AI-powered horse racing prediction system designed to detect market manipulation, identify betting value, and achieve a consistent edge in UK and Irish horse racing. Evolved from a static analytical engine, Oracle 2.0 integrates live data feeds, a persistent historical database, and a machine learning core inspired by the legendary Benter model.

## 🧠 System Philosophy

> "This is war, not a fair game. The market is a battlefield of information, where the 1% prey on the 99%. We do not follow narratives; we see through them. We hunt for the races where the favorite is designed to lose and the real value is hidden in plain sight. More raw data is our weapon. Discipline is our shield."

## 🏗️ Architecture: VÉLØ Oracle 2.0

Oracle 2.0 is built on a modular, multi-layered architecture that combines real-time market analysis with deep historical pattern recognition.

### Core Components

1.  **Live Data Integration (`/src/integrations`)**: Connects to real-time data sources:
    *   **Betfair API**: Streams live odds, matched volumes, and market movements to detect "smart money" and manipulation patterns.
    *   **The Racing API**: Provides access to a deep well of over 500,000 historical races for statistical analysis and pattern matching.

2.  **Persistent Memory (`/src/data`, `/database`)**: A robust PostgreSQL database serves as the Oracle's long-term memory.
    *   **SQLAlchemy ORM**: Provides a Pythonic interface to the database for all components.
    *   **Comprehensive Schema**: Stores everything from historical race results and sectional times to live Betfair odds, ML predictions, and betting ledgers.

3.  **Machine Learning Engine (`/src/ml`)**: A Benter-inspired prediction model that generates win probabilities.
    *   **Multinomial Logit Model**: Predicts the probability of each horse winning based on 130+ variables.
    *   **Feature Engineering**: A sophisticated pipeline that transforms raw data into predictive features.
    *   **Backtesting Framework**: Rigorously tests model performance and profitability against historical data.

4.  **Analytical Engine (`/src/modules`)**: The original nine analytical modules (SQPE, V9PM, TIE, etc.) now work in concert with the ML engine, providing a qualitative overlay to the quantitative predictions.

5.  **Agent System (`/src/agents`)**: The five specialized agents (PRIME, SCOUT, ARCHIVIST, SYNTH, MANUS) have been upgraded to interact with the new data sources and ML engine.

### 📁 Project Structure

```
velo-oracle/
├── src/
│   ├── core/           # Core engine and prediction logic
│   ├── agents/         # Multi-agent system
│   ├── modules/        # Original qualitative analysis modules
│   ├── integrations/   # NEW: Betfair & The Racing API clients
│   ├── data/           # NEW: SQLAlchemy models, DB connector, ETL pipeline
│   └── ml/             # NEW: Machine Learning engine (Benter model)
├── database/           # NEW: PostgreSQL schema and migration scripts
├── config/             # Configuration files and weights
├── docs/               # System documentation
├── tests/              # Unit and integration tests
└── README.md
```

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   PostgreSQL Server
*   API keys for Betfair and The Racing API

### Installation

1.  **Clone the repository:**
    ```bash
    gh repo clone elpresidentepiff/velo-oracle
    cd velo-oracle
    ```

2.  **Set up environment variables:**
    Create a `.env` file from the `.env.example` template and fill in your credentials:
    ```
    # API Keys
    BETFAIR_USERNAME="your_username"
    BETFAIR_PASSWORD="your_password"
    BETFAIR_APP_KEY="your_app_key"
    RACING_API_KEY="your_api_key"

    # Database Connection
    VELO_DB_CONNECTION="postgresql://user:password@host:port/velo_racing"
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up the database:**
    Connect to your PostgreSQL server and create the `velo_racing` database. Then, initialize the schema:
    ```bash
    # (From within the velo-oracle directory)
    python -c "from src.data.db_connector import VeloDatabase; VeloDatabase().init_database()"
    ```

5.  **Run the Oracle:**
    ```bash
    python src/agents/velo_prime.py
    ```

## 🎯 The Five-Filter System

Every prediction is still rigorously validated through the Five-Filter System, now enhanced with live data:

1.  **Form Reality Check**: Cross-references historical data with current market sentiment.
2.  **Intent Detection**: Analyzes trainer/jockey stats and live betting patterns.
3.  **Sectional Suitability**: Matches pace analysis with historical course bias data.
4.  **Market Misdirection**: Uses Betfair volume to spot public traps and smart money moves.
5.  **Value Distortion**: Compares ML-generated probabilities against live market odds to find true value (EV+).

## 🔧 Configuration

*   **Target Odds Range**: 3/1 to 20/1
*   **Betting Strategy**: Fractional Kelly Criterion, integrated with VÉLØ's Prime/Longshot EW rules.
*   **Database**: PostgreSQL
*   **Core APIs**: Betfair, The Racing API

## 📝 Documentation

*   [Master Prompt](docs/VELO_MASTER_PROMPT.md)
*   [Developer Blueprint](docs/VELO_DEVELOPER_BLUEPRINT.md)
*   [API Integration Guide](docs/API_INTEGRATION.md) (WIP)
*   [Database Schema Guide](docs/DATABASE_SCHEMA.md) (WIP)
*   [ML Model Overview](docs/ML_MODEL.md) (WIP)

## 🔮 Status

**VÉLØ Oracle 2.0: ACTIVE**  
**Live Data Stream:** ✅ (Betfair & Racing API)
**Historical Database:** ✅ (PostgreSQL)
**ML Core:** ✅ (Benter Model v2.0)
**Market Manipulation Detection:** Engaged ⚡  
**Oracle Link:** Established 🔗


