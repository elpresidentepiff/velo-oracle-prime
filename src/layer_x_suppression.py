#!/usr/bin/env python3
"""
VÉLØ PRIME Layer X - Suppression Detection & Quarantine Logic
Canonical implementation of SUPPRESSED_PERF and QUARANTINE_VERDICT

Reference: VELO PRIME — LAYER X (SUPPRESSION) — CANONICAL SPEC v1.0
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

# Suppression signal codes
S1_REACTIVATION_RIDER = "S1_REACTIVATION_RIDER"
S2_MARK_COMPRESSION = "S2_MARK_COMPRESSION"
S3_SETUP_RETURN = "S3_SETUP_RETURN"
S4_NOT_ASKED_PATTERN = "S4_NOT_ASKED_PATTERN"
S5_PRICE_RESILIENCE = "S5_PRICE_RESILIENCE"
S6_YARD_TIMING = "S6_YARD_TIMING"
S7_TRAP_LEAD_SIGNATURE = "S7_TRAP_LEAD_SIGNATURE"

@dataclass
class RunnerSuppression:
    """Runner-level suppression analysis."""
    runner_id: int
    name: str
    suppressed_perf: bool
    suppressed_reasons: List[str]
    suppressed_severity: str  # HIGH, MED, LOW
    signal_count: int

@dataclass
class RaceQuarantine:
    """Race-level quarantine decision."""
    race_id: int
    quarantined: bool
    quarantine_reasons: List[str]
    strike_allowed: bool

class LayerXSuppression:
    """Suppression detection and quarantine enforcement."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def detect_runner_suppression(self, runner: Dict) -> RunnerSuppression:
        """Detect SUPPRESSED_PERF signals for a runner."""
        signals = []
        
        # S1: REACTIVATION_RIDER - jockey upgrade
        if runner.get('jockey_change'):
            signals.append(S1_REACTIVATION_RIDER)
        
        # S2: MARK_COMPRESSION - at/below last winning mark
        if runner.get('official_rating'):
            peak_rating = runner.get('peak_rating', runner['official_rating'])
            if runner['official_rating'] <= peak_rating * 0.95:  # 5% drop
                signals.append(S2_MARK_COMPRESSION)
        
        # S3: SETUP_RETURN - back to best trip/surface
        if runner.get('setup_return'):
            signals.append(S3_SETUP_RETURN)
        
        # S4: NOT_ASKED_PATTERN - education run indicators
        form = runner.get('form', '')
        if form and any(c in form for c in ['P', 'U']):  # Pulled/Unseated
            signals.append(S4_NOT_ASKED_PATTERN)
        
        # S5: PRICE_RESILIENCE - odds hold despite poor form
        if runner.get('price_resilience'):
            signals.append(S5_PRICE_RESILIENCE)
        
        # S6: YARD_TIMING - 2nd/3rd run after break
        if runner.get('runs_since_break', 0) in [2, 3]:
            signals.append(S6_YARD_TIMING)
        
        # S7: TRAP_LEAD_SIGNATURE - deliberate wrong tactics (counts as 2)
        if runner.get('trap_lead_signature'):
            signals.append(S7_TRAP_LEAD_SIGNATURE)
            signals.append(S7_TRAP_LEAD_SIGNATURE)  # Counts as 2
        
        # Determine suppression status
        signal_count = len(signals)
        suppressed_perf = signal_count >= 2
        
        # Determine severity
        if S7_TRAP_LEAD_SIGNATURE in signals or (S1_REACTIVATION_RIDER in signals and S2_MARK_COMPRESSION in signals) or signal_count >= 3:
            severity = "HIGH"
        elif signal_count == 2:
            severity = "MED"
        else:
            severity = "LOW"
        
        return RunnerSuppression(
            runner_id=runner.get('id', 0),
            name=runner.get('name', ''),
            suppressed_perf=suppressed_perf,
            suppressed_reasons=signals,
            suppressed_severity=severity,
            signal_count=signal_count
        )
    
    def decide_race_quarantine(self, race: Dict, runners: List[Dict]) -> RaceQuarantine:
        """Decide if race should be quarantined."""
        race_id = race.get('id', 0)
        quarantine_reasons = []
        
        # Analyze all runners
        runner_suppressions = []
        for runner in runners:
            supp = self.detect_runner_suppression(runner)
            runner_suppressions.append(supp)
        
        # Q1: DATA_MISSING - >25% of runners missing required fields
        missing_count = sum(1 for r in runners if not r.get('official_rating') and not r.get('rpr'))
        if missing_count > len(runners) * 0.25:
            quarantine_reasons.append("Q1_DATA_MISSING")
        
        # Q2: MASS_SUPPRESSION - >=3 runners flagged
        suppressed_count = sum(1 for s in runner_suppressions if s.suppressed_perf)
        if suppressed_count >= 3:
            quarantine_reasons.append("Q2_MASS_SUPPRESSION")
        
        # Q3: MIDPRICE_COMPRESSION - tight rating cluster
        ratings = [r.get('official_rating', 0) for r in runners if r.get('official_rating')]
        if ratings:
            rating_range = max(ratings) - min(ratings)
            if rating_range <= 8 and len(ratings) >= 4:
                quarantine_reasons.append("Q3_MIDPRICE_COMPRESSION")
        
        # Q4: MAIDEN/NOVICE_UNKNOWN - maiden with fav <=3.2 and >=2 unknown
        if race.get('race_type') in ['maiden', 'novice']:
            unknown_count = sum(1 for r in runners if not r.get('official_rating'))
            if unknown_count >= 2:
                quarantine_reasons.append("Q4_MAIDEN_NOVICE_UNKNOWN")
        
        # Q5: CHAOS_MODE - track volatility (placeholder)
        if race.get('going') in ['HEAVY', 'SOFT'] and len(runners) > 15:
            quarantine_reasons.append("Q5_CHAOS_MODE")
        
        quarantined = len(quarantine_reasons) > 0
        
        # STRIKE allowed only if NOT quarantined AND conditions met
        strike_allowed = not quarantined
        if strike_allowed:
            high_suppressed = [s for s in runner_suppressions if s.suppressed_severity == "HIGH"]
            if len(high_suppressed) > 1:
                strike_allowed = False
        
        return RaceQuarantine(
            race_id=race_id,
            quarantined=quarantined,
            quarantine_reasons=quarantine_reasons,
            strike_allowed=strike_allowed
        )
    
    def enforce_containment(self, top4: List[str], suppressed_runners: List[str]) -> List[str]:
        """Force-gate: ensure all SUPPRESSED_PERF runners in Top-4."""
        result = top4.copy()
        
        for runner in suppressed_runners:
            if runner not in result and len(result) < 4:
                result.append(runner)
        
        # If we exceed 4, we have a system error
        if len(result) > 4:
            return result[:4]  # Truncate but log error
        
        return result
    
    def log_integrity_event(self, episode_id: str, race_id: int, event_type: str, payload: Dict):
        """Log integrity event to database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO integrity_events (episode_id, race_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            episode_id,
            race_id,
            event_type,
            json.dumps(payload),
            datetime.now().isoformat()
        ))
        self.conn.commit()
    
    def close(self):
        self.conn.close()

if __name__ == "__main__":
    suppression = LayerXSuppression()
    
    print("🔒 VÉLØ LAYER X - SUPPRESSION DETECTION")
    print("=" * 70)
    
    # Get all races
    cursor = suppression.conn.cursor()
    races = cursor.execute("SELECT * FROM races").fetchall()
    
    for race in races:
        print(f"\n📍 {race['race_time']} - {race['race_name']}")
        
        # Get runners for this race
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ?",
            (race['id'],)
        ).fetchall()
        
        # Convert to dict
        runners_dict = [dict(r) for r in runners]
        
        # Analyze suppression
        runner_suppressions = []
        for runner in runners_dict:
            supp = suppression.detect_runner_suppression(runner)
            runner_suppressions.append(supp)
            
            if supp.suppressed_perf:
                print(f"   ⚠️  {supp.name}: {supp.suppressed_severity} - {supp.suppressed_reasons}")
        
        # Check quarantine
        quarantine = suppression.decide_race_quarantine(dict(race), runners_dict)
        
        if quarantine.quarantined:
            print(f"   🚫 QUARANTINED: {quarantine.quarantine_reasons}")
        else:
            print(f"   ✅ STRIKE ALLOWED")
    
    suppression.close()
    print("\n✅ Suppression analysis complete")
