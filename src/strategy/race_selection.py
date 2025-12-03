"""
VÉLØ Oracle - Race Selection Protocol
Automates the process of identifying the most profitable race types.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class RaceType(Enum):
    """Race type classifications"""
    HANDICAP = "Handicap"
    STAKES = "Stakes"
    MAIDEN = "Maiden"
    CLAIMING = "Claiming"
    NOVICE = "Novice"
    LISTED = "Listed"
    GROUP = "Group"


class RaceClass(Enum):
    """UK race class system"""
    CLASS_1 = 1
    CLASS_2 = 2
    CLASS_3 = 3
    CLASS_4 = 4
    CLASS_5 = 5
    CLASS_6 = 6
    CLASS_7 = 7


@dataclass
class RaceAttractiveness:
    """Race attractiveness score and breakdown"""
    score: float  # 0-100
    profitability_score: float
    predictability_score: float
    field_quality_score: float
    data_quality_score: float
    recommendation: str
    reasons: List[str]


class RaceSelectionProtocol:
    """
    Automates race selection based on historical profitability analysis.
    
    Philosophy:
    - Not all races are created equal
    - Some race types are systematically more profitable
    - Field size, class, and type all impact edge
    - Focus resources on high-value opportunities
    """
    
    def __init__(self):
        # Historical profitability weights (to be updated from database analysis)
        self.type_weights = {
            RaceType.HANDICAP: 1.2,  # Higher edge in handicaps
            RaceType.STAKES: 0.8,    # Lower edge in stakes
            RaceType.MAIDEN: 0.9,
            RaceType.CLAIMING: 1.1,
            RaceType.NOVICE: 0.85,
            RaceType.LISTED: 0.75,
            RaceType.GROUP: 0.6      # Hardest to predict
        }
        
        self.class_weights = {
            RaceClass.CLASS_1: 0.6,
            RaceClass.CLASS_2: 0.7,
            RaceClass.CLASS_3: 0.9,
            RaceClass.CLASS_4: 1.1,  # Sweet spot
            RaceClass.CLASS_5: 1.2,  # Best edge
            RaceClass.CLASS_6: 1.0,
            RaceClass.CLASS_7: 0.8
        }
        
        # Field size preferences
        self.optimal_field_size = (8, 16)  # Ideal range
        self.min_field_size = 6
        self.max_field_size = 20
        
        # Minimum thresholds
        self.min_attractiveness_score = 60.0
        
    def evaluate_race(
        self,
        race_type: str,
        race_class: int,
        field_size: int,
        course: str,
        distance: str,
        going: str,
        prize_money: Optional[float] = None
    ) -> RaceAttractiveness:
        """
        Evaluate a race's attractiveness for betting.
        
        Returns a score from 0-100 where:
        - 80-100: Excellent opportunity (high priority)
        - 60-79: Good opportunity (standard priority)
        - 40-59: Marginal opportunity (low priority)
        - 0-39: Avoid (skip)
        """
        reasons = []
        
        # 1. Profitability Score (40% weight)
        profitability_score = self._calculate_profitability(
            race_type, race_class, reasons
        )
        
        # 2. Predictability Score (30% weight)
        predictability_score = self._calculate_predictability(
            field_size, race_type, reasons
        )
        
        # 3. Field Quality Score (20% weight)
        field_quality_score = self._calculate_field_quality(
            field_size, race_class, reasons
        )
        
        # 4. Data Quality Score (10% weight)
        data_quality_score = self._calculate_data_quality(
            course, distance, going, reasons
        )
        
        # Weighted total
        total_score = (
            profitability_score * 0.4 +
            predictability_score * 0.3 +
            field_quality_score * 0.2 +
            data_quality_score * 0.1
        )
        
        # Recommendation
        if total_score >= 80:
            recommendation = "EXCELLENT - High Priority"
        elif total_score >= 60:
            recommendation = "GOOD - Standard Priority"
        elif total_score >= 40:
            recommendation = "MARGINAL - Low Priority"
        else:
            recommendation = "AVOID - Skip"
        
        return RaceAttractiveness(
            score=round(total_score, 2),
            profitability_score=round(profitability_score, 2),
            predictability_score=round(predictability_score, 2),
            field_quality_score=round(field_quality_score, 2),
            data_quality_score=round(data_quality_score, 2),
            recommendation=recommendation,
            reasons=reasons
        )
    
    def _calculate_profitability(
        self, race_type: str, race_class: int, reasons: List[str]
    ) -> float:
        """Calculate profitability score based on type and class"""
        score = 50.0  # Base score
        
        # Type adjustment
        try:
            rt = RaceType(race_type)
            type_multiplier = self.type_weights.get(rt, 1.0)
            score *= type_multiplier
            
            if type_multiplier > 1.0:
                reasons.append(f"{race_type} races show higher historical ROI")
            elif type_multiplier < 0.8:
                reasons.append(f"{race_type} races are harder to predict profitably")
        except ValueError:
            pass
        
        # Class adjustment
        try:
            rc = RaceClass(race_class)
            class_multiplier = self.class_weights.get(rc, 1.0)
            score *= class_multiplier
            
            if class_multiplier > 1.0:
                reasons.append(f"Class {race_class} offers better value opportunities")
        except ValueError:
            pass
        
        return min(score, 100.0)
    
    def _calculate_predictability(
        self, field_size: int, race_type: str, reasons: List[str]
    ) -> float:
        """Calculate predictability based on field size and type"""
        score = 50.0
        
        # Field size impact
        if self.optimal_field_size[0] <= field_size <= self.optimal_field_size[1]:
            score += 30
            reasons.append(f"Optimal field size ({field_size} runners)")
        elif field_size < self.min_field_size:
            score -= 20
            reasons.append(f"Small field ({field_size} runners) reduces value")
        elif field_size > self.max_field_size:
            score -= 15
            reasons.append(f"Large field ({field_size} runners) increases variance")
        
        # Handicap bonus (more data points)
        if "Handicap" in race_type:
            score += 20
            reasons.append("Handicap provides more form data")
        
        return min(max(score, 0), 100.0)
    
    def _calculate_field_quality(
        self, field_size: int, race_class: int, reasons: List[str]
    ) -> float:
        """Calculate field quality score"""
        score = 50.0
        
        # Class 4-5 with 8-14 runners is ideal
        if race_class in [4, 5] and 8 <= field_size <= 14:
            score += 40
            reasons.append("Ideal class/field combination for value")
        elif race_class in [1, 2]:
            score -= 20
            reasons.append("Top-class races have efficient markets")
        
        return min(max(score, 0), 100.0)
    
    def _calculate_data_quality(
        self, course: str, distance: str, going: str, reasons: List[str]
    ) -> float:
        """Calculate data quality score"""
        score = 70.0  # Default good
        
        # Known courses get bonus
        major_courses = [
            "Ascot", "Cheltenham", "Newmarket", "York", "Goodwood",
            "Epsom", "Doncaster", "Sandown", "Kempton", "Haydock"
        ]
        
        if any(c in course for c in major_courses):
            score += 20
            reasons.append(f"{course} has extensive historical data")
        
        # Standard distances get bonus
        if any(d in distance for d in ["5f", "6f", "7f", "1m", "1m2f", "1m4f", "2m"]):
            score += 10
        
        return min(score, 100.0)
    
    def should_analyze_race(self, attractiveness: RaceAttractiveness) -> bool:
        """Determine if a race should be analyzed"""
        return attractiveness.score >= self.min_attractiveness_score
    
    def get_daily_race_priorities(self, races: List[Dict]) -> List[Dict]:
        """
        Prioritize a day's races by attractiveness.
        
        Args:
            races: List of race dicts with keys: type, class, field_size, course, etc.
        
        Returns:
            Sorted list with attractiveness scores
        """
        scored_races = []
        
        for race in races:
            attractiveness = self.evaluate_race(
                race_type=race.get("type", ""),
                race_class=race.get("class", 5),
                field_size=race.get("field_size", 10),
                course=race.get("course", ""),
                distance=race.get("distance", ""),
                going=race.get("going", "Good"),
                prize_money=race.get("prize_money")
            )
            
            scored_races.append({
                **race,
                "attractiveness": attractiveness
            })
        
        # Sort by score descending
        scored_races.sort(key=lambda x: x["attractiveness"].score, reverse=True)
        
        return scored_races
