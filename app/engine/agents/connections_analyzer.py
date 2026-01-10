"""
Connections Analyzer Agent
Analyzes trainer and jockey performance, identifies "hot combos"
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConnectionsAnalysisResult:
    """Result from connections analysis"""
    score: float  # 0-100
    confidence: float  # 0-1
    evidence: Dict[str, Any]


class ConnectionsAnalyzer:
    """
    Analyzes trainer and jockey connections
    - Queries trainer_velocity and jockey_velocity tables
    - Calculates combined strike rate
    - Identifies "hot combos" (both profitable in last 14 days)
    """
    
    def __init__(self, supabase_client):
        """
        Initialize Connections Analyzer
        
        Args:
            supabase_client: Supabase client for database queries
        """
        self.client = supabase_client
        self.name = "connections_analyzer"
    
    def analyze(self, runner: Dict[str, Any], race_context: Dict[str, Any]) -> ConnectionsAnalysisResult:
        """
        Analyze trainer/jockey connections for a runner
        
        Args:
            runner: Runner data including trainer and jockey
            race_context: Race metadata
            
        Returns:
            ConnectionsAnalysisResult with score, confidence, and evidence
        """
        trainer = runner.get('trainer', '').strip()
        jockey = runner.get('jockey', '').strip()
        
        evidence = {
            'trainer': trainer,
            'jockey': jockey,
            'factors': []
        }
        
        # Query trainer stats
        trainer_stats = self._get_trainer_stats(trainer)
        jockey_stats = self._get_jockey_stats(jockey)
        
        # If no data available, return neutral score with low confidence
        if not trainer_stats and not jockey_stats:
            return ConnectionsAnalysisResult(
                score=50.0,
                confidence=0.2,
                evidence={**evidence, 'reason': 'No velocity data available'}
            )
        
        # Calculate score based on trainer and jockey performance
        score = 50.0  # Start at neutral
        confidence = 0.5
        
        # Trainer analysis (50% weight)
        if trainer_stats:
            trainer_score = self._score_trainer(trainer_stats, evidence)
            score += (trainer_score - 50) * 0.5
            confidence += 0.2
        
        # Jockey analysis (30% weight)
        if jockey_stats:
            jockey_score = self._score_jockey(jockey_stats, evidence)
            score += (jockey_score - 50) * 0.3
            confidence += 0.2
        
        # Hot combo bonus (20% weight)
        if trainer_stats and jockey_stats:
            hot_combo_bonus = self._check_hot_combo(trainer_stats, jockey_stats, evidence)
            score += hot_combo_bonus
            confidence = min(1.0, confidence + 0.1)
        
        # Clamp score to 0-100
        score = max(0, min(100, score))
        confidence = min(1.0, confidence)
        
        evidence['final_score'] = score
        
        return ConnectionsAnalysisResult(
            score=score,
            confidence=confidence,
            evidence=evidence
        )
    
    def _get_trainer_stats(self, trainer: str) -> Optional[Dict[str, Any]]:
        """Query trainer velocity stats from database"""
        if not trainer or not self.client:
            return None
        
        try:
            result = self.client.table('trainer_velocity') \
                .select('*') \
                .eq('trainer_name', trainer) \
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
        except Exception as e:
            logger.warning(f"Failed to query trainer stats for {trainer}: {e}")
        
        return None
    
    def _get_jockey_stats(self, jockey: str) -> Optional[Dict[str, Any]]:
        """Query jockey velocity stats from database"""
        if not jockey or not self.client:
            return None
        
        try:
            result = self.client.table('jockey_velocity') \
                .select('*') \
                .eq('jockey_name', jockey) \
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
        except Exception as e:
            logger.warning(f"Failed to query jockey stats for {jockey}: {e}")
        
        return None
    
    def _score_trainer(self, stats: Dict[str, Any], evidence: Dict[str, Any]) -> float:
        """
        Score trainer based on velocity stats
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Last 14 days strike rate (most important)
        last_14d_sr = stats.get('last_14d_sr', 0)
        if last_14d_sr > 0:
            # SR > 25% = excellent, SR 15-25% = good, SR 10-15% = average
            if last_14d_sr >= 25:
                score += 25
                evidence['factors'].append(f'Trainer hot: {last_14d_sr:.1f}% SR (+25)')
            elif last_14d_sr >= 15:
                score += 15
                evidence['factors'].append(f'Trainer good form: {last_14d_sr:.1f}% SR (+15)')
            elif last_14d_sr >= 10:
                score += 5
                evidence['factors'].append(f'Trainer average: {last_14d_sr:.1f}% SR (+5)')
            else:
                score -= 10
                evidence['factors'].append(f'Trainer cold: {last_14d_sr:.1f}% SR (-10)')
        
        # Last 14 days profit/loss
        last_14d_pl = stats.get('last_14d_pl', 0)
        if last_14d_pl > 10:
            score += 10
            evidence['factors'].append(f'Trainer profitable: +£{last_14d_pl:.2f} (+10)')
        elif last_14d_pl < -10:
            score -= 5
            evidence['factors'].append(f'Trainer unprofitable: £{last_14d_pl:.2f} (-5)')
        
        # Overall strike rate (minor influence)
        overall_sr = stats.get('overall_sr', 0)
        if overall_sr >= 20:
            score += 5
            evidence['factors'].append(f'Top overall trainer: {overall_sr:.1f}% (+5)')
        
        evidence['trainer_stats'] = {
            'last_14d_sr': last_14d_sr,
            'last_14d_pl': last_14d_pl,
            'overall_sr': overall_sr
        }
        
        return score
    
    def _score_jockey(self, stats: Dict[str, Any], evidence: Dict[str, Any]) -> float:
        """
        Score jockey based on velocity stats
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Last 14 days strike rate
        last_14d_sr = stats.get('last_14d_sr', 0)
        if last_14d_sr > 0:
            if last_14d_sr >= 20:
                score += 20
                evidence['factors'].append(f'Jockey in form: {last_14d_sr:.1f}% SR (+20)')
            elif last_14d_sr >= 15:
                score += 10
                evidence['factors'].append(f'Jockey good: {last_14d_sr:.1f}% SR (+10)')
            elif last_14d_sr < 8:
                score -= 10
                evidence['factors'].append(f'Jockey struggling: {last_14d_sr:.1f}% SR (-10)')
        
        # Last 14 days profit/loss
        last_14d_pl = stats.get('last_14d_pl', 0)
        if last_14d_pl > 10:
            score += 10
            evidence['factors'].append(f'Jockey profitable: +£{last_14d_pl:.2f} (+10)')
        
        evidence['jockey_stats'] = {
            'last_14d_sr': last_14d_sr,
            'last_14d_pl': last_14d_pl
        }
        
        return score
    
    def _check_hot_combo(
        self,
        trainer_stats: Dict[str, Any],
        jockey_stats: Dict[str, Any],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Check if trainer/jockey is a "hot combo"
        Hot combo = both profitable in last 14 days
        
        Returns:
            Bonus score (0-20)
        """
        trainer_pl = trainer_stats.get('last_14d_pl', 0)
        jockey_pl = jockey_stats.get('last_14d_pl', 0)
        trainer_sr = trainer_stats.get('last_14d_sr', 0)
        jockey_sr = jockey_stats.get('last_14d_sr', 0)
        
        # Hot combo: both profitable AND good strike rates
        if trainer_pl > 5 and jockey_pl > 5 and trainer_sr > 15 and jockey_sr > 15:
            evidence['factors'].append('🔥 HOT COMBO: Both in excellent form (+20)')
            return 20
        
        # Warm combo: both profitable
        if trainer_pl > 0 and jockey_pl > 0:
            evidence['factors'].append('Solid combo: Both profitable (+10)')
            return 10
        
        return 0
