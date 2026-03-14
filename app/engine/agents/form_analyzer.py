"""
Form Analyzer Agent
Analyzes recent race form to calculate form score (0-100)
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FormAnalysisResult:
    """Result from form analysis"""
    score: float  # 0-100
    confidence: float  # 0-1
    evidence: Dict[str, Any]


class FormAnalyzer:
    """
    Analyzes horse form from recent runs
    - Recent finishing positions
    - Days since last run
    - Consistency of performance
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize Form Analyzer
        
        Args:
            supabase_client: Supabase client for database queries
        """
        self.client = supabase_client
        self.name = "form_analyzer"
    
    def analyze(self, runner: Dict[str, Any], race_context: Dict[str, Any]) -> FormAnalysisResult:
        """
        Analyze form for a runner
        
        Args:
            runner: Runner data including form figures
            race_context: Race metadata
            
        Returns:
            FormAnalysisResult with score, confidence, and evidence
        """
        form_figures = runner.get('form_figures', '')
        horse_name = runner.get('horse_name', '')
        
        # Initialize score and evidence
        score = 50.0  # Start at neutral
        evidence = {
            'form_figures': form_figures,
            'factors': []
        }
        
        # If no form data, return low confidence
        if not form_figures:
            return FormAnalysisResult(
                score=50.0,
                confidence=0.3,
                evidence={**evidence, 'reason': 'No form data available'}
            )
        
        # Parse form figures (e.g., "13212" = 1st, 3rd, 2nd, 1st, 2nd)
        recent_positions = self._parse_form_figures(form_figures)
        
        if not recent_positions:
            return FormAnalysisResult(
                score=50.0,
                confidence=0.3,
                evidence={**evidence, 'reason': 'Unable to parse form figures'}
            )
        
        # Analyze last 5 runs
        last_5 = recent_positions[:5]
        
        # 1. Recent win bonus (30 points max)
        if last_5 and last_5[0] == 1:
            score += 30
            evidence['factors'].append('Last time winner (+30)')
        elif last_5 and last_5[0] <= 3:
            score += 20
            evidence['factors'].append(f'Recent {self._ordinal(last_5[0])} (+20)')
        elif last_5 and last_5[0] <= 5:
            score += 10
            evidence['factors'].append(f'Recent {self._ordinal(last_5[0])} (+10)')
        
        # 2. Consistency (20 points max)
        if len(last_5) >= 3:
            consistent_runs = sum(1 for p in last_5 if p <= 4)
            consistency_pct = consistent_runs / len(last_5)
            consistency_score = consistency_pct * 20
            score += consistency_score
            evidence['factors'].append(
                f'Consistency: {consistent_runs}/{len(last_5)} top-4 (+{consistency_score:.0f})'
            )
        
        # 3. Improvement trend (15 points max)
        if len(last_5) >= 3:
            trend_score = self._calculate_trend(last_5[:3])
            score += trend_score
            if trend_score > 0:
                evidence['factors'].append(f'Improving form trend (+{trend_score:.0f})')
            elif trend_score < 0:
                evidence['factors'].append(f'Declining form trend ({trend_score:.0f})')
        
        # 4. No recent wins penalty
        if len(last_5) >= 5:
            if 1 not in last_5:
                score -= 15
                evidence['factors'].append('No wins in last 5 runs (-15)')
        
        # Clamp score to 0-100
        score = max(0, min(100, score))
        
        # Calculate confidence based on data availability
        confidence = min(1.0, len(recent_positions) / 5 * 0.9 + 0.3)
        
        evidence['recent_positions'] = last_5
        evidence['final_score'] = score
        
        return FormAnalysisResult(
            score=score,
            confidence=confidence,
            evidence=evidence
        )
    
    def _parse_form_figures(self, form_figures: str) -> List[int]:
        """
        Parse form figures string into list of positions
        
        Args:
            form_figures: String like "13212" or "1-3-2"
            
        Returns:
            List of positions [1, 3, 2, 1, 2]
        """
        positions = []
        
        # Remove common separators
        form_clean = form_figures.replace('-', '').replace('/', '').replace(' ', '')
        
        for char in form_clean:
            if char.isdigit():
                positions.append(int(char))
            elif char == 'P':  # Pulled up
                positions.append(99)
            elif char == 'U':  # Unseated rider
                positions.append(99)
            elif char == 'F':  # Fell
                positions.append(99)
        
        return positions
    
    def _calculate_trend(self, positions: List[int]) -> float:
        """
        Calculate improvement/decline trend
        
        Args:
            positions: List of recent positions (most recent first)
            
        Returns:
            Score adjustment (-15 to +15)
        """
        if len(positions) < 2:
            return 0.0
        
        # Compare most recent to previous
        recent = positions[0]
        previous = sum(positions[1:]) / len(positions[1:])
        
        # Improvement
        if recent < previous:
            improvement = (previous - recent) / previous
            return min(15, improvement * 20)
        
        # Decline
        elif recent > previous:
            decline = (recent - previous) / max(previous, 1)
            return max(-15, -decline * 20)
        
        return 0.0
    
    def _ordinal(self, n: int) -> str:
        """Convert number to ordinal string (1st, 2nd, 3rd, etc.)"""
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"
