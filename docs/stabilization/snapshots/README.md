# VÉLØ Oracle Prime

Auditable horse racing prediction and decision-support system.

VÉLØ scores UK/IRE races daily, reconciles predictions against results via a nightly Sigma loop, and accumulates evidence for future model improvement. It is not a live betting system. It is intelligence infrastructure built on an auditable, evidence-gated foundation.

---

## What It Does

- **Morning:** Ingests Racing Post PDFs, builds a runner profile, scores all races, sends a Telegram card with selections tiered A/B/C/X.
- **Evening:** Scrapes results, runs a Sigma reconciliation audit, sends Telegram report, updates Supabase, appends to the training corpus.
- **Shadow gate:** A challenger model runs in parallel, accumulating forward-test evidence toward a 300-runner promotion review gate.
- **Paper ledger:** An execution bridge simulates bet sizing decisions in SIM-only mode. No live betting.

---

## Current Production Architecture

```
RP PDFs (morning)
    │
    ├─ build_rp_runner_profile.py  →  rp_runner_profile_latest.parquet
    │
    └─ run_prime_today.py
           │
           ├─ SQPE v17 (0.45 weight) + 7 specialist models
           ├─ VeloPrimeEnsemble  (src/intelligence/velo_prime_ensemble.py)
           ├─ Decision tiers: A / B / C / X
           │
           ├─ → velo_verdicts (Supabase)
           └─ → Telegram card + local JSON backup

Results (evening)
    │
    ├─ scrape_results_atr.py        →  results_YYYY_MM_DD.json
    ├─ run_results_sigma.py         →  sigma_audits (Supabase) + Telegram
    ├─ ingest_results_to_horse_runs.py
    └─ build_shadow_model_forward_gate.py   (shadow gate tracker)
```

Railway deploys `app/main.py` (FastAPI) on a cron schedule. Supabase is the persistence layer.

---

## Local Setup

**Requirements:** Python 3.12, venv

```bash
git clone https://github.com/elpresidentepiff/velo-oracle-prime
cd velo-oracle-prime
python -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows
pip install -r requirements_production.txt
cp .env.example .env           # fill in your credentials
```

**Required env vars** (see `.env.example` for full list):
```
SUPABASE_URL=
SUPABASE_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
RACING_API_USERNAME=
RACING_API_PASSWORD=
```

---

## Daily Scoring Flow

```bash
# Morning — after RP PDFs arrive in data/incoming_pdfs/YYYY-MM-DD/
source venv/bin/activate
PYTHONPATH=. python scripts/ops/build_rp_runner_profile.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/run_prime_today.py

# Evening — after results close
PYTHONPATH=. python scripts/ops/scrape_results_atr.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/run_results_sigma.py --date YYYY-MM-DD --notify-telegram
PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/backtest/build_shadow_model_forward_gate.py
```

---

## Scripts Layout

```
scripts/
  ops/         Live operational scripts (scoring, sigma, ingestion, reporting)
  audit/       Forensic audits, evidence analysis, operator visibility tools
  backtest/    Model training, calibration, shadow gate management

archive/
  legacy/      Old experiments, stale docs, historical one-off reports
```

---

## Live vs Shadow vs Paper-Only

| Layer | Status | Description |
|---|---|---|
| Scoring (SQPE v17 + ensemble) | **LIVE** | Produces daily verdicts |
| Telegram reporting | **LIVE** | A/B/C/X card + sigma report |
| Supabase persistence | **LIVE** | velo_verdicts, sigma_audits |
| Playbook G / sentient loop | **SHADOW** | Evidence accumulation only |
| Shadow model (NO_VP_COMPOSITE) | **SHADOW GATE** | n=284/300 — not promoted |
| VeloExecutionBridge | **PAPER/SIM** | Hard LIVE → RuntimeError gate |
| Betfair execution | **BLOCKED** | Simulation mode only |

---

## Safety Gates

These are permanent. Never remove them.

```python
# src/velo/execution_bridge.py
if os.getenv("VELO_EXECUTION_MODE") == "LIVE":
    raise RuntimeError("LIVE execution blocked")
```

**Never import in the live scoring path:**
- `app/agents/betfair_execution_agent.py` — contains `place_order()`
- `app/agents/betfair_trading_agents.py` — contains `place_bet()`

**Never commit:** `.env`, credentials, model `.pkl` files.

---

## Where Docs Live

| Document | Location |
|---|---|
| **Single source of truth** | `CURRENT_RUNTIME_TRUTH.md` |
| Engineering decisions | `docs/engineering/` |
| Process wiring | `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md` |
| Shadow model governance | `docs/engineering/VELO_SHADOW_MODEL_ARTIFACT_GOVERNANCE_V1.md` |
| Safety sentinel | `docs/engineering/VELO_SAFETY_SENTINEL_V1.md` |

---

## Evidence Baseline

49-day audit as of 2026-04-28 (1,391 sigma rows):

| Signal | SR | Frame |
|---|---|---|
| Tier A (VP≥0.30) | 40.1% | 77.2% |
| MDS > 0.50 | 54.8% | 96.8% |
| improvement_score > 0.40 | 43.5% | 82.3% |
| VP ≥ 0.30 | 32.2% | 69.3% |
| Global | 20.6% | 48.4% |

Full audit: `data/evidence_vault/velo_unified_evidence_audit_v1.json`

Doctrine scorecard generator:

```bash
PYTHONPATH=. python scripts/audit/build_doctrine_market_scorecard.py \
  --input data/your_reconciled_export.csv
```

Outputs:
- `data/doctrine_market_scorecard_latest.json`
- `data/doctrine_market_scorecard_latest.md`

---

## Legacy History

Historical experiments, old agents, one-off analyses, and stale docs live in:

```
archive/legacy/2026-05-19-cleanup/
```

Full git history is preserved from inception (697+ commits).
