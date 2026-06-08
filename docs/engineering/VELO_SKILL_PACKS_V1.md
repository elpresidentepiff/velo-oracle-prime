# VÉLØ Skill Packs V1

**Status:** DESIGN ONLY  
**Phase:** 2 — Context Reuse  
**Classification:** `SKILL_PACKS_DEFINED` / `NO_RUNTIME_INSTALLATION` / `DESIGN_ONLY`

---

## Purpose

Every new agent session currently relearns VÉLØ from scratch. A CLAUDE.md exists but is broad. Skill packs are focused, purpose-specific context bundles that equip an agent for exactly one task domain without loading the entire system.

A skill pack is:
- A named, versioned context bundle
- Loaded by the agent at session start for a specific task class
- NOT a runtime installation
- NOT a library
- A governance-aware context document

---

## Skill Pack Catalogue

### VELO_SKILL_SENTINEL

**Purpose:** Guide any agent that needs to interact with the live scoring pipeline safely.

**Contents:**
- Hard rules for live-adjacent tasks
- No-go conditions catalogue (from Spec-First Protocol)
- Live runtime script classification
- Import safety rules
- Execution guard conditions
- How to verify no live mutation occurred

**When to load:** Any task that modifies `scripts/app/`, `src/intelligence/`, or any LIVE_RUNTIME script.

---

### VELO_SKILL_SIGMA

**Purpose:** Guide any agent running or interpreting the daily sigma process.

**Contents:**
- Canonical sigma command: `scripts/app/run_results_sigma.py --date YYYY-MM-DD`
- Banned scripts: `close_sigma_loops.py` — never use
- Sigma output format: locked, never change
- Telegram delivery format: locked, never change
- RPDC dependency chain order
- Blackout dates (2026-05-20 = SCORING_FLATLINE_CONTAMINATED)
- How to interpret sigma output and VP bands

**When to load:** Any daily evidence workflow, post-race analysis, or Telegram output task.

---

### VELO_SKILL_MISSION_CONTROL

**Purpose:** Guide any agent interacting with Mission Control dashboard or daily ops.

**Contents:**
- Mission Control file structure (`data/mission_control/`)
- Only `update_mission_control.py` should write to `latest.json`
- Daily harness order: sigma → ingest → rpdc → score → evidence → bridge
- Worktree state assertions
- Morning cockpit preflight requirements

**When to load:** Daily ops tasks, Mission Control updates, harness orchestration.

---

### VELO_SKILL_COUNCIL

**Purpose:** Guide any agent working with Council evidence packets, reports, or governance decisions.

**Contents:**
- Council module location: `src/velo/council/`
- Files: council_orchestrator.py, agents.py, verification.py, tool_registry.py, evidence_packet.py
- Council packet output: `data/council_packets/`
- Council report output: `data/council_reports/`
- How to produce a Council evidence packet
- Council sign-off requirements for model promotion
- Classification system: GATE_OPEN / NEEDS_EVIDENCE / BLOCKED

**When to load:** Council review tasks, model promotion discussions, governance audits.

---

### VELO_SKILL_RACE_SHAPE

**Purpose:** Guide any agent working with Race Shape or midprice research.

**Contents:**
- Race shape feature builder: `scripts/build_race_shape_features.py`
- Shadow ledger: `scripts/build_race_shape_shadow_ledger.py`
- Status: SHADOW_ONLY — not wired to live scoring
- Midprice hunter: `src/velo/midprice_hunter.py`
- SP 3–8.5 zone: 58% of all misses — primary research target
- Race shape precision tracker: `scripts/track_race_shape_precision.py`

**When to load:** Race shape research, midprice winner diagnosis, precision tracking.

---

### VELO_SKILL_INTERNATIONAL

**Purpose:** Guide any agent working on international expansion (HK/FR).

**Contents:**
- Gate: INTERNATIONAL_RATING_PROVENANCE_GATE_ACTIVE (locked `589b428`)
- Arena V1 result: all 5 packs FAILS_FAVOURITE_BASELINE (form-only)
- Arena V2 result: all 5 packs GATE_REOPENED_SAFE_SHADOW_CANDIDATE (with SP market signal)
- Key constraint: El Presidente sign-off required before migration
- FR leakage: same-race RPR/TS = POST_RACE_LEAKAGE_CONFIRMED — banned
- HK RPR/OR: PRE_RACE_SAFE (42–46% / 12–17% winner_max)
- Courses: HK (Sha Tin, Happy Valley), FR (Chantilly, Deauville, Longchamp, Saint-Cloud, Auteuil)
- Blocked actions: migration, workers, training, promotion
- Feature parquets: hk_prerace_features_v2, fr_prerace_features_v2

**When to load:** International feature building, arena tests, migration planning.

---

### VELO_SKILL_SECURITY_REVIEW

**Purpose:** Guide any agent performing a security review or credential audit.

**Contents:**
- All credentials in `.env` — never hardcode, never commit
- Repo is PUBLIC on GitHub — any committed value is public
- Racing API credentials were previously exposed in git history — rotate if needed
- Execution agents with `place_order()` / `place_bet()`: NEVER import in live path
- Import safety grep: `grep -r "place_order\|place_bet" src/ scripts/ | grep -v "app/agents"`
- VELO_EXECUTION_MODE=LIVE → RuntimeError (hard guard)
- BETFAIR_MODE=LIVE → RuntimeError (hard guard)

**When to load:** Security audits, credential reviews, deployment checks.

---

### VELO_SKILL_NO_LIVE_MUTATION

**Purpose:** The minimal safety pack — load this any time an agent touches production state.

**Contents:**
- `simulation_only=True` always
- `suggested_stake=None` always
- `max_liability=None` always
- `consumed_live=False` always
- Do not modify `weight_policy_registry.py` weights
- Do not modify `velo_prime_ensemble.py` ensemble composition
- Do not push to `main` without explicit operator instruction
- Do not apply SQL migrations without explicit operator sign-off
- Do not activate Railway workers without explicit operator sign-off

**When to load:** Any task even remotely adjacent to live state.

---

### VELO_SKILL_DATA_PROVENANCE

**Purpose:** Guide any agent dealing with feature engineering, training data, or new data sources.

**Contents:**
- Timestamp provenance test: winner_max_rate dominance test
- RACE_LEVEL_CONSTANT: features constant within race → PRE_RACE_SAFE (not leakage)
- POST_RACE_LEAKAGE_CONFIRMED: same-race RPR/TS for FR — banned
- PRE_RACE_SAFE threshold: winner_max_rate < 70% after within-race variance check
- DROP threshold: winner_max_rate > 70% with genuine within-race variance
- REVIEW_REQUIRED: 60–70% winner_max_rate
- Safety audit script: `scripts/audit_intl_prerace_feature_safety.py`
- Temporal split: train ≤2022-12-31, valid ≤2023-12-31, test >2023-12-31
- International lagged feature build: `scripts/build_international_lagged_rating_features.py`

**When to load:** Feature engineering, training data prep, new feature integration, provenance audits.

---

## Skill Pack Format (for future addition)

Each skill pack should be structured as:

```markdown
# VELO_SKILL_{NAME}

## Purpose
One sentence on what this context is for.

## Hard Rules
Non-negotiable constraints this agent must follow.

## Key Files
Critical paths with status annotations.

## Workflow
Step-by-step for the specific task class this pack governs.

## No-Go Conditions
Specific stop conditions for this domain.
```

---

## Installation

Skill packs are loaded at session start for specific task classes. They are NOT automatically loaded — the operator or orchestrator selects the relevant packs for each task.

No runtime installation required. No code changes. No dependencies.

```
SKILL_PACKS_V1_STATUS: DEFINED
PACKS: 9 defined (SENTINEL, SIGMA, MISSION_CONTROL, COUNCIL, RACE_SHAPE, INTERNATIONAL, SECURITY_REVIEW, NO_LIVE_MUTATION, DATA_PROVENANCE)
RUNTIME_INSTALLATION: NONE REQUIRED
```
