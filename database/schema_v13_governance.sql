-- VÉLØ V13 Governance Layer Schema
-- Phase 3A: Proposal Persistence + Review Gate
-- Date: 2026-01-19
-- Status: Implementation

-- =============================================================================
-- EPISODES (from V13 Constitutional Layer)
-- =============================================================================

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    decision_time TIMESTAMP NOT NULL,  -- Epistemic time (knowledge cutoff)
    created_at TIMESTAMP NOT NULL,     -- Execution time (artifact write)
    context_hash TEXT NOT NULL,        -- For replay validation
    finalized BOOLEAN DEFAULT FALSE,
    finalized_at TIMESTAMP,
    metadata JSON
);

CREATE INDEX idx_episodes_decision_time ON episodes(decision_time);
CREATE INDEX idx_episodes_finalized ON episodes(finalized);

-- =============================================================================
-- EPISODE ARTIFACTS (sparse storage)
-- =============================================================================

CREATE TABLE IF NOT EXISTS episode_artifacts (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,  -- PRE_STATE, INFERENCE, OUTCOME
    content JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX idx_artifacts_episode ON episode_artifacts(episode_id);
CREATE INDEX idx_artifacts_type ON episode_artifacts(artifact_type);

-- =============================================================================
-- PATCH PROPOSALS (from critics)
-- =============================================================================

CREATE TABLE IF NOT EXISTS patch_proposals (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    critic_type TEXT NOT NULL,  -- LEAKAGE, BIAS, FEATURE, DECISION
    severity TEXT NOT NULL,     -- CRITICAL, HIGH, MEDIUM, LOW
    finding_type TEXT NOT NULL,
    description TEXT NOT NULL,
    proposed_change JSON NOT NULL,
    fingerprint TEXT NOT NULL,  -- SHA256 hash for deduplication
    status TEXT NOT NULL,       -- DRAFT, PENDING, ACCEPTED, REJECTED, ROLLED_BACK
    created_at TIMESTAMP NOT NULL,
    reviewed_at TIMESTAMP,
    reviewer_id TEXT,
    review_rationale TEXT,
    doctrine_version_before TEXT,
    doctrine_version_after TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX idx_proposals_episode ON patch_proposals(episode_id);
CREATE INDEX idx_proposals_fingerprint ON patch_proposals(fingerprint);
CREATE INDEX idx_proposals_status ON patch_proposals(status);
CREATE INDEX idx_proposals_critic ON patch_proposals(critic_type);
CREATE INDEX idx_proposals_severity ON patch_proposals(severity);

-- =============================================================================
-- PROPOSAL-EPISODE JUNCTION (many-to-many)
-- =============================================================================

CREATE TABLE IF NOT EXISTS proposal_episodes (
    proposal_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    PRIMARY KEY (proposal_id, episode_id),
    FOREIGN KEY (proposal_id) REFERENCES patch_proposals(id),
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX idx_proposal_episodes_proposal ON proposal_episodes(proposal_id);
CREATE INDEX idx_proposal_episodes_episode ON proposal_episodes(episode_id);

-- =============================================================================
-- GOVERNANCE LEDGER (immutable audit log)
-- =============================================================================

CREATE TABLE IF NOT EXISTS governance_ledger (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- ACCEPT, REJECT, ROLLBACK
    actor TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    rationale TEXT NOT NULL,
    doctrine_version_snapshot TEXT NOT NULL,
    episode_count_at_decision INTEGER NOT NULL,
    metadata JSON,
    FOREIGN KEY (proposal_id) REFERENCES patch_proposals(id)
);

CREATE INDEX idx_ledger_proposal ON governance_ledger(proposal_id);
CREATE INDEX idx_ledger_action ON governance_ledger(action);
CREATE INDEX idx_ledger_timestamp ON governance_ledger(timestamp);

-- =============================================================================
-- DOCTRINE VERSIONS (semantic versioning)
-- =============================================================================

CREATE TABLE IF NOT EXISTS doctrine_versions (
    version TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    created_by TEXT NOT NULL,
    description TEXT NOT NULL,
    rules_snapshot JSON NOT NULL,
    parent_version TEXT,
    active BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (parent_version) REFERENCES doctrine_versions(version)
);

CREATE INDEX idx_doctrine_active ON doctrine_versions(active);
CREATE INDEX idx_doctrine_created ON doctrine_versions(created_at);

-- =============================================================================
-- INITIALIZE V13 BASELINE
-- =============================================================================

INSERT OR IGNORE INTO doctrine_versions (
    version,
    created_at,
    created_by,
    description,
    rules_snapshot,
    parent_version,
    active
) VALUES (
    '13.0.0',
    CURRENT_TIMESTAMP,
    'system',
    'V13 Constitutional Baseline - Episodic memory + read-only critics + doctrine guards',
    '{}',
    NULL,
    TRUE
);
