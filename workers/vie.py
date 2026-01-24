#!/usr/bin/env python3
"""
VIE - Value & Impact Engine
Integral worker for detecting value and market impact.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class VIE:
    """Value & Impact Engine."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def analyze(self, race_id: int) -> Dict[str, Any]:
        """Analyze value and impact for race."""
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
        
        # Simulate odds (in real system, would fetch market odds)
        # For now, assign fake odds based on rating
        runners_with_odds = []
        for runner in runners:
            rating = runner['official_rating'] or 0
            # Higher rating = lower odds
            odds = max(1.0, 10.0 - rating / 10) if rating > 0 else 10.0
            runners_with_odds.append((runner, odds))
        
        results = []
        for runner, odds in runners_with_odds:
            metrics = self._analyze_runner(runner, odds, runners_with_odds)
            results.append({
                "runner_id": runner['id'],
                "number": runner['number'],
                "name": runner['name'],
                "odds": odds,
                "vie_score": metrics['score'],
                "vie_flags": metrics['flags'],
                "vie_confidence": metrics['confidence'],
                "vie_rationale": metrics['rationale']
            })
        
        # Value detection summary
        value_picks = [r for r in results if r['vie_score'] >= 0.7]
        overvalued = [r for r in results if r['vie_score'] <= 0.3]
        
        return {
            "race_id": race_id,
            "venue": race['venue'],
            "race_time": race['race_time'],
            "vie_version": "1.0",
            "total_runners": len(runners),
            "results": results,
            "summary": {
                "value_picks": len(value_picks),
                "overvalued": len(overvalued),
                "top_value_pick": max(results, key=lambda x: x['vie_score'])['name'] if results else None,
                "avg_vie_score": sum(r['vie_score'] for r in results) / len(results) if results else 0,
                "market_efficiency": 1 - (len(value_picks) / len(runners)) if runners else 1  # fewer value picks = more efficient
            }
        }
    
    def _analyze_runner(self, runner, odds, all_runners) -> Dict[str, Any]:
        """Compute VIE metrics for a runner."""
        score = 0.0
        confidence = 0.0
        flags = []
        rationale = []
        
        # 1. Odds vs rating
        rating = runner['official_rating'] or 0
        if rating > 0:
            expected_odds = max(1.0, 10.0 - rating / 10)
            if odds > expected_odds * 1.5:
                score += 0.4
                rationale.append(f"Odds {odds:.1f} vs rating {rating} = value")
            elif odds < expected_odds * 0.7:
                score -= 0.2
                flags.append("OVERVALUED")
                rationale.append(f"Odds {odds:.1f} vs rating {rating} = overvalued")
            else:
                score += 0.1
                rationale.append("Fairly priced")
        
        # 2. Market impact (simulated)
        # If runner is top rated but not favorite by odds
        top_rating = max(r['official_rating'] or 0 for r, _ in all_runners)
        favorite_odds = min(odds for _, odds in all_runners)
        if rating == top_rating and odds > favorite_odds:
            score += 0.3
            confidence += 0.2
            rationale.append("Top rating but not favorite - market overlooking")
        
        # 3. Form impact
        form = runner['form'] or ''
        if form:
            recent = form[:3] if len(form) >= 3 else form
            if '1' in recent and odds > 5.0:
                score += 0.2
                rationale.append("Recent winner at generous odds")
            elif 'F' in recent or 'U' in recent:
                flags.append("RISKY_FORM")
                score -= 0.1
        
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
    vie = VIE()
    result = vie.analyze(race_id)
    import json
    print(json.dumps(result, indent=2))
