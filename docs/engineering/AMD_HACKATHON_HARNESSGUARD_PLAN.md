# HarnessGuard Project Plan — AMD Developer Hackathon: ACT II

## 1. Project Title
**HarnessGuard by VÉLØ** — Self-Auditing Agent for ML Pipeline Reliability

## 2. One-Line Pitch
An AMD-powered agentic reliability layer that audits ML prediction pipelines for silent degradation, blocks unsafe learning, and generates recovery plans before bad decisions ship.

## 3. Why This Fits the AMD Challenge
HarnessGuard is an AI agent designed to run natively on the **AMD Developer Cloud** using **ROCm** and **PyTorch**. It addresses a performance-critical workload: the real-time auditing and vectorization of high-velocity prediction artifacts. By utilizing the **AMD Instinct MI300X**, HarnessGuard can perform batch anomaly detection and local LLM inference across massive historical context windows that would saturate standard CPUs.

## 4. Why VÉLØ is the Case Study
VÉLØ is not the product; it is the **Evidence**. VÉLØ is a live, event-driven prediction OS with a complex feature harness. We are using VÉLØ's real-world production "scars" (historical artifacts of silent failures) to prove HarnessGuard's utility. This demonstrates a high-stakes enterprise use case while maintaining a clear distance from gambling/betting domain logic.

## 5. Technical Architecture
*   **Artifact Ingestion:** A specialized loader parses messy system logs and JSON artifacts into structured "observations."
*   **Compute Layer:** AMD Instinct MI300X instances running ROCm-optimized PyTorch.
*   **Agent Core:**
    *   **Inference:** Local open-source LLM (Mistral-7B or Llama-3-8B) for policy evaluation.
    *   **Embeddings:** Batch vectorization of logs for anomaly classification.
*   **Orchestration:** Multi-step pipeline that detects drift, checks the Policy Registry, and determines if a "Learning Block" is mandatory.
*   **UI:** Streamlit-based "Mission Control" for operators.

## 6. AMD GPU Usage Plan
*   **High-Throughput Vectorization:** Embedding 1,000+ historical artifacts using `bge-large-en-v1.5` on ROCm.
*   **Local LLM Inference:** Running incident classification and recovery plan generation on MI300X HBM.
*   **Simulation Benchmarking:** Comparing CPU-bound vs. GPU-accelerated auditing speeds to highlight the AMD hardware advantage.

## 7. ROCm/PyTorch Model Choices
*   **LLM:** `Llama-3-8B-Instruct` or `Mistral-7B-v0.3` (GGUF/vLLM for ROCm).
*   **Embeddings:** `BAAI/bge-large-en-v1.5` (native PyTorch on ROCm).

## 8. Demo Dataset Plan (The Scars)
*   **Incident 1: RPDC Flatline.** A feature (`improvement_score`) became constant (0.0). The model outputs stayed valid, but the data was junk. HarnessGuard must detect zero variance.
*   **Incident 2: Supabase NULL Persistence.** `decision_tier` disappeared from persistence but the pipeline stayed green. HarnessGuard must detect schema drift/missing keys.
*   **Incident 3: RPR Timestamp Prov.** Risk of data leakage via inconsistent provenance. HarnessGuard must audit metadata integrity.

## 9. 5-Day Build Schedule
*   **Day 1: Problem Packaging.** Extract and sanitize VÉLØ artifacts. Define the feature health schema.
*   **Day 2: AMD Environment.** Provision AMD Cloud. Install ROCm/PyTorch. Establish baseline inference on MI300X.
*   **Day 3: Agent Intelligence.** Build the artifact scanner and policy evaluator. Implement learning-block logic.
*   **Day 4: Interface & Integration.** Build the Streamlit "Mission Control" dashboard. Wire the agent to the demo datasets.
*   **Day 5: Polish & Submit.** Record the video demo. Generate benchmarks. Finalize the pitch.

## 10. Judging Story
HarnessGuard moves the "Human-in-the-Loop" from reactive monitoring to agentic oversight. It solves the "Silent Failure" problem that plagues enterprise AI, using AMD's most powerful hardware to ensure that when a data source degrades, the AI doesn't just keep learning—it stops and asks for help.

## 11. Risks and Mitigations
*   **ROCm Setup Latency:** Mitigated by using pre-configured AMD Developer Cloud Docker images.
*   **LLM Hallucinations:** Mitigated by using strict RAG against a defined `policy_registry.json`.

## 12. VÉLØ Protection Rules (Hard Constraints)
*   No changes to live scoring behavior.
*   No weight changes or model promotions.
*   No router, staking, or Telegram mutation.
*   Project is fully isolated under `/hackathon/amd_harnessguard`.

## 13. MVP File Structure
```text
/hackathon/amd_harnessguard
├── src/
│   ├── artifact_loader.py
│   ├── feature_health_detector.py
│   ├── policy_evaluator.py
│   ├── recovery_planner.py
│   └── gpu_embedder.py
├── data/
│   └── demo_incidents/ (Sanitized JSON)
└── dashboard/
    └── app.py (Streamlit)
```

## 14. Final Submission Checklist
* [ ] Public GitHub Repo.
* [ ] 3-Minute Video Demo.
* [ ] AMD ROCm Benchmark Report.
* [ ] Architecture Diagram.
* [ ] Clean Demo Dataset.
