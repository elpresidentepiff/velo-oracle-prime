#!/usr/bin/env python3
"""
VÉLØ PRIME Output Generator
Canonical VELO format: STRIKE + Positions 2-4 + Suppression alerts
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from layer_x_suppression import LayerXSuppression, RunnerSuppression, RaceQuarantine

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class VELOOutput:
    """Generate VELO-format verdicts with suppression logic."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.suppression = LayerXSuppression()
    
    def generate_race_verdict(self, race_id: int) -> Dict:
        """Generate complete VELO verdict for a race."""
        cursor = self.conn.cursor()
        
        # Get race
        race = cursor.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
        if not race:
            return {"error": "Race not found"}
        
        # Get runners
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ? ORDER BY CAST(number AS INTEGER)",
            (race_id,)
        ).fetchall()
        
        runners_dict = [dict(r) for r in runners]
        
        # Get existing episode/verdict
        episode = cursor.execute(
            "SELECT * FROM episodes WHERE race_id = ?",
            (race_id,)
        ).fetchone()
        
        # Analyze suppression
        runner_suppressions = []
        for runner in runners_dict:
            supp = self.suppression.detect_runner_suppression(runner)
            runner_suppressions.append(supp)
        
        # Check quarantine
        quarantine = self.suppression.decide_race_quarantine(dict(race), runners_dict)
        
        # Build verdict
        verdict = {
            'race_id': race_id,
            'race_time': race['race_time'],
            'race_name': race['race_name'],
            'distance': race['distance'],
            'going': race['going'],
            'prize_money': race['prize_money'],
            'runners_count': len(runners),
            'generated_at': datetime.now().isoformat(),
        }
        
        # STRIKE decision
        if quarantine.quarantined:
            verdict['strike'] = None
            verdict['quarantine_reason'] = quarantine.quarantine_reasons
            verdict['status'] = 'QUARANTINED'
        else:
            # Use existing episode verdict as STRIKE
            if episode and episode['verdict_layer_x']:
                verdict['strike'] = {
                    'name': episode['verdict_layer_x'],
                    'confidence': episode['verdict_confidence']
                }
            else:
                verdict['strike'] = None
        
        # Positions 2-4 (containment chassis)
        top_runners = sorted(
            runners_dict,
            key=lambda r: (
                r.get('official_rating') or 0,
                r.get('topspeed') or 0,
                r.get('rpr') or 0
            ),
            reverse=True
        )
        
        # Force-gate: include suppressed runners
        suppressed_names = [s.name for s in runner_suppressions if s.suppressed_perf]
        positions_2_4 = []
        
        for runner in top_runners:
            if runner['name'] != verdict['strike'].get('name') if verdict['strike'] else True:
                positions_2_4.append(runner['name'])
                if len(positions_2_4) >= 3:
                    break
        
        # Enforce containment: add suppressed runners if not present
        for supp_name in suppressed_names:
            if supp_name not in positions_2_4 and supp_name != (verdict['strike'].get('name') if verdict['strike'] else None):
                if len(positions_2_4) < 3:
                    positions_2_4.append(supp_name)
        
        verdict['positions_2_4'] = positions_2_4[:3]
        
        # Suppression alerts
        verdict['suppressed_perf'] = [
            {
                'name': s.name,
                'severity': s.suppressed_severity,
                'reasons': s.suppressed_reasons,
                'signal_count': s.signal_count
            }
            for s in runner_suppressions if s.suppressed_perf
        ]
        
        verdict['high_alert_count'] = sum(1 for s in runner_suppressions if s.suppressed_severity == 'HIGH')
        
        return verdict
    
    def print_velo_report(self):
        """Print VELO verdicts for all races."""
        cursor = self.conn.cursor()
        races = cursor.execute("SELECT id FROM races ORDER BY race_time").fetchall()
        
        print("🎯 VÉLØ GOWRAN PARK - VERDICTS & SUPPRESSION ALERTS")
        print("=" * 80)
        print()
        
        for race in races:
            verdict = self.generate_race_verdict(race['id'])
            
            print(f"📍 {verdict['race_time']} - {verdict['race_name']}")
            print(f"   Distance: {verdict['distance']} | Going: {verdict['going']} | Runners: {verdict['runners_count']}")
            print()
            
            if verdict.get('status') == 'QUARANTINED':
                print(f"   🚫 QUARANTINED: {verdict['quarantine_reason']}")
                print(f"   Reason: Race conditions compromised, containment only")
            else:
                if verdict['strike']:
                    print(f"   🏇 STRIKE: {verdict['strike']['name']} ({verdict['strike']['confidence']:.0%})")
                else:
                    print(f"   ⚠️  NO STRIKE: Conditions unclear")
            
            print(f"   📦 CONTAINMENT (Top-4 Chassis): {', '.join(verdict['positions_2_4'])}")
            
            if verdict['suppressed_perf']:
                print(f"   ⚠️  SUPPRESSED_PERF ({len(verdict['suppressed_perf'])} runners):")
                for supp in verdict['suppressed_perf']:
                    print(f"      - {supp['name']}: {supp['severity']} ({', '.join(supp['reasons'])})")
            
            if verdict['high_alert_count'] > 0:
                print(f"   🚨 HIGH ALERT: {verdict['high_alert_count']} runners with HIGH severity")
            
            print()
            print("-" * 80)
            print()
    
    def close(self):
        self.conn.close()
        self.suppression.close()

if __name__ == "__main__":
    velo = VELOOutput()
    velo.print_velo_report()
    velo.close()
