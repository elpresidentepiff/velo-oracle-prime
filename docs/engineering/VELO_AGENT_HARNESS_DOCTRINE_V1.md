# VÉLØ AGENT HARNESS DOCTRINE (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** May 28, 2026 | **Version:** 1.0.0

---

## 1. Introduction: The Harness-First Philosophy

Production agent quality does not come from model logic alone. The model is merely one node in a larger operational context; the true machine is the harness. As proven by VÉLØ’s May 24 operational failures, a highly refined predictive engine will still fail if its surrounding context, inputs, and state tracking are allowed to degrade silently. 

This doctrine establishes the **VÉLØ Operational Harness**, a six-layer protective and execution envelope that surrounds the VÉLØ Prime Model. The model’s sole responsibility is to score; the harness’s responsibility is to protect, recover, and observe.

```
+-----------------------------------------------------------------+
|                    VÉLØ GOVERNED OS (Learning)                  |
|  +-----------------------------------------------------------+  |
|  |             VÉLØ OPERATIONAL HARNESS (Protection)         |  |
|  |  +-----------------------------------------------------+  |  |
|  |  |              VÉLØ PRIME MODEL (Scoring)             |  |  |
|  |  +-----------------------------------------------------+  |  |
|  +-----------------------------------------------------------+  |
+-----------------------------------------------------------------+
```

---

## 2. The Six-Layer Harness Architecture

The VÉLØ Operational Harness is structured into six distinct layers, each with strict invariants, operational mappings, and responsibilities.

### Layer 1: Input Layer (Ingestion & Source Declaration)
No racecard or runner data may enter the scoring pipeline unless its source truth is explicitly declared and validated. This layer sanitizes raw inputs and assigns strict source-integrity labels.
* **Invariants:**
  * No raw payloads may reach the scoring workers.
  * Every input batch must carry a validated source label.
* **Source Integrity Labels:**
  * `RP_MERGED_CLEAN`: Synthesized from a complete set of 7 Racing Post PDFs, with full per-runner feature coverage.
  * `RP_MERGED_DEGRADED`: Synthesized from incomplete RP PDFs (e.g., missing Topspeed or Postdata), with feature degradation warnings active.
  * `RP_SCRAPER_CLEAN`: Sourced from Racing Post scraper pipeline with full integrity.
  * `RP_SCRAPER_DEGRADED`: Sourced from scraper but with partial data or errors.
  * `LOCAL_VERIFIED_ARTIFACT`: Loaded from verified local standard caches (`racecards_{date}_standard.json`).
  * `SOURCE_UNKNOWN_BLOCK`: Assigned when inputs do not match any known signature. Execution is strictly blocked.
* **Mapping:** Implemented in `src/velo/racecard_loader.py` and `workers/ingestion_spine/`.

### Layer 2: Knowledge Layer (Operating Memory & Grounding)
The Knowledge Layer maintains the permanent, immutable truth state of VÉLØ across execution sessions. It prevents "context drift" and ensures that the agent always operates on grounded, verified parameters.
* **Core Assets:**
  * `CLAUDE.md`: System-wide instructions, engineering rules, and baseline definitions.
  * `CURRENT_RUNTIME_TRUTH.md`: The live state of active formulas, disabled features, and blocklists.
  * `feature_registry_manifest_v1.csv`: Canonical list of all 21 production features and their valid ranges.
  * `policy_registry_manifest_v1.json`: Staking, decision-tier, and routing policies.
* **Mapping:** Grounded in `/home/ubuntu/velo-oracle-prime/data/` and `/home/ubuntu/velo-oracle-prime/docs/`.

### Layer 3: Context Manager (Session Discipline)
Prevents agent cognitive drift during long, multi-turn interactions. It enforces strict session start, checkpointing, and compaction protocols to maintain high-fidelity execution state.
* **Core Protocols:**
  * `VELO_SESSION_START_PROTOCOL_V1`: The mandatory checklist executed at the start of every session.
  * `VELO_HANDOFF_PACKET_V1`: The structured state packet generated prior to context compaction or session handover.
  * `VELO_CONTEXT_COMPACTION_RULES_V1`: Rules defining when and how to offload context to prevent factual loss.
* **Mapping:** Enforced by the operator and active agent loops.

### Layer 4: Task Graph (Command Structure & Gates)
Defines the strict directed acyclic graph (DAG) of execution. Tasks must execute in order, and subsequent nodes are gated by the success of predecessor nodes.
* **Execution Flow:**
  ```
  [Ingest PDFs] ---> [Normalize] ---> [Score VÉLØ Prime] ---> [Evaluate Gates] ---> [Persist DB] ---> [Telegram Alert]
  ```
* **Critical Invariant:**
  * Scoring and publication are strictly blocked if any preceding feature extraction or normalization node is degraded or fails.
* **Mapping:** Orchestrated in `scripts/ops/run_prime_today.py` and `workers/velo_supervisor.py`.

### Layer 5: Recovery Loop (Self-Healing & Fallbacks)
The active protection system that detects feature degradation, credential loss, or scoring collapse, and triggers immediate self-healing or safe-stop behaviors.
* **Core Recovery Handlers:**
  * *RPDC Return 0:* Warn and degrade run to `VISION_ONLY`.
  * *Constant Features:* Trigger `FEATURE_DEGRADED_BANNER` and block learning.
  * *Supabase Missing:* Fall back to local JSON persistence and issue high-priority Telegram alerts.
  * *Flatline VP Collapse:* Force `SCORING_COLLAPSED` flag, blocking all automated execution.
* **Mapping:** Defined in `src/velo/feature_audit.py` and `src/velo/signal_stack.py`.

### Layer 6: Observability Layer (The Audit Trail)
Every pipeline run must thoroughly explain itself. No silent failures, and no unproven "successes." Success is defined as verified data persistence combined with verified feature health.
* **Core Outputs:**
  * `Mission Control latest.json`: Live state and execution metrics.
  * `runner_prediction_snapshots`: Full per-runner scoring features.
  * `git_commit_sha`: The exact code fingerprint that produced the scoring.
* **Mapping:** Written to `data/` and `predictions/` tables.

---

## 3. Operational Matrix

| Layer | Responsibility | Primary Component | Verification Mechanism |
|---|---|---|---|
| **1. Input** | Declare and validate source truth | `racecard_loader.py` | Source Truth Header check |
| **2. Knowledge** | Ground session in immutable memory | `CLAUDE.md` | Verification of manifest hashes |
| **3. Context** | Enforce session start & stop discipline | `VELO_SESSION_START_PROTOCOL_V1` | Checkpoint commit on git |
| **4. Task Graph** | Control task execution order & gates | `run_prime_today.py` | Block downstream on error |
| **5. Recovery** | Handle active degradation and fallbacks | `feature_audit.py` | Active gates (Gate 2, 5, 6) |
| **6. Observability** | Produce unambiguous, auditable run logs | `runner_snapshot_store.py` | Snapshot count vs DB verification |

---

## 4. Harness Invariants

1. **Model Separation:** The model may never modify its own harness. Scoring weights, formulas, and parameters are read-only to the execution harness.
2. **Zero-Improvisation Rule:** The execution agent is strictly forbidden from bypassing task gates, ignoring preflight failures, or executing unapproved manual fallbacks.
3. **No-State Mutation:** The harness may not write to Supabase tables without a verified, un-degraded `git_commit_sha` and valid source truth declaration.
