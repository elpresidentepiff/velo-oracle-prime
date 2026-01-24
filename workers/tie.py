#!/usr/bin/env python3
"""
TIE - Trainer Intent Engine
Integral worker for analyzing trainer patterns and intent.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class TIE:
    """Trainer Intent Engine."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def analyze(self, race_id: int) -> Dict[str, Any]:
        """Analyze trainer intent for race."""
        cursor = self.conn.cursor()
        
        race = cursor.execute(
            "SELECT * FROM races WHERE id = ?", (race_id,)
        ).fetchone()
        if not race:
            return {"error": "Race not found"}
        
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ? ORDER BY number",
            (race_id,)
        ).fetchall()
        
        if not runners:
            return {"error": "No runners found"}
        
        # Group by trainer
        trainer_runners = defaultdict(list)
        for runner in runners:
            trainer = runner['trainer'] or 'UNKNOWN'
            trainer_runners[trainer].append(runner)
        
        results = []
        for runner in runners:
            metrics = self._analyze_runner(runner, trainer_runners, race)
            results.append({
                "runner_id": runner['id'],
                "number": runner['number'],
                "name": runner['name'],
                "trainer": runner['trainer'] or 'UNKNOWN',
                "tie_score": metrics['score'],
                "tie_flags": metrics['flags'],
                "tie_confidence": metrics['confidence'],
                "tie_rationale": metrics['rationale']
            })
        
        # Overall trainer metrics
        trainer_summary = {}
        for trainer, runs in trainer_runners.items():
            avg_score = sum(r['tie_score'] for r in results if r['trainer'] == trainer) / len(runs)
            trainer_summary[trainer] = {
                "runners": len(runs),
                "avg_tie_score": round(avg_score, 3),
                "strong_intent": any(r['tie_score'] >= 0.7 for r in results if r['trainer'] == trainer)
            }
        
        return {
            "race_id": race_id,
            "venue": race['venue'],
            "race_time": race['race_time'],
            "tie_version": "1.0",
            "total_runners": len(runners),
            "unique_trainers": len(trainer_runners),
            "results": results,
            "trainer_summary": trainer_summary,
            "summary": {
                "top_tie_pick": max(results, key=lambda x: x['tie_score'])['name'] if results else None,
                "avg_tie_score": sum(r['tie_score'] for r in results) / len(results) if results else 0,
                "trainers_with_strong_intent": sum(1 for t in trainer_summary.values() if t['strong_intent'])
            }
        }
    
    def _analyze_runner(self, runner, trainer_runners, race) -> Dict[str, Any]:
        """Compute TIE metrics for a runner."""
        score = 0.0
        confidence = 0.0
        flags = []
        rationale = []
        trainer = runner['trainer'] or 'UNKNOWN'
        
        # 1. Trainer runners in this race
        same_trainer_runners = trainer_runners[trainer]
        if len(same_trainer_runners) > 1:
            # Multiple entries from same trainer
            flags.append("MULTIPLE_ENTRIES")
            # If this runner is the highest rated, could be main hope
            ratings = [r['official_rating'] for r in same_trainer_runners if r['official_rating']]
            if ratings and runner['official_rating'] == max(ratings):
                score += 0.3
                rationale.append("Main hope among trainer's multiple entries")
            else:
                score -= 0.1
                rationale.append("Secondary entry among trainer's multiple entries")
        else:
            score += 0.1
            rationale.append("Sole entry for trainer")
        
        # 2. Trainer recent form (simulated)
        # In real system, would query historical data
        # Here we use runner's form as proxy
        form = runner['form'] or ''
        if form:
            recent = form[:3] if len(form) >= 3 else form
            if '1' in recent:
                score += 0.3
                confidence += 0.2
                rationale.append("Trainer recent winner")
            elif '2' in recent or '3' in recent:
                score += 0.2
                confidence += 0.1
                rationale.append("Trainer recent placed")
        
        # 3. Trainer track record (simulated)
        # Would need historical database
        # Assume unknown trainers penalized
        if trainer == 'UNKNOWN':
            flags.append("UNKNOWN_TRAINER")
            confidence -= 0.2
        else:
            score += 0.1
            rationale.append(f"Known trainer: {trainer}")
        
        # 4. Jockey-trainer combination
        jockey = runner['jockey'] or ''
        if jockey:
            score += 0.1
            rationale.append(f"Jockey {jockey} riding")
        
        # Normalize
        score = max(0.0, min(1.0, score))
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "flags": flags,
            "rationale": ' | '.join(rationale) if rationale else 'No rationale'
        }

if __name__ == "__main__":
    import sys
    race_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    tie = TIE()
    result = tie.analyze(race_id)
    import json
    print(json.dumps(result, indent=2))
