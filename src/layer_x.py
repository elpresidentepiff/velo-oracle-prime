#!/usr/bin/env python3
"""
VÉLØ PRIME Layer X - Intent/Anomaly/Trap-Lead Detection
Rule-based verdict generation (NEVER ML-trained)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class LayerX:
    """Rule-based verdict generator."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
    
    def generate_verdict(self, race_id: int) -> Dict:
        """Generate verdict for a race using Layer X rules."""
        cursor = self.conn.cursor()
        
        # Get race info
        race = cursor.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
        if not race:
            return {"error": "Race not found"}
        
        # Get all runners
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ? ORDER BY number",
            (race_id,)
        ).fetchall()
        
        if not runners:
            return {"error": "No runners found"}
        
        # Layer X Analysis
        verdict = self._analyze_race(race, runners)
        
        return verdict
    
    def _analyze_race(self, race, runners) -> Dict:
        """Apply Layer X rules to generate verdict."""
        
        # Rule 1: Expert Selection Alignment
        postdata_picks = [r for r in runners if r['is_postdata_selection']]
        topspeed_picks = [r for r in runners if r['is_topspeed_selection']]
        
        # Rule 2: Rating Convergence (OR, TS, RPR alignment)
        high_confidence_runners = []
        for runner in runners:
            ratings = [r for r in [runner['official_rating'], runner['topspeed'], runner['rpr']] if r]
            if len(ratings) >= 2:
                # If 2+ ratings present and close, confidence increases
                high_confidence_runners.append({
                    'name': runner['name'],
                    'number': runner['number'],
                    'ratings': ratings,
                    'avg_rating': sum(ratings) / len(ratings)
                })
        
        # Rule 3: Form Analysis (recent wins/places)
        form_leaders = []
        for runner in runners:
            form = runner['form'] or ''
            if form and form[0] in ['1', '2', '3']:  # Recent win/place
                form_leaders.append({
                    'name': runner['name'],
                    'number': runner['number'],
                    'form': form,
                    'recent_form': form[0]
                })
        
        # Rule 4: Going Suitability (heavy going = stamina/jumping)
        going = race['going']
        going_specialists = []
        if going in ['HEAVY', 'SOFT']:
            # Prefer older horses, proven jumpers, stamina sires
            for runner in runners:
                age = runner['age']
                form = runner['form'] or ''
                # Penalize falls/unseats in form
                if age and int(age) >= 6 and 'F' not in form and 'U' not in form:
                    going_specialists.append({
                        'name': runner['name'],
                        'number': runner['number'],
                        'age': age,
                        'form': form
                    })
        
        # Build verdict
        confidence = 0.0
        rationale = []
        top_pick = None
        
        # Scoring logic
        if postdata_picks or topspeed_picks:
            confidence += 0.3
            rationale.append(f"Expert selections: {len(postdata_picks)} POSTDATA, {len(topspeed_picks)} TOPSPEED")
            if postdata_picks:
                top_pick = postdata_picks[0]['name']
        
        if high_confidence_runners:
            confidence += 0.2
            top_by_rating = max(high_confidence_runners, key=lambda x: x['avg_rating'])
            rationale.append(f"Rating convergence: {top_by_rating['name']} ({top_by_rating['avg_rating']:.0f})")
            if not top_pick:
                top_pick = top_by_rating['name']
        
        if form_leaders:
            confidence += 0.2
            top_form = form_leaders[0]
            rationale.append(f"Recent form: {top_form['name']} ({top_form['form']})")
            if not top_pick:
                top_pick = top_form['name']
        
        if going_specialists and going in ['HEAVY', 'SOFT']:
            confidence += 0.15
            rationale.append(f"Heavy going: {len(going_specialists)} specialists identified")
        
        # Anomaly detection
        anomalies = []
        
        # Check for missing data
        missing_ratings = sum(1 for r in runners if not r['official_rating'] and not r['rpr'])
        if missing_ratings > len(runners) * 0.3:
            anomalies.append("HIGH_MISSING_RATINGS")
            confidence -= 0.1
        
        # Check for form anomalies (recent poor form)
        for runner in runners:
            form = runner['form'] or ''
            if form and len(form) >= 3:
                recent = form[:3]
                if all(c in ['7', '8', '9', 'F', 'P', 'U'] for c in recent):
                    anomalies.append(f"POOR_RECENT_FORM: {runner['name']}")
        
        # Trap-lead detection (favorite trap)
        if postdata_picks and topspeed_picks:
            if postdata_picks[0]['name'] == topspeed_picks[0]['name']:
                # Both systems agree - could be trap if market differs
                rationale.append("TRAP_ALERT: Consensus pick may be overpriced")
        
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            'race_id': race['id'],
            'venue': race['venue'],
            'race_time': race['race_time'],
            'race_name': race['race_name'],
            'going': race['going'],
            'top_pick': top_pick,
            'confidence': round(confidence, 2),
            'rationale': ' | '.join(rationale),
            'anomalies': anomalies,
            'expert_consensus': len(postdata_picks) > 0 or len(topspeed_picks) > 0,
            'runners_analyzed': len(runners),
            'generated_at': datetime.now().isoformat()
        }
    
    def save_verdict(self, verdict: Dict) -> str:
        """Save verdict to database and return episode_id."""
        cursor = self.conn.cursor()
        
        # Create episode_id: venue_date_time
        venue = verdict['venue'].upper().replace(' ', '_')
        race_date = cursor.execute(
            "SELECT race_date FROM races WHERE id = ?",
            (verdict['race_id'],)
        ).fetchone()['race_date'].replace('-', '')
        race_time = verdict['race_time'].replace('.', '')
        
        episode_id = f"{venue}_{race_date}_{race_time}"
        
        try:
            cursor.execute("""
                INSERT INTO episodes (
                    id, venue, race_date, race_id, verdict_layer_x, 
                    verdict_confidence, verdict_rationale, verdict_generated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode_id,
                verdict['venue'],
                race_date,
                verdict['race_id'],
                verdict['top_pick'],
                verdict['confidence'],
                verdict['rationale'],
                verdict['generated_at'],
                'PENDING_RESULT'
            ))
            self.conn.commit()
            return episode_id
        except sqlite3.IntegrityError:
            return episode_id  # Already exists
    
    def close(self):
        self.conn.close()

if __name__ == "__main__":
    layer_x = LayerX()
    
    # Get all races
    cursor = layer_x.conn.cursor()
    races = cursor.execute("SELECT id FROM races").fetchall()
    
    print("🎯 VÉLØ LAYER X - VERDICT GENERATION")
    print("=" * 60)
    
    for race in races:
        verdict = layer_x.generate_verdict(race['id'])
        episode_id = layer_x.save_verdict(verdict)
        
        print(f"\n📍 {verdict['race_name']}")
        print(f"   Time: {verdict['race_time']} | Going: {verdict['going']}")
        print(f"   Top Pick: {verdict['top_pick']}")
        print(f"   Confidence: {verdict['confidence']:.0%}")
        print(f"   Rationale: {verdict['rationale']}")
        if verdict['anomalies']:
            print(f"   ⚠️  Anomalies: {', '.join(verdict['anomalies'])}")
        print(f"   Episode ID: {episode_id}")
    
    layer_x.close()
    print("\n✅ Verdicts generated and saved")
