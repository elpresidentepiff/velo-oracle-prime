"""
VÉLØ v9.0++ CHAREX - DLV (Dynamic Longshot Validator)

Identifies genuine longshot value vs hopeless outsiders.
Validates horses at 10/1+ that have legitimate winning chances.

Validates:
- Hidden class droppers
- Returning handicappers
- Underestimated improvers
- Tactical longshots with edge
"""

from typing import Dict, List, Optional


class DynamicLongshotValidator:
    """
    DLV - Dynamic Longshot Validator
    
    Separates genuine longshot value from hopeless outsiders.
    Finds horses the market has mispriced at longer odds.
    """
    
    def __init__(self):
        """Initialize DLV module."""
        self.name = "DLV"
        self.version = "v9.0++"
        
        # Longshot odds range
        self.min_longshot_odds = 10.0
        self.max_longshot_odds = 20.0
        
        # Validation thresholds
        self.min_validation_score = 0.65
    
    def validate_longshot(self, horse: Dict, race_context: Dict) -> Dict:
        """
        Validate if a longshot has genuine winning chance.
        
        Args:
            horse: Horse data
            race_context: Race conditions
            
        Returns:
            Validation result
        """
        odds = horse.get("odds", 0.0)
        
        # Check if horse is in longshot range
        if not (self.min_longshot_odds <= odds <= self.max_longshot_odds):
            return {
                "horse_name": horse.get("name", "Unknown"),
                "odds": odds,
                "is_longshot": False,
                "is_valid": False,
                "validation_score": 0.0,
                "reason": f"Odds {odds} outside longshot range ({self.min_longshot_odds}-{self.max_longshot_odds})"
            }
        
        # Calculate validation score
        validation_score = 0.0
        validation_factors = []
        
        # Factor 1: Class drop
        class_drop_score = self._check_class_drop(horse, race_context)
        validation_score += class_drop_score
        if class_drop_score > 0:
            validation_factors.append("CLASS_DROP")
        
        # Factor 2: Returning handicapper
        handicap_score = self._check_handicap_potential(horse)
        validation_score += handicap_score
        if handicap_score > 0:
            validation_factors.append("HANDICAP_EDGE")
        
        # Factor 3: Recent improvement
        improvement_score = self._check_improvement_trend(horse)
        validation_score += improvement_score
        if improvement_score > 0:
            validation_factors.append("IMPROVING")
        
        # Factor 4: Tactical edge
        tactical_score = self._check_tactical_edge(horse, race_context)
        validation_score += tactical_score
        if tactical_score > 0:
            validation_factors.append("TACTICAL_EDGE")
        
        # Normalize score (0.0 to 1.0)
        validation_score = min(1.0, validation_score / 4.0)
        
        # Determine if valid longshot
        is_valid = validation_score >= self.min_validation_score
        
        return {
            "horse_name": horse.get("name", "Unknown"),
            "odds": odds,
            "is_longshot": True,
            "is_valid": is_valid,
            "validation_score": validation_score,
            "validation_factors": validation_factors,
            "reason": self._generate_validation_reason(is_valid, validation_factors, validation_score)
        }
    
    def _check_class_drop(self, horse: Dict, race_context: Dict) -> float:
        """
        Check if horse is dropping in class.
        
        Args:
            horse: Horse data
            race_context: Race conditions
            
        Returns:
            Class drop score (0.0 to 1.0)
        """
        # TODO: Implement with real class data
        # Placeholder: check if OR is higher than race class suggests
        official_rating = horse.get("official_rating", 0)
        
        # Simple heuristic: if OR > 70, might be dropping
        if official_rating >= 75:
            return 0.8
        elif official_rating >= 70:
            return 0.5
        
        return 0.0
    
    def _check_handicap_potential(self, horse: Dict) -> float:
        """
        Check if horse has handicap potential.
        
        Args:
            horse: Horse data
            
        Returns:
            Handicap score (0.0 to 1.0)
        """
        # Check weight vs rating
        weight = horse.get("weight", 0)
        official_rating = horse.get("official_rating", 0)
        
        # If carrying low weight relative to rating, could be well-handicapped
        # Simplified logic
        if weight > 0 and weight < 125:
            return 0.7
        
        return 0.0
    
    def _check_improvement_trend(self, horse: Dict) -> float:
        """
        Check if horse is on an improving trend.
        
        Args:
            horse: Horse data
            
        Returns:
            Improvement score (0.0 to 1.0)
        """
        form = horse.get("form", "")
        
        if not form or len(form) < 3:
            return 0.0
        
        # Check for improvement pattern (getting better positions)
        recent_positions = [int(c) for c in form[:3] if c.isdigit()]
        
        if len(recent_positions) >= 2:
            # Check if recent runs are better than earlier runs
            if recent_positions[0] < recent_positions[-1]:
                return 0.8
            elif recent_positions[0] <= 4:
                return 0.5
        
        return 0.0
    
    def _check_tactical_edge(self, horse: Dict, race_context: Dict) -> float:
        """
        Check if horse has tactical edge (pace, draw, etc.).
        
        Args:
            horse: Horse data
            race_context: Race conditions
            
        Returns:
            Tactical score (0.0 to 1.0)
        """
        # TODO: Integrate with SSM and BOP
        # Placeholder: check if trainer/jockey combo has good ROI
        trainer_stats = horse.get("trainer_stats", {})
        jockey_stats = horse.get("jockey_stats", {})
        
        trainer_roi = trainer_stats.get("roi", 0.0)
        jockey_roi = jockey_stats.get("roi", 0.0)
        
        if trainer_roi >= 15.0 or jockey_roi >= 15.0:
            return 0.7
        elif trainer_roi >= 10.0 or jockey_roi >= 10.0:
            return 0.4
        
        return 0.0
    
    def _generate_validation_reason(self, is_valid: bool, factors: List[str], score: float) -> str:
        """
        Generate validation reason.
        
        Args:
            is_valid: Whether longshot is valid
            factors: Validation factors
            score: Validation score
            
        Returns:
            Reason string
        """
        if is_valid:
            factors_str = ", ".join(factors) if factors else "Multiple factors"
            return f"✅ VALID LONGSHOT: {factors_str}. Score: {score:.2f}. Genuine value opportunity."
        else:
            return f"❌ INVALID LONGSHOT: Insufficient validation. Score: {score:.2f}. Likely hopeless outsider."
    
    def get_valid_longshots(self, horses: List[Dict], race_context: Dict) -> List[Dict]:
        """
        Get all valid longshots from the field.
        
        Args:
            horses: All horses
            race_context: Race conditions
            
        Returns:
            Valid longshots sorted by validation score
        """
        valid_longshots = []
        
        for horse in horses:
            validation = self.validate_longshot(horse, race_context)
            
            if validation["is_longshot"] and validation["is_valid"]:
                valid_longshots.append({
                    "horse": horse,
                    "validation": validation
                })
        
        # Sort by validation score
        valid_longshots.sort(
            key=lambda x: x["validation"]["validation_score"],
            reverse=True
        )
        
        return valid_longshots
    
    def filter_hopeless_outsiders(self, horses: List[Dict], race_context: Dict) -> List[Dict]:
        """
        Filter out hopeless outsiders.
        
        Args:
            horses: All horses
            race_context: Race conditions
            
        Returns:
            Horses that are NOT hopeless outsiders
        """
        filtered = []
        
        for horse in horses:
            odds = horse.get("odds", 0.0)
            
            # If not a longshot, include
            if odds < self.min_longshot_odds:
                filtered.append(horse)
                continue
            
            # If longshot, validate
            validation = self.validate_longshot(horse, race_context)
            
            if validation["is_valid"]:
                filtered.append(horse)
        
        return filtered


def main():
    """Test DLV module."""
    print("💎 DLV - Dynamic Longshot Validator")
    print("="*60)
    
    dlv = DynamicLongshotValidator()
    
    # Test horses
    test_horses = [
        {
            "name": "Valid Longshot",
            "odds": 12.0,
            "form": "234",
            "official_rating": 76,
            "weight": 123,
            "trainer_stats": {"roi": 16.0},
            "jockey_stats": {"roi": 14.0}
        },
        {
            "name": "Hopeless Outsider",
            "odds": 15.0,
            "form": "0999",
            "official_rating": 55,
            "weight": 135,
            "trainer_stats": {"roi": 2.0},
            "jockey_stats": {"roi": 3.0}
        },
        {
            "name": "Improving Longshot",
            "odds": 14.0,
            "form": "321",
            "official_rating": 72,
            "weight": 124,
            "trainer_stats": {"roi": 12.0},
            "jockey_stats": {"roi": 11.0}
        }
    ]
    
    test_race = {
        "class": "5",
        "distance": "6f"
    }
    
    print(f"\n📊 Longshot Validation Results:")
    for horse in test_horses:
        validation = dlv.validate_longshot(horse, test_race)
        status = "✅ VALID" if validation["is_valid"] else "❌ INVALID"
        print(f"\n  {status} {horse['name']} ({horse['odds']}/1)")
        print(f"    Validation Score: {validation['validation_score']:.2f}")
        print(f"    Factors: {', '.join(validation.get('validation_factors', [])) if validation.get('validation_factors') else 'None'}")
        print(f"    {validation['reason']}")
    
    # Get valid longshots
    valid = dlv.get_valid_longshots(test_horses, test_race)
    
    print(f"\n\n💎 VALID LONGSHOTS ({len(valid)}):")
    for item in valid:
        horse = item["horse"]
        val = item["validation"]
        print(f"  ✅ {horse['name']} ({horse['odds']}/1) - Score: {val['validation_score']:.2f}")


if __name__ == "__main__":
    main()

