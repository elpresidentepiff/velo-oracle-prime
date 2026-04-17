"""
VÉLØ v9.0++ CHAREX - Sub-Quadratic Prediction Engine (SQPE)

Core signal extractor reducing market noise and elevating truth vectors.
Detects strongest horse via sub-quadratic weighting of form, intent, and variance.
"""

import numpy as np
from typing import Dict, List, Tuple


class SQPE:
    """
    Sub-Quadratic Prediction Engine
    
    Extracts high-signal patterns from noisy race data using
    sub-quadratic weighting algorithms.
    """
    
    def __init__(self, weights: Dict = None):
        """
        Initialize SQPE with analytical weights.
        
        Args:
            weights: Dictionary containing form_signal, intent_signal, 
                    variance_signal, and noise_reduction_threshold
        """
        self.weights = weights or {
            "form_signal": 0.25,
            "intent_signal": 0.20,
            "variance_signal": 0.15,
            "noise_reduction_threshold": 0.30
        }
        
    def extract_signal(self, horse_data: Dict) -> float:
        """
        Extract signal strength from horse data.
        
        Args:
            horse_data: Dictionary containing horse performance metrics
            
        Returns:
            Signal strength score (0.0 to 1.0)
        """
        form_score = self._calculate_form_signal(horse_data)
        intent_score = self._calculate_intent_signal(horse_data)
        variance_score = self._calculate_variance_signal(horse_data)
        
        # Sub-quadratic weighting
        signal = (
            form_score * self.weights["form_signal"] +
            intent_score * self.weights["intent_signal"] +
            variance_score * self.weights["variance_signal"]
        )
        
        # Apply noise reduction
        if signal < self.weights["noise_reduction_threshold"]:
            signal *= 0.5  # Dampen weak signals
            
        return min(1.0, max(0.0, signal))
    
    def _calculate_form_signal(self, horse_data: Dict) -> float:
        """
        Calculate form signal from recent performance.
        
        Analyzes consistency, class, and recent results.
        """
        # TODO: Implement full form analysis
        # Placeholder logic
        form = horse_data.get("form", "")
        if not form:
            return 0.0
        
        # Simple form scoring (to be enhanced)
        form_chars = list(form[:6])  # Last 6 runs
        wins = form_chars.count('1')
        places = sum(1 for c in form_chars if c in ['1', '2', '3'])
        
        consistency = places / len(form_chars) if form_chars else 0.0
        win_rate = wins / len(form_chars) if form_chars else 0.0
        
        return (consistency * 0.6 + win_rate * 0.4)
    
    def _calculate_intent_signal(self, horse_data: Dict) -> float:
        """
        Calculate trainer/jockey intent signal.
        
        Detects placement strategy and booking patterns.
        """
        # TODO: Implement intent detection logic
        # Placeholder
        jockey_stats = horse_data.get("jockey_stats", {})
        trainer_stats = horse_data.get("trainer_stats", {})
        
        jockey_roi = jockey_stats.get("roi", 0.0)
        trainer_roi = trainer_stats.get("roi", 0.0)
        
        # Normalize ROI to 0-1 scale
        intent_score = min(1.0, (jockey_roi + trainer_roi) / 30.0)
        
        return max(0.0, intent_score)
    
    def _calculate_variance_signal(self, horse_data: Dict) -> float:
        """
        Calculate performance variance signal.
        
        Measures consistency vs volatility in recent runs.
        """
        # TODO: Implement variance analysis
        # Placeholder
        recent_ratings = horse_data.get("recent_ratings", [])
        
        if len(recent_ratings) < 2:
            return 0.5  # Neutral if insufficient data
        
        variance = np.var(recent_ratings)
        mean_rating = np.mean(recent_ratings)
        
        # Lower variance = higher signal (more consistent)
        if mean_rating > 0:
            cv = variance / mean_rating  # Coefficient of variation
            variance_score = 1.0 / (1.0 + cv)  # Inverse relationship
        else:
            variance_score = 0.0
        
        return min(1.0, max(0.0, variance_score))
    
    def rank_horses(self, race_data: List[Dict]) -> List[Tuple[str, float]]:
        """
        Rank all horses in a race by signal strength.
        
        Args:
            race_data: List of horse data dictionaries
            
        Returns:
            List of (horse_name, signal_score) tuples, sorted by score
        """
        rankings = []
        
        for horse in race_data:
            horse_name = horse.get("name", "Unknown")
            signal = self.extract_signal(horse)
            rankings.append((horse_name, signal))
        
        # Sort by signal strength (descending)
        rankings.sort(key=lambda x: x[1], reverse=True)
        
        return rankings
    
    def filter_noise(self, rankings: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """
        Filter out low-signal horses below noise threshold.
        
        Args:
            rankings: List of (horse_name, signal_score) tuples
            
        Returns:
            Filtered list with only high-signal horses
        """
        threshold = self.weights["noise_reduction_threshold"]
        return [(name, score) for name, score in rankings if score >= threshold]


if __name__ == "__main__":
    # Test SQPE
    print("🧠 SQPE - Sub-Quadratic Prediction Engine")
    print("="*50)
    
    sqpe = SQPE()
    
    # Sample horse data
    test_horse = {
        "name": "Test Runner",
        "form": "121343",
        "jockey_stats": {"roi": 15.0},
        "trainer_stats": {"roi": 12.0},
        "recent_ratings": [85, 87, 84, 86, 85]
    }
    
    signal = sqpe.extract_signal(test_horse)
    print(f"\nSignal extracted for {test_horse['name']}: {signal:.3f}")

