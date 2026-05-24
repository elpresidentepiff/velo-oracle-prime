# VÉLØ Master Rollout Plan V1

**Prepared:** 2026-05-23  
**Authority:** El Presidente  
**Status:** DESIGN ONLY — Read-only governance document  
**Classification:** `MASTER_ROLLOUT_PLAN_V1` / `NO_RUNTIME_CHANGES_AUTHORISED`

---

## Section 1 — Executive Doctrine

**VÉLØ is not:**
- A tipster
- A single model
- A chatbot
- A batch script

**VÉLØ is:**
- An event-driven racing intelligence operating system
- A governed prediction and learning system
- A shadow-first research lab
- A Council-supervised decision engine
- A provenance-first data platform
- A future product, media, and business layer — separated from the prediction brain

This distinction is permanent and non-negotiable. Every architectural decision must preserve the separation between the prediction core and the business layer. Every model change requires evidence. Every live-state mutation requires operator sign-off. The prediction brain does not take instructions from business automation.

**Governing principles:**
1. Shadow before live — all new features run in shadow before any promotion discussion
2. Evidence before promotion — no model change without n≥100 closed results + operator sign-off
3. Provenance before trust — no feature without timestamp verification
4. Council before change — governance layer has veto power over all significant changes
5. Spec before code — every build starts with a no-go conditions spec
6. Separation of concerns — business layer cannot touch prediction state

---

## Section 2 — Layer Map

### A. Governance Layer

The meta-layer that controls what the system is allowed to do.

| Component | File/Path | Status |
|---|---|---|
| Mission Control | `scripts/app/update_mission_control.py`, `data/mission_control/` | LIVE_ACTIVE |
| Sentinel | `scripts/app/` (preflight, watchdog) | LIVE_ACTIVE |
| Council | `src/velo/council/` | PRESENT / STATUS_UNCONFIRMED |
| Policy Registry | `docs/engineering/policy_registry_manifest_v1.json` | DESIGN_ONLY |
| Feature Registry | `docs/engineering/feature_registry_manifest_v1.csv` | DESIGN_ONLY |
| Quarantine Logic | `src/velo/execution_guard.py` | LIVE_ACTIVE |
| Next Safe Command | (to be defined in Spec-First Protocol) | PLANNED |

### B. Intelligence Layer

The prediction and signal engines.

| Component | Path | Status |
|---|---|---|
| SQPE v17 | `src/intelligence/sqpe.py` + `models/sqpe_v17/` | LIVE_ACTIVE |
| VeloPrimeEnsemble | `src/intelligence/velo_prime_ensemble.py` | LIVE_ACTIVE |
| Specialist Models (×7) | `models/specialist/` | LIVE_ACTIVE |
| Race Shape | `scripts/build_race_shape_features.py` | SHADOW_ONLY |
| CPU Gate V2 | `scripts/build_cpu_shadow_gate_v2.py` | SHADOW_ONLY |
| Shadow Model V1 | `models/shadow/model_arena/` | SHADOW_ACTIVE |
| Contextual Forecasting | (defined in Phase 5 doc) | PLANNED |
| Latent State / HMM | (defined in Phase 6 doc) | RESEARCH_ONLY |
| Policy RL Sandbox | (defined in Phase 7 doc) | RESEARCH_ONLY |

### C. Data Layer

The substrate everything runs on.

| Component | Path | Status |
|---|---|---|
| Supabase / Postgres | 54+ tables | LIVE_ACTIVE |
| Evidence Corpus | `scripts/audit/build_unified_evidence_corpus.py` | LIVE_ACTIVE |
| Learning Events | (sigma → ingest → rpdc chain) | LIVE_ACTIVE |
| Shadow/Live Separation | `src/velo/execution_guard.py` | LIVE_ACTIVE |
| Provenance Gates | `docs/engineering/INTL_MODEL_PROMOTION_GOVERNANCE_V1.md` | ACTIVE |
| International Pack Schemas | `migrations/intl_schemas_v1.sql` | NOT_APPLIED (gate-blocked) |
| Feature Registry | `docs/engineering/feature_registry_manifest_v1.csv` | DESIGN_ONLY |

### D. Agent Operations Layer

Governs what automated agents are allowed to do.

| Component | Status | Notes |
|---|---|---|
| Agent Harness | PLANNED (Phase 3) | Mission Control owns task queue |
| Sandbox Runner | PLANNED (Phase 3) | Disposable environments, read-only state |
| MCP Boundary | PLANNED (Phase 9) | Approved tool connections only |
| Skills Packs | PLANNED (Phase 2) | Reusable context bundles |
| Red Team Agent | PLANNED (Phase 8) | Internal defensive only |
| Automation Bus | PLANNED (Phase 9) | Ops/reporting only — no live mutation |

### E. Product / Media / Business Layer

Separated from the prediction brain. Cannot affect scoring, learning, or live state.

| Component | Status | Notes |
|---|---|---|
| Media Engine | PLANNED (Phase 10) | Ghost/Listmonk-style publishing |
| Product Analytics | PLANNED (Phase 10) | Plausible-style, privacy-first |
| Report Video Engine | PLANNED (Phase 10) | HTML-to-MP4 automated reporting |
| Business Automation | DEFERRED | Cloudflare/Stripe/autonomous-agent concepts explicitly deferred |

---

## Section 3 — Phase Rollout

### Phase 0 — V14 Governance Closure (ACTIVE)
**Goal:** Finish path verification, build registries, Council packet, close governance gaps.  
**Deliverables:** Architecture truth map, feature registry, policy registry, Council review packet.  
**Status:** COMPLETE as of 2026-05-23 (commit `6e65261`).

### Phase 1 — Spec-First Execution Protocol
**Goal:** Make spec-before-code a mandatory governance culture.  
**Deliverables:** `VELO_SPEC_FIRST_EXECUTION_PROTOCOL_V1.md`  
**Status:** NEXT

### Phase 2 — VÉLØ Skill Packs
**Goal:** Reusable context bundles that prevent every agent session relearning VÉLØ from scratch.  
**Deliverables:** `VELO_SKILL_PACKS_V1.md`  
**Status:** NEXT (can run parallel to Phase 1)

### Phase 3 — Agent Harness + Sandbox Runner
**Goal:** Define governed execution boundaries for automated agents.  
**Deliverables:** `VELO_AGENT_HARNESS_V1.md`, `VELO_SANDBOX_RUNNER_V1.md`  
**Status:** PLANNED (after Phase 1 spec culture is set)

### Phase 4 — Interaction Core / Micro-turn Learning
**Goal:** Move from batch-script architecture to event-sliced intelligence OS.  
**Deliverables:** `VELO_INTERACTION_CORE_V1.md`, `VELO_MICRO_FEEDBACK_LEDGER_V1.md`  
**Status:** PLANNED

### Phase 5 — Contextual Forecasting Layer
**Goal:** Model race context, not just form history.  
**Deliverables:** `VELO_CONTEXTUAL_FORECASTING_LAYER_V1.md`  
**Status:** RESEARCH

### Phase 6 — Latent State / HMM Research
**Goal:** Model hidden horse states (improving, regressing, laid-out, etc.).  
**Deliverables:** `VELO_LATENT_STATE_MODEL_V1.md`  
**Status:** RESEARCH_ONLY — no production use

### Phase 7 — Council Simulation Lab + Policy RL Sandbox
**Goal:** Shadow-only simulation of policy worlds and RL reward/penalty framework.  
**Deliverables:** `VELO_COUNCIL_SIMULATION_LAB_V1.md`, `VELO_POLICY_RL_SANDBOX_V1.md`  
**Status:** RESEARCH_ONLY

### Phase 8 — Red Team Agent + Complexity Audit
**Goal:** Internal defensive attack surface and system-level complexity audit.  
**Deliverables:** `VELO_RED_TEAM_AGENT_V1.md`, `VELO_COMPLEXITY_AUDIT_V1.md`  
**Status:** PLANNED (after Phase 3 harness)

### Phase 9 — MCP Boundary + Automation Bus
**Goal:** Governed agent-to-tool connections and ops-only automation.  
**Deliverables:** `VELO_MCP_BOUNDARY_V1.md`, `VELO_AUTOMATION_BUS_V1.md`  
**Status:** PLANNED

### Phase 10 — Product / Media / Analytics Layer
**Goal:** Public-facing product and media layer, fully separated from prediction core.  
**Deliverables:** `VELO_MEDIA_ENGINE_V1.md`, `VELO_PRODUCT_ANALYTICS_V1.md`, `VELO_REPORT_VIDEO_ENGINE_V1.md`  
**Status:** DEFERRED (after prediction layer proven)

### Phase 11 — International Continuation
**Goal:** Close the international gate, apply migrations, build ingest workers.  
**Deliverables:** `VELO_INTERNATIONAL_NEXT_GATE_PLAN_V1.md`  
**Status:** GATE_BLOCKED (provenance gate active; arena V2 opened gate — El Presidente sign-off required)

---

## Section 4 — Master Dependency Order

```
1.  V14 governance closure              [Phase 0 — COMPLETE]
2.  Spec-first protocol                 [Phase 1 — NEXT]
3.  Skill packs                         [Phase 2 — parallel to Phase 1]
4.  Agent harness / sandbox boundary    [Phase 3 — after Phase 1]
5.  Interaction core / micro-feedback   [Phase 4 — after Phase 3]
6.  Contextual forecasting              [Phase 5 — research, no dependency]
7.  Latent-state research               [Phase 6 — research, no dependency]
8.  Council simulation + RL sandbox     [Phase 7 — after Phase 3 + Phase 6]
9.  Red Team + complexity audit         [Phase 8 — after Phase 3]
10. MCP / automation boundary           [Phase 9 — after Phase 3]
11. Product / media layer               [Phase 10 — after prediction proven]
12. International next gate             [Phase 11 — El Presidente sign-off first]
```

No shortcuts. No phase can be skipped or merged that has a stated dependency.

---

## Section 5 — Hard Rules (Permanent)

```
NO scoring changes
NO model promotion
NO router/staking changes
NO Telegram runtime changes
NO Playbook G promotion
NO live-state mutation
NO migration without operator sign-off
NO worker activation without operator sign-off
NO external tool adoption without audit
Business automation SEPARATED from prediction brain
Cloudflare/Stripe/autonomous-company-agent concepts DEFERRED
```

---

## Section 6 — Final Classification

```
VELO_MASTER_ROLLOUT_PLAN_CREATED
V14_GOVERNANCE_FIRST
V15_INTERACTION_INTELLIGENCE_DEFINED
SPEC_FIRST_PROTOCOL_REQUIRED
AGENT_HARNESS_SHADOW_ONLY
CONTEXTUAL_FORECASTING_CORE_RESEARCH
POLICY_RL_SHADOW_ONLY
BUSINESS_LAYER_SEPARATED
INTERNATIONAL_STILL_GATED
NO_SCORING_CHANGE
NO_MODEL_PROMOTION
```
