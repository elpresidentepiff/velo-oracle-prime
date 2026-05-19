# VÉLØ TOOL ADOPTION BOARD V1

**Created:** 2026-05-18  
**Governance:** Every tool must prove value before touching scoring, learning, or execution.  
**Process:** SHADOW_TEST → evidence gate → ADOPT_NOW. No skipping stages.

---

## Adoption Status Legend

| Status | Meaning |
|---|---|
| `ADOPT_NOW` | Install, use in shadow pipeline, evidence gated |
| `SHADOW_TEST` | Install in dev, run against historical data, no production touch |
| `WATCH` | Monitor, do not install yet |
| `REJECT` | Do not adopt — licence, security, or scope issues |

---

## 1. Tabular ML — Model Arena

### XGBoost
- **Repo:** `dmlc/xgboost` — ~28.4k stars, Apache-2.0
- **Purpose:** Gradient boosted trees — win/frame/suppress classification
- **VÉLØ use:** Shadow challenger model alongside SQPE/LightGBM
- **Install risk:** LOW — pure Python/C extension, no system deps
- **Security risk:** LOW
- **Production readiness:** HIGH — industry standard
- **Status:** `SHADOW_TEST`
- **Install:** `pip install xgboost`
- **Gate:** must beat SQPE Brier score on time-split test before any promotion

### LightGBM
- **Repo:** `lightgbm-org/LightGBM` — ~18.4k stars, MIT
- **Purpose:** Fast gradient boosting, efficient on large datasets
- **VÉLØ use:** Model arena challenger, fast iteration
- **Install risk:** LOW
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `ADOPT_NOW` (already installed: 4.6.0)
- **Install:** already present

### CatBoost
- **Repo:** `catboost/catboost` — ~9k stars, Apache-2.0
- **Purpose:** Gradient boosting with native categorical support
- **VÉLØ use:** Best fit for horse/trainer/jockey/course categoricals
- **Install risk:** LOW (large binary, ~90MB)
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `SHADOW_TEST`
- **Install:** `pip install catboost`
- **Gate:** same as XGBoost — time-split comparison before promotion

---

## 2. Hyperparameter Optimization

### Optuna
- **Repo:** `optuna/optuna` — ~14.2k stars, MIT
- **Purpose:** Hyperparameter optimization with pruning
- **VÉLØ use:** Tune model arena — n_estimators, learning_rate, max_depth
- **Install risk:** LOW
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `SHADOW_TEST`
- **Install:** `pip install optuna`
- **Constraint:** Only runs offline against historical data. Never touches live scoring.

---

## 3. Experiment Tracking

### MLflow
- **Repo:** `mlflow/mlflow` — ~26k stars, Apache-2.0
- **Purpose:** Experiment ledger — log runs, metrics, model artifacts
- **VÉLØ use:** Track model arena runs, compare challengers, version models
- **Install risk:** LOW
- **Security risk:** LOW (local tracking only — no cloud dependency required)
- **Production readiness:** HIGH
- **Status:** `SHADOW_TEST`
- **Install:** `pip install mlflow`
- **Note:** Run locally — do not configure remote server yet

### DVC (Data Version Control)
- **Repo:** `iterative/dvc` — ~15k stars, Apache-2.0
- **Purpose:** Data and model versioning, lightweight ML pipelines
- **VÉLØ use:** Version training datasets and model artifacts alongside git
- **Install risk:** LOW
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `WATCH`
- **Rationale:** The data lineage problem is real but not blocking training arena. Revisit at 2K milestone.

---

## 4. Agent Orchestration

### LangGraph
- **Repo:** `langchain-ai/langgraph` — ~32.3k stars, MIT
- **Purpose:** Stateful agent graphs — durable execution, human-in-the-loop, persistent memory
- **VÉLØ use:** AutoResearch agent, multi-step analysis workflows
- **Install risk:** MEDIUM — pulls langchain deps
- **Security risk:** LOW (local execution)
- **Production readiness:** HIGH for stateful agentic pipelines
- **Status:** `SHADOW_TEST`
- **Install:** `pip install langgraph`
- **Constraint:** No live scoring integration. Research-only lane first.

### CrewAI
- **Repo:** `crewAIInc/crewAI` — ~51.7k stars, MIT
- **Purpose:** Multi-agent orchestration with role assignment
- **VÉLØ use:** Tool evaluation crew, research crew
- **Install risk:** LOW
- **Security risk:** LOW
- **Production readiness:** MEDIUM (fast-moving API)
- **Status:** `WATCH`
- **Rationale:** LangGraph is better fit for VÉLØ's stateful, auditable workflows. CrewAI is faster to prototype.

### AutoGen (Microsoft)
- **Repo:** `microsoft/autogen` — ~58.1k stars, MIT
- **Purpose:** Multi-agent conversation framework
- **VÉLØ use:** None recommended
- **Status:** `REJECT`
- **Reason:** Repo explicitly states AutoGen is in maintenance mode. New development has moved to Microsoft Agent Framework. Do not build new infrastructure on it.

---

## 5. SLM Training / Local Inference

### Unsloth
- **Repo:** `unslothai/unsloth` — ~64.5k stars, Apache-2.0
- **Purpose:** Local fine-tuning of open models (LoRA, RL, low-VRAM)
- **VÉLØ use:** Fine-tune claim extractor on Racing Post text + sigma outcomes
- **Install risk:** HIGH (CUDA deps, large model downloads)
- **Security risk:** LOW
- **Production readiness:** MEDIUM (GPU required for training)
- **Status:** `WATCH`
- **Gate:** SLM claim engine spec approved, training data curated, GPU available

### Axolotl
- **Repo:** `axolotl-ai-cloud/axolotl` — ~11.9k stars, Apache-2.0
- **Purpose:** LLM fine-tuning workflows (FSDP, QLoRA, etc.)
- **VÉLØ use:** Alternative to Unsloth for supervised claim extraction training
- **Install risk:** HIGH
- **Security risk:** LOW
- **Production readiness:** MEDIUM
- **Status:** `WATCH`
- **Note:** Evaluate alongside Unsloth when GPU is available

### llama.cpp
- **Repo:** `ggml-org/llama.cpp` — ~111k stars, MIT
- **Purpose:** LLM inference in C/C++, CPU-compatible
- **VÉLØ use:** Local inference of SLM claim extractor (CPU path)
- **Install risk:** LOW (binary or Python binding via llama-cpp-python)
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `SHADOW_TEST`
- **Install:** `pip install llama-cpp-python`
- **Note:** Enables SLM inference on CPU without GPU. Use for extraction, not generation.

### vLLM
- **Repo:** `vllm-project/vllm` — ~80.4k stars, Apache-2.0
- **Purpose:** High-throughput inference serving for LLMs
- **VÉLØ use:** Future serving layer if SLM is promoted to production
- **Install risk:** HIGH (GPU only, large deps)
- **Security risk:** LOW
- **Production readiness:** HIGH (at scale)
- **Status:** `WATCH`
- **Gate:** Not relevant until SLM is ADOPT_NOW and serving latency is a problem

### DSPy
- **Repo:** `stanfordnlp/dspy` — ~22k stars, MIT
- **Purpose:** Programming (not prompting) of LM pipelines — optimises prompts/weights
- **VÉLØ use:** Claim extraction pipeline, self-improving feature extraction
- **Install risk:** LOW
- **Security risk:** LOW
- **Production readiness:** HIGH
- **Status:** `SHADOW_TEST`
- **Install:** `pip install dspy`
- **Note:** DSPy is the right framework for structured extraction pipelines before full fine-tuning

---

## 6. Reinforcement Learning

### Stable-Baselines3
- **Repo:** `DLR-RM/stable-baselines3` — ~13.3k stars, MIT
- **Purpose:** PyTorch RL algorithms (PPO, SAC, A2C, etc.)
- **VÉLØ use:** Policy layer simulator — bet/no-bet, lane escalation, exposure limits
- **Install risk:** LOW (PyTorch required)
- **Security risk:** LOW
- **Production readiness:** MEDIUM (simulator only)
- **Status:** `WATCH`
- **Gate:** RL simulator spec approved, tabular model probabilities stable, n>=1000 training records

### Ray / RLlib
- **Repo:** `ray-project/ray` — ~42.6k stars, Apache-2.0
- **Purpose:** Distributed ML, RL at scale
- **VÉLØ use:** Large-scale RL training, distributed model search
- **Install risk:** MEDIUM (complex dependency tree)
- **Security risk:** LOW
- **Production readiness:** HIGH (at scale)
- **Status:** `WATCH`
- **Rationale:** Stable-Baselines3 first. Ray is a later-stage tool when scale is the constraint.

---

## 7. Research Agents

### MiroFlow
- **Paper:** arxiv 2602.22808 — open-source deep research agent framework
- **Purpose:** Agent graphs for reproducible research (GAIA/BrowseComp benchmarks)
- **VÉLØ use:** AutoResearch agent — scout tools, read docs, write scorecards
- **Status:** `WATCH`
- **Rationale:** Evaluate the framework once code is public and stable. VÉLØ's AutoResearch agent can be built with LangGraph first.

---

## 8. Repo Intelligence

### GitNexus (in-repo)
- **Scope:** Already integrated — see `CLAUDE.md`, `.claude/skills/gitnexus/`
- **Purpose:** Code graph, symbol impact analysis, dependency mapping, commit archaeology
- **VÉLØ use:** Catch producer/consumer mismatches (e.g. the May 18 synthetic ID regression would have been catchable via impact analysis on `_norm_horse_name`)
- **Status:** `ADOPT_NOW` — already installed and indexed
- **Lesson from May 18:** Always run `gitnexus_impact` before editing shared normalisation utilities

---

## 9. Visualization / Whiteboard

### Miro
- **Type:** Cloud whiteboard product (not a code tool)
- **VÉLØ use:** System architecture maps, agent permission matrix, data lineage boards, Sigma learning loop diagrams
- **Status:** `ADOPT_NOW` (for documentation/planning only — not runtime)
- **Hard rule:** Never a runtime dependency. Design artifacts only.

---

## Install Approval Queue

Tools approved for local dev install (no production deploy):

| Tool | Install command | Approved by |
|---|---|---|
| LightGBM | already installed | ✓ |
| XGBoost | `pip install xgboost` | PENDING_OPERATOR |
| CatBoost | `pip install catboost` | PENDING_OPERATOR |
| Optuna | `pip install optuna` | PENDING_OPERATOR |
| MLflow | `pip install mlflow` | PENDING_OPERATOR |
| DSPy | `pip install dspy` | PENDING_OPERATOR |
| llama-cpp-python | `pip install llama-cpp-python` | PENDING_OPERATOR |

No package is installed automatically. Operator approves each install.

---

## Hard Rules (Permanent)

```
NO new tool enters scoring path without adoption gate passed
NO LLM/SLM weights trained on actual_sp as predictive feature
NO RL policy touches live staking
NO new package installed without operator approval
NO AutoGen (maintenance mode)
NO skipping SHADOW_TEST stage
```
