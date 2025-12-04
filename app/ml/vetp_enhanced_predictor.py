"""
VETP-Enhanced Prediction Engine

This is where VETP Layer 1 (memory) meets SQPE (prediction).

Instead of treating every race the same, we now:
1. Check for pattern matches (Mesaafi trap, Castanea dominance, etc)
2. Adjust confidence based on lived experience
3. Apply learned rules before making predictions

This is how VÉLØ stops being a dumb model and becomes a learning system.
"""

import pickle
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..vetp import VETPLayer1


class VETPEnhancedPredictor:
    """
    Prediction engine enhanced with VETP memory.
    
    Flow:
    1. Load base SQPE model
    2. Check VETP patterns for the race context
    3. Apply confidence adjustments
    4. Generate prediction with context-aware warnings
    """
    
    def __init__(self, model_path: str, vetp_db_path: str):
        """
        Initialize with SQPE model and VETP memory.
        
        Args:
            model_path: Path to trained SQPE model (.pkl)
            vetp_db_path: Path to VETP SQLite database
        """
        # Load SQPE model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Connect to VETP memory
        engine = create_engine(f"sqlite:///{vetp_db_path}")
        SessionLocal = sessionmaker(bind=engine)
        self.vetp = VETPLayer1(SessionLocal())
    
    def predict_with_context(
        self,
        race_data: pd.DataFrame,
        race_context: Dict
    ) -> Dict:
        """
        Make prediction with VETP context awareness.
        
        Args:
            race_data: DataFrame with features (odds, age, runners, draw)
            race_context: Dict with {
                'course': str,
                'code': str,  # Flat-AW, Hurdle, etc
                'race_class': str,
                'field_size': int,
                'fav_sp': float,
                'date': date
            }
        
        Returns:
            Dict with predictions + VETP warnings/adjustments
        """
        # Base prediction
        base_probs = self.model.predict_proba(race_data)[:, 1]
        
        # Check VETP patterns
        warnings = []
        confidence_multiplier = 1.0
        recommended_action = "PROCEED"
        
        # Pattern 1: Mesaafi Trap (Fake Fav in AW Handicap)
        if self._is_mesaafi_trap_context(race_context):
            warnings.append("⚠️  MESAAFI TRAP PATTERN: Short-priced AW fav in messy handicap")
            warnings.append("   Historical: These are designed traps, not insurance")
            confidence_multiplier *= 0.5  # Halve confidence
            recommended_action = "LAY_FAV or NO_BET"
        
        # Pattern 2: Castanea Dominance (Clear Best Horse)
        if self._is_castanea_dominance_context(race_context, race_data):
            warnings.append("✅ CASTANEA PATTERN: Dominant engine in weak field")
            warnings.append("   Historical: When one horse is clearly best, it usually wins")
            confidence_multiplier *= 1.5  # Increase confidence
            recommended_action = "STRONG_WIN_PLAY"
        
        # Pattern 3: Small Field Hype Trap
        if self._is_small_field_hype_trap(race_context):
            warnings.append("⚠️  SMALL-FIELD HYPE: Media monster in tiny field")
            warnings.append("   Historical: Jumps = risk. Short fields = chaos magnifier")
            confidence_multiplier *= 0.3  # Massively reduce confidence
            recommended_action = "LAY_SHORTY or PASS"
        
        # Pattern 4: Kempton Kicker Advantage
        if self._is_kempton_kicker_context(race_context):
            warnings.append("💡 KEMPTON KICKER ADVANTAGE: Turn of foot > static speed here")
            confidence_multiplier *= 1.2
        
        # Adjusted predictions
        adjusted_probs = base_probs * confidence_multiplier
        adjusted_probs = np.clip(adjusted_probs, 0, 1)  # Keep in [0,1]
        
        # Get VETP statistics for this pattern
        pattern_stats = self._get_pattern_stats(race_context)
        
        return {
            'base_probabilities': base_probs.tolist(),
            'adjusted_probabilities': adjusted_probs.tolist(),
            'confidence_multiplier': confidence_multiplier,
            'warnings': warnings,
            'recommended_action': recommended_action,
            'pattern_stats': pattern_stats,
            'vetp_memory_active': True
        }
    
    def _is_mesaafi_trap_context(self, context: Dict) -> bool:
        """
        Check if race matches Mesaafi trap pattern.
        
        Trigger:
        - Code = Flat-AW
        - Class in C3–C6 hcp
        - Fav < 2.5
        - Field has 3–5 plausible alternatives
        """
        if context.get('code') != 'Flat-AW':
            return False
        
        race_class = context.get('race_class', '')
        if not any(c in race_class for c in ['C3', 'C4', 'C5', 'C6']):
            return False
        
        fav_sp = context.get('fav_sp', 999)
        if fav_sp >= 2.5:
            return False
        
        field_size = context.get('field_size', 0)
        if field_size < 8:  # Need decent field for "messy"
            return False
        
        return True
    
    def _is_castanea_dominance_context(self, context: Dict, race_data: pd.DataFrame) -> bool:
        """
        Check if race matches Castanea dominance pattern.
        
        Trigger:
        - One horse clearly top on ratings
        - Next 2-3 a step down
        - Field mostly exposed types
        """
        if len(race_data) < 5:
            return False
        
        # Check if there's a clear ratings gap
        # (In real implementation, would check TS/RPR data)
        # For now, use odds as proxy
        if 'odds_decimal' in race_data.columns:
            odds = race_data['odds_decimal'].values
            if len(odds) > 0:
                fav_odds = min(odds)
                second_fav = sorted(odds)[1] if len(odds) > 1 else 999
                
                # Clear favorite with gap to second
                if fav_odds < 5.0 and (second_fav / fav_odds) > 1.3:
                    return True
        
        return False
    
    def _is_small_field_hype_trap(self, context: Dict) -> bool:
        """
        Check if race matches small-field hype trap.
        
        Trigger:
        - Field_Size ≤ 6
        - Fav very short (< 1.5)
        - Jumps race
        """
        field_size = context.get('field_size', 999)
        if field_size > 6:
            return False
        
        fav_sp = context.get('fav_sp', 999)
        if fav_sp >= 1.5:
            return False
        
        code = context.get('code', '')
        if code not in ['Hurdle', 'Chase']:
            return False
        
        return True
    
    def _is_kempton_kicker_context(self, context: Dict) -> bool:
        """Check if race is at Kempton AW"""
        return (
            context.get('course', '').lower() == 'kempton' and
            context.get('code') == 'Flat-AW'
        )
    
    def _get_pattern_stats(self, context: Dict) -> Dict:
        """Get VETP statistics for similar races"""
        stats = self.vetp.get_stats()
        
        # Get pattern-specific counts
        mesaafi_count = len(self.vetp.mesaafi_trap_candidates(limit=1000))
        castanea_count = len(self.vetp.castanea_dominance_cases(limit=1000))
        hype_trap_count = len(self.vetp.small_field_hype_traps(limit=1000))
        
        return {
            'total_memory_events': stats['total_events'],
            'mesaafi_traps_logged': mesaafi_count,
            'castanea_dominance_logged': castanea_count,
            'hype_traps_logged': hype_trap_count,
            'total_pnl': stats['total_pnl_units']
        }
    
    def log_race_result(
        self,
        event_id: str,
        race_context: Dict,
        our_play: Dict,
        result: Dict,
        emotion: str
    ):
        """
        Log race result to VETP memory.
        
        This is how VÉLØ learns from every race.
        """
        from ..vetp import VETPEventIn, KeyRival
        
        event = VETPEventIn(
            event_id=event_id,
            date=race_context['date'],
            course=race_context['course'],
            code=race_context['code'],
            race_class=race_context.get('race_class'),
            field_size=race_context.get('field_size'),
            fav_sp=race_context.get('fav_sp'),
            
            our_play_type=our_play.get('type'),
            our_play_horses=our_play.get('horses'),
            our_play_stakes=our_play.get('stakes'),
            
            winner=result.get('winner'),
            places=result.get('places'),
            pnl_units=result.get('pnl'),
            read_race_right=result.get('correct'),
            
            behaviour_flags=result.get('flags'),
            market_story=result.get('market_narrative'),
            reality_story=result.get('what_happened'),
            key_learning=result.get('learning'),
            
            emotion_tag=emotion
        )
        
        return self.vetp.log_event(event)


def create_vetp_predictor(
    model_path: str = "/home/ubuntu/velo-oracle/models/sqpe_v15/sqpe_v15.pkl",
    vetp_db_path: str = "/home/ubuntu/velo-oracle/data/vetp_memory.db"
) -> VETPEnhancedPredictor:
    """Factory function to create VETP-enhanced predictor"""
    return VETPEnhancedPredictor(model_path, vetp_db_path)
