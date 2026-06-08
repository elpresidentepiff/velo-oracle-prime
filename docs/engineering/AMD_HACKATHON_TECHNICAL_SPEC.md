# AMD Hackathon: HarnessGuard — Technical Specification

**Status:** PLANNING  
**Created:** 2026-06-05  
**Project:** HarnessGuard by VÉLØ  
**Scope:** Docs only — no implementation until hackathon opens July 6, 2026

---

## Overview

This document defines the MVP component architecture, interface contracts, data schemas, and demo case structure for HarnessGuard. Every component is isolated under `hackathon/amd_harnessguard/`. No live VÉLØ code is modified or referenced at runtime.

---

## Component Specifications

### `artifact_loader.py`

**Purpose:** Loads and normalises VÉLØ pipeline artifacts from a local directory into a structured Python representation suitable for downstream analysis.

**Inputs:**
- `artifact_dir: str` — path to a demo case artifact folder
- `artifact_types: list[str]` — filter by type: `["prediction", "sigma", "feature_registry", "mission_control", "policy_registry"]`

**Outputs:**
- `list[Artifact]` — list of normalised artifact objects

**Artifact schema:**
```python
@dataclass
class Artifact:
    artifact_id: str          # deterministic hash of path + mtime
    artifact_type: str        # prediction | sigma | feature_registry | mission_control | policy_registry
    run_date: str             # YYYY-MM-DD
    raw: dict                 # parsed JSON content
    text_repr: str            # flattened text for embedding
    source_path: str          # original file path
```

**Safety contract:**
- Read-only. No writes to source directory.
- No network calls.
- No Supabase access.

---

### `feature_health_detector.py`

**Purpose:** Analyses loaded prediction artifacts to detect silent feature degradation patterns.

**Inputs:**
- `artifacts: list[Artifact]` — prediction artifacts for a given date
- `config: FeatureHealthConfig` — thresholds and feature registry

**Outputs:**
- `FeatureHealthReport` — per-feature health status with incident classifications

**Detection patterns:**

| Pattern | Classification | Trigger |
|---|---|---|
| Feature value constant across all runners | `FEATURE_FLATLINE_CRITICAL` | `std_dev == 0` across ≥ 80% of runners |
| Feature missing from >50% of runners | `FEATURE_MISSING_MAJORITY` | `null_rate > 0.5` |
| Feature value outside historical range | `FEATURE_RANGE_VIOLATION` | value > `mean + 4σ` or < `mean - 4σ` |
| Feature source fallback detected | `FEATURE_SOURCE_FALLBACK` | `source_tag` changed from primary to fallback |
| Schema field absent from artifact | `SCHEMA_CONTRACT_VIOLATION` | expected field not present in artifact |

**FeatureHealthReport schema:**
```python
@dataclass
class FeatureHealthReport:
    run_date: str
    features_checked: int
    incidents: list[FeatureIncident]
    overall_health: str           # HEALTHY | DEGRADED | CRITICAL
    learning_eligible: bool
    recommended_action: str
```

---

### `policy_evaluator.py`

**Purpose:** Evaluates whether a learning event should be allowed to proceed given the current feature health state and policy registry.

**Inputs:**
- `health_report: FeatureHealthReport`
- `policy_registry: dict` — loaded from `demo_cases/{case}/artifacts/policy_registry.json`

**Outputs:**
- `PolicyDecision` — ALLOW | WARN | BLOCK with reason

**Policy rules (MVP):**

| Condition | Decision |
|---|---|
| Any `FEATURE_FLATLINE_CRITICAL` incident | `BLOCK` |
| Any `SCHEMA_CONTRACT_VIOLATION` incident | `BLOCK` |
| `FEATURE_MISSING_MAJORITY` on a live-weighted feature | `BLOCK` |
| `FEATURE_SOURCE_FALLBACK` on a live-weighted feature | `WARN` |
| `FEATURE_RANGE_VIOLATION` on any feature | `WARN` |
| No incidents detected | `ALLOW` |

**PolicyDecision schema:**
```python
@dataclass
class PolicyDecision:
    decision: str             # ALLOW | WARN | BLOCK
    reason: str
    blocking_incidents: list[str]
    warning_incidents: list[str]
    safe_next_command: str    # e.g. "Run forensic-report only. Do not run learn-shadow."
```

---

### `recovery_planner.py`

**Purpose:** Generates a structured operator recovery plan given a policy decision and feature health report. Uses the AMD MI300X LLM to produce natural-language operator guidance.

**Inputs:**
- `policy_decision: PolicyDecision`
- `health_report: FeatureHealthReport`
- `llm_client: LLMClient` — wraps the ROCm-backed instruct model

**Outputs:**
- `RecoveryPlan` — structured plan with operator message, investigation steps, and safe next command

**RecoveryPlan schema:**
```python
@dataclass
class RecoveryPlan:
    incident_summary: str         # 1-2 sentence human-readable summary
    root_cause_hypothesis: str    # LLM-generated hypothesis
    investigation_steps: list[str]
    operator_message: str         # Telegram-style operator alert
    safe_next_command: str        # exact CLI command to run next
    blocked_commands: list[str]   # commands that must NOT be run
    estimated_recovery_time: str  # e.g. "30-60 minutes"
```

**LLM prompt template:**
```
You are HarnessGuard, an AI pipeline reliability agent.
A production ML pipeline has triggered the following incidents:
{incidents}

Policy decision: {decision}
Blocking reason: {reason}

Generate a structured recovery plan for the operator. Be specific, concise, and actionable.
Do not suggest any commands that would mutate live model weights or production state.
```

---

### `gpu_embedder.py`

**Purpose:** Embeds artifact text representations into a FAISS vector index using a sentence-transformer model running on AMD MI300X via ROCm.

**Inputs:**
- `artifacts: list[Artifact]`
- `model_name: str` — default: `"sentence-transformers/all-MiniLM-L6-v2"`
- `device: str` — default: `"cuda"` (ROCm maps CUDA device)

**Outputs:**
- `FAISSIndex` — searchable vector index
- `embedding_metadata: list[dict]` — maps vector IDs to artifact IDs

**GPU usage:**
- Model loaded to MI300X HBM3 via `model.to("cuda")`
- Batch size: 64 artifacts per forward pass
- Expected throughput: ~2,000 artifacts/minute on MI300X

---

### `benchmark_rocm_inference.py`

**Purpose:** Benchmarks embedding and LLM inference throughput on AMD MI300X vs CPU. Produces performance metrics for the hackathon submission.

**Benchmarks:**
1. Embedding throughput: artifacts/second (CPU vs MI300X)
2. LLM inference latency: tokens/second for recovery plan generation (CPU vs MI300X)
3. Batch anomaly detection: artifacts processed/second (CPU vs MI300X)

**Output:** `benchmark_results.json` with raw timings, throughput ratios, and a markdown summary table.

---

### `dashboard/app.py`

**Purpose:** Streamlit dashboard that allows a user to upload an artifact folder, run HarnessGuard, and view the incident report and recovery plan.

**Pages:**
1. **Upload** — drag-and-drop artifact folder or select a pre-loaded demo case
2. **Feature Health** — per-feature health status table with colour coding
3. **Policy Decision** — ALLOW / WARN / BLOCK banner with reason
4. **Recovery Plan** — operator message, investigation steps, safe next command
5. **Benchmark** — CPU vs MI300X throughput comparison chart

**Tech stack:** Streamlit 1.x, Plotly for charts, no external API calls.

---

## Demo Cases

### Case 1: `demo_cases/may24_rpdc_degraded/`

**Incident type:** `FEATURE_FLATLINE_CRITICAL`  
**Description:** The `improvement_score` feature, which carries a live weight of 0.12 in the SQPE ensemble, collapsed to a constant value (0.0) across all 33 runners on the affected race day. Telegram outputs remained green. No automated alarm fired.

**Expected agent output:**
```json
{
  "overall_health": "CRITICAL",
  "learning_eligible": false,
  "policy_decision": "BLOCK",
  "blocking_reason": "FEATURE_FLATLINE_CRITICAL: improvement_score std_dev=0.0 across 33/33 runners",
  "safe_next_command": "python workers/velo_ops_worker.py forensic-report --date 2026-05-24",
  "blocked_commands": ["learn-shadow", "daily-eod", "bulk-shadow-build"]
}
```

---

### Case 2: `demo_cases/supabase_decision_tier_null/`

**Incident type:** `SCHEMA_CONTRACT_VIOLATION`  
**Description:** The `decision_tier` field in the `sigma_audits` table was persisting as NULL for a subset of races due to a schema contract gap introduced during a migration. Downstream learning events were being built with missing classification data.

**Expected agent output:**
```json
{
  "overall_health": "CRITICAL",
  "learning_eligible": false,
  "policy_decision": "BLOCK",
  "blocking_reason": "SCHEMA_CONTRACT_VIOLATION: decision_tier NULL in 8/34 sigma_audit rows",
  "safe_next_command": "python workers/velo_ops_worker.py forensic-report --date {date}",
  "blocked_commands": ["learn-shadow", "daily-eod"]
}
```

---

### Case 3: `demo_cases/international_rpr_timestamp_risk/`

**Incident type:** `TEMPORAL_PROVENANCE_RISK`  
**Description:** International race entries were being processed with RPR (Racing Post Rating) timestamps that did not correctly reflect the data vintage, creating a risk of future data leakage into historical training sets.

**Expected agent output:**
```json
{
  "overall_health": "DEGRADED",
  "learning_eligible": false,
  "policy_decision": "WARN",
  "warning_reason": "TEMPORAL_PROVENANCE_RISK: RPR timestamp source unverified for 4 international entries",
  "safe_next_command": "python scripts/ops/runtime_truth_support.py --date {date} --check-rpr-provenance",
  "blocked_commands": ["bulk-shadow-build"]
}
```

---

## Interface Contract Summary

All components communicate via typed Python dataclasses. No shared mutable state. No database connections. No network calls. The entire agent runs in a fully offline mode against the demo dataset.

```
artifact_loader → [list[Artifact]]
                        ↓
feature_health_detector → [FeatureHealthReport]
                        ↓
policy_evaluator → [PolicyDecision]
                        ↓
recovery_planner → [RecoveryPlan]
                        ↓
dashboard/app.py → rendered report
```

The `gpu_embedder` runs as a parallel enrichment step, adding semantic search capability to the dashboard without blocking the core audit pipeline.

---

## Safety Contract

```
LIVE_STATE_MUTATION: NEVER
SUPABASE_WRITES: NEVER
MODEL_WEIGHT_CHANGES: NEVER
SCORING_PIPELINE_CALLS: NEVER
TELEGRAM_SENDS: NEVER
PLAYBOOK_G_CHANGES: NEVER
LIVE_ARTIFACT_WRITES: NEVER
```

All operations are read-only against pre-packaged demo datasets. The hackathon project is fully isolated under `hackathon/amd_harnessguard/`.
