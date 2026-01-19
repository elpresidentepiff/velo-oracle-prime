# GOVERNANCE PIPELINE ARCHITECTURE (PHASE 3)

**Status:** Design Complete, Ready for Implementation  
**Version:** 1.0  
**Date:** 2026-01-19  
**Depends On:** V13 Constitutional Layer (merged)

---

## EXECUTIVE SUMMARY

The Governance Pipeline is the human-in-loop control layer that routes critic findings to explicit approval before any system change. It enforces the constitutional guarantee: **no auto-apply, ever.**

---

## CORE PRINCIPLES

1. **Separation of Powers**: Critics propose, humans decide, system executes (only after approval)
2. **Explicit Ledger**: Every decision (accept/reject) is recorded with timestamp, reviewer, and rationale
3. **Atomic Promotion**: Patches move through discrete states (DRAFT → PENDING → ACCEPTED/REJECTED)
4. **Reversibility**: Accepted patches can be rolled back with full audit trail
5. **No Backdoors**: Zero code paths that bypass human approval

---

## ARCHITECTURE COMPONENTS

### 1. Patch Proposal Flow

```
┌─────────────────┐
│   Critics       │ (Read-only, episode-bound)
│  - Leakage      │
│  - Bias         │
│  - Feature      │
│  - Decision     │
└────────┬────────┘
         │ emit PatchProposal
         ▼
┌─────────────────┐
│ Proposal Queue  │ (Database table: patch_proposals)
│  Status: DRAFT  │
└────────┬────────┘
         │ auto-transition after episode finalization
         ▼
┌─────────────────┐
│ Review Queue    │ (Status: PENDING)
│  Human UI       │
└────────┬────────┘
         │ human decision
         ▼
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ACCEPTED│ │REJECTED│
└───┬────┘ └───┬────┘
    │          │
    │          └─→ Ledger (audit log)
    ▼
┌─────────────────┐
│ Doctrine Update │ (Version bump, rollback anchor)
└─────────────────┘
```

---

### 2. Database Schema (Governance Layer)

#### Existing Table (from V13)

```python
patch_proposals = Table(
    "patch_proposals",
    id (UUID, primary key),
    episode_id (UUID, foreign key → episodes),
    critic_type (enum: LEAKAGE, BIAS, FEATURE, DECISION),
    severity (enum: CRITICAL, HIGH, MEDIUM, LOW),
    finding_type (string),
    description (text),
    proposed_change (JSON),  # Structured patch payload
    status (enum: DRAFT, PENDING, ACCEPTED, REJECTED, ROLLED_BACK),
    created_at (timestamp),
    reviewed_at (timestamp, nullable),
    reviewer_id (string, nullable),
    review_rationale (text, nullable),
    doctrine_version_before (string, nullable),
    doctrine_version_after (string, nullable),
)
```

#### New Table (Governance Ledger)

```python
governance_ledger = Table(
    "governance_ledger",
    id (UUID, primary key),
    proposal_id (UUID, foreign key → patch_proposals),
    action (enum: ACCEPT, REJECT, ROLLBACK),
    actor (string),  # Reviewer username/ID
    timestamp (timestamp),
    rationale (text),
    doctrine_version_snapshot (string),
    episode_count_at_decision (integer),  # Context: how many episodes informed this
    metadata (JSON),  # Additional context (e.g., vote count if multi-reviewer)
)
```

---

### 3. Patch Proposal Lifecycle

#### State Machine

```
DRAFT → PENDING → ACCEPTED → ACTIVE
                ↓           ↓
              REJECTED   ROLLED_BACK
```

#### State Definitions

- **DRAFT**: Critic emitted proposal, attached to episode, not yet ready for review
- **PENDING**: Episode finalized, proposal moved to review queue
- **ACCEPTED**: Human approved, patch applied to doctrine, version bumped
- **REJECTED**: Human declined, proposal archived with rationale
- **ROLLED_BACK**: Previously accepted patch was reverted (doctrine version decremented)

#### Transition Rules

1. `DRAFT → PENDING`: Automatic when episode is finalized (outcome recorded)
2. `PENDING → ACCEPTED`: Human approval via UI
3. `PENDING → REJECTED`: Human rejection via UI
4. `ACCEPTED → ROLLED_BACK`: Human-initiated rollback (rare, emergency only)

---

### 4. Human Review Interface (UI)

#### Review Queue Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ Governance Pipeline - Pending Proposals (12)            │
├─────────────────────────────────────────────────────────┤
│ Filters: [All Critics ▼] [All Severity ▼] [Sort: Date ▼]│
├─────────────────────────────────────────────────────────┤
│                                                          │
│ 🔴 CRITICAL - Leakage Detector                          │
│ Episode: race_2026-01-18_R7                             │
│ Finding: Future market leakage detected                 │
│ Proposed Change: Add temporal validation rule           │
│ [View Details] [Accept] [Reject]                        │
│                                                          │
│ 🟡 MEDIUM - Cognitive Bias                              │
│ Episode: race_2026-01-18_R3                             │
│ Finding: Anchoring bias (over-weighted favorite)        │
│ Proposed Change: Adjust confidence calibration          │
│ [View Details] [Accept] [Reject]                        │
│                                                          │
│ ... (10 more)                                           │
└─────────────────────────────────────────────────────────┘
```

#### Proposal Detail View

```
┌─────────────────────────────────────────────────────────┐
│ Proposal #a3f9b2e4 - CRITICAL                           │
├─────────────────────────────────────────────────────────┤
│ Critic: Leakage Detector                                │
│ Episode: race_2026-01-18_R7 (decision_time: 12:00 UTC)  │
│ Finding Type: FUTURE_MARKET_LEAKAGE                     │
│                                                          │
│ Description:                                            │
│ Market snapshot at 12:05 UTC was used in pre-state,    │
│ 5 minutes after decision time. This violates epistemic │
│ time separation.                                        │
│                                                          │
│ Proposed Change:                                        │
│ {                                                       │
│   "rule_type": "temporal_validation",                  │
│   "condition": "market_snapshot.timestamp <= decision_time", │
│   "action": "reject_snapshot",                         │
│   "severity": "CRITICAL"                               │
│ }                                                       │
│                                                          │
│ Episode Artifacts:                                      │
│ - PRE_STATE: [View JSON]                               │
│ - INFERENCE: [View JSON]                               │
│ - OUTCOME: [View JSON]                                 │
│                                                          │
│ Similar Findings: 3 episodes with same pattern         │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐│
││ Review Decision:                                     ││
││ ○ Accept - Apply this patch to doctrine             ││
││ ○ Reject - Archive without applying                 ││
││                                                       ││
││ Rationale (required):                                ││
││ [Text area]                                          ││
││                                                       ││
││ [Cancel] [Submit Decision]                           ││
│└─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

### 5. Explicit Accept/Reject Ledger

#### Ledger Entry Example (ACCEPT)

```json
{
  "id": "ledger_001",
  "proposal_id": "a3f9b2e4",
  "action": "ACCEPT",
  "actor": "presidente@velo.ai",
  "timestamp": "2026-01-19T03:15:00Z",
  "rationale": "Confirmed via replay: 3 episodes leaked future data. Temporal validation rule is necessary to prevent false confidence.",
  "doctrine_version_snapshot": "13.0.0",
  "episode_count_at_decision": 2847,
  "metadata": {
    "affected_episodes": ["race_2026-01-18_R7", "race_2026-01-18_R3", "race_2026-01-17_R9"],
    "estimated_impact": "Prevents 2.1% of episodes from leaking future data"
  }
}
```

#### Ledger Entry Example (REJECT)

```json
{
  "id": "ledger_002",
  "proposal_id": "b8c4d1f3",
  "action": "REJECT",
  "actor": "presidente@velo.ai",
  "timestamp": "2026-01-19T03:20:00Z",
  "rationale": "Overconfidence finding is valid but proposed calibration change is too aggressive. Will monitor for 100 more episodes before deciding.",
  "doctrine_version_snapshot": "13.0.0",
  "episode_count_at_decision": 2847,
  "metadata": {
    "defer_until_episode_count": 2947,
    "alternative_approach": "Collect more data on confidence-outcome correlation"
  }
}
```

---

### 6. Doctrine Version Management

#### Doctrine Versions Table (from V13)

```python
doctrine_versions = Table(
    "doctrine_versions",
    version (string, primary key),  # Semantic versioning: 13.0.0, 13.1.0, etc.
    created_at (timestamp),
    created_by (string),
    description (text),
    rules_snapshot (JSON),  # Full snapshot of all active rules
    parent_version (string, nullable),  # For rollback
    active (boolean),  # Only one version can be active
)
```

#### Version Bump Logic

- **PATCH** (13.0.0 → 13.0.1): Bug fix, no behavior change
- **MINOR** (13.0.0 → 13.1.0): New rule added (e.g., temporal validation)
- **MAJOR** (13.0.0 → 14.0.0): Breaking change (e.g., critic authority model changed)

#### Rollback Mechanism

```python
def rollback_doctrine(target_version: str):
    # 1. Verify target version exists
    # 2. Mark current version as inactive
    # 3. Activate target version
    # 4. Log rollback in governance_ledger
    # 5. Notify all systems of doctrine change
    pass
```

---

### 7. Integration with Critics

#### Critic Emission (No Change)

Critics continue to emit `PatchProposal` objects as before:

```python
@enforce_read_only
def critique(self, episode: Episode) -> Critique:
    findings = self._detect_issues(episode)
    proposals = self._generate_proposals(findings)
    
    return Critique(
        episode_id=episode.id,
        critic_type=self.critic_type,
        findings=findings,
        proposals=proposals,  # Automatically inserted into patch_proposals table
        timestamp=datetime.now(UTC),
    )
```

#### Proposal Persistence (New)

```python
def persist_proposals(critique: Critique):
    for proposal in critique.proposals:
        db.insert(patch_proposals, {
            "id": generate_uuid(),
            "episode_id": critique.episode_id,
            "critic_type": critique.critic_type,
            "severity": proposal.severity,
            "finding_type": proposal.finding_type,
            "description": proposal.description,
            "proposed_change": proposal.change,
            "status": "DRAFT",  # Initial state
            "created_at": datetime.now(UTC),
        })
```

---

### 8. Governance API (Backend)

#### Endpoints

```python
# List pending proposals
GET /api/governance/proposals?status=PENDING

# Get proposal details
GET /api/governance/proposals/{proposal_id}

# Accept proposal
POST /api/governance/proposals/{proposal_id}/accept
Body: { "rationale": "...", "reviewer_id": "..." }

# Reject proposal
POST /api/governance/proposals/{proposal_id}/reject
Body: { "rationale": "...", "reviewer_id": "..." }

# Rollback accepted proposal
POST /api/governance/proposals/{proposal_id}/rollback
Body: { "rationale": "...", "reviewer_id": "..." }

# Get governance ledger
GET /api/governance/ledger?limit=50&offset=0

# Get doctrine version history
GET /api/governance/doctrine/versions
```

---

### 9. Hard Gates (Enforcement)

#### No Backdoors

```python
# WRONG: Auto-apply based on confidence
if proposal.severity == "CRITICAL" and proposal.confidence > 0.95:
    apply_patch(proposal)  # ❌ VIOLATION

# CORRECT: Always route to human
if proposal.severity == "CRITICAL":
    mark_as_pending(proposal)  # ✅ COMPLIANT
    notify_reviewer(proposal)
```

#### Doctrine Immutability

```python
# WRONG: Direct doctrine mutation
doctrine.rules.append(new_rule)  # ❌ VIOLATION

# CORRECT: Version-controlled promotion
new_version = doctrine.create_version(
    parent=current_version,
    changes=[new_rule],
    approved_by=reviewer_id,
)
activate_doctrine_version(new_version)  # ✅ COMPLIANT
```

---

### 10. Metrics & Observability

#### Governance Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ Governance Metrics (Last 30 Days)                       │
├─────────────────────────────────────────────────────────┤
│ Proposals Emitted: 247                                  │
│ Proposals Pending: 12                                   │
│ Proposals Accepted: 18 (7.3%)                           │
│ Proposals Rejected: 217 (87.9%)                         │
│ Proposals Rolled Back: 0                                │
│                                                          │
│ Avg Time to Review: 4.2 hours                           │
│ Doctrine Version: 13.2.1                                │
│ Active Rules: 34                                        │
│                                                          │
│ Top Critics by Proposals:                               │
│ 1. Leakage Detector: 89 (36%)                           │
│ 2. Cognitive Bias: 72 (29%)                             │
│ 3. Feature Extractor: 54 (22%)                          │
│ 4. Decision Critic: 32 (13%)                            │
└─────────────────────────────────────────────────────────┘
```

---

## IMPLEMENTATION PHASES

### Phase 3A: Proposal Persistence (Week 1)
- Implement proposal insertion on critique emission
- Add DRAFT → PENDING transition logic
- Build proposal query API

### Phase 3B: Review UI (Week 2)
- Build review queue dashboard
- Implement proposal detail view
- Add accept/reject actions

### Phase 3C: Ledger & Doctrine Management (Week 3)
- Implement governance ledger writes
- Build doctrine version management
- Add rollback mechanism

### Phase 3D: Observability & Metrics (Week 4)
- Build governance dashboard
- Add proposal analytics
- Implement reviewer notifications

---

## SUCCESS CRITERIA

✅ **Zero auto-apply**: No code path bypasses human approval  
✅ **Full audit trail**: Every decision logged with timestamp, actor, rationale  
✅ **Reversibility**: Accepted patches can be rolled back  
✅ **Doctrine versioning**: All changes tracked with semantic versioning  
✅ **Human-in-loop**: UI enables informed decisions with full episode context

---

## NEXT STEPS

1. Review this architecture document
2. Approve Phase 3A implementation (Proposal Persistence)
3. Begin backend implementation in `velo-oracle-prime` repository
4. Build frontend UI in `velo_strategic` project

---

**This is the control layer that makes VÉLØ trustable at scale.**
