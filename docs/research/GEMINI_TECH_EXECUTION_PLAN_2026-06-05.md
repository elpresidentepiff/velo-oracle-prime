# Gemini Execution Plan - VELO Tech Upgrade Scout

**Date:** 2026-06-05  
**Executor:** Gemini  
**Source scout:** `docs/research/VELO_GITHUB_TECH_SCOUT_2026-06-05.md`  
**Mission:** Convert the GitHub tech scout into safe, staged VELO infrastructure upgrades.

## Non-Negotiable Boundaries

- Do not change live scoring behavior.
- Do not import live betting/execution packages into production paths.
- Do not touch `app/agents/betfair_execution_agent.py`, `app/agents/betfair_trading_agents.py`, or `src/velo/execution_bridge.py`.
- Do not promote any challenger model or Human Intent signal to live scoring.
- Keep all new tools optional, offline, shadow, or research-only until operator approval.
- If editing symbols, follow GitNexus doctrine from `CLAUDE.md`: run impact analysis first and detect changes before commit.

## Phase 0 - Orientation

1. Read:
   - `CURRENT_RUNTIME_TRUTH.md`
   - `CLAUDE.md`
   - `docs/research/VELO_GITHUB_TECH_SCOUT_2026-06-05.md`
   - `docs/evidence/HUMAN_INTENT_INTELLIGENCE_VAULT.md`

2. Confirm current dependency state:
   - `requirements.txt`
   - `requirements_production.txt`
   - any worker-specific requirements

3. Produce a short pre-flight note:
   - what is already present
   - what is missing
   - which phase will be implemented first

## Phase 1 - DuckDB Evidence Analytics Spine

**Goal:** Give VELO fast local SQL access over predictions, features, Sigma outputs, and evidence artifacts.

### Deliverables

1. Add optional dependency:
   - Prefer dev/research dependency only.
   - Do not force production runtime unless needed.

2. Create:
   - `scripts/ops/query_evidence_duckdb.py`

3. Script should support:
   - listing available local evidence sources
   - querying `data/new_build/paper_predictions/*.jsonl`
   - querying `data/velo_prime_verdicts_*.json`
   - querying `data/features/*.parquet`
   - writing output to `data/reports/duckdb/`

4. Add at least three useful canned queries:
   - latest New Build prediction counts by date
   - old VELO vs New Build runner overlap by date if available
   - feature null/drift summary from latest Parquet file

### Acceptance Checks

- Script runs without touching Supabase.
- Script works even if some data files are missing.
- Output is written as CSV or JSON under `data/reports/duckdb/`.
- No live scoring files changed.

## Phase 2 - Evidently Offline Drift Report

**Goal:** Catch source-shape decay and feature drift before it poisons evidence.

### Deliverables

1. Add optional dependency:
   - `evidently`
   - research/dev only unless operator approves otherwise

2. Create:
   - `scripts/ops/generate_feature_drift_report.py`

3. Report should compare:
   - latest `data/features/rp_runner_profile_latest.parquet`
   - a configurable reference file/window

4. Output:
   - `data/reports/evidently/YYYY_MM_DD_feature_drift.html`
   - `data/reports/evidently/YYYY_MM_DD_feature_drift.json` if supported

5. Include guardrails:
   - fail softly if reference data is missing
   - never alter features
   - never write to live prediction tables

### Acceptance Checks

- HTML report opens locally.
- Missing reference data produces a clear warning, not a crash.
- Drift script is standalone and offline.

## Phase 3 - MLflow Optional Experiment Memory

**Goal:** Track New Build/challenger runs without changing their decisions.

### Deliverables

1. Add optional MLflow support behind an environment flag:
   - `VELO_MLFLOW=1`

2. Create a small utility:
   - `src/ops/mlflow_tracking.py` or similar

3. Instrument only paper/shadow paths first:
   - New Build paper scoring
   - challenger comparison reports

4. Log:
   - run date
   - model/challenger name
   - thresholds
   - runner count
   - artifact paths
   - post-Sigma metrics when available

### Acceptance Checks

- With `VELO_MLFLOW` unset, behavior is unchanged.
- With `VELO_MLFLOW=1`, local MLflow artifacts are created.
- No live VP/tier logic changes.

## Phase 4 - Human Intent Typed Extraction

**Goal:** Turn raw Human Intent Vault notes into structured candidate mechanisms without hallucinated promotion.

### Deliverables

1. Use Pydantic schemas first, with or without Pydantic AI:
   - `Observation`
   - `Mechanism`
   - `EvidencePointer`
   - `PromotionStatus`

2. Create:
   - `scripts/ops/extract_human_intent_mechanisms.py`

3. Input:
   - `data/evidence_vault/human_intent_intelligence/*.md`

4. Output:
   - `data/evidence_vault/human_intent_intelligence/mechanisms_YYYY_MM_DD.jsonl`

5. Every mechanism must include:
   - source file
   - source timestamp or section if available
   - observation
   - inference
   - risk flag
   - status = `CANDIDATE_ONLY`

### Acceptance Checks

- No mechanism can be emitted without a source pointer.
- Output status is always `CANDIDATE_ONLY`.
- No output is consumed by live scoring.

## Phase 5 - Optuna Gate And Threshold Research

**Goal:** Tune New Build/shadow thresholds with evidence, not vibes.

### Deliverables

1. Add research-only Optuna dependency.

2. Create:
   - `research/threshold_tuning/optuna_new_build_gates.py`

3. Tune only historical or paper outputs:
   - VP thresholds
   - lane weights
   - Passport gates
   - frame/SR tradeoff

4. Output:
   - `data/reports/optuna/YYYY_MM_DD_new_build_gate_study.json`
   - optional plots if available

### Acceptance Checks

- Cannot write to live config.
- Results are marked `RESEARCH_ONLY`.
- Includes sample size and date window.

## Phase 6 - Watchlist Only

Do not implement yet unless explicitly requested:

- DSPy prompt optimization
- AutoGluon challengers
- TabPFN challengers
- betfairlightweight market tape ingestion
- flumine replay lab
- Gortex/codebase-memory-mcp benchmarking against GitNexus

## Execution Order

1. DuckDB spine.
2. Evidently drift report.
3. MLflow optional tracking.
4. Human Intent structured extraction.
5. Optuna research tuner.
6. Watchlist experiments only after operator approval.

## Final Gemini Output Required

When finished, provide:

- changed files
- dependencies added
- commands run
- reports generated
- proof that live scoring behavior was not changed
- any blockers or missing data
- next recommended phase

## Recommended First Command Set

```powershell
git status --short
Get-Content CURRENT_RUNTIME_TRUTH.md -TotalCount 180
Get-Content docs/research/VELO_GITHUB_TECH_SCOUT_2026-06-05.md -TotalCount 220
Get-Content docs/evidence/HUMAN_INTENT_INTELLIGENCE_VAULT.md -TotalCount 120
```

