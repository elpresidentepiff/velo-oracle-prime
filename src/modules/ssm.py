"""
VÉLØ v9.0++ CHAREX - SSM (Sectional Speed Matrix)

Pace analysis engine that predicts race shape and identifies
horses suited to the expected sectional splits.

Analyzes:
- Early pace pressure
- Mid-race positioning
- Closing sectionals
- Pace collapse scenarios
"""

from typing import Dict, List, Optional, Tuple


class SectionalSpeedMatrix:
    """
    SSM - Sectional Speed Matrix
    
    Analyzes pace dynamics and identifies horses whose running
    style matches the expected race shape.
    """
    
    def __init__(self):
        """Initialize SSM module."""
        self.name = "SSM"
        self.version = "v9.0++"
        
        # Pace categories
        self.PACE_CATEGORIES = {
            "FRONT_RUNNER": "Leads from the front",
            "PROMINENT": "Races close to the pace",
            "MIDFIELD": "Settles in midfield",
            "CLOSER": "Comes from behind"
        }
    
    def analyze_race_pace(self, horses: List[Dict], race_context: Dict) -> Dict:
        """
        Analyze expected pace scenario for the race.
        
        Args:
            horses: List of all horses with pace data
            race_context: Race conditions (distance, going, etc.)
            
        Returns:
            Pace analysis with scenario prediction
        """
        # Count horses by running style
        front_runners = []
        prominent = []
        midfield = []
        closers = []
        
        for horse in horses:
            pace_style = self._determine_pace_style(horse)
            
            if pace_style == "FRONT_RUNNER":
                front_runners.append(horse["name"])
            elif pace_style == "PROMINENT":
                prominent.append(horse["name"])
            elif pace_style == "MIDFIELD":
                midfield.append(horse["name"])
            elif pace_style == "CLOSER":
                closers.append(horse["name"])
        
        # Determine pace scenario
        scenario = self._predict_pace_scenario(
            len(front_runners),
            len(prominent),
            len(closers)
        )
        
        # Identify advantaged running styles
        advantaged_styles = self._identify_advantaged_styles(scenario)
        
        return {
            "pace_scenario": scenario,
            "front_runners": front_runners,
            "prominent": prominent,
            "midfield": midfield,
            "closers": closers,
            "front_runner_count": len(front_runners),
            "closer_count": len(closers),
            "advantaged_styles": advantaged_styles,
            "tactical_note": self._generate_pace_note(scenario)
        }
    
    def _determine_pace_style(self, horse: Dict) -> str:
        """
        Determine a horse's typical running style.
        
        Args:
            horse: Horse data
            
        Returns:
            Pace style category
        """
        # TODO: Implement based on historical sectional data
        # Placeholder logic based on form patterns
        
        form = horse.get("form", "")
        
        # Simple heuristic: horses with early wins tend to be front runners
        if form and form[0] in ["1", "2"]:
            return "FRONT_RUNNER"
        elif form and form[0] in ["3", "4"]:
            return "PROMINENT"
        else:
            return "CLOSER"
    
    def _predict_pace_scenario(self, front_count: int, prominent_count: int, closer_count: int) -> str:
        """
        Predict the likely pace scenario.
        
        Args:
            front_count: Number of front runners
            prominent_count: Number of prominent runners
            closer_count: Number of closers
            
        Returns:
            Pace scenario description
        """
        if front_count >= 3:
            return "HOT_PACE"  # Multiple front runners = pace collapse likely
        elif front_count == 1:
            return "LONE_SPEED"  # Single front runner = uncontested lead
        elif front_count == 0:
            return "SLOW_PACE"  # No natural leaders = tactical race
        else:
            return "MODERATE_PACE"  # Balanced pace
    
    def _identify_advantaged_styles(self, scenario: str) -> List[str]:
        """
        Identify which running styles are advantaged by the pace scenario.
        
        Args:
            scenario: Predicted pace scenario
            
        Returns:
            List of advantaged running styles
        """
        if scenario == "HOT_PACE":
            # Pace collapse favors closers
            return ["CLOSER", "MIDFIELD"]
        elif scenario == "LONE_SPEED":
            # Uncontested lead favors front runner
            return ["FRONT_RUNNER"]
        elif scenario == "SLOW_PACE":
            # Tactical race favors prominent runners who can kick
            return ["PROMINENT", "FRONT_RUNNER"]
        else:
            # Moderate pace is balanced
            return ["PROMINENT", "MIDFIELD"]
    
    def _generate_pace_note(self, scenario: str) -> str:
        """
        Generate tactical note about the pace scenario.
        
        Args:
            scenario: Pace scenario
            
        Returns:
            Tactical note
        """
        notes = {
            "HOT_PACE": "Multiple front runners will clash early. Pace collapse likely. Favor closers.",
            "LONE_SPEED": "Single front runner gets uncontested lead. Hard to peg back. Favor the leader.",
            "SLOW_PACE": "No natural pace. Tactical race. Favor horses that can quicken.",
            "MODERATE_PACE": "Balanced pace. Form horses should get their chance."
        }
        
        return notes.get(scenario, "Standard pace expected.")
    
    def evaluate_horse_pace_suitability(self, horse: Dict, pace_analysis: Dict) -> Dict:
        """
        Evaluate if a horse's running style suits the expected pace.
        
        Args:
            horse: Horse data
            pace_analysis: Output from analyze_race_pace()
            
        Returns:
            Suitability score and reasoning
        """
        horse_style = self._determine_pace_style(horse)
        advantaged_styles = pace_analysis["advantaged_styles"]
        
        is_suited = horse_style in advantaged_styles
        
        # Calculate suitability score (0.0 to 1.0)
        if is_suited:
            suitability_score = 0.85
        else:
            suitability_score = 0.45
        
        return {
            "horse_name": horse.get("name", "Unknown"),
            "running_style": horse_style,
            "pace_scenario": pace_analysis["pace_scenario"],
            "is_suited": is_suited,
            "suitability_score": suitability_score,
            "reasoning": f"{horse_style} in {pace_analysis['pace_scenario']} scenario"
        }
    
    def get_pace_advantage_horses(self, horses: List[Dict], race_context: Dict) -> List[Dict]:
        """
        Get list of horses with pace advantage.
        
        Args:
            horses: All horses in race
            race_context: Race conditions
            
        Returns:
            Horses with pace advantage, sorted by suitability
        """
        # Analyze race pace
        pace_analysis = self.analyze_race_pace(horses, race_context)
        
        # Evaluate each horse
        evaluations = []
        for horse in horses:
            eval_result = self.evaluate_horse_pace_suitability(horse, pace_analysis)
            if eval_result["is_suited"]:
                evaluations.append({
                    "horse": horse,
                    "evaluation": eval_result
                })
        
        # Sort by suitability score
        evaluations.sort(key=lambda x: x["evaluation"]["suitability_score"], reverse=True)
        
        return evaluations


def main():
    """Test SSM module."""
    print("⚡ SSM - Sectional Speed Matrix")
    print("="*60)
    
    ssm = SectionalSpeedMatrix()
    
    # Test horses
    test_horses = [
        {"name": "Speed King", "form": "112"},
        {"name": "Front Runner A", "form": "211"},
        {"name": "Front Runner B", "form": "121"},
        {"name": "Closer A", "form": "543"},
        {"name": "Closer B", "form": "654"},
        {"name": "Midfield Runner", "form": "334"}
    ]
    
    test_race = {
        "distance": "6f",
        "going": "Good"
    }
    
    # Analyze pace
    pace_analysis = ssm.analyze_race_pace(test_horses, test_race)
    
    print(f"\n📊 Pace Analysis:")
    print(f"  Scenario: {pace_analysis['pace_scenario']}")
    print(f"  Front Runners: {pace_analysis['front_runner_count']}")
    print(f"  Closers: {pace_analysis['closer_count']}")
    print(f"  Advantaged Styles: {', '.join(pace_analysis['advantaged_styles'])}")
    print(f"\n  Tactical Note: {pace_analysis['tactical_note']}")
    
    # Get pace advantage horses
    advantaged = ssm.get_pace_advantage_horses(test_horses, test_race)
    
    print(f"\n🎯 Horses with Pace Advantage:")
    for item in advantaged:
        horse = item["horse"]
        eval_result = item["evaluation"]
        print(f"  ✅ {horse['name']} - {eval_result['running_style']} (Score: {eval_result['suitability_score']:.2f})")


if __name__ == "__main__":
    main()

