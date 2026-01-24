#!/usr/bin/env python3
"""
VÉLØ PRIME - Central Brain
Orchestrates integral workers and makes final decisions.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import sys
sys.path.append(str(Path(__file__).parent.parent / 'workers'))

from sqpe import SQPE
from tie import TIE
from vie import VIE
from nds import NDS

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class VeloPrime:
    """VÉLØ PRIME central brain."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        # Initialize workers
        self.workers = {
            'sqpe': SQPE(),
            'tie': TIE(),
            'vie': VIE(),
            'nds': NDS()
        }
    
    def analyze_race(self, race_id: int) -> Dict[str, Any]:
        """Orchestrate workers and produce final verdict."""
        print(f"VÉLØ PRIME analyzing race {race_id}")
        
        # Get race info
        cursor = self.conn.cursor()
        race = cursor.execute(
            "SELECT * FROM races WHERE id = ?", (race_id,)
        ).fetchone()
        if not race:
            return {"error": "Race not found"}
        
        # Run workers sequentially
        worker_results = {}
        for name, worker in self.workers.items():
            try:
                result = worker.analyze(race_id)
                worker_results[name] = result
            except Exception as e:
                worker_results[name] = {"error": str(e)}
        
        # Aggregate results
        aggregated = self._aggregate_results(worker_results, race)
        
        # Generate final verdict
        verdict = self._generate_verdict(aggregated, race)
        
        # Save to database
        episode_id = self._save_analysis(race_id, worker_results, verdict)
        
        return {
            "race_id": race_id,
            "episode_id": episode_id,
            "worker_results": worker_results,
            "aggregated": aggregated,
            "verdict": verdict
        }
    
    def _aggregate_results(self, worker_results: Dict, race) -> Dict[str, Any]:
        """Aggregate worker results into unified scores."""
        runners = {}
        
        # Initialize runner dict from any worker result
        first_worker = next(iter(worker_results.values()))
        if 'results' not in first_worker or first_worker.get('error'):
            return {'runners': [], 'top_pick': None, 'avg_composite_score': 0.0, 'race_info': {}}
        
        for result in first_worker['results']:
            runner_id = result['runner_id']
            runners[runner_id] = {
                'runner_id': runner_id,
                'number': result['number'],
                'name': result['name'],
                'scores': {},
                'flags': [],
                'rationales': []
            }
        
        # Collect scores from each worker
        for worker_name, result in worker_results.items():
            if 'results' not in result:
                continue
            for runner_result in result['results']:
                runner_id = runner_result['runner_id']
                if runner_id not in runners:
                    continue
                score_key = f'{worker_name}_score'
                if score_key in runner_result:
                    runners[runner_id]['scores'][worker_name] = runner_result[score_key]
                if 'flags' in runner_result:
                    runners[runner_id]['flags'].extend(runner_result['flags'])
                if 'rationale' in runner_result:
                    runners[runner_id]['rationales'].append(runner_result['rationale'])
        
        # Compute composite score
        for runner_id, runner in runners.items():
            scores = list(runner['scores'].values())
            if scores:
                runner['composite_score'] = sum(scores) / len(scores)
            else:
                runner['composite_score'] = 0.0
            runner['flags'] = list(set(runner['flags']))
            runner['rationales'] = list(set(runner['rationales']))
        
        # Sort by composite score
        sorted_runners = sorted(runners.values(), key=lambda x: x['composite_score'], reverse=True)
        
        avg_composite = sum(r['composite_score'] for r in sorted_runners) / len(sorted_runners) if sorted_runners else 0.0
        return {
            'runners': sorted_runners,
            'top_pick': sorted_runners[0]['name'] if sorted_runners else None,
            'avg_composite_score': avg_composite,
            'race_info': {
                'venue': race['venue'],
                'race_time': race['race_time'],
                'going': race['going']
            }
        }
    
    def _generate_verdict(self, aggregated: Dict, race) -> Dict[str, Any]:
        """Generate final verdict based on aggregated results."""
        top_pick = aggregated.get('top_pick')
        runners = aggregated.get('runners', [])
        avg_composite = aggregated.get('avg_composite_score', 0.0)
        
        # Confidence based on score spread
        if len(runners) >= 2:
            top_score = runners[0]['composite_score']
            second_score = runners[1]['composite_score']
            spread = top_score - second_score
            confidence = min(0.9, 0.5 + spread * 2)  # scale spread to confidence
        else:
            confidence = 0.5
        
        # Rationale
        rationales = []
        if runners:
            top = runners[0]
            rationales.append(f"Top pick {top['name']} with composite score {top['composite_score']:.3f}")
            if top['flags']:
                rationales.append(f"Flags: {', '.join(top['flags'])}")
        
        # Anomalies
        anomalies = []
        if avg_composite < 0.3:
            anomalies.append("LOW_CONFIDENCE_ACROSS_BOARD")
        
        return {
            'race_id': race['id'],
            'venue': race['venue'],
            'race_time': race['race_time'],
            'top_pick': top_pick,
            'confidence': round(confidence, 3),
            'rationale': ' | '.join(rationales),
            'anomalies': anomalies,
            'runners_recommended': len([r for r in runners if r['composite_score'] >= 0.5]),
            'generated_at': datetime.now().isoformat()
        }
    
    def _save_analysis(self, race_id: int, worker_results: Dict, verdict: Dict) -> str:
        """Save analysis to database and return episode_id."""
        cursor = self.conn.cursor()
        
        # Create episode_id
        race = cursor.execute("SELECT venue, race_date, race_time FROM races WHERE id = ?", (race_id,)).fetchone()
        venue = race['venue'].upper().replace(' ', '_')
        race_date = race['race_date'].replace('-', '')
        race_time = verdict['race_time'].replace('.', '')
        episode_id = f"{venue}_{race_date}_{race_time}"
        
        # Save worker results as JSON
        worker_json = json.dumps(worker_results)
        verdict_json = json.dumps(verdict)
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO episodes (
                    id, venue, race_date, race_id,
                    worker_results, verdict_layer_x,
                    verdict_confidence, verdict_rationale,
                    verdict_generated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode_id,
                race['venue'],
                race['race_date'],
                race_id,
                worker_json,
                verdict['top_pick'],
                verdict['confidence'],
                verdict['rationale'],
                verdict['generated_at'],
                'PENDING_RESULT'
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Error saving episode: {e}")
        
        return episode_id

if __name__ == "__main__":
    import sys
    race_id = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    prime = VeloPrime()
    result = prime.analyze_race(race_id)
    print(json.dumps(result, indent=2))
