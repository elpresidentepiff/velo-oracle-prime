# VÉLØ TRAINING ROADMAP 2026

**Created:** 2026-05-18  
**Status:** ACTIVE — Stage 1 beginning  
**Classification:** TRAINING_ROADMAP | NO_AUTO_PROMOTE | EVIDENCE_GATED

---

## Current Baseline (49-day audit as of 2026-04-28)

| Metric | Value |
|---|---|
| Training rows available | 1,310 (clean, result_matched, pre-May18) |
| Global SR | 20.6% |
| Global frame rate | 48.4% |
| VP ≥ 0.30 SR | 32.2% |
| Tier A SR | 40.1% |
| MDS > 0.5 SR | 54.8% |
| Primary model | SQPE v17 (0.45 weight) |
| Ensemble profile | SQPE_IMPROVEMENT_MDS_V1 |

This is the baseline everything must beat. No promotion without evidence.

---

## Stage 1 — CPU Model Arena (NOW)

**Goal:** Run XGBoost / LightGBM / CatBoost / logistic against the 1310 training rows. Establish challenger baseline.

**Script:** `scripts/train_velo_model_arena.py`  
**Output:** `data/reports/velo_model_arena_latest.json`, `models/shadow/model_arena/`

**Targets:**
1. `win` — binary win classification
2. `frame` — binary place/top-3 classification
3. `suppress` — binary no-bet classification (Tier C/X + VP < 0.20)

**Evaluation (time-split only — no random split):**
- Brier score (calibration quality)
- Log loss
- AUC
- SR by probability decile
- Frame rate by decile
- ROI by decile (with SP from corpus)
- Outlier-stripped ROI (remove top/bottom 5% SP)

**Packages available now:** LightGBM 4.6.0, sklearn 1.8.0  
**Packages needing operator approval:** XGBoost, CatBoost, Optuna

**Promotion gate:** Challenger must beat SQPE Brier score on full time-split validation. No partial wins accepted.

**2K milestone:** When training corpus reaches 2,000 clean rows, retrain all models and re-evaluate. Expected: 2026-07 at current scoring rate (~30 races/day).

---

## Stage 2 — Horse Career Memory (NOW, parallel)

**Goal:** Build per-horse career timeline from all available signals.

**Script:** `scripts/build_horse_career_memory.py`  
**Output:** `data/features/horse_career_memory_latest.parquet`

**Tracks per horse:**
- First/last seen date
- Age, starts observed, wins, frames
- OR/TS/RPR progression (earliest, latest, peak, delta)
- VP average across career
- MDS, improvement, CASHRUN tag history
- RPDC tags (CYCLE_RUN_2, STABLE_WARM, COURSE_RETURN, etc.)
- Trajectory label: EARLY_STAGE / IMPROVING / PLATEAU / REGRESSING / EXPOSED

**Special flags:**
- `juvenile_2yo` — age <= 2, fewer than 5 career starts
- `second_run_improve` — second career start with positive OR delta
- `nursery_pattern` — trainer + distance + class pattern for 2yo development

**Gate:** This feeds back into next-day VP scoring once approved by operator.

---

## Stage 3 — SLM Claim Engine (NEXT)

**Goal:** Extract structured claims from RP text.

**Spec:** `docs/engineering/VELO_SLM_CLAIM_ENGINE_V1.md`

**Phase A** — Rule-based extraction (regex, keyword matching)  
**Phase B** — DSPy pipeline (requires DSPy install, operator approval)  
**Phase C** — Fine-tuned SLM (requires GPU, separate operator approval)

**Prerequisite:** Stage 1 and 2 complete. Training corpus ≥ 1,500 verified rows.

---

## Stage 4 — AutoResearch Agent (PARALLEL TO STAGE 3)

**Goal:** Autonomous tool scouting and scorecard production.

**Spec:** `docs/engineering/VELO_AUTORESEARCH_AGENT_V1.md`

**Phase 1** — Stub agent (GitHub API + arXiv reader)  
**Phase 2** — DSPy-powered summarization  
**Phase 3** — Benchmark runner

**Prerequisite:** DSPy or LangGraph install approved.

---

## Stage 5 — RL Policy Simulator (LATER)

**Goal:** Learn action policy (bet/hold/suppress/lane-escalation) from historical outcomes.

**Spec:** `docs/engineering/VELO_RL_POLICY_SIMULATOR_V1.md`

**Prerequisite:**
- Training corpus ≥ 1,000 rows with full signal vector + SP + outcome
- Model arena probabilities stable (Stage 1 complete)
- Stable-Baselines3 installed and approved

**Gate:** Simulator ROI > +15% on validation before paper ledger test begins.

---

## Stage 6 — Shadow Policy Promotion (FUTURE)

**Goal:** Promote trained policy to shadow execution (paper ledger).

**Prerequisite:**
- RL simulator paper ledger n ≥ 100
- ROI > 0% at n ≥ 100
- Operator explicit approval
- No VELO_EXECUTION_MODE=LIVE

---

## Milestone Gates

| Milestone | Trigger | Expected date |
|---|---|---|
| 2K corpus | 2,000 clean training rows | 2026-07 (est.) |
| 5K corpus | 5,000 clean training rows | 2026-11 (est.) |
| Model arena first run | Stage 1 complete | 2026-05-18 |
| Horse career memory live | Stage 2 complete | 2026-05-18 |
| SLM Phase A | 1,500+ rows, Stage 1 done | 2026-06 (est.) |
| SLM Phase B | Phase A precision ≥ 0.80 | 2026-07 (est.) |
| RL simulator first run | 1,000 rows, Stage 1 done | 2026-07 (est.) |
| RL paper ledger | Simulator ROI > +15% | 2026-09 (est.) |

Dates are estimates. All gates are evidence-conditional, not time-conditional.

---

## Hard Rules (Permanent)

```
NO_PROMOTION_WITHOUT_EVIDENCE_GATE   = TRUE
NO_LIVE_STAKING_FROM_TRAINING        = TRUE
NO_SCORING_CHANGE_FROM_ARENA         = TRUE
NO_MODEL_REPLACEMENT_WITHOUT_GATE    = TRUE
NO_RL_LIVE_STAKING                   = TRUE
NO_SP_AS_PREDICTIVE_FEATURE          = TRUE (historical training context only)
OPERATOR_DECISION_AT_EVERY_GATE      = TRUE
ROLLBACK_ALWAYS_AVAILABLE            = TRUE (VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE)
```
