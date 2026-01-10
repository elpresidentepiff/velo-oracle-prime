"""
Course/Distance Analyzer Agent
Analyzes horse suitability for course, distance, and going conditions
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CourseDistanceAnalysisResult:
    """Result from course/distance analysis"""
    score: float  # 0-100
    confidence: float  # 0-1
    evidence: Dict[str, Any]


class CourseDistanceAnalyzer:
    """
    Analyzes course, distance, and going suitability
    - Queries horse_velocity table
    - Checks course/distance/going suitability
    - Identifies specialists (SR > 15%)
    """
    
    def __init__(self, supabase_client):
        """
        Initialize Course/Distance Analyzer
        
        Args:
            supabase_client: Supabase client for database queries
        """
        self.client = supabase_client
        self.name = "course_distance_analyzer"
    
    def analyze(self, runner: Dict[str, Any], race_context: Dict[str, Any]) -> CourseDistanceAnalysisResult:
        """
        Analyze course/distance/going suitability for a runner
        
        Args:
            runner: Runner data
            race_context: Race metadata including course, distance, going
            
        Returns:
            CourseDistanceAnalysisResult with score, confidence, and evidence
        """
        horse_name = runner.get('horse_name', '').strip()
        course = race_context.get('course', '').strip().lower()
        distance = race_context.get('distance', '').strip()
        going = race_context.get('going', '').strip().lower()
        
        evidence = {
            'horse_name': horse_name,
            'course': course,
            'distance': distance,
            'going': going,
            'factors': []
        }
        
        # Query horse velocity stats
        horse_stats = self._get_horse_stats(horse_name)
        
        if not horse_stats:
            return CourseDistanceAnalysisResult(
                score=50.0,
                confidence=0.2,
                evidence={**evidence, 'reason': 'No velocity data available'}
            )
        
        # Calculate score based on course/distance/going stats
        score = 50.0  # Start at neutral
        confidence = 0.5
        
        # Course analysis (40% weight)
        course_stat = self._find_stat(horse_stats, f'course_{course}')
        if course_stat:
            course_score = self._score_stat(course_stat, 'course', evidence)
            score += (course_score - 50) * 0.4
            confidence += 0.2
        
        # Distance analysis (35% weight)
        distance_normalized = self._normalize_distance(distance)
        distance_stat = self._find_stat(horse_stats, f'distance_{distance_normalized}')
        if distance_stat:
            distance_score = self._score_stat(distance_stat, 'distance', evidence)
            score += (distance_score - 50) * 0.35
            confidence += 0.15
        
        # Going analysis (25% weight)
        going_stat = self._find_stat(horse_stats, f'going_{going}')
        if going_stat:
            going_score = self._score_stat(going_stat, 'going', evidence)
            score += (going_score - 50) * 0.25
            confidence += 0.15
        
        # Specialist bonus
        specialist_bonus = self._check_specialist(course_stat, distance_stat, going_stat, evidence)
        score += specialist_bonus
        
        # Clamp score to 0-100
        score = max(0, min(100, score))
        confidence = min(1.0, confidence)
        
        evidence['final_score'] = score
        
        return CourseDistanceAnalysisResult(
            score=score,
            confidence=confidence,
            evidence=evidence
        )
    
    def _get_horse_stats(self, horse_name: str) -> List[Dict[str, Any]]:
        """Query horse velocity stats from database"""
        if not horse_name or not self.client:
            return []
        
        try:
            result = self.client.table('horse_velocity') \
                .select('*') \
                .eq('horse_name', horse_name) \
                .execute()
            
            if result.data:
                return result.data
        except Exception as e:
            logger.warning(f"Failed to query horse stats for {horse_name}: {e}")
        
        return []
    
    def _find_stat(self, stats: List[Dict[str, Any]], stat_type: str) -> Optional[Dict[str, Any]]:
        """Find specific stat type in horse stats"""
        for stat in stats:
            if stat.get('stat_type', '').lower() == stat_type.lower():
                return stat
        return None
    
    def _score_stat(self, stat: Dict[str, Any], category: str, evidence: Dict[str, Any]) -> float:
        """
        Score a specific stat (course/distance/going)
        
        Returns:
            Score 0-100
        """
        score = 50.0
        sr = stat.get('sr', 0)
        record = stat.get('record', '')
        
        # Parse record (e.g., "2-5" = 2 wins from 5 runs)
        wins, runs = self._parse_record(record)
        
        # Strike rate scoring
        if sr > 0:
            if sr >= 33:  # 33%+ = specialist
                score += 40
                evidence['factors'].append(
                    f'⭐ {category.upper()} SPECIALIST: {sr:.1f}% SR ({record}) (+40)'
                )
            elif sr >= 20:
                score += 25
                evidence['factors'].append(
                    f'{category.capitalize()} proven: {sr:.1f}% SR ({record}) (+25)'
                )
            elif sr >= 15:
                score += 15
                evidence['factors'].append(
                    f'{category.capitalize()} good: {sr:.1f}% SR ({record}) (+15)'
                )
            elif sr < 10 and runs >= 3:
                score -= 20
                evidence['factors'].append(
                    f'{category.capitalize()} poor: {sr:.1f}% SR ({record}) (-20)'
                )
        
        # Sample size consideration
        if runs >= 5:
            evidence['factors'].append(f'Good sample: {runs} runs at {category}')
        elif runs <= 1:
            score = 50.0  # Reset to neutral for small sample
            evidence['factors'].append(f'Limited data: only {runs} run(s) at {category}')
        
        evidence[f'{category}_stats'] = {
            'sr': sr,
            'record': record,
            'wins': wins,
            'runs': runs
        }
        
        return score
    
    def _parse_record(self, record: str) -> tuple:
        """
        Parse record string like "2-5" into (wins, runs)
        
        Returns:
            (wins, runs) tuple
        """
        if not record or '-' not in record:
            return (0, 0)
        
        try:
            parts = record.split('-')
            wins = int(parts[0])
            runs = int(parts[1])
            return (wins, runs)
        except (ValueError, IndexError):
            return (0, 0)
    
    def _normalize_distance(self, distance: str) -> str:
        """
        Normalize distance string for lookup
        e.g., "2m" -> "2m", "1m 2f" -> "1m2f"
        
        Returns:
            Normalized distance string
        """
        if not distance:
            return ''
        
        # Remove spaces
        normalized = distance.lower().replace(' ', '')
        return normalized
    
    def _check_specialist(
        self,
        course_stat: Optional[Dict[str, Any]],
        distance_stat: Optional[Dict[str, Any]],
        going_stat: Optional[Dict[str, Any]],
        evidence: Dict[str, Any]
    ) -> float:
        """
        Check if horse is a true specialist (excels in multiple categories)
        
        Returns:
            Bonus score (0-15)
        """
        specialist_count = 0
        
        if course_stat and course_stat.get('sr', 0) >= 20:
            specialist_count += 1
        
        if distance_stat and distance_stat.get('sr', 0) >= 20:
            specialist_count += 1
        
        if going_stat and going_stat.get('sr', 0) >= 20:
            specialist_count += 1
        
        if specialist_count >= 2:
            evidence['factors'].append(
                f'🎯 MULTI-SPECIALIST: Excels in {specialist_count} categories (+15)'
            )
            return 15
        
        return 0
