# VÉLØ Oracle Prime — Release Truth Ledger

**Status:** Canonical Release Definition | **Revision:** 2026-04-18.01

This document defines the "Minimum Honest VÉLØ." It serves as the definitive map for auditing, operating, and defending the release. Anything not listed as **Live/Operational** is considered shadow, support, or research.

---

## 1. Live Operational Organism
*The core circuits that must function for a "Pass" verdict to be issued.*

| Component | Path | Truth Role |
|---|---|---|
| **Ingestion Spine** | `workers/racing_api_fetcher.py` | Canonical API bridge (Basic Auth + Token Bucket). |
| **Normalization** | `workers/racing_api_normalizer.py` | Standardizes raw Racing API into VÉLØ internal schema. |
| **Primary Engine** | `app/services/velo_prime_service.py` | Orchestrates Feature Forge → Specialist Scores → Ensemble. |
| **Base Signal** | `models/sqpe_v17/sqpe_v17.pkl` | SQPE v17 (45% weight). The statistical floor. |
| **Specialists** | `models/specialist/` | 7 active specialist pkls (Market Deception, Place, Longshot, etc). |
| **Macro Layer** | `src/intelligence/macro_regime/` | BHA Context dampener. Prevents betting in "Chaos Mode." |
| **Ensemble** | `src/intelligence/velo_prime_ensemble.py` | The final meta-ensemble probability (`VELO_PRIME_prob`). |
| **Daily Loop** | `scripts/run_prime_today.py` | Daily orchestration, persist to `velo_verdicts`, Telegram broadcast. |
| **Sigma Loop** | `scripts/close_sigma_loops.py` | Nightly forensic reconciliation of results vs. predictions. |

---

## 2. Shadow & Support Systems
*Systems that run alongside the organism but do NOT mutate the live betting verdict.*

| Component | Path | Support Role |
|---|---|---|
| **Playbook G** | `app/playbooks/sentient_loopback.py` | Sentient memory. Logged as `g_shadow_multiplier`. **Mode: SHADOW ONLY.** |
| **Veteran Orchestrator**| `app/engine/orchestrator.py` | The 5-Agent system (Form, Connections, etc). Used for **Validation Only.** |
| **Spotlight NLP** | `workers/spotlight_parser.py` | NLP comment extraction. Feeds `horse_comments` for briefing context. |
| **Track Context** | `src/intelligence/track_context.py` | Decorative track/draw bias info. **Display-Only.** |

---

## 3. Live-Safe Endpoints
*Only these endpoints are audited for external production consumption.*

- `GET /health` : Comprehensive system health (DB + Stale Run + Model Check).
- `GET /` : Root status.
- `POST /api/v1/predict/race` : The primary ensemble scoring entry point.
- `GET /api/v1/status` : Version and uptime fingerprint.

---

## 4. Explicitly Out of Scope (Decommissioned/Broken)
*Do not audit, do not defend, do not expose.*

- **Broken Endpoints:** `POST /predict/full` (refactored out of scope).
- **Legacy Scrapers:** `scrapers/velo_scraper.py` (Linux-only, deprecated for API fetch).
- **ML Flow:** `mlruns/` (Internal dev only).
- **Unmerged Tech:** LangGraph Orchestration, Real-time Betfair Trading logic.

---

## 5. Defensive Mandates
1. **Truth Before Optimization:** If a race is "Chaos Mode," the probability must be flattened. No exceptions.
2. **Deterministic States:** The `HorseStateEngine` must remain deterministic and auditable.
3. **Quarantine Doctrine:** Targeted 45% pass rate. If the signal is noise, the system MUST pass.
