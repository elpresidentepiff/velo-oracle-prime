# AMD Hackathon: HarnessGuard by VÉLØ — Project Plan

**Status:** PLANNING  
**Branch:** main  
**Created:** 2026-06-05  
**Hackathon:** AMD Developer: ACT II — July 6–11, 2026  
**Classification:** `AMD_HACKATHON_FIT_CONFIRMED`

---

## 1. Project Title

**HarnessGuard by VÉLØ**  
*Self-Auditing Agent for ML Pipeline Reliability*

---

## 2. One-Line Pitch

> HarnessGuard is an AMD-powered AI agent that reads a production ML prediction pipeline, detects silent feature degradation, blocks unsafe learning, and generates the operator recovery plan — demonstrated on VÉLØ, a real event-driven prediction OS.

---

## 3. Why This Fits the AMD Challenge

The AMD Developer: ACT II Hackathon requires an AI agent or high-performance AI application running on AMD Developer Cloud using ROCm and cloud-accessible AMD Instinct MI300X GPUs. HarnessGuard satisfies every criterion:

| Requirement | HarnessGuard Fit |
|---|---|
| Runs on AMD Developer Cloud | All inference and embedding runs on MI300X via AMD Developer Cloud |
| Uses ROCm + open-source AI frameworks | PyTorch/ROCm for model inference; HuggingFace Transformers for embeddings |
| AI agent that solves a real problem | Autonomous pipeline audit agent with multi-step reasoning |
| Agent orchestration | Artifact scanner → feature health detector → policy evaluator → recovery planner |
| Enterprise use case | AI reliability and MLOps observability — applicable to any production ML system |
| Performance-critical workloads | Batch embedding of 1,000+ prediction artifacts; anomaly detection at scale |

The MI300X's large HBM3 memory pool (192 GB) is specifically suited to loading large embedding models and running batch inference across many artifacts simultaneously — which is exactly what HarnessGuard does.

---

## 4. Why VÉLØ Is the Case Study, Not the Product

VÉLØ is a production event-driven prediction OS that generates real daily predictions, persists results to Supabase, and runs a closed learning loop. It is not being entered as a gambling or tipster product.

VÉLØ is the **case study** — the real-world system that experienced the exact failure modes HarnessGuard is designed to detect:

1. **RPDC/improvement_score degradation**: A live-weighted feature silently collapsed to a constant value. Telegram outputs remained green. No alarm fired. Learning had to be manually blocked.
2. **Supabase decision_tier NULL persistence gap**: A schema contract gap caused NULL values to persist in a critical decision field, silently corrupting downstream outputs.
3. **International RPR timestamp provenance risk**: A timestamp leakage risk was identified in international race data, threatening the integrity of time-sensitive features.

These are not hypothetical scenarios. They happened. HarnessGuard is the agent that would have caught them automatically.

The pitch is clean: **VÉLØ created the problem. HarnessGuard solves the problem. AMD powers the solution.**

---

## 5. Technical Architecture

```
AMD MI300X (ROCm)
        ↓
Open-Source LLM / Embedding Model (PyTorch/ROCm)
        ↓
┌─────────────────────────────────────────────────────┐
│              HarnessGuard Agent                     │
│                                                     │
│  artifact_loader.py                                 │
│    → reads logs, JSON artifacts, prediction files   │
│                                                     │
│  feature_health_detector.py                         │
│    → detects flatlines, missing fields, drift       │
│                                                     │
│  policy_evaluator.py                                │
│    → checks learning eligibility, weight contracts  │
│                                                     │
│  gpu_embedder.py                                    │
│    → embeds artifacts into vector index on MI300X   │
│                                                     │
│  recovery_planner.py                                │
│    → generates operator correction message          │
│    → outputs safe next command                      │
└─────────────────────────────────────────────────────┘
        ↓
dashboard/app.py (Streamlit/FastAPI)
        ↓
Mission Control Style Incident Report
```

The agent operates in a fully read-only mode against production artifacts. It does not mutate any live state, weights, models, or database records.

---

## 6. AMD GPU Usage Plan

The AMD MI300X is used for three distinct workloads:

**A. Artifact Embedding (Primary GPU Workload)**  
All VÉLØ prediction artifacts, sigma reports, mission control files, and feature registry documents are embedded into a local vector index using a HuggingFace sentence-transformer model running on ROCm. This enables semantic search across the entire pipeline history.

**B. Incident Classification (LLM Inference)**  
A small open-source instruct model (e.g., Mistral-7B-Instruct or Phi-3-mini) is loaded onto the MI300X and used to classify incidents, generate natural-language recovery plans, and produce operator-facing summaries. The MI300X's 192 GB HBM3 is ideal for running these models without quantization.

**C. Batch Anomaly Detection**  
Historical run artifacts (feature vectors, scoring outputs, sigma results) are processed in large batches on the GPU to detect statistical anomalies — flatlines, sudden variance collapse, distribution shift — across the full prediction history.

**D. Benchmarking**  
A dedicated `benchmark_rocm_inference.py` script compares CPU vs. MI300X throughput for embedding and inference tasks, producing a concrete performance story for the submission.

---

## 7. ROCm/PyTorch Model Choices

| Component | Model / Library | Reason |
|---|---|---|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Fast, lightweight, ROCm-compatible |
| LLM Inference | `mistralai/Mistral-7B-Instruct-v0.2` | Strong instruction following, fits MI300X HBM |
| Fallback LLM | `microsoft/Phi-3-mini-4k-instruct` | Smaller footprint, faster iteration |
| Vector Index | FAISS (GPU build) | Native GPU acceleration, ROCm-compatible |
| Framework | PyTorch 2.x + ROCm 6.x | AMD's primary supported stack |
| Serving | vLLM (if available on ROCm) | High-throughput inference for demo |

All models are open-source and available on HuggingFace. No proprietary API keys required.

---

## 8. Demo Dataset Plan

Three incident cases will be packaged as clean, anonymised demo datasets under `hackathon/amd_harnessguard/demo_cases/`:

**Case 1: `may24_rpdc_degraded/`**  
Artifacts from the RPDC/improvement_score degradation event. Includes prediction JSON, feature registry snapshot, sigma audit, and mission control report. The agent must detect that `improvement_score` is constant across all runners and classify the incident as `FEATURE_FLATLINE_CRITICAL`.

**Case 2: `supabase_decision_tier_null/`**  
Artifacts showing the decision_tier NULL persistence gap. The agent must detect the schema contract violation and classify it as `PERSISTENCE_GAP_SCHEMA_DRIFT`.

**Case 3: `international_rpr_timestamp_risk/`**  
Artifacts showing the international RPR timestamp provenance risk. The agent must detect the timestamp leakage and classify it as `TEMPORAL_PROVENANCE_RISK`.

Each demo case includes: raw artifacts, expected agent output, ground truth classification, and recovery plan template.

---

## 9. Five-Day Build Schedule

| Day | Focus | Deliverables |
|---|---|---|
| **Day 1** | Problem packaging | Clean demo datasets, feature health schema, README, demo story |
| **Day 2** | AMD environment | ROCm/PyTorch setup, model loaded on MI300X, inference verified, benchmark baseline |
| **Day 3** | Agent logic | `artifact_loader.py`, `feature_health_detector.py`, `policy_evaluator.py`, `recovery_planner.py` |
| **Day 4** | Demo application | `dashboard/app.py` (Streamlit), upload artifact folder, agent produces incident report, safe next command shown |
| **Day 5** | Polish and submission | Video demo, architecture diagram, performance metrics, before/after VÉLØ incident story, prize submission |

---

## 10. Judging Story

The submission narrative follows a three-act structure:

**Act I — The Problem**: Modern AI systems do not only fail when models are wrong. They fail when the harness goes blind. Features degrade silently. Data sources fall back without alerting. Schema contracts drift. Learning pipelines consume corrupted truth. By the time a human notices, the damage is done.

**Act II — The Evidence**: VÉLØ, a production event-driven prediction OS, experienced exactly this. A live-weighted feature (`improvement_score`) collapsed to a constant value. Telegram outputs remained green. No alarm fired. A human had to manually block learning. This is not a toy example — it is a real production incident with real consequences.

**Act III — The Solution**: HarnessGuard is the agent that would have caught it. Running on AMD MI300X via ROCm, it embeds the entire pipeline artifact history, runs semantic search across mission control files, detects the flatline in real time, evaluates learning eligibility against the policy registry, and generates the operator recovery plan — all before a single bad prediction reaches the user.

---

## 11. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ROCm compatibility issues with specific model versions | Medium | Test on Day 2; have CPU fallback path ready |
| AMD Developer Cloud access delays | Low | Apply for credits immediately on hackathon open |
| Demo dataset too domain-specific for judges | Medium | Add clear annotations explaining each incident type in enterprise terms |
| vLLM not available on ROCm | Medium | Fall back to HuggingFace `pipeline()` with `device="cuda"` (ROCm maps to CUDA device) |
| Scope creep into live VÉLØ code | Low | Strict isolation under `/hackathon/amd_harnessguard/`; hard rules enforced |

---

## 12. What Will Not Be Touched in Live VÉLØ

The following components are completely out of scope for the hackathon project and will not be modified, referenced, or exposed:

- Live scoring pipeline (`app/main.py`, `app/engine/`)
- Live model weights (`data/sentient_state.json`, `data/shadow_*`)
- Staking and router logic
- Telegram notification system
- Playbook G
- Supabase production tables (no writes)
- Any live prediction artifacts for dates after the hackathon start date

The hackathon project is fully isolated under `hackathon/amd_harnessguard/` and operates exclusively on pre-packaged demo datasets.

---

## 13. MVP File Structure

```
hackathon/
└── amd_harnessguard/
    ├── README.md
    ├── requirements.txt
    ├── artifact_loader.py
    ├── feature_health_detector.py
    ├── policy_evaluator.py
    ├── recovery_planner.py
    ├── gpu_embedder.py
    ├── benchmark_rocm_inference.py
    ├── dashboard/
    │   └── app.py
    └── demo_cases/
        ├── may24_rpdc_degraded/
        │   ├── artifacts/
        │   ├── expected_output.json
        │   └── README.md
        ├── supabase_decision_tier_null/
        │   ├── artifacts/
        │   ├── expected_output.json
        │   └── README.md
        └── international_rpr_timestamp_risk/
            ├── artifacts/
            ├── expected_output.json
            └── README.md
```

---

## 14. Final Submission Checklist

- [ ] Project runs end-to-end on AMD Developer Cloud (MI300X)
- [ ] ROCm/PyTorch inference verified and benchmarked
- [ ] All three demo cases produce correct incident classifications
- [ ] Dashboard deployed and accessible
- [ ] Video demo recorded (max 3 minutes)
- [ ] Architecture diagram included
- [ ] Performance benchmark (CPU vs MI300X) included
- [ ] README complete with setup instructions
- [ ] No live VÉLØ code modified
- [ ] No live VÉLØ data exposed
- [ ] Submission form completed before July 11, 2026 deadline

---

**Final Classification:**

```
AMD_HACKATHON_FIT_CONFIRMED
PROJECT_NAME: HARNESSGUARD_BY_VELO
VELO_USED_AS_REAL_CASE_STUDY
CORE_PRODUCT: AI_PIPELINE_RELIABILITY_AGENT
NO_LIVE_WEIGHT_CHANGES
NO_SCORING_CHANGE
NO_MODEL_PROMOTION
```
