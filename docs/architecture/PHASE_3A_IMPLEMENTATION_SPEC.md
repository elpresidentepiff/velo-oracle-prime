# PHASE 3A IMPLEMENTATION SPECIFICATION

**Branch:** `feature/phase-3a-governance`  
**Target:** Proposal Persistence + Review Gate (Minimal Viable Governance)  
**Status:** In Progress  
**Date:** 2026-01-19

---

## OBJECTIVE

Enable controlled doctrine evolution by persisting critic proposals, transitioning them to review state, and providing a minimal API for human approval/rejection. No UI, no auto-apply, no doctrine mutation without explicit human action.

---

## SCOPE (EXACT)

### ✅ IN SCOPE

1. **Proposal Fingerprinting**: Deduplicate identical proposals across episodes
2. **Proposal Persistence**: Write proposals to `patch_proposals` table in DRAFT state
3. **State Transition**: Auto-promote DRAFT → PENDING when episode is finalized
4. **Governance API**: Minimal read/write endpoints (list, get, accept, reject)
5. **Ledger Integration**: Write accept/reject decisions to `governance_ledger`
6. **Doctrine Versioning**: Bump version on acceptance (no actual rule application yet)

### ❌ OUT OF SCOPE (DEFERRED)

- Frontend UI (Phase 3B)
- Doctrine rule application logic (Phase 3C)
- Rollback mechanism (Phase 3C)
- Metrics dashboard (Phase 3D)
- Batch operations (Phase 3D)
- Multi-reviewer voting (Phase 3D)

---

## DELIVERABLES

### 1. Proposal Fingerprinting

**File:** `src/v13/governance/fingerprint.py`

**Purpose:** Generate deterministic hash for proposals to detect duplicates

**Implementation:**

```python
import hashlib
import json
from typing import Any, Dict

def fingerprint_proposal(
    critic_type: str,
    finding_type: str,
    proposed_change: Dict[str, Any],
) -> str:
    """
    Generate deterministic fingerprint for proposal deduplication.
    
    Fingerprint includes:
    - critic_type (e.g., "LEAKAGE")
    - finding_type (e.g., "FUTURE_MARKET_LEAKAGE")
    - proposed_change (normalized JSON)
    
    Does NOT include:
    - episode_id (same proposal can appear in multiple episodes)
    - timestamp (temporal variance irrelevant)
    - description (human text may vary)
    """
    payload = {
        "critic_type": critic_type,
        "finding_type": finding_type,
        "proposed_change": proposed_change,
    }
    
    # Normalize JSON (sorted keys, no whitespace)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    
    # SHA256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**Test Cases:**

```python
def test_fingerprint_identical_proposals():
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    assert fp1 == fp2

def test_fingerprint_different_episodes():
    # Same proposal in different episodes should have same fingerprint
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    assert fp1 == fp2

def test_fingerprint_different_changes():
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "reject_future"})
    assert fp1 != fp2
```

---

### 2. Proposal Persistence Layer

**File:** `src/v13/governance/persistence.py`

**Purpose:** Write proposals to database in DRAFT state, handle deduplication

**Implementation:**

```python
from datetime import datetime, UTC
from typing import List, Optional
from uuid import uuid4

from .fingerprint import fingerprint_proposal
from ..episodes.schema import Episode
from ..critics.schema import Critique, PatchProposal

def persist_proposals(
    critique: Critique,
    episode: Episode,
    db_connection,
) -> List[str]:
    """
    Persist proposals from critique to database.
    
    Returns list of proposal IDs (new or existing).
    """
    proposal_ids = []
    
    for proposal in critique.proposals:
        # Generate fingerprint
        fp = fingerprint_proposal(
            critic_type=critique.critic_type,
            finding_type=proposal.finding_type,
            proposed_change=proposal.change,
        )
        
        # Check if proposal already exists (any status)
        existing = db_connection.execute(
            "SELECT id, status FROM patch_proposals WHERE fingerprint = ?",
            (fp,)
        ).fetchone()
        
        if existing:
            # Link existing proposal to this episode
            db_connection.execute(
                "INSERT INTO proposal_episodes (proposal_id, episode_id) VALUES (?, ?)",
                (existing["id"], episode.id)
            )
            proposal_ids.append(existing["id"])
            continue
        
        # Create new proposal
        proposal_id = str(uuid4())
        db_connection.execute(
            """
            INSERT INTO patch_proposals (
                id, episode_id, critic_type, severity, finding_type,
                description, proposed_change, fingerprint, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                episode.id,
                critique.critic_type,
                proposal.severity,
                proposal.finding_type,
                proposal.description,
                proposal.change,  # JSON
                fp,
                "DRAFT",
                datetime.now(UTC),
            )
        )
        
        proposal_ids.append(proposal_id)
    
    return proposal_ids
```

**Schema Addition:**

```sql
-- Add fingerprint column to patch_proposals
ALTER TABLE patch_proposals ADD COLUMN fingerprint TEXT NOT NULL;
CREATE INDEX idx_patch_proposals_fingerprint ON patch_proposals(fingerprint);

-- Add junction table for many-to-many (proposal can appear in multiple episodes)
CREATE TABLE proposal_episodes (
    proposal_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    PRIMARY KEY (proposal_id, episode_id),
    FOREIGN KEY (proposal_id) REFERENCES patch_proposals(id),
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);
```

---

### 3. DRAFT → PENDING Transition

**File:** `src/v13/governance/transitions.py`

**Purpose:** Auto-promote proposals when episode is finalized

**Implementation:**

```python
from datetime import datetime, UTC

def transition_proposals_to_pending(episode_id: str, db_connection):
    """
    Transition all DRAFT proposals for an episode to PENDING.
    
    Called when episode is finalized (outcome recorded).
    """
    db_connection.execute(
        """
        UPDATE patch_proposals
        SET status = 'PENDING'
        WHERE episode_id = ? AND status = 'DRAFT'
        """,
        (episode_id,)
    )
    
    # Also transition linked proposals (from proposal_episodes junction)
    db_connection.execute(
        """
        UPDATE patch_proposals
        SET status = 'PENDING'
        WHERE id IN (
            SELECT proposal_id FROM proposal_episodes WHERE episode_id = ?
        ) AND status = 'DRAFT'
        """,
        (episode_id,)
    )
```

**Integration Point:**

```python
# In episode finalization logic (src/v13/episodes/constructor.py)
def finalize_episode(episode: Episode, outcome: Dict, db_connection):
    # Write outcome artifact
    write_artifact(episode.id, "OUTCOME", outcome)
    
    # Mark episode as finalized
    db_connection.execute(
        "UPDATE episodes SET finalized = TRUE, finalized_at = ? WHERE id = ?",
        (datetime.now(UTC), episode.id)
    )
    
    # Transition proposals to PENDING
    from ..governance.transitions import transition_proposals_to_pending
    transition_proposals_to_pending(episode.id, db_connection)
```

---

### 4. Minimal Governance API

**File:** `src/v13/governance/api.py`

**Purpose:** Expose read/write endpoints for proposal management

**Endpoints:**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/governance")

class ProposalListResponse(BaseModel):
    id: str
    episode_id: str
    critic_type: str
    severity: str
    finding_type: str
    description: str
    status: str
    created_at: str

class ProposalDetailResponse(BaseModel):
    id: str
    episode_id: str
    critic_type: str
    severity: str
    finding_type: str
    description: str
    proposed_change: dict
    status: str
    created_at: str
    reviewed_at: Optional[str]
    reviewer_id: Optional[str]
    review_rationale: Optional[str]
    similar_proposals: List[str]  # List of episode IDs with same fingerprint

class ReviewRequest(BaseModel):
    rationale: str
    reviewer_id: str

@router.get("/proposals", response_model=List[ProposalListResponse])
def list_proposals(status: Optional[str] = None):
    """List proposals, optionally filtered by status."""
    query = "SELECT * FROM patch_proposals"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    
    results = db.execute(query, params).fetchall()
    return [ProposalListResponse(**row) for row in results]

@router.get("/proposals/{proposal_id}", response_model=ProposalDetailResponse)
def get_proposal(proposal_id: str):
    """Get proposal details."""
    result = db.execute(
        "SELECT * FROM patch_proposals WHERE id = ?",
        (proposal_id,)
    ).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Find similar proposals (same fingerprint)
    similar = db.execute(
        """
        SELECT DISTINCT pe.episode_id
        FROM proposal_episodes pe
        WHERE pe.proposal_id IN (
            SELECT id FROM patch_proposals WHERE fingerprint = ?
        ) AND pe.episode_id != ?
        """,
        (result["fingerprint"], result["episode_id"])
    ).fetchall()
    
    return ProposalDetailResponse(
        **result,
        similar_proposals=[row["episode_id"] for row in similar]
    )

@router.post("/proposals/{proposal_id}/accept")
def accept_proposal(proposal_id: str, request: ReviewRequest):
    """Accept a proposal and bump doctrine version."""
    from .ledger import write_ledger_entry
    from .doctrine import bump_doctrine_version
    
    # Verify proposal exists and is PENDING
    proposal = db.execute(
        "SELECT * FROM patch_proposals WHERE id = ?",
        (proposal_id,)
    ).fetchone()
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Proposal is {proposal['status']}, not PENDING")
    
    # Get current doctrine version
    current_version = get_active_doctrine_version()
    
    # Bump doctrine version (no actual rule application yet)
    new_version = bump_doctrine_version(
        current_version=current_version,
        change_type="MINOR",  # New rule added
        description=f"Accepted proposal {proposal_id}: {proposal['finding_type']}",
        created_by=request.reviewer_id,
    )
    
    # Update proposal status
    db.execute(
        """
        UPDATE patch_proposals
        SET status = 'ACCEPTED',
            reviewed_at = ?,
            reviewer_id = ?,
            review_rationale = ?,
            doctrine_version_after = ?
        WHERE id = ?
        """,
        (datetime.now(UTC), request.reviewer_id, request.rationale, new_version, proposal_id)
    )
    
    # Write ledger entry
    write_ledger_entry(
        proposal_id=proposal_id,
        action="ACCEPT",
        actor=request.reviewer_id,
        rationale=request.rationale,
        doctrine_version=new_version,
    )
    
    return {"status": "accepted", "doctrine_version": new_version}

@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, request: ReviewRequest):
    """Reject a proposal."""
    from .ledger import write_ledger_entry
    
    # Verify proposal exists and is PENDING
    proposal = db.execute(
        "SELECT * FROM patch_proposals WHERE id = ?",
        (proposal_id,)
    ).fetchone()
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Proposal is {proposal['status']}, not PENDING")
    
    # Update proposal status
    db.execute(
        """
        UPDATE patch_proposals
        SET status = 'REJECTED',
            reviewed_at = ?,
            reviewer_id = ?,
            review_rationale = ?
        WHERE id = ?
        """,
        (datetime.now(UTC), request.reviewer_id, request.rationale, proposal_id)
    )
    
    # Write ledger entry
    current_version = get_active_doctrine_version()
    write_ledger_entry(
        proposal_id=proposal_id,
        action="REJECT",
        actor=request.reviewer_id,
        rationale=request.rationale,
        doctrine_version=current_version,
    )
    
    return {"status": "rejected"}
```

---

### 5. Governance Ledger Integration

**File:** `src/v13/governance/ledger.py`

**Purpose:** Write immutable audit log for all governance decisions

**Implementation:**

```python
from datetime import datetime, UTC
from uuid import uuid4

def write_ledger_entry(
    proposal_id: str,
    action: str,  # ACCEPT, REJECT, ROLLBACK
    actor: str,
    rationale: str,
    doctrine_version: str,
    metadata: dict = None,
):
    """
    Write governance decision to immutable ledger.
    """
    # Get episode count at decision time
    episode_count = db.execute(
        "SELECT COUNT(*) as count FROM episodes WHERE finalized = TRUE"
    ).fetchone()["count"]
    
    ledger_id = str(uuid4())
    db.execute(
        """
        INSERT INTO governance_ledger (
            id, proposal_id, action, actor, timestamp,
            rationale, doctrine_version_snapshot, episode_count_at_decision, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ledger_id,
            proposal_id,
            action,
            actor,
            datetime.now(UTC),
            rationale,
            doctrine_version,
            episode_count,
            metadata or {},
        )
    )
    
    return ledger_id
```

---

### 6. Doctrine Version Management

**File:** `src/v13/governance/doctrine.py`

**Purpose:** Bump doctrine version on proposal acceptance

**Implementation:**

```python
from datetime import datetime, UTC

def get_active_doctrine_version() -> str:
    """Get currently active doctrine version."""
    result = db.execute(
        "SELECT version FROM doctrine_versions WHERE active = TRUE"
    ).fetchone()
    
    if not result:
        # Initialize with V13 baseline
        initialize_doctrine_version("13.0.0", "V13 Constitutional Baseline")
        return "13.0.0"
    
    return result["version"]

def bump_doctrine_version(
    current_version: str,
    change_type: str,  # MAJOR, MINOR, PATCH
    description: str,
    created_by: str,
) -> str:
    """
    Bump doctrine version and create new version record.
    
    Does NOT apply actual rule changes (deferred to Phase 3C).
    """
    # Parse semantic version
    major, minor, patch = map(int, current_version.split("."))
    
    if change_type == "MAJOR":
        new_version = f"{major + 1}.0.0"
    elif change_type == "MINOR":
        new_version = f"{major}.{minor + 1}.0"
    elif change_type == "PATCH":
        new_version = f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid change_type: {change_type}")
    
    # Deactivate current version
    db.execute(
        "UPDATE doctrine_versions SET active = FALSE WHERE version = ?",
        (current_version,)
    )
    
    # Create new version
    db.execute(
        """
        INSERT INTO doctrine_versions (
            version, created_at, created_by, description,
            rules_snapshot, parent_version, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_version,
            datetime.now(UTC),
            created_by,
            description,
            {},  # Empty rules snapshot (no actual rules yet)
            current_version,
            True,
        )
    )
    
    return new_version

def initialize_doctrine_version(version: str, description: str):
    """Initialize doctrine version (first-time setup)."""
    db.execute(
        """
        INSERT INTO doctrine_versions (
            version, created_at, created_by, description,
            rules_snapshot, parent_version, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version,
            datetime.now(UTC),
            "system",
            description,
            {},
            None,
            True,
        )
    )
```

---

## INTEGRATION POINTS

### Episode Finalization Hook

```python
# In src/v13/episodes/constructor.py
def finalize_episode(episode: Episode, outcome: Dict):
    # Write outcome artifact
    write_artifact(episode.id, "OUTCOME", outcome)
    
    # Mark episode as finalized
    db.execute(
        "UPDATE episodes SET finalized = TRUE, finalized_at = ? WHERE id = ?",
        (datetime.now(UTC), episode.id)
    )
    
    # Transition proposals to PENDING
    from ..governance.transitions import transition_proposals_to_pending
    transition_proposals_to_pending(episode.id, db)
```

### Critic Execution Hook

```python
# In src/v13/critics/runner.py (or wherever critics are executed)
def run_critics(episode: Episode) -> List[Critique]:
    critics = [
        LeakageDetectorCritic(),
        CognitiveBiasCritic(),
        FeatureExtractorCritic(),
        DecisionCritic(),
    ]
    
    critiques = []
    for critic in critics:
        critique = critic.critique(episode)
        critiques.append(critique)
        
        # Persist proposals
        from ..governance.persistence import persist_proposals
        persist_proposals(critique, episode, db)
    
    return critiques
```

---

## TESTING STRATEGY

### Unit Tests

```python
# test_fingerprint.py
def test_fingerprint_deduplication()
def test_fingerprint_normalization()

# test_persistence.py
def test_persist_new_proposal()
def test_persist_duplicate_proposal()
def test_proposal_episode_linking()

# test_transitions.py
def test_draft_to_pending_transition()
def test_transition_only_affects_finalized_episodes()

# test_api.py
def test_list_proposals()
def test_get_proposal_details()
def test_accept_proposal()
def test_reject_proposal()
def test_accept_non_pending_proposal_fails()

# test_ledger.py
def test_write_ledger_entry()
def test_ledger_immutability()

# test_doctrine.py
def test_bump_minor_version()
def test_bump_major_version()
def test_only_one_active_version()
```

### Integration Test (Shadow Racing)

```python
def test_shadow_racing_full_flow():
    # 1. Ingest race data
    race = ingest_race("2026-01-19_R1")
    
    # 2. Create episode
    episode = create_episode(race)
    
    # 3. Run critics
    critiques = run_critics(episode)
    
    # 4. Verify proposals persisted in DRAFT
    proposals = db.execute(
        "SELECT * FROM patch_proposals WHERE episode_id = ? AND status = 'DRAFT'",
        (episode.id,)
    ).fetchall()
    assert len(proposals) > 0
    
    # 5. Finalize episode
    finalize_episode(episode, outcome={"winner": "Horse #3"})
    
    # 6. Verify proposals transitioned to PENDING
    proposals = db.execute(
        "SELECT * FROM patch_proposals WHERE episode_id = ? AND status = 'PENDING'",
        (episode.id,)
    ).fetchall()
    assert len(proposals) > 0
    
    # 7. Accept one proposal via API
    response = client.post(
        f"/api/governance/proposals/{proposals[0]['id']}/accept",
        json={"rationale": "Test acceptance", "reviewer_id": "test_user"}
    )
    assert response.status_code == 200
    
    # 8. Verify ledger entry
    ledger = db.execute(
        "SELECT * FROM governance_ledger WHERE proposal_id = ?",
        (proposals[0]['id'],)
    ).fetchone()
    assert ledger["action"] == "ACCEPT"
    
    # 9. Verify doctrine version bumped
    version = get_active_doctrine_version()
    assert version == "13.1.0"  # Assuming started at 13.0.0
```

---

## SUCCESS CRITERIA

✅ Proposals persist to database in DRAFT state when critics run  
✅ Duplicate proposals (same fingerprint) are linked, not duplicated  
✅ Proposals transition to PENDING when episode is finalized  
✅ API endpoints (list, get, accept, reject) are functional  
✅ Accept/reject actions write to governance ledger  
✅ Doctrine version bumps on acceptance (no rule application yet)  
✅ Shadow racing protocol works end-to-end (observe-only)  
✅ Zero auto-apply code paths exist

---

## DELIVERABLE CHECKLIST

- [ ] `src/v13/governance/fingerprint.py` - Proposal fingerprinting
- [ ] `src/v13/governance/persistence.py` - Proposal persistence layer
- [ ] `src/v13/governance/transitions.py` - DRAFT → PENDING transition
- [ ] `src/v13/governance/api.py` - Governance API endpoints
- [ ] `src/v13/governance/ledger.py` - Ledger write operations
- [ ] `src/v13/governance/doctrine.py` - Doctrine version management
- [ ] Schema migration (fingerprint column, proposal_episodes table)
- [ ] Integration hooks (episode finalization, critic execution)
- [ ] Unit tests (6 test files)
- [ ] Integration test (shadow racing full flow)
- [ ] Documentation update (README, API docs)

---

## NEXT STEPS AFTER PHASE 3A

**Phase 3B:** Build frontend UI for proposal review  
**Phase 3C:** Implement actual doctrine rule application + rollback  
**Phase 3D:** Add metrics, analytics, batch operations

---

**Phase 3A is the foundation. Everything else builds on this.**
