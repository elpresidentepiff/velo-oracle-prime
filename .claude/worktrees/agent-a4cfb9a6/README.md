# VÉLØ ORACLE PRIME

**A strategic intelligence engine for horse racing prediction, built on verifiable signal, strict quarantine doctrine, and probabilistic scoring.**

---

## What Is VÉLØ?

VÉLØ Oracle Prime is a data-driven racing intelligence system. It ingests race card data, applies a structured analytical engine (SQPE + quarantine gates), and produces scored strike recommendations with explicit confidence levels. It does not guess. It does not bet on noise. It quarantines races where signal is insufficient.

The engine is built around a core doctrine:

> **Truth before optimization. Memory before learning. Doctrine before power.**

---

## Core Architecture

```
[Race Card Ingest]
       │
       ▼
[Feature Forge]  →  Form, Going, Field Size, Trainer Intent, Market Shape
       │
       ▼
[VÉLØ Engine]    →  Quarantine Gates → SQPE Scoring → Verdict
       │
       ▼
[Output Layer]   →  Prediction JSON + Strike Report + Supabase Write
```

**Key Components:**

| Layer | Location | Purpose |
|:---|:---|:---|
| API Gateway | `app/api/` | Agent registration, observation, action endpoints |
| Engine Core | `app/engine/` | SQPE scoring, quarantine gate logic |
| ML Models | `app/ml/` | Glicko-2 rating, ablation tests, learning gate |
| Strategy | `app/strategy/` | Value overlay, Kelly staking, market analysis |
| Workers | `workers/` | Background prediction jobs |
| Scrapers | `scrapers/` | Race card data ingestion |

---

## Quarantine Doctrine

The engine enforces strict quarantine gates before issuing any strike:

| Gate | Condition | Action |
|:---|:---|:---|
| Q5 | Heavy/Soft going + 12+ runners | QUARANTINE |
| Q6 | < 5 runners | Conditional strike only |
| Q7 | Maiden with no form data | QUARANTINE |
| Q8 | Market chaos detected | QUARANTINE |
| Q9 | Conflicting picks + high chaos | QUARANTINE or LOW |

**Target quarantine rate: 45%.** If the engine is quarantining fewer than 40% of races, the gates are too loose.

---

## Confidence Levels

| Level | Conditions |
|:---|:---|
| **HIGH** | Small field + consensus OR AW + consensus + chaos ≤ 2 |
| **MEDIUM** | Consensus + chaos ≤ 3 OR AW + chaos ≤ 3 |
| **LOW** | Conflicting picks OR chaos 4 OR soft/heavy going |
| **NONE** | Quarantined — no strike issued |

---

## Strike Report Format

Predictions are saved to `predictions/` as JSON and compiled into Markdown/PDF reports in `results/`.

**Sample prediction JSON:**
```json
{
  "race_id": "naas_20260308_race4",
  "meeting": "Naas",
  "date": "2026-03-08",
  "race_number": 4,
  "time": "16:37",
  "distance": "2m4f",
  "going": "HEAVY",
  "chaos_rating": 3,
  "quarantine_status": "STRIKE_CONDITIONAL",
  "top_strike": "Ballygunner Castle",
  "confidence": "MEDIUM",
  "suppression_signals": ["S7"]
}
```

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run engine on a race meeting
python run_daily_predictions.py

# Run tests
pytest tests/
```

---

## Documentation

Full documentation lives in `/docs`:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System design
- [`docs/VELO_DEVELOPER_BLUEPRINT.md`](docs/VELO_DEVELOPER_BLUEPRINT.md) — Developer guide
- [`docs/ML_INTEGRATION_GUIDE.md`](docs/ML_INTEGRATION_GUIDE.md) — ML model details
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — Supabase schema
- [`docs/QUICK_START.md`](docs/QUICK_START.md) — Getting started

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI, Prefect
- **Database:** Supabase (PostgreSQL)
- **Deployment:** Railway
- **ML:** Scikit-learn, XGBoost, Glicko-2
- **Data:** Racing Post, Racing API, Betfair

---

## Doctrine

*The engine runs when you call it. It learns while it waits.*
