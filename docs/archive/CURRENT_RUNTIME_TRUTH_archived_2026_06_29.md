# VÉLØ Oracle Prime — Current Runtime Truth

**Last updated:** 2026-06-02 (Integrated New Build Paper Pipeline & Stabilization Hardening)  
**Status:** PRODUCTION — read this before touching anything  
**Authority:** This document supersedes TRUTH_REGISTRY.md, SYSTEM_MAP.md, BRANCH_MAP.md, and any prior stabilization logs.

---

## 1. What VÉLØ Is

VÉLØ Oracle Prime is an auditable horse racing prediction and decision-support system.

It scores races daily, reconciles predictions against results via a nightly Sigma loop, and accumulates evidence for future model promotion. It is **not** a live betting system. It is **not** a tipster service. It is intelligence infrastructure.

---

## 2. Live Scoring Path (Production)

```
RP PDFs (Racing Post F_0010 / colour cards)
    │
    ▼
scripts/ops/build_rp_runner_profile.py
    │  Outputs: data/features/rp_runner_profile_latest.parquet
    │
    ▼
app/pipelines/score_daily_runner.py   ← LIVE_RUNTIME entry point (via /api/trigger/score-daily)
    │  (wraps scripts/ops/run_prime_today.py)
    │
    ├─ load_model: models/sqpe_v17/sqpe_v17.pkl  (SQPE v17, primary probability model)
    ├─ load_specialist: models/specialist/*       (7 specialist models)
    ├─ ensemble: src/intelligence/velo_prime_ensemble.py
    ├─ tier: A/B/C/X decision gate (A = highest conviction)
    │
    ├─► velo_verdicts (Supabase) — persisted per runner
    ├─► Telegram: VP30 card, A-strikes, B-playables, place signals
    └─► data/velo_prime_verdicts_YYYY_MM_DD.json (local backup)
```

---

## 2.1. New Build Paper Pipeline (Shadow Challenger V1)

In parallel with Live Scoring, the system runs the "New Build" pipeline to test high-fidelity feature engineering (Passport V2) and multi-lane intent scoring.

```
RP Profile Scrape (Headed Playwright)
    │
    ▼
scripts/ops/new_build_horse_passports.py
    │  Outputs: data/new_build/passports/horse_passports_v1.jsonl
    │
    ▼
scripts/ops/new_build_paper_score_today.py
    │  Model: Challenger_V1 (core_v0_or_passport_intent)
    │  Features: Passport V2 (last-N windows, trends, dynamic layoff)
    │
    ▼
scripts/ops/new_build_two_lane_score.py
    │
    ├─ LANE A: Core Passport (30 features)
    └─ LANE B: High Intent (Candidate intent signals)
    │
    ├─► data/new_build/paper_predictions/new_build_predictions_YYYY_MM_DD.jsonl
    └─► Dashboard: Side-by-side comparison (Old VÉLØ vs. New Build)
```

**Status:** SHADOW/PAPER. Used for forward evidence accumulation and architecture validation. Not currently governing live betting or primary Telegram alerts.

---

## 3. Active Ensemble — Signal Truth Table

| Signal | Current weight | Live weighted? | Stored? | Shadow only? | Notes |
|---|---|---|---|---|---|
| `sqpe_v17_prob` (VP) | **0.45** | YES | YES | NO | Dominant anchor — SQPE v17 |
| `improvement_score` | **0.12** | YES | YES | NO | LIVE_WEIGHTED — active since ensemble surgery 2026-05-08 |
| `market_deception_score` (MDS) | **0.10** | YES | YES | NO | Best sidecar, SR=54.8% at MDS>0.5 |
| `place_prob` | declared 0.08, **BADGE_ONLY** | NO (excluded from VP) | YES | NO | BADGE_ONLY — frame badge, not VP-weighted in current profile |
| `longshot_score` | declared 0.07, **FROZEN** | NO (excluded from VP) | YES | NO | SP≥10 gate still used for tier X |
| `release_window_score` | 0.00 (STORED_ONLY) | NO | YES | NO | Calculated, stored, not weighted |
| `comment_intel_score` | 0.00 (STORED_ONLY) | NO | YES | NO | Calculated, stored, not weighted |
| Playbook G / sentient | 0 | NO | YES | YES | Shadow mode — multiplier computed but NOT applied to VP |
| Challenger V1 (NB) | 0 | NO | YES | YES | New Build Paper Model — Passport V2 integrated |

**Active ensemble profile:** `SQPE_IMPROVEMENT_MDS_V1` (commit b7e4e0c, 2026-05-08)  
**Rollback:** `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE`  

---

## 4. Evening Reconciliation (Sigma Loop)

```
After results close:
    scripts/ops/scrape_results_atr.py --date YYYY-MM-DD
        │  Outputs: data/results_YYYY_MM_DD.json
        ▼
    app/pipelines/sigma_runner.py --date YYYY-MM-DD --notify-telegram
        │  Writes: sigma_audits (Supabase), Telegram sigma report
        │  Logic: ID-First Matching (Race ID -> Horse ID -> Name)
        ▼
    app/pipelines/results_ingest_runner.py --date YYYY-MM-DD
        │  Writes: racing_horse_runs (Supabase) — feeds tomorrow's RPDC
        ▼
    scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
        │  Appends: velo_innovation_protocol_1k_deduped.csv
```

---

## 5. File and Module Classification

### Core Runtime — LIVE_RUNTIME

| File | Role |
|---|---|
| `app/main.py` | FastAPI entry point (Railway) — includes safety lifespan guards |
| `app/pipelines/*.py` | Canonical pipeline wrappers (Scoring, Sigma, Ingestion) |
| `app/core/safety_guards.py` | AST forbidden-import enforcement utility |
| `scripts/ops/run_prime_today.py` | Daily scoring orchestrator |
| `scripts/ops/run_results_sigma.py` | Nightly reconciliation + Telegram (ID-First) |
| `src/intelligence/velo_prime_ensemble.py` | Live ensemble scoring engine |
| `src/intelligence/sqpe.py` | SQPE base probability model |
| `new_build_velo/` | Modules for Passport V2 and New Build feed logic |

### Shadow / Evidence Only — SHADOW_ONLY

| File | Role | Promote only if |
|---|---|---|
| `scripts/ops/new_build_paper_score_today.py` | Challenger V1 scorer | n≥300 + operator approval |
| `scripts/ops/new_build_horse_passports.py` | Passport V2 builder | Baseline confirmed |
| `app/playbooks/` | Playbook G / Sentient loop logic | G-shadow evidence passes |
| `data/new_build/` | Artifacts for the paper scoring pipeline | N/A |

### Audit / Operational Intelligence — OPERATOR_VISIBILITY_ONLY

| File | Role |
|---|---|
| `scripts/ops/update_mission_control.py` | Gate refresh (uses `MC_CONFIG`) |
| `app/core/mission_control_config.py` | Centralized gate thresholds and constants |
| `docs/stabilization/` | Stabilization artifacts (Map, Changelog, Governance) |
| `docs/operations/` | Production Runbooks (Scoring, Sigma, Rollback) |
| `tests/smoke_test.py` | System integrity verification (Golden Path) |

### Legacy / Archive — LEGACY_ARCHIVE

| Location | Contents |
|---|---|
| `archive/` | Retired scripts, dead code, and old experiments |
| `archive/requirements/` | Outdated dependency files |
| `models/sqpe_v18/` | Candidate — not yet promoted |

### Execution Safety — NEVER TOUCH

| File | Why |
|---|---|
| `app/agents/betfair_execution_agent.py` | Contains `place_order()` — NEVER import in live path |
| `app/agents/betfair_trading_agents.py` | Contains `place_bet()` — NEVER import in live path |
| `src/velo/execution_bridge.py` | Has `VELO_EXECUTION_MODE=LIVE → RuntimeError` — do not remove |

---

## 9. Hard Operating Rules (Permanent — Never Override)

```
NO live staking
NO changes to scoring logic without evidence gate
NO changes to model weights without gate + operator approval
NO Playbook G live promotion
NO VeloExecutionBridge in LIVE mode
NO import of betfair_execution_agent.py into scoring path (Code Enforced)

ALWAYS:
  source venv/bin/activate && PYTHONPATH=. python ...
  Credentials from .env only — never hardcoded
  Sigma run after every race day (ID-First matching)
  Verify system health with tests/smoke_test.py
```
