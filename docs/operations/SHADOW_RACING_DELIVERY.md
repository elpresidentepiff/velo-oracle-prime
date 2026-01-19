# SHADOW RACING V13 DELIVERY SUMMARY

**Status:** ✅ COMPLETE - CLI/Logs Only  
**Date:** 2026-01-19  
**Commit:** `8f98278`  
**Branch:** `feature/v10-launch`

---

## WHAT WAS BUILT

### Core Modules (3 files)

1. **Shadow Racing Runner** (`src/v13/operations/shadow_racing_runner.py`)
   - Episode creation with epistemic time separation
   - Artifact storage (PRE_STATE, INFERENCE, OUTCOME)
   - Critic execution (placeholder - 4 critics)
   - Proposal persistence (DRAFT → PENDING pipeline)
   - Episode finalization

2. **Daily Metrics Collector** (`src/v13/operations/daily_metrics.py`)
   - Episodes processed (processed, finalized, pending)
   - Proposals by critic + severity
   - Pending queue stats (total, by critic, by severity)
   - Top 10 finding types
   - CRITICAL leakage events
   - Summary stats (acceptance rate, doctrine version)

3. **CLI Tool** (`src/v13/operations/cli.py`)
   - `run-race` - Run shadow racing for a race
   - `finalize` - Finalize episode with race result
   - `report` - Generate daily report
   - `stats` - Show summary statistics

### Test Data (2 files)

- `test_data/sample_race.json` - Sample race data
- `test_data/sample_result.json` - Sample race result

### Documentation (2 files)

- `docs/operations/SHADOW_RACING_V13_SPEC.md` - Full specification (copyable)
- `docs/operations/SHADOW_RACING_DELIVERY.md` - This file

---

## CONSTITUTIONAL GUARANTEES

✅ **No auto-apply** - All proposals end in PENDING state  
✅ **No learning** - No model updates, no weight changes  
✅ **No doctrine mutation** - No rule application in code yet  
✅ **Read-only critics** - Zero state mutation  
✅ **Epistemic time separation** - decisionTime ≠ createdAt

---

## INTEGRATION TESTS

```
✅ Shadow racing complete
   Episode ID: race_2026-01-19_R1
   Decision Time: 2026-01-19T14:30:00+00:00
   Venue: Kempton

✅ Episode finalized: race_2026-01-19_R1
   Winner: runner_2
   Placed: runner_2, runner_1, runner_3

✅ Daily report generated
   Episodes: 1 processed, 1 finalized, 0 pending
   Proposals: 4 total (1 CRITICAL, 1 HIGH, 1 MEDIUM, 1 LOW)
   Pending queue: 4 proposals

✅ Summary stats
   Total Episodes: 1
   Total Proposals: 4
   Pending Proposals: 4
   Doctrine Version: 13.0.0
```

---

## USAGE

### Run Shadow Racing for a Race

```bash
python -m src.v13.operations.cli run-race --race-file race_data.json
```

**Race data format:**
```json
{
  "race_id": "R1",
  "off_time": "2026-01-19T14:30:00+00:00",
  "venue": "Kempton",
  "distance": 1600,
  "going": "Standard",
  "class_": 4,
  "runners": [...],
  "market_snapshot": {...},
  "form_data": {...}
}
```

### Finalize Episode with Race Result

```bash
python -m src.v13.operations.cli finalize \
  --episode-id race_2026-01-19_R1 \
  --result-file result.json
```

**Result data format:**
```json
{
  "winner": "runner_2",
  "placed": ["runner_2", "runner_1", "runner_3"],
  "starting_prices": {
    "runner_1": 2.8,
    "runner_2": 2.9,
    "runner_3": 4.2
  }
}
```

### Generate Daily Report

```bash
# Today's report
python -m src.v13.operations.cli report

# Specific date
python -m src.v13.operations.cli report --date 2026-01-19

# Save to file
python -m src.v13.operations.cli report --date 2026-01-19 --output report.txt
```

**Report format:**
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
...

CRITICAL LEAKAGE EVENTS:
1. Episode: race_2026-01-19_R3
   Finding: Future market leakage detected
   Description: Market snapshot at 14:05 UTC was used, 5 minutes after decision time
   Proposed Change: Add temporal validation rule
```

### Show Summary Statistics

```bash
python -m src.v13.operations.cli stats
```

**Output:**
```
=== SHADOW RACING V13 SUMMARY STATS ===

Total Episodes: 142
Total Proposals: 287
Pending Proposals: 54
Accepted Proposals: 12
Rejected Proposals: 8
Acceptance Rate: 60.0%
Doctrine Version: 13.2.0
```

---

## REVIEW CADENCE

### Twice Daily Review (Morning + Evening)

**Morning Review (09:00 UTC):**
```bash
# Generate report
python -m src.v13.operations.cli report

# Review CRITICAL findings (always)
# Review HIGH findings (if repeated ≥ 3 episodes)
# Accept/reject via governance API (Phase 3B)
```

**Evening Review (18:00 UTC):**
```bash
# Generate report
python -m src.v13.operations.cli report

# Review CRITICAL findings (always)
# Review HIGH findings (if repeated ≥ 3 episodes)
# Accept/reject via governance API (Phase 3B)
```

**MEDIUM/LOW findings:**
- Sit in queue until volume gives signal
- Review weekly or when pattern emerges

---

## WHAT'S NEXT

### Immediate (Before UI)

1. **Integrate actual VÉLØ engine** (currently placeholder)
   - Replace `_run_engine()` in shadow_racing_runner.py
   - Use existing engine code from velo-oracle-prime

2. **Integrate actual critics** (currently placeholder)
   - Replace `_run_critics()` in shadow_racing_runner.py
   - Use existing critic code from velo-oracle-prime
   - Wire up: LeakageDetectorCritic, CognitiveBiasCritic, FeatureExtractorCritic, DecisionCritic

3. **Set up race data ingestion**
   - Connect to Racing Post / TheRacingAPI
   - Parse race cards into JSON format
   - Automate daily race ingestion

4. **Run shadow racing on today's cards**
   - Process 50-100 episodes
   - Generate daily reports
   - Observe proposal patterns

### After 50-100 Episodes (48-72 hours)

5. **Analyze real data**
   - Which critics dominate?
   - Is severity well-calibrated?
   - How noisy is the queue?
   - What are the top finding types?

6. **Decide on UI approach**
   - Fix velo_strategic (TypeScript web app)
   - Build separate governance console
   - Continue with CLI/logs only

7. **Build Phase 3B Review UI** (if needed)
   - Review queue (filters: critic, severity, status, date)
   - Proposal detail (episode link, artifacts, similar episodes, accept/reject)
   - Ledger view (last 50 entries)
   - Doctrine version history

---

## INTEGRATION POINTS

### Engine Integration

```python
# In shadow_racing_runner.py, replace _run_engine()

from ..engine.velo_engine import VELOEngine

def _run_engine(self, episode_id: str, pre_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run actual VÉLØ engine."""
    engine = VELOEngine()
    
    inference = engine.run(
        runners=pre_state["runners"],
        market=pre_state["market"],
        form=pre_state["form"],
    )
    
    return {
        "verdict": inference.verdict,
        "confidence": inference.confidence,
        "top_4": inference.top_4,
        "internal_signals": inference.internal_signals,
        "rationale": inference.rationale,
    }
```

### Critic Integration

```python
# In shadow_racing_runner.py, replace _run_critics()

from ..critics.leakage_detector import LeakageDetectorCritic
from ..critics.cognitive_bias import CognitiveBiasCritic
from ..critics.feature_extractor import FeatureExtractorCritic
from ..critics.decision_critic import DecisionCritic

def _run_critics(self, episode_id: str):
    """Run actual critics."""
    critics = [
        LeakageDetectorCritic(),
        CognitiveBiasCritic(),
        FeatureExtractorCritic(),
        DecisionCritic(),
    ]
    
    for critic in critics:
        critique = critic.critique(episode_id, self.db)
        
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
            episode_id=episode_id,
            critic_type=critic.critic_type,
            proposals=proposals
        )
```

---

## SUCCESS CRITERIA

✅ Shadow racing runner implemented  
✅ Daily metrics collector implemented  
✅ CLI tool implemented (run-race, finalize, report, stats)  
✅ Integration tests passing (end-to-end flow verified)  
✅ Sample test data created  
✅ Documentation complete  
✅ Constitutional guarantees enforced (no auto-apply, no learning, no doctrine mutation)  
✅ Committed and pushed to GitHub

**Next:** Integrate actual engine + critics, start processing today's race cards

---

## FILES DELIVERED

```
src/v13/operations/
├── __init__.py                      # Module init
├── shadow_racing_runner.py          # Shadow racing runner (episode + critics)
├── daily_metrics.py                 # Daily metrics collector
└── cli.py                           # CLI tool (run-race, finalize, report, stats)

test_data/
├── sample_race.json                 # Sample race data
└── sample_result.json               # Sample race result

docs/operations/
├── SHADOW_RACING_V13_SPEC.md        # Full specification (copyable)
└── SHADOW_RACING_DELIVERY.md        # This file
```

---

**Shadow racing is ready. CLI/logs only. No UI yet.**

**Governance truth > governance comfort.**

**Build UI on real data, not assumptions.**
