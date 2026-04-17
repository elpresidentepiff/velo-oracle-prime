# SHADOW RACING V13 SPECIFICATION

**Status:** Active  
**Mode:** Observe-Only  
**Date:** 2026-01-19

---

## OBJECTIVE

Run VÉLØ V13 engine on live race cards in observe-only mode to:
1. Generate real episodes with epistemic time separation
2. Execute all 4 critics (Leakage, Bias, Feature, Decision)
3. Persist proposals in DRAFT → PENDING pipeline
4. Build governance queue for human review
5. Collect real-world finding patterns to inform UI design

**No selection changes. No tuning. No learning. Just truth + evidence.**

---

## OPERATING CONSTRAINTS

### Constitutional Guarantees

- ✅ **No auto-apply** - All proposals end in PENDING state
- ✅ **No learning** - No model updates, no weight changes
- ✅ **No doctrine mutation** - No rule application in code yet
- ✅ **Read-only critics** - Zero state mutation
- ✅ **Epistemic time separation** - decisionTime ≠ createdAt

### Hard Gates

```python
# WRONG: Auto-apply proposals
if proposal.severity == "CRITICAL":
    apply_patch(proposal)  # ❌ VIOLATION

# CORRECT: All proposals to PENDING
if proposal.severity == "CRITICAL":
    mark_as_pending(proposal)  # ✅ COMPLIANT
    notify_reviewer(proposal)
```

---

## SHADOW RACING PIPELINE

### 1. Race Ingestion

```python
# Ingest today's race cards
races = ingest_races_for_date(datetime.now(UTC).date())

for race in races:
    # Create episode
    episode = create_episode(
        race_id=race.id,
        decision_time=race.off_time - timedelta(minutes=10),  # 10 min before off
        context={
            "venue": race.venue,
            "distance": race.distance,
            "going": race.going,
            "class": race.class_,
        }
    )
    
    # Write PRE_STATE artifact
    pre_state = {
        "runners": race.runners,
        "market": race.market_snapshot,
        "form": race.form_data,
    }
    write_artifact(episode.id, "PRE_STATE", pre_state)
```

### 2. Engine Execution

```python
# Run VÉLØ engine (no changes to existing logic)
inference = run_engine(episode)

# Write INFERENCE artifact
write_artifact(episode.id, "INFERENCE", inference)
```

### 3. Critic Execution

```python
# Run all 4 critics
critics = [
    LeakageDetectorCritic(),
    CognitiveBiasCritic(),
    FeatureExtractorCritic(),
    DecisionCritic(),
]

persistence = ProposalPersistence(db)

for critic in critics:
    critique = critic.critique(episode)
    
    # Persist proposals (DRAFT state)
    proposals = [
        {
            "severity": finding.severity,
            "finding_type": finding.finding_type,
            "description": finding.description,
            "proposed_change": finding.proposed_change,
        }
        for finding in critique.findings
    ]
    
    persistence.persist_proposals(
        episode_id=episode.id,
        critic_type=critic.critic_type,
        proposals=proposals
    )
```

### 4. Episode Finalization

```python
# After race completes, write outcome
outcome = {
    "winner": race.result.winner,
    "placed": race.result.placed,
    "sp": race.result.starting_prices,
}
write_artifact(episode.id, "OUTCOME", outcome)

# Mark episode as finalized
db.execute(
    "UPDATE episodes SET finalized = TRUE, finalized_at = ? WHERE id = ?",
    (datetime.now(UTC).isoformat(), episode.id)
)

# Transition proposals to PENDING
transitions = ProposalTransitions(db)
transitions.transition_to_pending(episode.id)
```

---

## DAILY REPORTING

### Metrics to Track

1. **Episodes Processed**
   - Total episodes created
   - Episodes finalized
   - Episodes pending finalization

2. **Proposals Created** (by critic + severity)
   - Leakage Detector: CRITICAL, HIGH, MEDIUM, LOW
   - Cognitive Bias: CRITICAL, HIGH, MEDIUM, LOW
   - Feature Extractor: CRITICAL, HIGH, MEDIUM, LOW
   - Decision Critic: CRITICAL, HIGH, MEDIUM, LOW

3. **Pending Queue Size**
   - Total proposals in PENDING state
   - Breakdown by critic
   - Breakdown by severity

4. **Top 10 Finding Types**
   - Most common finding types across all critics
   - Frequency count

5. **CRITICAL Leakage Events**
   - Any CRITICAL findings from Leakage Detector
   - Episode ID, description, proposed change

### Daily Report Format

```
=== SHADOW RACING V13 DAILY REPORT ===
Date: 2026-01-19

EPISODES:
- Processed: 47
- Finalized: 42
- Pending: 5

PROPOSALS CREATED:
- Leakage Detector: 12 (CRITICAL: 2, HIGH: 4, MEDIUM: 5, LOW: 1)
- Cognitive Bias: 18 (CRITICAL: 0, HIGH: 7, MEDIUM: 9, LOW: 2)
- Feature Extractor: 9 (CRITICAL: 1, HIGH: 3, MEDIUM: 4, LOW: 1)
- Decision Critic: 15 (CRITICAL: 0, HIGH: 5, MEDIUM: 8, LOW: 2)

PENDING QUEUE:
- Total: 54 proposals
- By Critic: Leakage (12), Bias (18), Feature (9), Decision (15)
- By Severity: CRITICAL (3), HIGH (19), MEDIUM (26), LOW (6)

TOP 10 FINDING TYPES:
1. ANCHORING_BIAS (12 occurrences)
2. FUTURE_MARKET_LEAKAGE (8 occurrences)
3. MISSING_FEATURE (7 occurrences)
4. OVERCONFIDENCE (6 occurrences)
5. NARRATIVE_DRIFT (5 occurrences)
6. RECENCY_BIAS (5 occurrences)
7. REDUNDANT_FEATURE (4 occurrences)
8. CONFIRMATION_BIAS (4 occurrences)
9. INCOHERENT_RATIONALE (3 occurrences)
10. FUTURE_OUTCOME_LEAKAGE (3 occurrences)

CRITICAL LEAKAGE EVENTS:
1. Episode: race_2026-01-19_R3
   Finding: Future market leakage detected
   Description: Market snapshot at 14:05 UTC was used, 5 minutes after decision time
   Proposed Change: Add temporal validation rule

2. Episode: race_2026-01-19_R7
   Finding: Future outcome leakage detected
   Description: Race result was available in pre-state artifact
   Proposed Change: Add outcome validation rule
```

---

## REVIEW CADENCE

### Twice Daily Review (Morning + Evening)

**Morning Review (09:00 UTC):**
- Review CRITICAL findings (always)
- Review HIGH findings (if repeated ≥ 3 episodes)
- Accept/reject via API

**Evening Review (18:00 UTC):**
- Review CRITICAL findings (always)
- Review HIGH findings (if repeated ≥ 3 episodes)
- Accept/reject via API

**MEDIUM/LOW findings:**
- Sit in queue until volume gives signal
- Review weekly or when pattern emerges

### Review Decision Criteria

**CRITICAL - Always Review:**
- Temporal leakage (future data contamination)
- Missing critical features
- Incoherent decision rationale

**HIGH - Review if Repeated ≥ 3 Episodes:**
- Cognitive biases (anchoring, confirmation, recency)
- Redundant features
- Narrative drift

**MEDIUM/LOW - Review Weekly:**
- Minor biases
- Low-impact feature issues
- Cosmetic rationale improvements

---

## IMPLEMENTATION

### Shadow Racing Runner

**File:** `src/v13/operations/shadow_racing_runner.py`

```python
import sqlite3
from datetime import datetime, UTC, timedelta
from typing import List

from ..episodes.constructor import create_episode, write_artifact, finalize_episode
from ..critics.leakage_detector import LeakageDetectorCritic
from ..critics.cognitive_bias import CognitiveBiasCritic
from ..critics.feature_extractor import FeatureExtractorCritic
from ..critics.decision_critic import DecisionCritic
from ..governance import ProposalPersistence, ProposalTransitions


class ShadowRacingRunner:
    """
    Shadow racing runner for V13 observe-only mode.
    
    Runs VÉLØ engine on live race cards, executes critics,
    persists proposals, and generates daily reports.
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self.persistence = ProposalPersistence(db_connection)
        self.transitions = ProposalTransitions(db_connection)
        self.critics = [
            LeakageDetectorCritic(),
            CognitiveBiasCritic(),
            FeatureExtractorCritic(),
            DecisionCritic(),
        ]
    
    def run_race(self, race_data: dict) -> str:
        """
        Run shadow racing for a single race.
        
        Args:
            race_data: Race data dict with runners, market, form, etc.
        
        Returns:
            Episode ID
        """
        # Create episode
        episode = create_episode(
            race_id=race_data["race_id"],
            decision_time=race_data["off_time"] - timedelta(minutes=10),
            context={
                "venue": race_data["venue"],
                "distance": race_data["distance"],
                "going": race_data["going"],
                "class": race_data.get("class"),
            }
        )
        
        # Write PRE_STATE artifact
        pre_state = {
            "runners": race_data["runners"],
            "market": race_data["market_snapshot"],
            "form": race_data["form_data"],
        }
        write_artifact(episode.id, "PRE_STATE", pre_state)
        
        # Run engine (placeholder - integrate actual engine)
        inference = self._run_engine(episode, pre_state)
        
        # Write INFERENCE artifact
        write_artifact(episode.id, "INFERENCE", inference)
        
        # Run critics
        for critic in self.critics:
            critique = critic.critique(episode)
            
            # Persist proposals
            proposals = [
                {
                    "severity": finding.severity,
                    "finding_type": finding.finding_type,
                    "description": finding.description,
                    "proposed_change": finding.proposed_change,
                }
                for finding in critique.findings
            ]
            
            self.persistence.persist_proposals(
                episode_id=episode.id,
                critic_type=critic.critic_type,
                proposals=proposals
            )
        
        return episode.id
    
    def finalize_race(self, episode_id: str, result: dict):
        """
        Finalize episode after race completes.
        
        Args:
            episode_id: Episode ID
            result: Race result dict with winner, placed, sp
        """
        # Write OUTCOME artifact
        outcome = {
            "winner": result["winner"],
            "placed": result["placed"],
            "sp": result["starting_prices"],
        }
        write_artifact(episode_id, "OUTCOME", outcome)
        
        # Mark episode as finalized
        finalize_episode(episode_id, outcome, self.db)
        
        # Transition proposals to PENDING
        self.transitions.transition_to_pending(episode_id)
    
    def _run_engine(self, episode, pre_state):
        """Placeholder for actual engine integration."""
        # TODO: Integrate actual VÉLØ engine
        return {
            "verdict": "PLACEHOLDER",
            "confidence": 0.0,
            "top_4": [],
        }
```

### Daily Metrics Collector

**File:** `src/v13/operations/daily_metrics.py`

```python
import sqlite3
from datetime import datetime, UTC, timedelta
from collections import Counter


class DailyMetricsCollector:
    """
    Collects and reports daily shadow racing metrics.
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def generate_report(self, date: datetime.date = None) -> str:
        """
        Generate daily report for shadow racing.
        
        Args:
            date: Date to report on (defaults to today)
        
        Returns:
            Formatted report string
        """
        if date is None:
            date = datetime.now(UTC).date()
        
        # Episodes
        episodes = self._get_episode_stats(date)
        
        # Proposals
        proposals = self._get_proposal_stats(date)
        
        # Pending queue
        pending = self._get_pending_queue_stats()
        
        # Top finding types
        top_findings = self._get_top_finding_types(date)
        
        # CRITICAL leakage events
        critical_leakage = self._get_critical_leakage_events(date)
        
        # Format report
        report = f"""
=== SHADOW RACING V13 DAILY REPORT ===
Date: {date}

EPISODES:
- Processed: {episodes['processed']}
- Finalized: {episodes['finalized']}
- Pending: {episodes['pending']}

PROPOSALS CREATED:
"""
        
        for critic, counts in proposals.items():
            report += f"- {critic}: {sum(counts.values())} ("
            report += ", ".join([f"{sev}: {count}" for sev, count in counts.items()])
            report += ")\n"
        
        report += f"""
PENDING QUEUE:
- Total: {pending['total']} proposals
- By Critic: {', '.join([f"{c} ({n})" for c, n in pending['by_critic'].items()])}
- By Severity: {', '.join([f"{s} ({n})" for s, n in pending['by_severity'].items()])}

TOP 10 FINDING TYPES:
"""
        
        for i, (finding_type, count) in enumerate(top_findings[:10], 1):
            report += f"{i}. {finding_type} ({count} occurrences)\n"
        
        if critical_leakage:
            report += "\nCRITICAL LEAKAGE EVENTS:\n"
            for i, event in enumerate(critical_leakage, 1):
                report += f"{i}. Episode: {event['episode_id']}\n"
                report += f"   Finding: {event['finding_type']}\n"
                report += f"   Description: {event['description']}\n"
                report += f"   Proposed Change: {event['proposed_change']}\n\n"
        
        return report
    
    def _get_episode_stats(self, date):
        """Get episode statistics for date."""
        # TODO: Implement actual queries
        return {
            "processed": 0,
            "finalized": 0,
            "pending": 0,
        }
    
    def _get_proposal_stats(self, date):
        """Get proposal statistics by critic and severity."""
        # TODO: Implement actual queries
        return {}
    
    def _get_pending_queue_stats(self):
        """Get pending queue statistics."""
        # TODO: Implement actual queries
        return {
            "total": 0,
            "by_critic": {},
            "by_severity": {},
        }
    
    def _get_top_finding_types(self, date):
        """Get top finding types for date."""
        # TODO: Implement actual queries
        return []
    
    def _get_critical_leakage_events(self, date):
        """Get CRITICAL leakage events for date."""
        # TODO: Implement actual queries
        return []
```

---

## SUCCESS CRITERIA

✅ Shadow racing runs automatically on today's cards  
✅ Episodes created with epistemic time separation  
✅ All 4 critics execute on every episode  
✅ Proposals persist in DRAFT → PENDING pipeline  
✅ Daily reports generated with required metrics  
✅ CRITICAL leakage events flagged immediately  
✅ Review cadence established (twice daily)  
✅ Zero auto-apply, zero learning, zero doctrine mutation

---

## NEXT STEPS

1. Implement shadow racing runner
2. Implement daily metrics collector
3. Set up automated daily reporting
4. Start shadow racing on today's cards
5. Establish review cadence (morning + evening)
6. Build Phase 3B Review UI in parallel

---

**Shadow racing gives you momentum + truth.**

**Build UI on real data, not assumptions.**
