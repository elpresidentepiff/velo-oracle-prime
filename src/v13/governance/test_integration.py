"""
Integration tests for Phase 3A Governance Pipeline.

Tests the full flow:
1. Persist proposals (DRAFT)
2. Transition to PENDING (episode finalization)
3. Accept/reject proposals
4. Ledger writes
5. Doctrine version bumps
"""

import sqlite3
import tempfile
import os
from datetime import datetime, UTC

from .api import GovernanceAPI


def setup_test_db():
    """Create temporary database with V13 governance schema."""
    # Create temp database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    
    # Load schema
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "../../../database/schema_v13_governance.sql"
    )
    
    with open(schema_path, "r") as f:
        schema = f.read()
    
    conn.executescript(schema)
    conn.commit()
    
    return conn, path


def test_full_governance_flow():
    """Test complete governance flow from proposal to acceptance."""
    conn, db_path = setup_test_db()
    
    try:
        api = GovernanceAPI(conn)
        
        # 1. Create episode
        episode_id = "test_episode_001"
        conn.execute(
            """
            INSERT INTO episodes (id, decision_time, created_at, context_hash, finalized)
            VALUES (?, ?, ?, ?, ?)
            """,
            (episode_id, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), "test_hash", False)
        )
        conn.commit()
        
        # 2. Persist proposals (DRAFT)
        proposals = [
            {
                "severity": "CRITICAL",
                "finding_type": "FUTURE_MARKET_LEAKAGE",
                "description": "Market snapshot at 12:05 UTC was used, 5 minutes after decision time",
                "proposed_change": {
                    "rule_type": "temporal_validation",
                    "condition": "market_snapshot.timestamp <= decision_time",
                    "action": "reject_snapshot"
                }
            },
            {
                "severity": "MEDIUM",
                "finding_type": "ANCHORING_BIAS",
                "description": "Over-weighted favorite by 15%",
                "proposed_change": {
                    "rule_type": "confidence_calibration",
                    "adjustment": -0.15
                }
            }
        ]
        
        proposal_ids = api.persistence.persist_proposals(
            episode_id=episode_id,
            critic_type="LEAKAGE",
            proposals=proposals
        )
        
        print(f"✅ Step 1: Persisted {len(proposal_ids)} proposals in DRAFT state")
        
        # 3. Verify proposals are DRAFT
        draft_proposals = api.list_proposals(status="DRAFT")
        assert len(draft_proposals) == 2, f"Expected 2 DRAFT proposals, got {len(draft_proposals)}"
        print(f"✅ Step 2: Verified {len(draft_proposals)} proposals in DRAFT state")
        
        # 4. Finalize episode (transition to PENDING)
        conn.execute(
            "UPDATE episodes SET finalized = TRUE, finalized_at = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), episode_id)
        )
        conn.commit()
        
        api.transitions.transition_to_pending(episode_id)
        
        # 5. Verify proposals are PENDING
        pending_proposals = api.list_proposals(status="PENDING")
        assert len(pending_proposals) == 2, f"Expected 2 PENDING proposals, got {len(pending_proposals)}"
        print(f"✅ Step 3: Transitioned {len(pending_proposals)} proposals to PENDING state")
        
        # 6. Accept first proposal
        result = api.accept_proposal(
            proposal_id=proposal_ids[0],
            reviewer_id="test_reviewer",
            rationale="Confirmed via replay: temporal leakage detected in 3 episodes",
            metadata={"affected_episodes": ["ep1", "ep2", "ep3"]}
        )
        
        assert result["status"] == "accepted"
        assert result["doctrine_version"] == "13.1.0"  # Minor bump
        print(f"✅ Step 4: Accepted proposal, doctrine bumped to {result['doctrine_version']}")
        
        # 7. Reject second proposal
        result = api.reject_proposal(
            proposal_id=proposal_ids[1],
            reviewer_id="test_reviewer",
            rationale="Need more data before adjusting calibration"
        )
        
        assert result["status"] == "rejected"
        print(f"✅ Step 5: Rejected proposal")
        
        # 8. Verify ledger entries
        ledger = api.get_ledger()
        assert len(ledger) == 2, f"Expected 2 ledger entries, got {len(ledger)}"
        assert ledger[0]["action"] in ["ACCEPT", "REJECT"]
        assert ledger[1]["action"] in ["ACCEPT", "REJECT"]
        print(f"✅ Step 6: Verified {len(ledger)} ledger entries")
        
        # 9. Verify doctrine version
        versions = api.get_doctrine_versions()
        assert len(versions) == 2, f"Expected 2 versions (13.0.0, 13.1.0), got {len(versions)}"
        assert versions[0]["version"] == "13.1.0"
        assert versions[0]["active"] == True
        print(f"✅ Step 7: Verified doctrine version history")
        
        # 10. Verify stats
        stats = api.get_stats()
        assert stats["proposals_accepted"] == 1
        assert stats["proposals_rejected"] == 1
        assert stats["proposals_pending"] == 0
        assert stats["doctrine_version"] == "13.1.0"
        assert stats["acceptance_rate"] == 0.5  # 1 accepted / 2 total
        print(f"✅ Step 8: Verified governance stats")
        
        print("\n🎉 All integration tests passed!")
        
    finally:
        conn.close()
        os.unlink(db_path)


def test_deduplication():
    """Test proposal deduplication via fingerprinting."""
    conn, db_path = setup_test_db()
    
    try:
        api = GovernanceAPI(conn)
        
        # Create two episodes
        for i in range(2):
            episode_id = f"test_episode_{i:03d}"
            conn.execute(
                """
                INSERT INTO episodes (id, decision_time, created_at, context_hash, finalized)
                VALUES (?, ?, ?, ?, ?)
                """,
                (episode_id, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), f"hash_{i}", False)
            )
        conn.commit()
        
        # Persist identical proposal in both episodes
        identical_proposal = {
            "severity": "CRITICAL",
            "finding_type": "FUTURE_MARKET_LEAKAGE",
            "description": "Same issue",
            "proposed_change": {"rule": "validate_time"}
        }
        
        ids_1 = api.persistence.persist_proposals(
            episode_id="test_episode_000",
            critic_type="LEAKAGE",
            proposals=[identical_proposal]
        )
        
        ids_2 = api.persistence.persist_proposals(
            episode_id="test_episode_001",
            critic_type="LEAKAGE",
            proposals=[identical_proposal]
        )
        
        # Should return same proposal ID (deduplicated)
        assert ids_1[0] == ids_2[0], "Identical proposals should be deduplicated"
        
        # Verify only one proposal exists
        all_proposals = api.list_proposals()
        assert len(all_proposals) == 1, f"Expected 1 proposal (deduplicated), got {len(all_proposals)}"
        
        # Verify linked to both episodes
        proposal = api.get_proposal(ids_1[0])
        similar = proposal["similar_episodes"]
        assert len(similar) >= 1, "Proposal should be linked to multiple episodes"
        
        print("✅ Deduplication test passed")
        
    finally:
        conn.close()
        os.unlink(db_path)


if __name__ == "__main__":
    print("Running Phase 3A Integration Tests...\n")
    test_full_governance_flow()
    print()
    test_deduplication()
    print("\n✅ All tests passed!")
