"""
VÉLØ Oracle - Odds Movement Predictor
Predicts which horses' odds will shorten BEFORE it happens
Uses behavioral intelligence, narrative modeling, and intent detection
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np


class OddsMovementPredictor:
    """Predicts odds movements using VÉLØ's behavioral intelligence"""
    
    def __init__(self):
        self.intent_engine = IntentEngine()
        self.narrative_analyzer = NarrativeAnalyzer()
        self.behavioral_model = BehavioralIntelligence()
        self.manipulation_detector = MarketManipulationRadar()
    
    def predict_odds_movement(self, horse_data: Dict, race_data: Dict) -> Dict:
        """
        Predict if and when a horse's odds will shorten
        
        Returns:
            {
                'will_shorten': bool,
                'confidence': float (0-1),
                'predicted_movement': float (e.g., 20.0 -> 10.0),
                'timeframe': str ('1-2 days', '2-4 hours', etc.),
                'reasons': List[str],
                'recommended_action': str,
                'entry_odds': float,
                'target_lay_odds': float,
                'expected_profit_pct': float
            }
        """
        
        # Analyze multiple intelligence layers
        intent_score = self.intent_engine.analyze(horse_data, race_data)
        narrative_score = self.narrative_analyzer.analyze(horse_data, race_data)
        behavioral_score = self.behavioral_model.analyze(horse_data, race_data)
        manipulation_score = self.manipulation_detector.analyze(horse_data, race_data)
        
        # Calculate composite odds movement probability
        movement_probability = self._calculate_movement_probability(
            intent_score,
            narrative_score,
            behavioral_score,
            manipulation_score
        )
        
        # Predict magnitude of movement
        predicted_movement = self._predict_movement_magnitude(
            horse_data,
            intent_score,
            narrative_score
        )
        
        # Determine timeframe
        timeframe = self._predict_timeframe(
            horse_data,
            race_data,
            intent_score
        )
        
        # Generate reasons
        reasons = self._generate_reasons(
            intent_score,
            narrative_score,
            behavioral_score,
            manipulation_score
        )
        
        # Calculate recommended action
        recommendation = self._generate_recommendation(
            movement_probability,
            predicted_movement,
            horse_data
        )
        
        return {
            'will_shorten': movement_probability > 0.65,
            'confidence': movement_probability,
            'predicted_movement': predicted_movement,
            'timeframe': timeframe,
            'reasons': reasons,
            'recommended_action': recommendation['action'],
            'entry_odds': recommendation['entry_odds'],
            'target_lay_odds': recommendation['target_lay_odds'],
            'expected_profit_pct': recommendation['expected_profit_pct']
        }
    
    def _calculate_movement_probability(
        self,
        intent_score: Dict,
        narrative_score: Dict,
        behavioral_score: Dict,
        manipulation_score: Dict
    ) -> float:
        """Calculate probability that odds will shorten"""
        
        # Weight different intelligence layers
        weights = {
            'intent': 0.35,      # Intent is most important
            'narrative': 0.30,   # Narrative drives market perception
            'behavioral': 0.25,  # Behavioral patterns are reliable
            'manipulation': 0.10 # Manipulation is less predictive
        }
        
        # Calculate weighted score
        probability = (
            intent_score['go_day_probability'] * weights['intent'] +
            narrative_score['narrative_shift_probability'] * weights['narrative'] +
            behavioral_score['pattern_strength'] * weights['behavioral'] +
            (1 - manipulation_score['manipulation_detected']) * weights['manipulation']
        )
        
        return min(max(probability, 0.0), 1.0)
    
    def _predict_movement_magnitude(
        self,
        horse_data: Dict,
        intent_score: Dict,
        narrative_score: Dict
    ) -> Dict:
        """Predict how much odds will move"""
        
        current_odds = horse_data.get('current_odds', 10.0)
        
        # Base movement on intent strength and narrative power
        intent_strength = intent_score.get('intent_strength', 0.5)
        narrative_power = narrative_score.get('narrative_power', 0.5)
        
        # Calculate expected movement
        movement_factor = 0.3 + (intent_strength * 0.4) + (narrative_power * 0.3)
        
        # Predict target odds
        target_odds = current_odds * (1 - movement_factor)
        
        return {
            'current_odds': current_odds,
            'target_odds': round(target_odds, 1),
            'movement_pct': round(movement_factor * 100, 1),
            'ticks': self._calculate_ticks(current_odds, target_odds)
        }
    
    def _calculate_ticks(self, current_odds: float, target_odds: float) -> int:
        """Calculate number of ticks movement"""
        # Simplified tick calculation
        return int(abs(current_odds - target_odds) / 0.5)
    
    def _predict_timeframe(
        self,
        horse_data: Dict,
        race_data: Dict,
        intent_score: Dict
    ) -> str:
        """Predict when odds will move"""
        
        days_to_race = race_data.get('days_to_race', 3)
        urgency = intent_score.get('urgency', 0.5)
        
        if urgency > 0.8:
            return "Within 24 hours"
        elif urgency > 0.6:
            return "1-2 days"
        elif urgency > 0.4:
            return "2-3 days"
        else:
            return "3-5 days"
    
    def _generate_reasons(
        self,
        intent_score: Dict,
        narrative_score: Dict,
        behavioral_score: Dict,
        manipulation_score: Dict
    ) -> List[str]:
        """Generate human-readable reasons for prediction"""
        
        reasons = []
        
        # Intent reasons
        if intent_score.get('go_day_probability', 0) > 0.7:
            reasons.append(f"🎯 GO DAY DETECTED: {intent_score.get('go_day_reason', 'Strong intent signals')}")
        
        # Narrative reasons
        if narrative_score.get('narrative_shift_probability', 0) > 0.6:
            reasons.append(f"📖 NARRATIVE SHIFT: {narrative_score.get('narrative', 'Story changing')}")
        
        # Behavioral reasons
        if behavioral_score.get('pattern_strength', 0) > 0.7:
            reasons.append(f"🧠 PATTERN MATCH: {behavioral_score.get('pattern_description', 'Historical pattern detected')}")
        
        # Manipulation reasons
        if manipulation_score.get('manipulation_detected', 0) < 0.3:
            reasons.append("✅ GENUINE MARKET: No manipulation detected - real value")
        
        return reasons
    
    def _generate_recommendation(
        self,
        movement_probability: float,
        predicted_movement: Dict,
        horse_data: Dict
    ) -> Dict:
        """Generate trading recommendation"""
        
        current_odds = predicted_movement['current_odds']
        target_odds = predicted_movement['target_odds']
        
        if movement_probability < 0.65:
            return {
                'action': 'PASS',
                'entry_odds': None,
                'target_lay_odds': None,
                'expected_profit_pct': 0
            }
        
        # Calculate optimal entry and exit
        entry_odds = current_odds
        target_lay_odds = target_odds
        
        # Calculate expected profit percentage
        # Simplified calculation - assumes equal stakes
        if current_odds > 0 and target_odds > 0:
            profit_pct = ((current_odds - target_odds) / current_odds) * 100
        else:
            profit_pct = 0
        
        return {
            'action': 'BACK NOW, LAY LATER',
            'entry_odds': entry_odds,
            'target_lay_odds': target_lay_odds,
            'expected_profit_pct': round(profit_pct, 1)
        }


class IntentEngine:
    """Detects trainer/owner intent - the "go day" signal"""
    
    def analyze(self, horse_data: Dict, race_data: Dict) -> Dict:
        """Analyze intent signals"""
        
        # Factors that indicate "go day"
        factors = []
        scores = []
        
        # 1. Trainer pattern analysis
        trainer = horse_data.get('trainer', '')
        trainer_pattern = self._analyze_trainer_pattern(trainer, race_data)
        if trainer_pattern['is_go_pattern']:
            factors.append(f"Trainer {trainer} shows GO pattern")
            scores.append(0.8)
        
        # 2. Jockey booking
        jockey = horse_data.get('jockey', '')
        if self._is_premium_jockey(jockey):
            factors.append(f"Premium jockey {jockey} booked")
            scores.append(0.7)
        
        # 3. Equipment changes
        equipment_change = horse_data.get('equipment_change', False)
        if equipment_change:
            factors.append("Equipment change signals intent")
            scores.append(0.6)
        
        # 4. Race selection
        if self._is_optimal_race_selection(horse_data, race_data):
            factors.append("Optimal race selection for this horse")
            scores.append(0.7)
        
        # 5. Recent trial/workout
        recent_trial = horse_data.get('recent_trial', False)
        if recent_trial:
            factors.append("Recent trial indicates preparation")
            scores.append(0.6)
        
        # Calculate composite score
        if scores:
            go_day_probability = np.mean(scores)
            intent_strength = np.max(scores)
        else:
            go_day_probability = 0.3
            intent_strength = 0.3
        
        # Determine urgency
        urgency = self._calculate_urgency(horse_data, race_data)
        
        return {
            'go_day_probability': go_day_probability,
            'intent_strength': intent_strength,
            'urgency': urgency,
            'go_day_reason': '; '.join(factors) if factors else 'No strong intent signals',
            'factors': factors
        }
    
    def _analyze_trainer_pattern(self, trainer: str, race_data: Dict) -> Dict:
        """Analyze if trainer shows "go day" pattern"""
        # Placeholder - would analyze historical trainer patterns
        return {
            'is_go_pattern': False,
            'confidence': 0.5
        }
    
    def _is_premium_jockey(self, jockey: str) -> bool:
        """Check if jockey is premium/championship level"""
        premium_jockeys = [
            'Ryan Moore', 'William Buick', 'Frankie Dettori',
            'Oisin Murphy', 'James Doyle', 'Tom Marquand'
        ]
        return jockey in premium_jockeys
    
    def _is_optimal_race_selection(self, horse_data: Dict, race_data: Dict) -> bool:
        """Check if race selection is optimal for horse"""
        # Placeholder - would analyze course/distance suitability
        return False
    
    def _calculate_urgency(self, horse_data: Dict, race_data: Dict) -> float:
        """Calculate urgency of intent"""
        days_to_race = race_data.get('days_to_race', 7)
        
        # More urgent as race approaches
        if days_to_race <= 1:
            return 0.9
        elif days_to_race <= 2:
            return 0.7
        elif days_to_race <= 3:
            return 0.5
        else:
            return 0.3


class NarrativeAnalyzer:
    """Analyzes the story/narrative around a horse"""
    
    def analyze(self, horse_data: Dict, race_data: Dict) -> Dict:
        """Analyze narrative factors"""
        
        narrative_factors = []
        scores = []
        
        # 1. Class dropper narrative
        class_change = horse_data.get('class_change', 0)
        if class_change < 0:
            narrative_factors.append(f"CLASS DROPPER: Dropping {abs(class_change)} classes")
            scores.append(0.8)
        
        # 2. Return from layoff
        days_since_last_run = horse_data.get('days_since_last_run', 0)
        if 60 <= days_since_last_run <= 120:
            narrative_factors.append("FRESH RETURN: Optimal layoff period")
            scores.append(0.7)
        
        # 3. Course specialist
        course_wins = horse_data.get('course_wins', 0)
        course_runs = horse_data.get('course_runs', 1)
        if course_wins > 0 and (course_wins / course_runs) > 0.5:
            narrative_factors.append(f"COURSE SPECIALIST: {course_wins}/{course_runs} wins")
            scores.append(0.75)
        
        # 4. Improving form
        recent_form = horse_data.get('recent_form', '')
        if self._is_improving_form(recent_form):
            narrative_factors.append("IMPROVING FORM: Upward trajectory")
            scores.append(0.7)
        
        # 5. Big race angle
        if race_data.get('is_big_race', False):
            narrative_factors.append("BIG RACE TARGET: Prepared for this")
            scores.append(0.6)
        
        # Calculate scores
        if scores:
            narrative_shift_probability = np.mean(scores)
            narrative_power = np.max(scores)
        else:
            narrative_shift_probability = 0.3
            narrative_power = 0.3
        
        # Generate narrative description
        if narrative_factors:
            narrative = narrative_factors[0]  # Lead with strongest narrative
        else:
            narrative = "No strong narrative"
        
        return {
            'narrative_shift_probability': narrative_shift_probability,
            'narrative_power': narrative_power,
            'narrative': narrative,
            'factors': narrative_factors
        }
    
    def _is_improving_form(self, form: str) -> bool:
        """Check if form shows improvement"""
        if not form or len(form) < 3:
            return False
        
        # Simple check - are recent runs better than older runs?
        try:
            recent = [int(c) for c in form[:3] if c.isdigit()]
            if len(recent) >= 2:
                return recent[0] < recent[-1]  # Most recent better than older
        except:
            pass
        
        return False


class BehavioralIntelligence:
    """Models behavioral patterns of trainers, jockeys, owners"""
    
    def analyze(self, horse_data: Dict, race_data: Dict) -> Dict:
        """Analyze behavioral patterns"""
        
        patterns = []
        scores = []
        
        # 1. Trainer strike rate at course
        trainer_course_sr = horse_data.get('trainer_course_strike_rate', 0)
        if trainer_course_sr > 0.20:
            patterns.append(f"Trainer {trainer_course_sr*100:.0f}% strike rate at course")
            scores.append(0.7)
        
        # 2. Jockey/trainer combination
        jockey_trainer_combo = horse_data.get('jockey_trainer_combo_sr', 0)
        if jockey_trainer_combo > 0.25:
            patterns.append(f"Jockey/Trainer combo {jockey_trainer_combo*100:.0f}% strike rate")
            scores.append(0.75)
        
        # 3. Owner pattern
        owner = horse_data.get('owner', '')
        if self._is_big_owner(owner):
            patterns.append(f"Big owner {owner} - serious operation")
            scores.append(0.6)
        
        # 4. Historical pattern match
        if self._matches_winning_pattern(horse_data):
            patterns.append("Matches historical winning pattern")
            scores.append(0.8)
        
        # Calculate scores
        if scores:
            pattern_strength = np.mean(scores)
        else:
            pattern_strength = 0.3
        
        # Generate pattern description
        if patterns:
            pattern_description = patterns[0]
        else:
            pattern_description = "No strong behavioral patterns"
        
        return {
            'pattern_strength': pattern_strength,
            'pattern_description': pattern_description,
            'patterns': patterns
        }
    
    def _is_big_owner(self, owner: str) -> bool:
        """Check if owner is major player"""
        # Placeholder
        return False
    
    def _matches_winning_pattern(self, horse_data: Dict) -> bool:
        """Check if horse matches historical winning patterns"""
        # Placeholder - would check against historical patterns
        return False


class MarketManipulationRadar:
    """Detects market manipulation and artificial odds inflation"""
    
    def analyze(self, horse_data: Dict, race_data: Dict) -> Dict:
        """Detect manipulation signals"""
        
        manipulation_signals = []
        scores = []
        
        # 1. Odds drift without reason
        odds_drift = horse_data.get('odds_drift_24h', 0)
        if odds_drift > 3.0 and not self._has_negative_news(horse_data):
            manipulation_signals.append("Artificial odds inflation detected")
            scores.append(0.7)
        
        # 2. Late money pattern
        late_money = horse_data.get('late_money_pattern', False)
        if late_money:
            manipulation_signals.append("Late money pattern - possible manipulation")
            scores.append(0.6)
        
        # 3. Show pattern
        if self._is_show_pattern(horse_data):
            manipulation_signals.append("Show pattern detected - not serious")
            scores.append(0.8)
        
        # Calculate manipulation score
        if scores:
            manipulation_detected = np.mean(scores)
        else:
            manipulation_detected = 0.1
        
        return {
            'manipulation_detected': manipulation_detected,
            'signals': manipulation_signals,
            'is_genuine': manipulation_detected < 0.3
        }
    
    def _has_negative_news(self, horse_data: Dict) -> bool:
        """Check for negative news that would justify odds drift"""
        # Placeholder
        return False
    
    def _is_show_pattern(self, horse_data: Dict) -> bool:
        """Check if this looks like a 'show' run"""
        # Placeholder
        return False


# Example usage
if __name__ == "__main__":
    predictor = OddsMovementPredictor()
    
    # Sample horse data
    horse = {
        'name': 'SILVER SAMURAI',
        'current_odds': 20.0,
        'trainer': 'Marco Botti',
        'jockey': 'Ryan Moore',
        'class_change': -2,  # Dropping 2 classes
        'course_wins': 0,
        'course_runs': 1,
        'recent_form': '275769',
        'days_since_last_run': 21,
        'equipment_change': True,
        'trainer_course_strike_rate': 0.22,
        'jockey_trainer_combo_sr': 0.28
    }
    
    race = {
        'course': 'KEMPTON',
        'race_class': 3,
        'days_to_race': 2,
        'is_big_race': False
    }
    
    # Predict odds movement
    prediction = predictor.predict_odds_movement(horse, race)
    
    print("=" * 60)
    print("VÉLØ ORACLE - ODDS MOVEMENT PREDICTION")
    print("=" * 60)
    print(f"\nHorse: {horse['name']}")
    print(f"Current Odds: {horse['current_odds']}")
    print(f"\n{'Will Shorten:':<20} {'YES' if prediction['will_shorten'] else 'NO'}")
    print(f"{'Confidence:':<20} {prediction['confidence']*100:.1f}%")
    print(f"{'Target Odds:':<20} {prediction['predicted_movement']['target_odds']}")
    print(f"{'Movement:':<20} {prediction['predicted_movement']['movement_pct']}%")
    print(f"{'Timeframe:':<20} {prediction['timeframe']}")
    print(f"{'Expected Profit:':<20} {prediction['expected_profit_pct']}%")
    print(f"\n{'Recommendation:':<20} {prediction['recommended_action']}")
    print(f"{'Entry Odds:':<20} {prediction['entry_odds']}")
    print(f"{'Target Lay Odds:':<20} {prediction['target_lay_odds']}")
    
    print(f"\nReasons:")
    for reason in prediction['reasons']:
        print(f"  • {reason}")
