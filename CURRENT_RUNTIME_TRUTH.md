# VÉLØ Oracle Prime — Current Runtime Truth

**Last updated:** 2026-05-23 (Section 3 corrected — signal truth table reconciled to runtime code)  
**Status:** PRODUCTION — read this before touching anything  
**Authority:** This document supersedes TRUTH_REGISTRY.md, SYSTEM_MAP.md, BRANCH_MAP.md, and any phase-specific docs.

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
scripts/ops/run_prime_today.py   ← LIVE_RUNTIME entry point
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

**Racing API status:** DECOMMISSIONED as primary source (2026-05-14). 401 on API = WARN_ONLY when RP profile exists. RP PDFs are now the primary data source.

---

## 3. Active Ensemble — Signal Truth Table

| Signal | Current weight | Live weighted? | Stored? | Shadow only? | Notes |
|---|---|---|---|---|---|
| `sqpe_v17_prob` (VP) | **0.45** | YES | YES | NO | Dominant anchor — SQPE v17 |
| `improvement_score` | **0.12** | YES | YES | NO | LIVE_WEIGHTED — active since ensemble surgery 2026-05-08 |
| `market_deception_score` (MDS) | **0.10** | YES | YES | NO | Best sidecar, SR=54.8% at MDS>0.5 |
| `place_prob` | declared 0.08, **BADGE_ONLY** | NO (excluded from VP) | YES | NO | BADGE_ONLY — frame badge, not VP-weighted in current profile |
| `longshot_score` | declared 0.07, **FROZEN** | NO (excluded from VP) | YES | NO | FROZEN (FREEZE_CANDIDATE) — ROI=-0.065; SP≥10 gate still used for tier X |
| `release_window_score` | 0.00 (STORED_ONLY) | NO | YES | NO | STORED_ONLY — both profiles; calculated, stored, not weighted |
| `comment_intel_score` | 0.00 (STORED_ONLY) | NO | YES | NO | STORED_ONLY — both profiles; calculated, stored, not weighted |
| Playbook G / sentient | 0 | NO | YES | YES | Shadow mode — multiplier computed but NOT applied to VP |
| NO_VP_COMPOSITE challenger | 0 | NO | Shadow gate | YES | Forward gate at n=284/300 runners |

**Active ensemble profile:** `SQPE_IMPROVEMENT_MDS_V1` (commit b7e4e0c, 2026-05-08)  
**Rollback:** `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE`  
**Section 3 corrected:** 2026-05-23 — prior table described LEGACY_FULL_ENSEMBLE (pre-surgery) state. See `LIVE_SCORING_TRUTH_AUDIT_2026_05_23.md` for full audit.

**Effective VP formula (renormalized by active weights):**  
`VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67`

---

## 4. Evening Reconciliation (Sigma Loop)

```
After results close:
    scripts/ops/scrape_results_atr.py --date YYYY-MM-DD
        │  Outputs: data/results_YYYY_MM_DD.json
        ▼
    scripts/ops/run_results_sigma.py --date YYYY-MM-DD --notify-telegram
        │  Writes: sigma_audits (Supabase), Telegram sigma report
        ▼
    scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
        │  Writes: racing_horse_runs (Supabase) — feeds tomorrow's RPDC
        ▼
    scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
        │  Appends: velo_innovation_protocol_1k_deduped.csv
        ▼
    scripts/backtest/build_shadow_model_forward_gate.py
        │  Updates: data/reports/shadow_model_forward_gate_latest.json
```

---

## 5. File and Module Classification

### Core Runtime — LIVE_RUNTIME

| File | Role |
|---|---|
| `scripts/ops/run_prime_today.py` | Daily scoring orchestrator (Railway cron) |
| `scripts/ops/run_results_sigma.py` | Nightly reconciliation + Telegram |
| `scripts/ops/scrape_results_atr.py` | Results scraper (Sporting Life) |
| `scripts/ops/ingest_results_to_horse_runs.py` | Results ingestion to Supabase |
| `scripts/ops/build_rpdc_daily.py` | RPDC tags (run before scoring next day) |
| `scripts/ops/build_rp_runner_profile.py` | RP PDF → parquet profile |
| `scripts/ops/publish_daily_predictions_to_dashboard.py` | Dashboard JSON publisher |
| `scripts/ops/runtime_truth_support.py` | Runtime support utilities |
| `src/intelligence/velo_prime_ensemble.py` | Live ensemble scoring engine |
| `src/intelligence/sqpe.py` | SQPE base probability model |
| `src/velo/product_router.py` | Verdict routing / tier decision |
| `app/main.py` | FastAPI entry point (Railway) |

### Shadow / Evidence Only — SHADOW_ONLY

| File | Role | Promote only if |
|---|---|---|
| `scripts/backtest/build_shadow_model_forward_gate.py` | Forward gate tracker | n≥300 + operator approval |
| `scripts/backtest/train_velo_model_arena_v2.py` | 90-model arena training | Not live |
| `src/velo/execution_bridge.py` | Paper execution only | Hard `LIVE → RuntimeError` gate |
| `models/shadow/model_arena_v2/` | 90 challenger pkl files | All 8 gates + operator approval |
| `data/sentient_state.json` | Playbook G live state | READ ONLY — mutation forbidden |
| Playbook G (`shadow_full_train_v2`) | Shadow learning target | Evidence-gated + promotion audit |

### Audit / Operational Intelligence — OPERATOR_VISIBILITY_ONLY

| File | Role |
|---|---|
| `scripts/ops/velo_mission_control.py` | Read-only operator dashboard |
| `scripts/ops/velo_morning_cockpit.py` | Morning preflight summary |
| `scripts/audit/` (all) | Forensic audits — no scoring side effects |
| `scripts/ops/router_shadow_audit.py` | Router lane evidence accumulator |
| `scripts/ops/build_innovation_protocol.py` | Corpus builder |

### Paper Execution Only — PAPER_ONLY

| File | Role |
|---|---|
| `src/velo/execution_bridge.py` | VeloExecutionBridge — SIM only |
| `scripts/ops/run_execution_bridge_shadow.py` | Paper ledger runner |
| `data/velo_execution_bridge_paper_ledger.csv` | Paper P&L |

### Legacy / Archive — LEGACY_ARCHIVE

| Location | Contents |
|---|---|
| `archive/legacy/2026-05-19-cleanup/scripts/` | One-off scripts, design docs, old experiments |
| `archive/legacy/2026-05-19-cleanup/data/` | Historical snapshots, old sentient state backups |
| `archive/legacy/2026-05-19-cleanup/models/` | sqpe_v14/v15/v16, tie_v1/v2, overlay_v5, longshot_v6 |
| `models/sqpe_v17_dev/` | Development reference only |
| `models/sqpe_v18/` | Candidate — not yet promoted |
| `models/tie_v9/` | Legacy TIE model — not in current ensemble |

### Execution Safety — NEVER TOUCH

| File | Why |
|---|---|
| `app/agents/betfair_execution_agent.py` | Contains `place_order()` — NEVER import in live path |
| `app/agents/betfair_trading_agents.py` | Contains `place_bet()` — NEVER import in live path |
| `src/velo/execution_bridge.py` | Has `VELO_EXECUTION_MODE=LIVE → RuntimeError` — do not remove |

---

## 6. Active Model Artifacts

| Model | Path | Status | Used by |
|---|---|---|---|
| SQPE v17 | `models/sqpe_v17/sqpe_v17.pkl` | **LIVE** | `run_prime_today.py` |
| improvement_model | `models/specialist/improvement_model/` | **LIVE** | ensemble (evidence weight) |
| market_deception_model | `models/specialist/market_deception_model/` | **LIVE** | ensemble (0.10 weight) |
| place_model | `models/specialist/place_model/` | **LIVE** | ensemble (0.08 weight) |
| longshot_model | `models/specialist/longshot_model/` | **LIVE, gated** | SP≥10 only |
| release_window_model | `models/specialist/release_window_model/` | live (disabled) | visibility only |
| comment_intel_model | `models/specialist/comment_intelligence_model/` | live (disabled) | visibility only |
| draw_bias_model | `models/specialist/draw_bias_model/` | live (disabled) | visibility only |
| NO_VP_COMPOSITE LR | `models/shadow/model_arena_v2/*.pkl` | **SHADOW GATE** | forward gate only |
| SQPE v18 | `models/sqpe_v18/sqpe_v18.pkl` | Candidate | Not yet wired |

---

## 7. Shadow Model Forward Gate

**Model:** `NO_VP_COMPOSITE_logistic_win`  
**Training cutoff:** 2026-05-10 (immutable)  
**Current gate status:** `GATE_OPEN_ACCUMULATING` — n=284/300  
**Gate requirement:** n≥300 runners + n≥75 top-decile + operator approval  
**`consumed_live` flag:** `False` — permanent until all 8 gates pass + explicit operator sign-off

Full gate state: `data/reports/shadow_model_forward_gate_latest.json`

---

## 8. Proven Evidence Baseline (49-day audit, 2026-04-28)

| Signal | n | SR | Frame | Rank |
|---|---|---|---|---|
| VP≥0.30 + Tier A | 162 | 40.1% | 77.2% | PROVEN |
| MDS > 0.50 | 31 | 54.8% | 96.8% | PROVEN (small n) |
| improvement_score > 0.40 | 62 | 43.5% | 82.3% | PROVEN |
| VP≥0.30 | 345 | 32.2% | 69.3% | PROMISING |
| place_prob > 0.80 | 392 | 31.6% | 66.8% | PROMISING |
| Tier B VP<0.30 | 272 | 16.9% | 44.1% | SUPPRESS |

Global baseline: SR=20.6%, Frame=48.4% over 49 days, 1,391 sigma rows.

---

## 9. Hard Operating Rules (Permanent — Never Override)

```
NO live staking
NO changes to scoring logic without evidence gate
NO changes to model weights without gate + operator approval
NO Playbook G live promotion
NO VeloExecutionBridge in LIVE mode
NO Betfair order placement
NO Railway schema changes without operator sign-off
NO import of betfair_execution_agent.py or betfair_trading_agents.py into scoring path
NO scoring runs from non-canonical repo/branch

ALWAYS:
  source venv/bin/activate && PYTHONPATH=. python ...
  Credentials from .env only — never hardcoded
  Sigma run after every race day
  git status clean before any scoring run
```

---

## 10. Next Operational Gates

| Gate | Trigger | Action |
|---|---|---|
| Shadow model gate | n=300 runners (16 remaining) | Run 300-runner review packet |
| 2K corpus milestone | ~2026-07 at current rate | Full V2 arena retraining |
| VP40_TIER_A shortprice | n≥150 VP40+Tier A | Shortprice lane review |
| SP_2X embryo lane | n≥50 SP≥2x selections | SP_2X policy review |
| improvement_score evidence review | n≥100 matched forward | Forward evidence review (already LIVE_WEIGHTED since 2026-05-08) |

---

## 11. Infrastructure

| Service | Status | Detail |
|---|---|---|
| Railway `velo-oracle` | LIVE | FastAPI, `app/main.py`, nixpacks |
| Supabase | LIVE | `ltbsxbvfsxtnharjvqcm.supabase.co`, eu-west-2 |
| GitHub | LIVE | `elpresidentepiff/velo-oracle-prime` |
| Racing API | DEGRADED | 401 frequent — RP PDFs are primary |
| Betfair | NOT ACTIVE | Simulation mode only, execution blocked |

Credentials: `.env` file only. Never commit. See `.env.example` for required vars.
