#!/usr/bin/env python3
"""
VÉLØ PRIME Completeness Gate
Lock 3: No metrics/exports without complete data
"""

import sqlite3
from pathlib import Path
from typing import Dict, List

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class CompletenessGate:
    """Validates episode completeness before export."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def check_episodes(self, expected_count: int = None) -> Dict:
        """Check if episodes match expected count."""
        cursor = self.conn.cursor()
        
        # Get actual episode count
        actual = cursor.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        
        # Get actual race count
        races = cursor.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        
        # Get runners per race
        cursor.execute("SELECT race_id, COUNT(*) as count FROM runners GROUP BY race_id")
        runners_by_race = {row['race_id']: row['count'] for row in cursor.fetchall()}
        
        result = {
            'episodes_actual': actual,
            'episodes_expected': expected_count or races,
            'races_total': races,
            'runners_total': sum(runners_by_race.values()),
            'runners_by_race': runners_by_race,
            'is_complete': actual == (expected_count or races),
            'gaps': []
        }
        
        # Find missing episodes
        cursor.execute("SELECT id FROM races WHERE id NOT IN (SELECT race_id FROM episodes)")
        missing = cursor.fetchall()
        if missing:
            result['gaps'] = [row['id'] for row in missing]
        
        return result
    
    def validate_before_export(self, expected_count: int = None) -> bool:
        """Validate completeness before allowing export."""
        check = self.check_episodes(expected_count)
        
        print("📋 COMPLETENESS GATE CHECK")
        print("=" * 60)
        print(f"Races: {check['races_total']}")
        print(f"Runners: {check['runners_total']}")
        print(f"Episodes: {check['episodes_actual']}/{check['episodes_expected']}")
        
        if check['is_complete']:
            print("✅ COMPLETE - Safe to export")
            return True
        else:
            print(f"❌ INCOMPLETE - {len(check['gaps'])} missing episodes")
            for gap in check['gaps']:
                print(f"   Missing episode for race_id: {gap}")
            print("\n⚠️  NO EXPORT ALLOWED - Silent partials forbidden")
            return False
    
    def close(self):
        self.conn.close()

if __name__ == "__main__":
    gate = CompletenessGate()
    is_complete = gate.validate_before_export()
    gate.close()
    
    exit(0 if is_complete else 1)
