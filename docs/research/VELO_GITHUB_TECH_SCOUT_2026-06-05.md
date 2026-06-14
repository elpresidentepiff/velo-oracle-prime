# VELO GitHub Tech Scout - 2026-06-05

**Purpose:** Scout current GitHub/open-source tech that can strengthen VELO without turning it into a live betting bot.

**Baseline:** VELO already has GitNexus, which is strong for code graph intelligence. Keep it. Scout alternatives only as benchmark pressure, not replacement.

## Executive Shortlist

| Priority | Tech | Repo / Source | VELO Use | Recommendation |
|---|---|---|---|---|
| P0 | DuckDB | https://github.com/duckdb/duckdb | Fast local analytics over Parquet/JSONL evidence, Sigma audits, New Build comparisons | Add as local analytics spine |
| P0 | Evidently | https://github.com/evidentlyai/evidently | Drift, data quality, prediction monitoring, CI test suites | Add weekly/offline drift reports first |
| P0 | MLflow | https://github.com/mlflow/mlflow | Experiment tracking, model registry, run comparison, LLM/agent tracing | Add lightweight local tracking before full registry |
| P1 | DVC | https://github.com/iterative/dvc | Version datasets, model artifacts, experiments outside Git blob hell | Add if data/model artifacts keep growing |
| P1 | Pydantic AI | https://github.com/pydantic/pydantic-ai | Typed operator agents for evidence extraction, report writing, guarded research workflows | Best fit for VELO agent tools |
| P1 | DSPy | https://github.com/stanfordnlp/dspy | Optimize extraction prompts and doctrine classifiers against scored examples | Use for Human Intent Vault extraction once labels exist |
| P1 | Optuna | https://github.com/optuna/optuna | Tune gates, ensemble weights, Passport thresholds, risk surfaces | Add to challenger experiments, not live path |
| P2 | AutoGluon | https://github.com/autogluon/autogluon | Benchmark tabular models against SQPE/New Build challengers | Use in research only due dependency weight |
| P2 | TabPFN | https://github.com/PriorLabs/TabPFN | Tabular foundation-model challenger for smaller labelled slices | Research sandbox only |
| P2 | betfairlightweight | https://github.com/betcode-org/betfair | Exchange stream / historic market data ingestion | Paper/replay only; never execution |
| P2 | flumine | https://github.com/betcode-org/flumine | Event replay, simulation, market-microstructure lab | Paper/replay only; never execution |
| Watch | Gortex / codebase-memory-mcp | https://gortex.dev/ / https://github.com/DeusData/codebase-memory-mcp | Code graph MCP alternatives to GitNexus | Benchmark only if GitNexus becomes stale or slow |

## Best Fits For VELO Right Now

### 1. DuckDB Analytics Spine

VELO has many local artifacts: JSONL predictions, Parquet features, Sigma audits, evidence reports. DuckDB is a high-performance in-process analytical database and can query Parquet/CSV directly without standing up infrastructure.

**Why it matters:** turns evidence review from ad hoc scripts into repeatable SQL notebooks/reports.

**Candidate first task:** create `scripts/ops/query_evidence_duckdb.py` that reads:

- `data/new_build/paper_predictions/*.jsonl`
- `data/velo_prime_verdicts_*.json`
- `data/features/*.parquet`
- Sigma audit exports

### 2. Evidently For Drift And Regression Gates

Evidently now covers tabular ML, LLM evals, data drift, prediction drift, quality checks, and test suites. VELO needs exactly that for New Build vs old VELO, Passport V2, and forward evidence.

**Why it matters:** catches "silent decay" when data source shape changes or a feature starts lying.

**Candidate first task:** generate a weekly `data/reports/evidently/YYYY_MM_DD_drift.html` comparing latest runner features vs a stable reference window.

### 3. MLflow For Experiment Memory

VELO currently has many paper/challenger runs. MLflow can track params, metrics, artifacts, model versions, and traces. It is useful even locally before any hosted registry.

**Why it matters:** stops model-promotion evidence from living only in scattered files.

**Candidate first task:** wrap New Build paper scoring with optional `VELO_MLFLOW=1` logging for model name, thresholds, date, runner count, SR/frame after Sigma, and artifacts.

### 4. Pydantic AI For Typed Operator Agents

Pydantic AI is a strong fit because VELO already prefers explicit contracts and safety boundaries. It gives typed dependencies, typed outputs, model-agnostic agents, and OpenTelemetry-style observability.

**Why it matters:** Human Intent Vault extraction can become structured without letting agents invent facts.

**Candidate first task:** a `HumanIntentExtractor` agent with strict output schema:

- observation
- inferred mechanism
- evidence quote/timestamp
- risk flag
- promotion status

### 5. DSPy For Prompt Optimization

DSPy is less about chat agents and more about optimizing language-model programs. This fits the Human Intent Vault once VELO has labelled examples of "good extraction" vs "bad extraction."

**Why it matters:** improves extraction/classification quality using examples instead of hand-tuned prompts.

**Candidate first task:** build a small gold set from the seven Human Intent files and optimize the mechanism classifier.

## Racing / Market-Specific Finds

### betfairlightweight

Fast Python wrapper for Betfair API-NG, including market and order streaming plus historic-data abstractions.

**VELO use:** market tape ingestion and historical replay only.

**Safety boundary:** never connect to live order placement in runtime. VELO remains intelligence infrastructure.

### flumine

Event-based betting/trading framework built around stream handling, paper trading, simulation, risk controls, and historical data.

**VELO use:** useful architecture reference for event replay and market-microstructure simulation.

**Safety boundary:** do not import execution into live scoring. If used, isolate in `research/market_replay/` or `scripts/paper/`.

### Horse Racing Prediction Repos

Most public horse-racing prediction repos are weaker than VELO. They are useful mainly for:

- feature ideas
- backtest pitfalls
- public benchmark datasets
- market replay patterns

Do not treat them as architecture leaders.

## Code Intelligence Scout

GitNexus remains the keeper. Current adjacent tools are moving in the same MCP code-graph direction:

- Gortex: in-memory repo graph, MCP/HTTP/UI, broad language support, editor-buffer overlays.
- codebase-memory-mcp: persistent tree-sitter knowledge graph, sub-ms style graph queries, Claude hooks.
- trace-mcp/codegraph variants: similar idea, structured code context for agents.

**Recommendation:** keep GitNexus. Add only one benchmark note: if GitNexus index freshness, Windows behavior, or symbol coverage becomes a problem, compare Gortex and codebase-memory-mcp on:

- Python call graph coverage
- FastAPI route detection
- stale-index behavior
- token savings
- edit-impact accuracy

## Model / Challenger Scout

### Optuna

Best immediate tool for threshold and ensemble tuning. Use for:

- VP gates
- New Build lane weights
- Passport feature thresholds
- risk bands
- Sigma postmortem sweeps

### AutoGluon

Good for "are we missing an obvious tabular baseline?" research. Heavy dependency, so keep outside production.

### TabPFN

Interesting for small/medium tabular slices and calibrated probabilistic predictions. Treat as a challenger, not a replacement for SQPE.

### SHAP

VELO already has SHAP references/code. Refreshing the dependency and adding explanation artifacts to challenger reports would help operator trust.

## Suggested Implementation Order

1. Add DuckDB local evidence query spine.
2. Add Evidently weekly drift report for runner features and prediction distributions.
3. Add MLflow optional local logging around New Build paper scoring.
4. Add Pydantic AI typed extraction for Human Intent Vault.
5. Add Optuna tuner for New Build gates and ensemble thresholds.
6. Add DSPy optimization only after labelled extraction examples exist.
7. Keep Betfair tools quarantined to paper replay/research only.

## Hard No

- Do not add live execution packages into production scoring paths.
- Do not replace GitNexus just because another code-graph tool is trending.
- Do not promote AutoML/TabPFN outputs without forward evidence.
- Do not let LLM agents write model doctrine without structured evidence and review.

## Final Read

The best current move is not a sexy new predictor. It is an evidence-and-ops upgrade:

**DuckDB + Evidently + MLflow + Pydantic AI + Optuna.**

That stack gives VELO better memory, better drift control, better challenger governance, and safer agent intelligence while preserving the core rule: evidence first, promotion later.

