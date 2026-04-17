"""
VÉLØ Oracle - Pace Map Intelligence
Create and analyze pace scenarios for races
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class PaceMapAnalyzer:
    """Analyze race pace scenarios and runner positioning"""
    
    def __init__(self):
        self.pace_styles = {
            "leader": {"early_speed": 0.9, "sustained": 0.7},
            "stalker": {"early_speed": 0.7, "sustained": 0.8},
            "midfield": {"early_speed": 0.5, "sustained": 0.7},
            "closer": {"early_speed": 0.3, "sustained": 0.9}
        }
    
    def create_pace_map(self, runners: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create pace map for a race
        
        Args:
            runners: List of runner dictionaries
            
        Returns:
            Pace map with runner positioning and scenarios
        """
        logger.debug(f"Creating pace map for {len(runners)} runners")
        
        # Classify each runner by pace style
        classified_runners = self._classify_runners(runners)
        
        # Identify pace scenario
        pace_scenario = self._identify_pace_scenario(classified_runners)
        
        # Calculate pace pressure
        pace_pressure = self._calculate_pace_pressure(classified_runners)
        
        # Identify advantaged runners
        advantaged_runners = self._identify_advantaged_runners(
            classified_runners, 
            pace_scenario
        )
        
        result = {
            "leaders": classified_runners["leaders"],
            "stalkers": classified_runners["stalkers"],
            "midfield": classified_runners["midfield"],
            "closers": classified_runners["closers"],
            "pace_scenario": pace_scenario,
            "pace_pressure": pace_pressure,
            "advantaged_runners": advantaged_runners,
            "analysis": self._generate_analysis(pace_scenario, pace_pressure),
            "recommendations": self._generate_recommendations(
                pace_scenario, 
                advantaged_runners
            )
        }
        
        logger.debug(f"Pace scenario: {pace_scenario['type']} (pressure: {pace_pressure:.2f})")
        
        return result
    
    def _classify_runners(self, runners: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify runners by pace style"""
        classified = {
            "leaders": [],
            "stalkers": [],
            "midfield": [],
            "closers": []
        }
        
        for runner in runners:
            pace_style = self._determine_pace_style(runner)
            
            runner_info = {
                "horse": runner.get("horse"),
                "runner_id": runner.get("runner_id"),
                "draw": runner.get("draw"),
                "odds": runner.get("odds", 10.0),
                "pace_score": self._calculate_pace_score(runner, pace_style)
            }
            
            classified[pace_style].append(runner_info)
        
        # Sort each group by pace score
        for style in classified:
            classified[style].sort(key=lambda r: r["pace_score"], reverse=True)
        
        return classified
    
    def _determine_pace_style(self, runner: Dict) -> str:
        """Determine runner's pace style"""
        # Analyze form and sectionals to determine style
        form = runner.get("form", "0-0-0-0-0")
        positions = [int(p) if p.isdigit() else 10 for p in form.split("-")]
        
        # Early positions suggest pace style
        avg_position = sum(positions[:3]) / 3 if positions else 5
        
        draw = runner.get("draw", 10)
        
        # Leaders: early positions + good draw
        if avg_position <= 2 and draw <= 6:
            return "leaders"
        
        # Stalkers: moderate early positions
        elif avg_position <= 4:
            return "stalkers"
        
        # Closers: back in field
        elif avg_position >= 8:
            return "closers"
        
        # Midfield: everything else
        else:
            return "midfield"
    
    def _calculate_pace_score(self, runner: Dict, pace_style: str) -> float:
        """Calculate pace score for runner in their style"""
        base_score = 0.5
        
        # Factor in speed ratings
        speed_ratings = runner.get("speed_ratings", {})
        speed_score = speed_ratings.get("adjusted", 100) / 150  # Normalize
        
        # Factor in sectionals
        sectionals = runner.get("sectional_times", {})
        
        if pace_style == "leaders":
            # Leaders need early speed
            first_400m = sectionals.get("first_400m", 25.0)
            sectional_score = max(1.0 - (first_400m - 23.0) / 5.0, 0.0)
        
        elif pace_style == "closers":
            # Closers need late speed
            last_200m = sectionals.get("last_200m", 12.0)
            sectional_score = max(1.0 - (last_200m - 11.0) / 3.0, 0.0)
        
        else:
            # Stalkers/midfield need balanced speed
            sectional_score = 0.6
        
        # Combine scores
        pace_score = (speed_score * 0.6) + (sectional_score * 0.4)
        
        return min(max(pace_score, 0.0), 1.0)
    
    def _identify_pace_scenario(self, classified: Dict) -> Dict[str, Any]:
        """Identify the likely pace scenario"""
        leader_count = len(classified["leaders"])
        closer_count = len(classified["closers"])
        
        # Determine scenario type
        if leader_count == 0:
            scenario_type = "no_pace"
            description = "No genuine leaders - slow early pace likely"
            
        elif leader_count == 1:
            scenario_type = "solo_leader"
            description = "Single leader - controlled pace likely"
            
        elif leader_count >= 3:
            scenario_type = "speed_duel"
            description = "Multiple leaders - fast early pace likely"
            
        else:
            scenario_type = "moderate_pace"
            description = "Moderate early pace expected"
        
        # Assess closer advantage
        closer_advantage = (
            scenario_type in ["speed_duel", "moderate_pace"] and 
            closer_count >= 3
        )
        
        return {
            "type": scenario_type,
            "description": description,
            "leader_count": leader_count,
            "closer_count": closer_count,
            "closer_advantage": closer_advantage,
            "confidence": self._scenario_confidence(leader_count, closer_count)
        }
    
    def _calculate_pace_pressure(self, classified: Dict) -> float:
        """Calculate overall pace pressure (0 = slow, 1 = fast)"""
        leader_count = len(classified["leaders"])
        stalker_count = len(classified["stalkers"])
        
        # Base pressure from leader count
        if leader_count == 0:
            base_pressure = 0.2
        elif leader_count == 1:
            base_pressure = 0.4
        elif leader_count == 2:
            base_pressure = 0.6
        else:
            base_pressure = 0.8
        
        # Adjust for stalkers
        stalker_adjustment = min(stalker_count * 0.05, 0.2)
        
        total_pressure = base_pressure + stalker_adjustment
        
        return min(total_pressure, 1.0)
    
    def _identify_advantaged_runners(self, classified: Dict, 
                                    pace_scenario: Dict) -> List[Dict]:
        """Identify runners with pace advantage"""
        advantaged = []
        
        scenario_type = pace_scenario["type"]
        
        if scenario_type == "no_pace":
            # Leaders advantaged in no-pace scenario
            advantaged.extend(classified["leaders"][:2])
            advantaged.extend(classified["stalkers"][:2])
        
        elif scenario_type == "solo_leader":
            # Solo leader has advantage
            if classified["leaders"]:
                advantaged.append(classified["leaders"][0])
            # Plus best stalker
            if classified["stalkers"]:
                advantaged.append(classified["stalkers"][0])
        
        elif scenario_type == "speed_duel":
            # Closers advantaged in speed duel
            advantaged.extend(classified["closers"][:3])
            # Plus midfield runners
            advantaged.extend(classified["midfield"][:2])
        
        else:  # moderate_pace
            # Stalkers advantaged in moderate pace
            advantaged.extend(classified["stalkers"][:2])
            advantaged.extend(classified["midfield"][:2])
        
        return advantaged
    
    def _scenario_confidence(self, leader_count: int, closer_count: int) -> float:
        """Calculate confidence in pace scenario prediction"""
        # More extreme scenarios = higher confidence
        if leader_count == 0 or leader_count >= 4:
            return 0.85
        elif leader_count == 1:
            return 0.75
        else:
            return 0.65
    
    def _generate_analysis(self, pace_scenario: Dict, pace_pressure: float) -> str:
        """Generate pace analysis text"""
        scenario_type = pace_scenario["type"]
        
        if scenario_type == "no_pace":
            return (
                "Lack of genuine early speed suggests slow early fractions. "
                "On-pace runners and those with tactical speed will be advantaged. "
                "Closers may struggle to make up ground."
            )
        
        elif scenario_type == "solo_leader":
            return (
                "Single leader likely to control tempo and dictate terms. "
                "Difficult to run down if allowed soft fractions. "
                "Stalkers in striking position best placed to challenge."
            )
        
        elif scenario_type == "speed_duel":
            return (
                "Multiple leaders will engage early, creating fast fractions. "
                "Pace pressure will compromise on-pace runners. "
                "Closers and midfield runners with strong finish advantaged."
            )
        
        else:  # moderate_pace
            return (
                "Moderate early pace expected with competitive positioning. "
                "Race likely to be run on its merits. "
                "Stalkers with tactical speed well positioned."
            )
    
    def _generate_recommendations(self, pace_scenario: Dict, 
                                 advantaged_runners: List[Dict]) -> List[str]:
        """Generate betting recommendations based on pace"""
        recommendations = []
        
        scenario_type = pace_scenario["type"]
        
        if scenario_type == "speed_duel":
            recommendations.append("Favor closers and midfield runners")
            recommendations.append("Avoid betting on leaders unless exceptional class")
        
        elif scenario_type == "solo_leader":
            recommendations.append("Solo leader is strong chance if quality")
            recommendations.append("Best stalker presents value opportunity")
        
        elif scenario_type == "no_pace":
            recommendations.append("On-pace runners have significant advantage")
            recommendations.append("Closers face difficult task")
        
        # Add specific runner recommendations
        if advantaged_runners:
            top_pick = advantaged_runners[0]
            recommendations.append(
                f"Top pace pick: {top_pick['horse']} (odds: {top_pick['odds']})"
            )
        
        return recommendations


def create_pace_map(runners: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function to create pace map
    
    Args:
        runners: List of runner dictionaries
        
    Returns:
        Pace map analysis
    """
    analyzer = PaceMapAnalyzer()
    return analyzer.create_pace_map(runners)
