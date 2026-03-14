"""
Market Analyzer Agent
Analyzes odds and market position to identify value bets
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysisResult:
    """Result from market analysis"""
    score: float  # 0-100
    confidence: float  # 0-1
    evidence: Dict[str, Any]


class MarketAnalyzer:
    """
    Analyzes market odds and position
    - Analyzes odds
    - Compares market rank vs ratings rank
    - Identifies value bets (underpriced in market)
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize Market Analyzer
        
        Args:
            supabase_client: Supabase client (not used in this agent)
        """
        self.client = supabase_client
        self.name = "market_analyzer"
    
    def analyze(self, runner: Dict[str, Any], race_context: Dict[str, Any]) -> MarketAnalysisResult:
        """
        Analyze market position for a runner
        
        Args:
            runner: Runner data including odds
            race_context: Race metadata including all runners
            
        Returns:
            MarketAnalysisResult with score, confidence, and evidence
        """
        horse_name = runner.get('horse_name', '')
        
        # Try different odds field names
        odds = (
            runner.get('odds') or 
            runner.get('win_odds') or 
            runner.get('sp') or 
            0
        )
        
        or_rating = runner.get('or_rating') or runner.get('or') or 0
        
        evidence = {
            'horse_name': horse_name,
            'odds': odds,
            'or_rating': or_rating,
            'factors': []
        }
        
        # If no odds available, return neutral score
        if not odds or odds <= 0:
            return MarketAnalysisResult(
                score=50.0,
                confidence=0.2,
                evidence={**evidence, 'reason': 'No odds data available'}
            )
        
        # Get all runners for comparison
        all_runners = race_context.get('runners', [])
        
        # Calculate score
        score = 50.0  # Start at neutral
        confidence = 0.6
        
        # 1. Odds range check (15% weight)
        odds_score = self._analyze_odds_range(odds, evidence)
        score += (odds_score - 50) * 0.15
        
        # 2. Market rank vs ratings rank (50% weight)
        if or_rating > 0:
            rank_score = self._analyze_market_vs_ratings(
                runner, all_runners, evidence
            )
            score += (rank_score - 50) * 0.5
            confidence += 0.2
        
        # 3. Value analysis (35% weight)
        value_score = self._analyze_value(odds, or_rating, all_runners, evidence)
        score += (value_score - 50) * 0.35
        confidence += 0.1
        
        # Clamp score to 0-100
        score = max(0, min(100, score))
        confidence = min(1.0, confidence)
        
        evidence['final_score'] = score
        
        return MarketAnalysisResult(
            score=score,
            confidence=confidence,
            evidence=evidence
        )
    
    def _analyze_odds_range(self, odds: float, evidence: Dict[str, Any]) -> float:
        """
        Analyze if odds are in optimal betting range
        Prefer odds between 3/1 (4.0) and 20/1 (21.0)
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Sweet spot: 4.0 to 15.0
        if 4.0 <= odds <= 15.0:
            score += 20
            evidence['factors'].append(f'Optimal odds range ({odds:.1f}) (+20)')
        
        # Acceptable: 3.0 to 20.0
        elif 3.0 <= odds <= 21.0:
            score += 10
            evidence['factors'].append(f'Acceptable odds ({odds:.1f}) (+10)')
        
        # Too short (favorite)
        elif odds < 3.0:
            score -= 15
            evidence['factors'].append(f'Odds too short ({odds:.1f}) (-15)')
        
        # Too long (outsider)
        elif odds > 21.0:
            score -= 20
            evidence['factors'].append(f'Odds too long ({odds:.1f}) (-20)')
        
        return score
    
    def _analyze_market_vs_ratings(
        self,
        runner: Dict[str, Any],
        all_runners: List[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Compare market rank (by odds) vs ratings rank
        Value = rated higher than market position suggests
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Get odds for this runner
        odds = (
            runner.get('odds') or 
            runner.get('win_odds') or 
            runner.get('sp') or 
            0
        )
        
        or_rating = runner.get('or_rating') or runner.get('or') or 0
        
        if not odds or not or_rating:
            return score
        
        # Calculate market rank (1 = shortest odds)
        runners_with_odds = [
            r for r in all_runners 
            if (r.get('odds') or r.get('win_odds') or r.get('sp') or 0) > 0
        ]
        
        if len(runners_with_odds) < 2:
            return score
        
        sorted_by_odds = sorted(
            runners_with_odds,
            key=lambda r: r.get('odds') or r.get('win_odds') or r.get('sp') or 999
        )
        market_rank = next(
            (i + 1 for i, r in enumerate(sorted_by_odds) 
             if r.get('horse_name') == runner.get('horse_name')),
            999
        )
        
        # Calculate ratings rank (1 = highest rating)
        runners_with_ratings = [
            r for r in all_runners 
            if (r.get('or_rating') or r.get('or') or 0) > 0
        ]
        
        if len(runners_with_ratings) < 2:
            return score
        
        sorted_by_rating = sorted(
            runners_with_ratings,
            key=lambda r: r.get('or_rating') or r.get('or') or 0,
            reverse=True
        )
        ratings_rank = next(
            (i + 1 for i, r in enumerate(sorted_by_rating) 
             if r.get('horse_name') == runner.get('horse_name')),
            999
        )
        
        # Compare ranks
        rank_diff = market_rank - ratings_rank
        
        evidence['market_rank'] = market_rank
        evidence['ratings_rank'] = ratings_rank
        
        # Value: rated higher than market suggests
        if rank_diff > 2:
            score += 35
            evidence['factors'].append(
                f'🎯 VALUE: Rated #{ratings_rank}, priced #{market_rank} (+35)'
            )
        elif rank_diff > 0:
            score += 20
            evidence['factors'].append(
                f'Potential value: Rated #{ratings_rank}, priced #{market_rank} (+20)'
            )
        
        # Market favorite but not top-rated
        elif rank_diff < -2:
            score -= 25
            evidence['factors'].append(
                f'Overbet: Priced #{market_rank}, rated #{ratings_rank} (-25)'
            )
        
        return score
    
    def _analyze_value(
        self,
        odds: float,
        or_rating: int,
        all_runners: List[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Analyze value using implied probability vs expected probability
        
        Returns:
            Score 0-100
        """
        score = 50.0
        
        # Calculate implied probability from odds
        implied_prob = 1 / odds if odds > 0 else 0
        
        # Rough expected probability from OR rating
        # This is a simplified model
        if or_rating > 0:
            all_or = [
                r.get('or_rating') or r.get('or', 0)
                for r in all_runners
                if (r.get('or_rating') or r.get('or', 0)) > 0
            ]
            
            if all_or and len(all_or) >= 2:
                # Calculate expected probability based on ratings
                total_or = sum(all_or)
                expected_prob = or_rating / total_or if total_or > 0 else 0
                
                # Calculate edge
                edge = expected_prob - implied_prob
                
                evidence['implied_prob'] = f"{implied_prob:.3f}"
                evidence['expected_prob'] = f"{expected_prob:.3f}"
                evidence['edge'] = f"{edge:.3f}"
                
                # Strong value
                if edge > 0.10:  # 10%+ edge
                    score += 30
                    evidence['factors'].append(
                        f'Strong value: {edge*100:.1f}% edge (+30)'
                    )
                
                # Moderate value
                elif edge > 0.05:  # 5%+ edge
                    score += 20
                    evidence['factors'].append(
                        f'Moderate value: {edge*100:.1f}% edge (+20)'
                    )
                
                # Slight value
                elif edge > 0:
                    score += 10
                    evidence['factors'].append(
                        f'Slight value: {edge*100:.1f}% edge (+10)'
                    )
                
                # Overpriced
                elif edge < -0.10:
                    score -= 20
                    evidence['factors'].append(
                        f'Overpriced: {edge*100:.1f}% negative edge (-20)'
                    )
        
        return score
