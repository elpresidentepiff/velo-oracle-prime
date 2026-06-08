# HarnessGuard Technical Specification

## 1. Overview
HarnessGuard is a reliability agent that sits as a "guardian" layer above ML data pipelines. It utilizes the **AMD Instinct MI300X** to perform compute-intensive artifact auditing.

## 2. Component Definitions

### `artifact_loader.py`
*   **Responsibility:** Ingests raw JSON artifacts and system logs from the `/data/demo_incidents/` directory.
*   **Interface:** Returns a stream of `Observation` objects containing timestamp, component, and payload.

### `gpu_embedder.py`
*   **Responsibility:** Initializes the ROCm-backed PyTorch environment.
*   **Task:** Vectorizes incoming observation payloads using `bge-large-en-v1.5`.
*   **Hardware Target:** AMD Instinct MI300X via ROCm.

### `feature_health_detector.py`
*   **Responsibility:** Scans vectorized observations for anomalies.
*   **Specific Detectors:**
    *   **Zero-Variance:** Detects features that have become constant (e.g., the RPDC incident).
    *   **Schema Drift:** Detects missing or NULL keys (e.g., the Supabase persistence incident).
    *   **Temporal Leakage:** Audits timestamp provenance.

### `policy_evaluator.py`
*   **Responsibility:** Cross-references detected anomalies against `policy_registry.json`.
*   **Output:** Determines the severity: `INFO`, `WARNING`, `DEGRADED`, or `CRITICAL`.
*   **Rule:** If `severity >= DEGRADED`, it issues a **LEARNING_BLOCK** instruction.

### `recovery_planner.py`
*   **Responsibility:** Uses a local LLM (Mistral-7B/Llama-3-8B) running on the MI300X.
*   **Prompt:** "Given the anomaly [X] and policy [Y], generate a recovery command for the operator."
*   **Output:** Human-readable recovery plan and specific shell command.

### `benchmark_rocm_inference.py`
*   **Responsibility:** A dedicated script to measure latency and throughput.
*   **Goal:** Provide empirical proof of the AMD hardware advantage (Inference throughput on MI300X vs. dual-socket CPU).

### `dashboard/app.py`
*   **Responsibility:** Streamlit front-end.
*   **View:** "Mission Control" visualization of current pipeline health, anomaly heatmaps, and the agent's recovery recommendations.

## 3. Demo Data Schema (Sanitized VÉLØ Artifacts)
Demo cases will be stored in `/data/demo_incidents/`:
*   `rp_rpdc_degradation.json`: Artifacts where `improvement_score` is stuck at a constant value.
*   `supabase_null_persistence.json`: Artifacts where the `decision_tier` key is missing from the persistence layer.
*   `rpr_timestamp_provenance.json`: Artifacts showing RPR data injected with future/mismatched timestamps.

## 4. Hardware Environment
*   **Target:** AMD Developer Cloud
*   **OS:** Ubuntu 22.04 / ROCm 6.1
*   **PyTorch:** ROCm-enabled version (installed via `pip install torch --index-url https://download.pytorch.org/whl/rocm6.1`)
*   **LLM Runtime:** `vLLM` or `llama.cpp` compiled for ROCm.
