"""
Ratings Analyzer Agent
Analyzes ratings (OR, TS, RPR, Master) to identify well-handicapped horses
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class RatingsAnalysisResult:
    """Result from ratings analysis"""
    score: float  # 0-100
    confidence: float  # 0-1
    evidence: Dict[str, Any]


class RatingsAnalyzer:
    """
    Analyzes ratings to find value
    - Uses OR/TS/RPR/Master ratings
    - Calculates race average OR
    - Identifies well-handicapped horses (rating vs field)
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize Ratings Analyzer
        
        Args:
            supabase_client: Supabase client (not used in this agent)
        """
        self.client = supabase_client
        self.name = "ratings_analyzer"
    
    def analyze(self, runner: Dict[str, Any], race_context: Dict[str, Any]) -> RatingsAnalysisResult:
        """
        Analyze ratings for a runner
        
        Args:
            runner: Runner data including OR, RPR, TS ratings
            race_context: Race metadata including all runners
            
        Returns:
            RatingsAnalysisResult with score, confidence, and evidence
        """
        horse_name = runner.get('horse_name', '')
        or_rating = runner.get('or_rating') or runner.get('or') or 0
        rpr = runner.get('rpr', 0)
        ts = runner.get('ts', 0)
        
        evidence = {
            'horse_name': horse_name,
            'or_rating': or_rating,
            'rpr': rpr,
            'ts': ts,
            'factors': []
        }
        
        # If no ratings available, return neutral score
        if not any([or_rating, rpr, ts]):
            return RatingsAnalysisResult(
                score=50.0,
                confidence=0.2,
                evidence={**evidence, 'reason': 'No ratings data available'}
            )
        
        # Get all runners for race average calculation
        all_runners = race_context.get('runners', [])
        
        # Calculate score
        score = 50.0  # Start at neutral
        confidence = 0.6
        
        # 1. OR rating analysis (40% weight)
        if or_rating > 0:
            or_score = self._analyze_or_rating(or_rating, all_runners, evidence)
            score += (or_score - 50) * 0.4
            confidence += 0.15
        
        # 2. RPR analysis (30% weight)
        if rpr > 0:
            rpr_score = self._analyze_rpr(rpr, all_runners, evidence)
            score += (rpr_score - 50) * 0.3
            confidence += 0.1
        
        # 3. TS analysis (30% weight)
        if ts > 0:
            ts_score = self._analyze_ts(ts, all_runners, evidence)
            score += (ts_score - 50) * 0.3
            confidence += 0.1
        
        # Clamp score to 0-100
        score = max(0, min(100, score))
        confidence = min(1.0, confidence)
        
        evidence['final_score'] = score
        
        return RatingsAnalysisResult(
            score=score,
            confidence=confidence,
            evidence=evidence
        )
    
    def _analyze_or_rating(
        self,
        or_rating: int,
        all_runners: List[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Analyze OR (Official Rating) relative to field
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Get all OR ratings in race
        all_or = [
            r.get('or_rating') or r.get('or', 0)
            for r in all_runners
            if (r.get('or_rating') or r.get('or', 0)) > 0
        ]
        
        if not all_or or len(all_or) < 2:
            return score
        
        # Calculate statistics
        avg_or = statistics.mean(all_or)
        max_or = max(all_or)
        
        # Horse's position relative to field
        diff_from_avg = or_rating - avg_or
        diff_from_top = or_rating - max_or
        
        evidence['or_avg'] = avg_or
        evidence['or_max'] = max_or
        
        # Top-rated horse
        if diff_from_top == 0:
            score += 35
            evidence['factors'].append(f'Top-rated (OR {or_rating}) (+35)')
        
        # Well above average
        elif diff_from_avg > 5:
            score += 25
            evidence['factors'].append(
                f'Well-handicapped (OR {or_rating} vs avg {avg_or:.1f}) (+25)'
            )
        
        # Above average
        elif diff_from_avg > 0:
            score += 15
            evidence['factors'].append(
                f'Above average (OR {or_rating} vs avg {avg_or:.1f}) (+15)'
            )
        
        # Below average
        elif diff_from_avg < -5:
            score -= 20
            evidence['factors'].append(
                f'Below average (OR {or_rating} vs avg {avg_or:.1f}) (-20)'
            )
        
        return score
    
    def _analyze_rpr(
        self,
        rpr: int,
        all_runners: List[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Analyze RPR (Racing Post Rating)
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Get all RPR in race
        all_rpr = [
            r.get('rpr', 0)
            for r in all_runners
            if r.get('rpr', 0) > 0
        ]
        
        if not all_rpr or len(all_rpr) < 2:
            return score
        
        # Calculate statistics
        avg_rpr = statistics.mean(all_rpr)
        max_rpr = max(all_rpr)
        
        # Horse's position relative to field
        diff_from_avg = rpr - avg_rpr
        diff_from_top = rpr - max_rpr
        
        evidence['rpr_avg'] = avg_rpr
        evidence['rpr_max'] = max_rpr
        
        # Top RPR
        if diff_from_top == 0:
            score += 30
            evidence['factors'].append(f'Best RPR ({rpr}) (+30)')
        
        # Well above average
        elif diff_from_avg > 5:
            score += 20
            evidence['factors'].append(
                f'Strong RPR ({rpr} vs avg {avg_rpr:.1f}) (+20)'
            )
        
        # Above average
        elif diff_from_avg > 0:
            score += 10
            evidence['factors'].append(
                f'Above avg RPR ({rpr} vs avg {avg_rpr:.1f}) (+10)'
            )
        
        # Well below average
        elif diff_from_avg < -8:
            score -= 25
            evidence['factors'].append(
                f'Poor RPR ({rpr} vs avg {avg_rpr:.1f}) (-25)'
            )
        
        return score
    
    def _analyze_ts(
        self,
        ts: int,
        all_runners: List[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Analyze TS (Topspeed Rating)
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Get all TS in race
        all_ts = [
            r.get('ts', 0)
            for r in all_runners
            if r.get('ts', 0) > 0
        ]
        
        if not all_ts or len(all_ts) < 2:
            return score
        
        # Calculate statistics
        avg_ts = statistics.mean(all_ts)
        max_ts = max(all_ts)
        
        # Horse's position relative to field
        diff_from_avg = ts - avg_ts
        diff_from_top = ts - max_ts
        
        evidence['ts_avg'] = avg_ts
        evidence['ts_max'] = max_ts
        
        # Top TS
        if diff_from_top == 0:
            score += 30
            evidence['factors'].append(f'Best TS ({ts}) (+30)')
        
        # Well above average
        elif diff_from_avg > 5:
            score += 20
            evidence['factors'].append(
                f'Strong TS ({ts} vs avg {avg_ts:.1f}) (+20)'
            )
        
        # Above average
        elif diff_from_avg > 0:
            score += 10
            evidence['factors'].append(
                f'Above avg TS ({ts} vs avg {avg_ts:.1f}) (+10)'
            )
        
        # Well below average
        elif diff_from_avg < -8:
            score -= 25
            evidence['factors'].append(
                f'Poor TS ({ts} vs avg {avg_ts:.1f}) (-25)'
            )
        
        return score
