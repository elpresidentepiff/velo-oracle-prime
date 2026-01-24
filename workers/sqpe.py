#!/usr/bin/env python3
"""
SQPE - Statistical Qualification & Performance Engine
Integral worker for VÉLØ MCP.
Input: race_id, runner data.
Output: qualification scores, flags, metrics.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class SQPE:
    """Statistical Qualification & Performance Engine."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def analyze(self, race_id: int) -> Dict[str, Any]:
        """Analyze race and runners, returning SQPE metrics."""
        cursor = self.conn.cursor()
        
        # Get race info
        race = cursor.execute(
            "SELECT * FROM races WHERE id = ?", (race_id,)
        ).fetchone()
        if not race:
            return {"error": "Race not found"}
        
        # Get all runners
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ? ORDER BY number",
            (race_id,)
        ).fetchall()
        
        if not runners:
            return {"error": "No runners found"}
        
        # SQPE Analysis
        results = []
        for runner in runners:
            metrics = self._analyze_runner(runner, race)
            results.append({
                "runner_id": runner['id'],
                "number": runner['number'],
                "name": runner['name'],
                "sqpe_score": metrics['score'],
                "sqpe_flags": metrics['flags'],
                "sqpe_confidence": metrics['confidence'],
                "sqpe_rationale": metrics['rationale']
            })
        
        # Overall race SQPE metrics
        qualified = [r for r in results if r['sqpe_score'] >= 0.6]
        high_confidence = [r for r in results if r['sqpe_confidence'] >= 0.8]
        
        return {
            "race_id": race_id,
            "venue": race['venue'],
            "race_time": race['race_time'],
            "sqpe_version": "1.0",
            "total_runners": len(runners),
            "qualified_runners": len(qualified),
            "high_confidence_runners": len(high_confidence),
            "results": results,
            "summary": {
                "qualification_rate": len(qualified) / len(runners) if runners else 0,
                "avg_sqpe_score": sum(r['sqpe_score'] for r in results) / len(results) if results else 0,
                "top_sqpe_pick": max(results, key=lambda x: x['sqpe_score'])['name'] if results else None
            }
        }
    
    def _analyze_runner(self, runner, race) -> Dict[str, Any]:
        """Compute SQPE metrics for a single runner."""
        score = 0.0
        confidence = 0.0
        flags = []
        rationale = []
        
        # 1. Rating completeness
        ratings = [r for r in [runner['official_rating'], runner['topspeed'], runner['rpr']] if r is not None]
        if len(ratings) >= 2:
            score += 0.3
            confidence += 0.3
            rationale.append(f"{len(ratings)} ratings present")
        elif len(ratings) == 1:
            score += 0.1
            confidence += 0.1
            flags.append("LOW_RATING_COVERAGE")
        else:
            flags.append("NO_RATINGS")
            confidence -= 0.2
        
        # 2. Form analysis
        form = runner['form'] or ''
        if form:
            recent = form[:3] if len(form) >= 3 else form
            # Count wins/places (1,2,3)
            good = sum(1 for c in recent if c in '123')
            if good >= 2:
                score += 0.4
                confidence += 0.3
                rationale.append(f"Strong recent form: {recent}")
            elif good >= 1:
                score += 0.2
                confidence += 0.1
                rationale.append(f"Decent recent form: {recent}")
            else:
                flags.append("POOR_RECENT_FORM")
                score -= 0.1
        else:
            flags.append("NO_FORM_DATA")
            confidence -= 0.1
        
        # 3. Age suitability
        age = runner['age']
        if age:
            age_int = int(age)
            # Ideal age range 4-8
            if 4 <= age_int <= 8:
                score += 0.1
                rationale.append(f"Prime age: {age_int}")
            elif age_int > 10:
                flags.append("AGE_CONCERN")
                score -= 0.1
        
        # 4. Going suitability (simplified)
        going = race['going'] or ''
        if going.upper() in ['HEAVY', 'SOFT']:
            # Older horses may handle heavy better
            if age and int(age) >= 6:
                score += 0.1
                rationale.append(f"Heavy going specialist age {age}")
        
        # Normalize score 0-1
        score = max(0.0, min(1.0, score))
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "flags": flags,
            "rationale": ' | '.join(rationale) if rationale else 'No rationale'
        }

if __name__ == "__main__":
    # Test with race_id 1
    import sys
    race_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sqpe = SQPE()
    result = sqpe.analyze(race_id)
    import json
    print(json.dumps(result, indent=2))
