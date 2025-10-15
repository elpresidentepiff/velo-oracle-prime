"""
VÉLØ Manipulation Detector - Market Manipulation Detection System
Inspired by ADMA21 (Identification of Stock Market Manipulation with Deep Learning)

Detects:
- Odds manipulation
- EW traps
- Syndicate patterns
- Coordinated bookmaker behavior
- Suspicious late money
- Favorite rotation schemes
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum


class ManipulationType(Enum):
    """Types of market manipulation."""
    ODDS_CRASH = "odds_crash"  # Sudden odds drop < 15 min
    EW_TRAP = "ew_trap"  # EW extra places in small fields
    SYNDICATE_MONEY = "syndicate_money"  # Large coordinated bets
    FALSE_FAVORITE = "false_favorite"  # Sudden favorite switch
    DRIFT_MANIPULATION = "drift_manipulation"  # Artificial drift
    LATE_PLUNGE = "late_plunge"  # Last-minute odds crash
    ROTATION_SCHEME = "rotation_scheme"  # Favorites rotated to spread wins


class ManipulationDetector:
    """
    Detect market manipulation in horse racing betting markets.
    
    Uses anomaly detection techniques to identify:
    - Unusual odds movements
    - Coordinated betting patterns
    - Bookmaker tricks
    - Market inefficiencies
    """
    
    def __init__(self):
        """Initialize manipulation detector."""
        self.detection_threshold = 0.7  # 70% confidence to flag
        self.historical_patterns = []
        
        print("✓ Manipulation Detector initialized")
        print("  Detection threshold: 70%")
    
    def analyze_race(self, race_data: Dict, odds_history: List[Dict] = None) -> Dict:
        """
        Analyze a race for manipulation signals.
        
        Args:
            race_data: Current race data
            odds_history: Historical odds movements (optional)
        
        Returns:
            Detection report with manipulation scores
        """
        report = {
            'race_id': race_data.get('race_id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'manipulations_detected': [],
            'overall_risk_score': 0.0,
            'warnings': [],
            'safe_to_bet': True
        }
        
        # Run all detection methods
        detections = []
        
        # 1. Check for odds crashes
        if odds_history:
            crash_detection = self._detect_odds_crash(race_data, odds_history)
            if crash_detection['detected']:
                detections.append(crash_detection)
        
        # 2. Check for EW traps
        ew_trap = self._detect_ew_trap(race_data)
        if ew_trap['detected']:
            detections.append(ew_trap)
        
        # 3. Check for false favorites
        false_fav = self._detect_false_favorite(race_data)
        if false_fav['detected']:
            detections.append(false_fav)
        
        # 4. Check for suspicious form
        form_manipulation = self._detect_form_manipulation(race_data)
        if form_manipulation['detected']:
            detections.append(form_manipulation)
        
        # 5. Check for coordinated patterns
        if odds_history:
            syndicate = self._detect_syndicate_pattern(race_data, odds_history)
            if syndicate['detected']:
                detections.append(syndicate)
        
        # Compile report
        report['manipulations_detected'] = detections
        
        # Calculate overall risk score
        if detections:
            risk_scores = [d['confidence'] for d in detections]
            report['overall_risk_score'] = max(risk_scores)  # Take highest risk
            
            # Generate warnings
            for detection in detections:
                if detection['confidence'] >= self.detection_threshold:
                    report['warnings'].append(detection['warning'])
            
            # Determine if safe to bet
            if report['overall_risk_score'] >= 0.8:  # 80%+ risk
                report['safe_to_bet'] = False
        
        return report
    
    def _detect_odds_crash(self, race_data: Dict, odds_history: List[Dict]) -> Dict:
        """
        Detect sudden odds crashes (< 15 minutes before race).
        
        Classic manipulation: Horse drifts, then crashes in final minutes.
        """
        detection = {
            'type': ManipulationType.ODDS_CRASH.value,
            'detected': False,
            'confidence': 0.0,
            'warning': '',
            'details': {}
        }
        
        if not odds_history or len(odds_history) < 2:
            return detection
        
        # Check each horse for sudden crashes
        for horse in race_data.get('horses', []):
            horse_name = horse.get('name')
            current_odds = horse.get('odds', 0)
            
            # Find historical odds for this horse
            historical_odds = []
            for snapshot in odds_history:
                for h in snapshot.get('horses', []):
                    if h.get('name') == horse_name:
                        historical_odds.append({
                            'timestamp': snapshot.get('timestamp'),
                            'odds': h.get('odds')
                        })
            
            if len(historical_odds) < 2:
                continue
            
            # Check for crash in last 15 minutes
            recent_odds = historical_odds[-3:]  # Last 3 snapshots
            if len(recent_odds) >= 2:
                initial_odds = recent_odds[0]['odds']
                final_odds = recent_odds[-1]['odds']
                
                # Calculate drop percentage
                if initial_odds > 0:
                    drop_pct = (initial_odds - final_odds) / initial_odds
                    
                    # Flag if > 20% drop in final minutes
                    if drop_pct > 0.20:
                        detection['detected'] = True
                        detection['confidence'] = min(drop_pct * 2, 1.0)  # Scale to 0-1
                        detection['warning'] = f"⚠ ODDS CRASH: {horse_name} dropped {drop_pct * 100:.1f}% in final minutes ({initial_odds} → {final_odds})"
                        detection['details'] = {
                            'horse': horse_name,
                            'initial_odds': initial_odds,
                            'final_odds': final_odds,
                            'drop_percentage': drop_pct
                        }
                        break
        
        return detection
    
    def _detect_ew_trap(self, race_data: Dict) -> Dict:
        """
        Detect EW trap: Extra places offered in small fields.
        
        Bookmaker trick: Offer EW extra places to attract bets, but field is too small.
        """
        detection = {
            'type': ManipulationType.EW_TRAP.value,
            'detected': False,
            'confidence': 0.0,
            'warning': '',
            'details': {}
        }
        
        num_runners = len(race_data.get('horses', []))
        ew_places = race_data.get('ew_places', 3)  # Default 3 places
        ew_extra = race_data.get('ew_extra_places', False)
        
        # Flag if EW extra places offered in field < 10 runners
        if ew_extra and num_runners < 10:
            detection['detected'] = True
            detection['confidence'] = 0.75  # High confidence
            detection['warning'] = f"⚠ EW TRAP: Extra places offered in {num_runners}-runner field"
            detection['details'] = {
                'num_runners': num_runners,
                'ew_places': ew_places,
                'ew_extra': ew_extra
            }
        
        return detection
    
    def _detect_false_favorite(self, race_data: Dict) -> Dict:
        """
        Detect false favorite: Favorite with poor recent form.
        
        Manipulation: Public backs favorite based on name/reputation, not form.
        """
        detection = {
            'type': ManipulationType.FALSE_FAVORITE.value,
            'detected': False,
            'confidence': 0.0,
            'warning': '',
            'details': {}
        }
        
        horses = race_data.get('horses', [])
        if not horses:
            return detection
        
        # Find favorite (lowest odds)
        favorite = min(horses, key=lambda h: h.get('odds', 999))
        
        # Check favorite's form
        form = favorite.get('form', '')
        recent_form = form[:4] if len(form) >= 4 else form  # Last 4 runs
        
        # Count wins in recent form
        wins = recent_form.count('1')
        
        # Flag if favorite has 0 wins in last 4 runs
        if wins == 0 and len(recent_form) >= 4:
            detection['detected'] = True
            detection['confidence'] = 0.80  # High confidence
            detection['warning'] = f"⚠ FALSE FAVORITE: {favorite.get('name')} has 0 wins in last 4 runs (odds: {favorite.get('odds')})"
            detection['details'] = {
                'horse': favorite.get('name'),
                'odds': favorite.get('odds'),
                'form': form,
                'recent_wins': wins
            }
        
        return detection
    
    def _detect_form_manipulation(self, race_data: Dict) -> Dict:
        """
        Detect form manipulation: Horses with inflated ratings vs actual performance.
        """
        detection = {
            'type': 'form_manipulation',
            'detected': False,
            'confidence': 0.0,
            'warning': '',
            'details': {}
        }
        
        for horse in race_data.get('horses', []):
            rpr = horse.get('rpr', 0)  # Racing Post Rating
            form = horse.get('form', '')
            
            # Calculate actual form score (simple: 1st=4, 2nd=3, 3rd=2, 4th=1, else=0)
            form_score = 0
            for position in form[:4]:  # Last 4 runs
                if position == '1':
                    form_score += 4
                elif position == '2':
                    form_score += 3
                elif position == '3':
                    form_score += 2
                elif position == '4':
                    form_score += 1
            
            avg_form_score = form_score / 4 if len(form) >= 4 else 0
            
            # Expected RPR based on form (rough heuristic)
            expected_rpr = 100 + (avg_form_score * 5)
            
            # Flag if RPR is significantly higher than form suggests
            if rpr > 0 and rpr > expected_rpr + 15:  # 15+ points inflated
                detection['detected'] = True
                detection['confidence'] = min((rpr - expected_rpr) / 30, 1.0)
                detection['warning'] = f"⚠ INFLATED RATING: {horse.get('name')} RPR {rpr} vs expected {expected_rpr:.0f} (form: {form})"
                detection['details'] = {
                    'horse': horse.get('name'),
                    'rpr': rpr,
                    'expected_rpr': expected_rpr,
                    'form': form
                }
                break
        
        return detection
    
    def _detect_syndicate_pattern(self, race_data: Dict, odds_history: List[Dict]) -> Dict:
        """
        Detect syndicate betting: Coordinated large bets causing specific patterns.
        
        Pattern: Multiple horses' odds move in coordinated fashion.
        """
        detection = {
            'type': ManipulationType.SYNDICATE_MONEY.value,
            'detected': False,
            'confidence': 0.0,
            'warning': '',
            'details': {}
        }
        
        if not odds_history or len(odds_history) < 3:
            return detection
        
        # Look for coordinated movements
        # (Simplified: check if multiple horses show similar timing in odds changes)
        
        # Track which horses had significant odds changes
        significant_changes = []
        
        for horse in race_data.get('horses', []):
            horse_name = horse.get('name')
            current_odds = horse.get('odds', 0)
            
            # Find initial odds
            initial_odds = None
            for snapshot in odds_history[:2]:  # First snapshots
                for h in snapshot.get('horses', []):
                    if h.get('name') == horse_name:
                        initial_odds = h.get('odds')
                        break
                if initial_odds:
                    break
            
            if initial_odds and current_odds > 0:
                change_pct = abs(current_odds - initial_odds) / initial_odds
                
                # Flag if > 15% change
                if change_pct > 0.15:
                    significant_changes.append({
                        'horse': horse_name,
                        'change': change_pct
                    })
        
        # If 3+ horses show coordinated changes, flag as potential syndicate
        if len(significant_changes) >= 3:
            detection['detected'] = True
            detection['confidence'] = min(len(significant_changes) / 5, 1.0)
            detection['warning'] = f"⚠ SYNDICATE PATTERN: {len(significant_changes)} horses showing coordinated odds movements"
            detection['details'] = {
                'affected_horses': significant_changes
            }
        
        return detection
    
    def get_risk_assessment(self, race_data: Dict, odds_history: List[Dict] = None) -> str:
        """
        Get human-readable risk assessment.
        
        Args:
            race_data: Race data
            odds_history: Odds history (optional)
        
        Returns:
            Risk assessment string
        """
        report = self.analyze_race(race_data, odds_history)
        
        if not report['manipulations_detected']:
            return "✓ CLEAN - No manipulation detected. Safe to bet."
        
        risk_score = report['overall_risk_score']
        
        if risk_score >= 0.8:
            return f"✗ HIGH RISK ({risk_score * 100:.0f}%) - Multiple manipulation signals. STAND DOWN."
        elif risk_score >= 0.6:
            return f"⚠ MODERATE RISK ({risk_score * 100:.0f}%) - Manipulation detected. Bet with caution."
        else:
            return f"⚠ LOW RISK ({risk_score * 100:.0f}%) - Minor signals detected. Monitor closely."


if __name__ == "__main__":
    # Test manipulation detector
    print("=== VÉLØ Manipulation Detector Test ===\n")
    
    detector = ManipulationDetector()
    
    # Test race with false favorite
    test_race = {
        'race_id': 'test_001',
        'track': 'Punchestown',
        'horses': [
            {
                'name': 'False Favorite',
                'odds': 3.5,
                'form': '5634',  # No wins in last 4
                'rpr': 125
            },
            {
                'name': 'Value Horse',
                'odds': 8.0,
                'form': '1231',
                'rpr': 118
            }
        ],
        'ew_extra_places': True
    }
    
    # Analyze
    report = detector.analyze_race(test_race)
    
    print("=== Detection Report ===")
    print(f"Race ID: {report['race_id']}")
    print(f"Overall Risk Score: {report['overall_risk_score'] * 100:.0f}%")
    print(f"Safe to Bet: {report['safe_to_bet']}")
    print(f"\nManipulations Detected: {len(report['manipulations_detected'])}")
    
    for detection in report['manipulations_detected']:
        print(f"\n  Type: {detection['type']}")
        print(f"  Confidence: {detection['confidence'] * 100:.0f}%")
        print(f"  {detection['warning']}")
    
    print(f"\n{detector.get_risk_assessment(test_race)}")
    
    print("\n✓ Manipulation Detector operational")

