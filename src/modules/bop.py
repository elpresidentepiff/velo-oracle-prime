"""
VÉLØ v9.0++ CHAREX - BOP (Bias/Optimal Positioning)

Detects course bias, draw advantage, and optimal positioning
based on going, rail position, and historical track patterns.

Analyzes:
- Draw bias (high/low numbers)
- Rail position effects
- Going-specific advantages
- Track configuration bias
"""

from typing import Dict, List, Optional, Tuple


class BiasOptimalPositioning:
    """
    BOP - Bias/Optimal Positioning Module
    
    Identifies course and draw biases that can significantly
    impact race outcomes.
    """
    
    def __init__(self):
        """Initialize BOP module."""
        self.name = "BOP"
        self.version = "v9.0++"
        
        # Track bias database (simplified - would be expanded with real data)
        self.track_biases = {
            "Yarmouth": {"bias": "LOW", "strength": 0.7},
            "Chester": {"bias": "LOW", "strength": 0.9},
            "Epsom": {"bias": "HIGH", "strength": 0.6},
            "Ascot": {"bias": "NEUTRAL", "strength": 0.1}
        }
        
        # Going effects on bias
        self.going_modifiers = {
            "Heavy": 1.3,  # Amplifies bias
            "Soft": 1.2,
            "Good to Soft": 1.1,
            "Good": 1.0,
            "Good to Firm": 0.9,
            "Firm": 0.8  # Reduces bias
        }
    
    def analyze_draw_bias(self, track: str, going: str, distance: str, field_size: int) -> Dict:
        """
        Analyze draw bias for the race.
        
        Args:
            track: Course name
            going: Ground conditions
            distance: Race distance
            field_size: Number of runners
            
        Returns:
            Draw bias analysis
        """
        # Get base track bias
        track_data = self.track_biases.get(track, {"bias": "NEUTRAL", "strength": 0.0})
        base_bias = track_data["bias"]
        base_strength = track_data["strength"]
        
        # Apply going modifier
        going_modifier = self.going_modifiers.get(going, 1.0)
        adjusted_strength = base_strength * going_modifier
        
        # Determine advantaged stalls
        if base_bias == "LOW":
            advantaged_range = (1, min(5, field_size))
            disadvantaged_range = (max(1, field_size - 4), field_size)
        elif base_bias == "HIGH":
            advantaged_range = (max(1, field_size - 4), field_size)
            disadvantaged_range = (1, min(5, field_size))
        else:
            advantaged_range = None
            disadvantaged_range = None
        
        # Generate tactical note
        if adjusted_strength >= 0.7:
            severity = "STRONG"
        elif adjusted_strength >= 0.4:
            severity = "MODERATE"
        else:
            severity = "WEAK"
        
        return {
            "track": track,
            "bias_type": base_bias,
            "bias_strength": adjusted_strength,
            "severity": severity,
            "going": going,
            "going_modifier": going_modifier,
            "advantaged_stalls": advantaged_range,
            "disadvantaged_stalls": disadvantaged_range,
            "tactical_note": self._generate_bias_note(base_bias, severity, going)
        }
    
    def _generate_bias_note(self, bias_type: str, severity: str, going: str) -> str:
        """
        Generate tactical note about draw bias.
        
        Args:
            bias_type: Type of bias (LOW/HIGH/NEUTRAL)
            severity: Strength of bias
            going: Ground conditions
            
        Returns:
            Tactical note
        """
        if bias_type == "NEUTRAL" or severity == "WEAK":
            return "No significant draw bias. All stalls have fair chance."
        
        if bias_type == "LOW":
            if severity == "STRONG":
                return f"STRONG low draw bias on {going}. Low numbers heavily favored. Avoid high stalls."
            else:
                return f"Moderate low draw bias. Low numbers preferred but not decisive."
        
        if bias_type == "HIGH":
            if severity == "STRONG":
                return f"STRONG high draw bias on {going}. High numbers heavily favored. Avoid low stalls."
            else:
                return f"Moderate high draw bias. High numbers preferred but not decisive."
        
        return "Standard draw conditions."
    
    def evaluate_horse_draw(self, horse: Dict, bias_analysis: Dict) -> Dict:
        """
        Evaluate if a horse has draw advantage or disadvantage.
        
        Args:
            horse: Horse data with draw number
            bias_analysis: Output from analyze_draw_bias()
            
        Returns:
            Draw evaluation
        """
        draw = horse.get("number", 0)
        
        if not draw:
            return {
                "horse_name": horse.get("name", "Unknown"),
                "draw": None,
                "advantage": "UNKNOWN",
                "impact_score": 0.5
            }
        
        advantaged = bias_analysis["advantaged_stalls"]
        disadvantaged = bias_analysis["disadvantaged_stalls"]
        bias_strength = bias_analysis["bias_strength"]
        
        # Determine advantage
        if advantaged and advantaged[0] <= draw <= advantaged[1]:
            advantage = "ADVANTAGED"
            # Impact score: higher for stronger bias
            impact_score = 0.5 + (bias_strength * 0.4)  # 0.5 to 0.9
        elif disadvantaged and disadvantaged[0] <= draw <= disadvantaged[1]:
            advantage = "DISADVANTAGED"
            impact_score = 0.5 - (bias_strength * 0.3)  # 0.2 to 0.5
        else:
            advantage = "NEUTRAL"
            impact_score = 0.5
        
        return {
            "horse_name": horse.get("name", "Unknown"),
            "draw": draw,
            "advantage": advantage,
            "impact_score": impact_score,
            "bias_type": bias_analysis["bias_type"],
            "bias_strength": bias_analysis["bias_strength"]
        }
    
    def get_draw_advantaged_horses(self, horses: List[Dict], race_context: Dict) -> List[Dict]:
        """
        Get horses with draw advantage.
        
        Args:
            horses: All horses in race
            race_context: Race conditions (track, going, distance, field_size)
            
        Returns:
            Horses with draw advantage, sorted by impact
        """
        # Analyze draw bias
        bias_analysis = self.analyze_draw_bias(
            race_context.get("track", "Unknown"),
            race_context.get("going", "Good"),
            race_context.get("distance", "6f"),
            race_context.get("field_size", len(horses))
        )
        
        # Evaluate each horse
        advantaged = []
        for horse in horses:
            eval_result = self.evaluate_horse_draw(horse, bias_analysis)
            
            if eval_result["advantage"] == "ADVANTAGED":
                advantaged.append({
                    "horse": horse,
                    "evaluation": eval_result
                })
        
        # Sort by impact score
        advantaged.sort(key=lambda x: x["evaluation"]["impact_score"], reverse=True)
        
        return advantaged
    
    def apply_bias_filter(self, horses: List[Dict], race_context: Dict, threshold: float = 0.6) -> List[Dict]:
        """
        Filter horses based on draw bias.
        
        Args:
            horses: All horses
            race_context: Race conditions
            threshold: Minimum impact score to pass
            
        Returns:
            Horses that pass bias filter
        """
        bias_analysis = self.analyze_draw_bias(
            race_context.get("track", "Unknown"),
            race_context.get("going", "Good"),
            race_context.get("distance", "6f"),
            race_context.get("field_size", len(horses))
        )
        
        passed = []
        for horse in horses:
            eval_result = self.evaluate_horse_draw(horse, bias_analysis)
            
            # Pass if impact score meets threshold (advantaged or neutral)
            if eval_result["impact_score"] >= threshold:
                passed.append({
                    "horse": horse,
                    "bias_evaluation": eval_result
                })
        
        return passed


def main():
    """Test BOP module."""
    print("🎯 BOP - Bias/Optimal Positioning")
    print("="*60)
    
    bop = BiasOptimalPositioning()
    
    # Test horses with different draws
    test_horses = [
        {"name": "Low Draw Horse", "number": 2},
        {"name": "Middle Draw Horse", "number": 5},
        {"name": "High Draw Horse", "number": 9}
    ]
    
    test_race = {
        "track": "Yarmouth",
        "going": "Good to Soft",
        "distance": "6f",
        "field_size": 10
    }
    
    # Analyze draw bias
    bias_analysis = bop.analyze_draw_bias(
        test_race["track"],
        test_race["going"],
        test_race["distance"],
        test_race["field_size"]
    )
    
    print(f"\n📊 Draw Bias Analysis:")
    print(f"  Track: {bias_analysis['track']}")
    print(f"  Bias Type: {bias_analysis['bias_type']}")
    print(f"  Severity: {bias_analysis['severity']}")
    print(f"  Bias Strength: {bias_analysis['bias_strength']:.2f}")
    print(f"  Advantaged Stalls: {bias_analysis['advantaged_stalls']}")
    print(f"  Disadvantaged Stalls: {bias_analysis['disadvantaged_stalls']}")
    print(f"\n  Tactical Note: {bias_analysis['tactical_note']}")
    
    # Evaluate each horse
    print(f"\n🎯 Horse Draw Evaluations:")
    for horse in test_horses:
        eval_result = bop.evaluate_horse_draw(horse, bias_analysis)
        status = "✅" if eval_result["advantage"] == "ADVANTAGED" else "⚠️" if eval_result["advantage"] == "NEUTRAL" else "❌"
        print(f"  {status} {horse['name']} (Draw {horse['number']}): {eval_result['advantage']} (Impact: {eval_result['impact_score']:.2f})")
    
    # Get advantaged horses
    advantaged = bop.get_draw_advantaged_horses(test_horses, test_race)
    print(f"\n✅ Horses with Draw Advantage: {len(advantaged)}")
    for item in advantaged:
        print(f"  - {item['horse']['name']} (Draw {item['horse']['number']})")


if __name__ == "__main__":
    main()

