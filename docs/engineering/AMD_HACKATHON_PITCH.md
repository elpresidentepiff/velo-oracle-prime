# HarnessGuard Pitch Deck & Scripts

## 1. The 30-Second Elevator Pitch
"Modern AI systems don’t just fail when models hallucinate; they fail when their data harness goes blind. Missing features, stale data, and broken persistence silently degrade AI pipelines, leading to corrupted learning. **HarnessGuard** is an AMD-powered agent that audits ML prediction pipelines in real-time. By leveraging the **AMD Instinct MI300X** and **ROCm**, it detects silent degradation, blocks unsafe learning, and generates recovery plans before bad data poisons your models. We built it using real-world scars from a live, event-driven prediction OS, proving it works under production-grade complexity."

## 2. The 2-Minute Full Pitch
**(The Hook)** "Everyone focuses on training the best models, but what happens when the pipeline feeding that model breaks in production? Features drop out. APIs return NULLs. Timestamps leak. When this happens, your AI fails silently, and worse—it starts learning from garbage data.

**(The Problem)** "Silent degradation is the single greatest risk to enterprise AI. Traditional monitoring catches crashes, but it doesn't catch the 'RPDC Flatline'—where a feature technically exists but is providing constant, useless noise.

**(The Solution)** "Enter HarnessGuard. We’ve built a self-auditing agent that sits natively on the AMD Developer Cloud. HarnessGuard doesn't just watch for errors; it constantly vectorizes and audits pipeline artifacts, evaluating feature health against a high-fidelity policy registry.

**(The Hardware Angle)** "Auditing massive amounts of telemetry and complex JSON artifacts in real-time requires serious compute. By utilizing ROCm and the massive memory bandwidth of the AMD MI300X GPUs, HarnessGuard performs batch anomaly detection and local LLM inference with sub-second latency. It holds months of historical context in HBM to ensure that today's run isn't just valid, but *consistent*.

**(The Proof)** "This isn't hypothetical. We fed HarnessGuard real production incidents from VÉLØ, an active event-driven OS. Our demo shows HarnessGuard catching a silent data degradation, automatically issuing a *Learning Block* to protect the model's integrity, and generating the exact recovery plan for the operator. HarnessGuard ensures your AI stays reliable, and AMD ensures HarnessGuard stays fast."

## 3. The Technical Pitch (For Engineering Judges)
"HarnessGuard is built entirely on the AMD open-source stack. We utilize **PyTorch with the ROCm backend** to run a `Llama-3-8B-Instruct` model via `vLLM`. When a pipeline artifact is ingested, `gpu_embedder.py` vectorizes the payload using the MI300X. Our `feature_health_detector` flags anomalies like zero-variance features or schema drift in the vector space. 

If an anomaly is detected, the agent queries our `policy_evaluator`, passing the vectorized context to the MI300X-hosted LLM to determine risk severity. We have benchmarked this pipeline, proving that the MI300X's memory bandwidth enables artifact analysis throughput that makes real-time enterprise-grade auditing viable where CPUs fail to keep pace."

## 4. Judge-Facing Demo Script
1.  **Opening:** "Welcome to the HarnessGuard Mission Control. We are currently monitoring a live event-driven prediction pipeline."
2.  **The Trigger:** "Let's upload a batch of artifacts from a real incident. In this case, the `improvement_score` feature has silently become constant due to an upstream API change."
3.  **The Agent in Action:** "Notice the AMD GPU utilization spike as HarnessGuard vectorizes the artifact batch. In real-time, the `feature_health_detector` flags a zero-variance anomaly."
4.  **The Decision:** "HarnessGuard instantly cross-references the Policy Registry. Because this feature is critical for weights, the agent has issued a **LEARNING_BLOCK**. The model is protected from corrupted updates."
5.  **The Recovery:** "Finally, the agent generates a recovery plan. Here is the Mistral-7B generated command to reset the specific feature source."
6.  **The Benchmark:** "And here is the evidence: the MI300X processed this audit batch 14x faster than the CPU, allowing us to audit every single prediction without introducing pipeline lag."
