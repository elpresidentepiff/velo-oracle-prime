#!/usr/bin/env python3
"""
NDS - Non-Dogma Selection
Integral worker for identifying non-obvious selections.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class NDS:
    """Non-Dogma Selection Engine."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def analyze(self, race_id: int) -> Dict[str, Any]:
        """Identify non-dogma selections for race."""
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
        
        # Determine consensus picks (based on ratings)
        rated_runners = [r for r in runners if r['official_rating']]
        if rated_runners:
            top_rating = max(r['official_rating'] for r in rated_runners)
            consensus = [r for r in rated_runners if r['official_rating'] == top_rating]
        else:
            consensus = []
        
        results = []
        for runner in runners:
            metrics = self._analyze_runner(runner, consensus, runners)
            results.append({
                "runner_id": runner['id'],
                "number": runner['number'],
                "name": runner['name'],
                "nds_score": metrics['score'],
                "nds_flags": metrics['flags'],
                "nds_confidence": metrics['confidence'],
                "nds_rationale": metrics['rationale']
            })
        
        # Non-dogma picks (high score but not consensus)
        non_dogma = [r for r in results if r['nds_score'] >= 0.7 and r['name'] not in [c['name'] for c in consensus]]
        
        return {
            "race_id": race_id,
            "venue": race['venue'],
            "race_time": race['race_time'],
            "nds_version": "1.0",
            "total_runners": len(runners),
            "consensus_picks": [c['name'] for c in consensus],
            "results": results,
            "summary": {
                "non_dogma_picks": len(non_dogma),
                "top_nds_pick": max(results, key=lambda x: x['nds_score'])['name'] if results else None,
                "avg_nds_score": sum(r['nds_score'] for r in results) / len(results) if results else 0,
                "dogma_alert": len(consensus) > 0 and len(consensus) <= 2  # strong consensus = dogma risk
            }
        }
    
    def _analyze_runner(self, runner, consensus, all_runners) -> Dict[str, Any]:
        """Compute NDS metrics for a runner."""
        score = 0.0
        confidence = 0.0
        flags = []
        rationale = []
        
        # 1. Non-consensus status
        is_consensus = runner['name'] in [c['name'] for c in consensus]
        if is_consensus:
            score -= 0.2
            flags.append("CONSENSUS_PICK")
            rationale.append("Consensus pick - dogma risk")
        else:
            score += 0.3
            rationale.append("Non-consensus pick")
        
        # 2. Underrated factors
        rating = runner['official_rating'] or 0
        top_rating = max(r['official_rating'] or 0 for r in all_runners)
        if 0 < rating < top_rating * 0.8:
            score += 0.2
            rationale.append(f"Underrated relative to top ({rating} vs {top_rating})")
        
        # 3. Form surprise
        form = runner['form'] or ''
        if form:
            recent = form[:3] if len(form) >= 3 else form
            # If form shows improvement (e.g., 9 -> 5 -> 3)
            if len(recent) >= 3 and recent[2] < recent[0]:
                score += 0.2
                rationale.append("Improving form")
            # If recent winner but not top rated
            if '1' in recent and not is_consensus:
                score += 0.3
                rationale.append("Recent winner overlooked")
        
        # 4. Trainer/jockey combo
        trainer = runner['trainer'] or ''
        jockey = runner['jockey'] or ''
        if trainer and jockey:
            score += 0.1
            rationale.append(f"{trainer} + {jockey} combo")
        
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
    nds = NDS()
    result = nds.analyze(race_id)
    import json
    print(json.dumps(result, indent=2))
