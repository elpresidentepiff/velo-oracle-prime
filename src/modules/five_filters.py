"""
VÉLØ v9.0++ CHAREX - Five-Filter System

The core filtering mechanism that every selection must pass.
No exceptions. No shortcuts.

Five Filters:
1. Form Reality Check - True consistency vs inflated ratings
2. Intent Detection - Trainer, jockey, placement signals
3. Sectional Suitability - Course, going, distance match
4. Market Misdirection - Public bias, odds traps
5. Value Distortion - Implied odds vs true win chance
"""

from typing import Dict, List, Tuple, Optional


class FiveFilters:
    """
    Five-Filter System
    
    Every horse must pass all five filters to be shortlisted.
    This is the Oracle's primary defense against market noise.
    """
    
    def __init__(self, thresholds: Optional[Dict] = None):
        """
        Initialize Five-Filter System.
        
        Args:
            thresholds: Dictionary of threshold values for each filter
        """
        self.thresholds = thresholds or {
            "form_reality_threshold": 0.65,
            "intent_detection_threshold": 0.60,
            "sectional_suitability_threshold": 0.70,
            "market_misdirection_threshold": 0.55,
            "value_distortion_threshold": 0.60
        }
        
        # Odds range (corrected to 3/1 - 20/1)
        self.min_odds = 3.0
        self.max_odds = 20.0
    
    def apply_all_filters(self, horse_data: Dict, race_context: Dict) -> Dict:
        """
        Apply all five filters to a horse.
        
        Args:
            horse_data: Individual horse data
            race_context: Race conditions and context
            
        Returns:
            Filter results with pass/fail for each filter
        """
        results = {
            "horse_name": horse_data.get("name", "Unknown"),
            "filters": {},
            "passed_all": False,
            "passed_count": 0,
            "failed_filters": []
        }
        
        # Filter 1: Form Reality Check
        filter_1 = self.filter_1_form_reality(horse_data)
        results["filters"]["form_reality"] = filter_1
        
        # Filter 2: Intent Detection
        filter_2 = self.filter_2_intent_detection(horse_data)
        results["filters"]["intent_detection"] = filter_2
        
        # Filter 3: Sectional Suitability
        filter_3 = self.filter_3_sectional_suitability(horse_data, race_context)
        results["filters"]["sectional_suitability"] = filter_3
        
        # Filter 4: Market Misdirection
        filter_4 = self.filter_4_market_misdirection(horse_data, race_context)
        results["filters"]["market_misdirection"] = filter_4
        
        # Filter 5: Value Distortion
        filter_5 = self.filter_5_value_distortion(horse_data)
        results["filters"]["value_distortion"] = filter_5
        
        # Count passes
        passed = [f["passed"] for f in results["filters"].values()]
        results["passed_count"] = sum(passed)
        results["passed_all"] = all(passed)
        
        # Identify failed filters
        results["failed_filters"] = [
            name for name, data in results["filters"].items()
            if not data["passed"]
        ]
        
        return results
    
    def filter_1_form_reality(self, horse_data: Dict) -> Dict:
        """
        Filter 1: Form Reality Check
        
        Eliminates horses with inflated ratings or inconsistent form.
        Looks for TRUE consistency, not just high ratings.
        
        Args:
            horse_data: Horse performance data
            
        Returns:
            Filter result
        """
        form = horse_data.get("form", "")
        
        if not form:
            return {
                "passed": False,
                "score": 0.0,
                "reason": "No form data available"
            }
        
        # Analyze last 6 runs
        recent_form = form[:6]
        
        # Count top-4 finishes
        top_4_finishes = sum(1 for c in recent_form if c.isdigit() and int(c) <= 4)
        
        # Consistency score
        consistency = top_4_finishes / len(recent_form) if recent_form else 0.0
        
        # Check for at least 1 top-4 in last 3
        last_3 = recent_form[:3]
        has_recent_top_4 = any(c.isdigit() and int(c) <= 4 for c in last_3)
        
        # Pass threshold
        passed = (
            consistency >= self.thresholds["form_reality_threshold"] and
            has_recent_top_4
        )
        
        return {
            "passed": passed,
            "score": consistency,
            "reason": f"Consistency: {consistency:.2f}, Recent top-4: {has_recent_top_4}",
            "details": {
                "form": form,
                "top_4_count": top_4_finishes,
                "consistency": consistency
            }
        }
    
    def filter_2_intent_detection(self, horse_data: Dict) -> Dict:
        """
        Filter 2: Intent Detection
        
        Detects trainer and jockey signals indicating readiness.
        Uses TIE (Trainer Intention Engine) logic.
        
        Args:
            horse_data: Horse data with trainer/jockey info
            
        Returns:
            Filter result
        """
        trainer_stats = horse_data.get("trainer_stats", {})
        jockey_stats = horse_data.get("jockey_stats", {})
        
        trainer_roi = trainer_stats.get("roi", 0.0)
        jockey_roi = jockey_stats.get("roi", 0.0)
        
        # Combined intent score
        intent_score = (trainer_roi + jockey_roi) / 40.0  # Normalize to 0-1
        intent_score = min(1.0, max(0.0, intent_score))
        
        # Check for positive signals
        has_intent = (
            trainer_roi >= 10.0 or
            jockey_roi >= 10.0 or
            intent_score >= self.thresholds["intent_detection_threshold"]
        )
        
        return {
            "passed": has_intent,
            "score": intent_score,
            "reason": f"Trainer ROI: {trainer_roi}%, Jockey ROI: {jockey_roi}%",
            "details": {
                "trainer_roi": trainer_roi,
                "jockey_roi": jockey_roi,
                "intent_score": intent_score
            }
        }
    
    def filter_3_sectional_suitability(self, horse_data: Dict, race_context: Dict) -> Dict:
        """
        Filter 3: Sectional Suitability
        
        Matches horse's pace profile to race conditions.
        Distance, going, course suitability.
        
        Args:
            horse_data: Horse data
            race_context: Race conditions
            
        Returns:
            Filter result
        """
        # TODO: Implement full sectional analysis with SSM
        # Placeholder logic
        
        distance = race_context.get("distance", "")
        going = race_context.get("going", "")
        
        # Simple suitability check (to be enhanced)
        suitability_score = 0.75  # Placeholder
        
        passed = suitability_score >= self.thresholds["sectional_suitability_threshold"]
        
        return {
            "passed": passed,
            "score": suitability_score,
            "reason": f"Distance: {distance}, Going: {going}",
            "details": {
                "distance": distance,
                "going": going,
                "suitability_score": suitability_score
            }
        }
    
    def filter_4_market_misdirection(self, horse_data: Dict, race_context: Dict) -> Dict:
        """
        Filter 4: Market Misdirection
        
        Identifies public bias, odds traps, and manipulation.
        Filters out false favorites and market distortions.
        
        Args:
            horse_data: Horse data with odds
            race_context: Market context
            
        Returns:
            Filter result
        """
        odds = horse_data.get("odds", 0.0)
        
        # Check odds range (3/1 to 20/1)
        in_target_range = (self.min_odds <= odds <= self.max_odds)
        
        # Check for odds crash (from SYNTH if available)
        # Placeholder: assume no crash for now
        no_crash = True
        
        # Market distortion score
        if odds < self.min_odds:
            distortion_score = 0.3  # Too short - public favorite
        elif odds > self.max_odds:
            distortion_score = 0.4  # Too long - market rejection
        else:
            distortion_score = 0.8  # In sweet spot
        
        passed = (
            in_target_range and
            no_crash and
            distortion_score >= self.thresholds["market_misdirection_threshold"]
        )
        
        return {
            "passed": passed,
            "score": distortion_score,
            "reason": f"Odds: {odds} (Target: {self.min_odds}-{self.max_odds})",
            "details": {
                "odds": odds,
                "in_target_range": in_target_range,
                "no_crash": no_crash,
                "distortion_score": distortion_score
            }
        }
    
    def filter_5_value_distortion(self, horse_data: Dict) -> Dict:
        """
        Filter 5: Value Distortion
        
        Compares implied probability from odds vs true win chance.
        Identifies overlays where true chance > implied odds.
        
        Args:
            horse_data: Horse data with odds and ratings
            
        Returns:
            Filter result
        """
        odds = horse_data.get("odds", 0.0)
        
        if odds <= 0:
            return {
                "passed": False,
                "score": 0.0,
                "reason": "Invalid odds"
            }
        
        # Implied probability from odds
        implied_prob = 1.0 / odds
        
        # Estimate true probability (placeholder - to be enhanced with full analysis)
        # This should come from SQPE + V9PM confidence index
        estimated_true_prob = 0.15  # Placeholder
        
        # Value score: true prob vs implied prob
        value_score = estimated_true_prob / implied_prob if implied_prob > 0 else 0.0
        
        # Normalize to 0-1
        value_score = min(1.0, value_score)
        
        # Overlay exists if true prob > implied prob
        is_overlay = (estimated_true_prob > implied_prob)
        
        passed = (
            is_overlay and
            value_score >= self.thresholds["value_distortion_threshold"]
        )
        
        return {
            "passed": passed,
            "score": value_score,
            "reason": f"Implied: {implied_prob:.2%}, Estimated: {estimated_true_prob:.2%}",
            "details": {
                "odds": odds,
                "implied_probability": implied_prob,
                "estimated_probability": estimated_true_prob,
                "value_score": value_score,
                "is_overlay": is_overlay
            }
        }
    
    def filter_field(self, horses: List[Dict], race_context: Dict) -> List[Dict]:
        """
        Apply Five-Filter System to entire field.
        
        Args:
            horses: List of all horses in race
            race_context: Race conditions
            
        Returns:
            List of horses that passed all filters
        """
        passed_horses = []
        
        for horse in horses:
            result = self.apply_all_filters(horse, race_context)
            
            if result["passed_all"]:
                passed_horses.append({
                    "horse_data": horse,
                    "filter_results": result
                })
        
        return passed_horses
    
    def get_shortlist(self, horses: List[Dict], race_context: Dict, limit: int = 3) -> List[Dict]:
        """
        Get shortlist of top horses that passed filters.
        
        Args:
            horses: List of all horses
            race_context: Race conditions
            limit: Maximum number in shortlist
            
        Returns:
            Shortlisted horses
        """
        # Filter field
        passed = self.filter_field(horses, race_context)
        
        # Sort by number of filters passed (all should be 5) then by scores
        passed.sort(
            key=lambda x: (
                x["filter_results"]["passed_count"],
                sum(f["score"] for f in x["filter_results"]["filters"].values())
            ),
            reverse=True
        )
        
        return passed[:limit]


if __name__ == "__main__":
    print("🎯 Five-Filter System")
    print("="*60)
    
    filters = FiveFilters()
    
    # Test horse
    test_horse = {
        "name": "Test Runner A",
        "form": "121343",
        "odds": 8.0,
        "trainer_stats": {"roi": 15.0},
        "jockey_stats": {"roi": 12.0}
    }
    
    test_race = {
        "distance": "6f",
        "going": "Good"
    }
    
    result = filters.apply_all_filters(test_horse, test_race)
    
    print(f"\nHorse: {result['horse_name']}")
    print(f"Passed All Filters: {'✅ YES' if result['passed_all'] else '❌ NO'}")
    print(f"Passed Count: {result['passed_count']}/5")
    
    print(f"\nFilter Results:")
    for filter_name, filter_data in result['filters'].items():
        status = "✅" if filter_data['passed'] else "❌"
        print(f"  {status} {filter_name}: {filter_data['reason']}")
    
    if result['failed_filters']:
        print(f"\nFailed Filters: {', '.join(result['failed_filters'])}")

