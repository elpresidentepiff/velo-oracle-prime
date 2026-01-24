#!/usr/bin/env python3
"""
Orchestrator - Layer 2
Manages execution of VÉLØ PRIME across multiple races.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))

from velo_prime import VeloPrime

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class Orchestrator:
    """Orchestrates race analysis across multiple races."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.prime = VeloPrime()
    
    def get_all_race_ids(self) -> list[int]:
        """Return list of all race IDs in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM races ORDER BY id")
        rows = cursor.fetchall()
        return [row['id'] for row in rows]
    
    def process_race(self, race_id: int) -> dict:
        """Process a single race and return result."""
        try:
            result = self.prime.analyze_race(race_id)
            return {
                "race_id": race_id,
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "race_id": race_id,
                "success": False,
                "error": str(e)
            }
    
    def process_all_races(self) -> list[dict]:
        """Process all races sequentially."""
        race_ids = self.get_all_race_ids()
        print(f"Found {len(race_ids)} races to process")
        
        results = []
        for race_id in race_ids:
            print(f"Processing race {race_id}...")
            result = self.process_race(race_id)
            results.append(result)
            if result['success']:
                print(f"  Success: top pick {result['result']['verdict']['top_pick']}")
            else:
                print(f"  Failed: {result['error']}")
        
        return results
    
    def generate_report(self, results: list[dict]) -> dict:
        """Generate summary report from results."""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful
        
        # Collect top picks
        top_picks = []
        for r in results:
            if r['success']:
                verdict = r['result']['verdict']
                top_picks.append({
                    "race_id": r['race_id'],
                    "top_pick": verdict['top_pick'],
                    "confidence": verdict['confidence'],
                    "runners_recommended": verdict['runners_recommended']
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_races": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "top_picks": top_picks,
            "results": results
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Orchestrate VÉLØ PRIME analysis')
    parser.add_argument('--race-id', type=int, help='Process specific race ID')
    parser.add_argument('--all', action='store_true', help='Process all races')
    args = parser.parse_args()
    
    orchestrator = Orchestrator()
    
    if args.race_id:
        result = orchestrator.process_race(args.race_id)
        print(json.dumps(result, indent=2))
    elif args.all:
        results = orchestrator.process_all_races()
        report = orchestrator.generate_report(results)
        print(json.dumps(report, indent=2))
    else:
        print("No action specified. Use --race-id or --all")
