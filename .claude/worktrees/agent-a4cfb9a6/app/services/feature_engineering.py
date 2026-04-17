"""
VÉLØ Oracle - Feature Engineering
20 engineered features for horse racing prediction
"""
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class FeatureEngineer:
    """Feature engineering pipeline for VÉLØ Oracle"""
    
    def __init__(self):
        self.feature_names = [
            "speed_normalized",
            "form_decay",
            "weight_penalty",
            "trainer_intent_factor",
            "jockey_synergy",
            "distance_efficiency",
            "draw_bias",
            "late_burst_index",
            "pace_map_position",
            "sectional_delta",
            "variance_score",
            "trend_score",
            "freshness_penalty",
            "course_affinity",
            "jockey_sr_adj",
            "trainer_sr_adj",
            "odds_value_gap",
            "market_move_1h",
            "market_move_24h",
            "combined_velocity_index"
        ]
    
    def extract_all_features(self, runner: Dict[str, Any], race: Dict[str, Any], 
                            historical: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Extract all 20 engineered features for a runner"""
        features = {}
        
        # Core features
        features["speed_normalized"] = self.speed_normalized(runner, race)
        features["form_decay"] = self.form_decay(runner)
        features["weight_penalty"] = self.weight_penalty(runner, race)
        features["trainer_intent_factor"] = self.trainer_intent_factor(runner, historical)
        features["jockey_synergy"] = self.jockey_synergy(runner, historical)
        
        # Distance and position features
        features["distance_efficiency"] = self.distance_efficiency(runner, race)
        features["draw_bias"] = self.draw_bias(runner, race)
        features["late_burst_index"] = self.late_burst_index(runner)
        features["pace_map_position"] = self.pace_map_position(runner, race)
        features["sectional_delta"] = self.sectional_delta(runner)
        
        # Statistical features
        features["variance_score"] = self.variance_score(runner, historical)
        features["trend_score"] = self.trend_score(runner, historical)
        features["freshness_penalty"] = self.freshness_penalty(runner)
        features["course_affinity"] = self.course_affinity(runner, race, historical)
        
        # Participant features
        features["jockey_sr_adj"] = self.jockey_sr_adj(runner, historical)
        features["trainer_sr_adj"] = self.trainer_sr_adj(runner, historical)
        
        # Market features
        features["odds_value_gap"] = self.odds_value_gap(runner)
        features["market_move_1h"] = self.market_move_1h(runner, historical)
        features["market_move_24h"] = self.market_move_24h(runner, historical)
        
        # Combined index
        features["combined_velocity_index"] = self.combined_velocity_index(features)
        
        return features
    
    # Feature 1: Speed Normalized
    def speed_normalized(self, runner: Dict[str, Any], race: Dict[str, Any]) -> float:
        """Normalize speed rating by distance and track condition"""
        speed_rating = runner.get("speed_ratings", {}).get("adjusted", 100.0)
        distance = race.get("distance", 1600)
        going_factor = self._going_factor(race.get("going", "Good"))
        
        # Normalize: speed per 100m, adjusted for going
        normalized = (speed_rating / (distance / 100)) * going_factor
        return min(max(normalized / 10, 0.0), 1.0)  # Scale to [0, 1]
    
    # Feature 2: Form Decay
    def form_decay(self, runner: Dict[str, Any]) -> float:
        """Calculate form decay based on recent performance"""
        form_string = runner.get("form", "0-0-0-0-0")
        positions = [int(p) if p.isdigit() else 10 for p in form_string.split("-")]
        
        # Exponential decay weights
        weights = [0.4, 0.3, 0.2, 0.1]
        weighted_form = sum(
            (1 / pos if pos > 0 else 0) * weights[i] 
            for i, pos in enumerate(positions[:4])
        )
        return min(weighted_form, 1.0)
    
    # Feature 3: Weight Penalty
    def weight_penalty(self, runner: Dict[str, Any], race: Dict[str, Any]) -> float:
        """Calculate weight penalty relative to field average"""
        runner_weight = runner.get("weight", 57.0)
        # Assume average weight is 56kg, each kg = 2% penalty
        penalty = (runner_weight - 56.0) * 0.02
        return max(1.0 - penalty, 0.0)
    
    # Feature 4: Trainer Intent Factor
    def trainer_intent_factor(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Detect trainer intent signals (gear changes, jockey booking, etc.)"""
        if not historical:
            return 0.5
        
        # Stub: Check for gear changes, jockey upgrades, etc.
        gear_change = runner.get("gear") != historical.get("last_gear")
        jockey_upgrade = runner.get("jockey") in ["James McDonald", "Hugh Bowman"]  # Top jockeys
        
        intent_score = 0.5
        if gear_change:
            intent_score += 0.2
        if jockey_upgrade:
            intent_score += 0.3
        
        return min(intent_score, 1.0)
    
    # Feature 5: Jockey Synergy
    def jockey_synergy(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Calculate jockey-trainer-horse synergy"""
        if not historical:
            return 0.5
        
        # Stub: Check historical win rate for this combination
        combo_wins = historical.get("jockey_trainer_wins", 0)
        combo_starts = historical.get("jockey_trainer_starts", 1)
        
        synergy = combo_wins / combo_starts if combo_starts > 0 else 0.5
        return min(synergy, 1.0)
    
    # Feature 6: Distance Efficiency
    def distance_efficiency(self, runner: Dict[str, Any], race: Dict[str, Any]) -> float:
        """Calculate runner's efficiency at this distance"""
        distance = race.get("distance", 1600)
        # Stub: Optimal distance range for this horse
        optimal_min = 1400
        optimal_max = 1800
        
        if optimal_min <= distance <= optimal_max:
            return 1.0
        else:
            deviation = min(abs(distance - optimal_min), abs(distance - optimal_max))
            return max(1.0 - (deviation / 400), 0.0)
    
    # Feature 7: Draw Bias
    def draw_bias(self, runner: Dict[str, Any], race: Dict[str, Any]) -> float:
        """Calculate draw advantage/disadvantage"""
        draw = runner.get("draw", 10)
        distance = race.get("distance", 1600)
        
        # Shorter races favor inside draws
        if distance < 1200:
            optimal_draw = 3
        elif distance < 1600:
            optimal_draw = 5
        else:
            optimal_draw = 8
        
        bias = 1.0 - (abs(draw - optimal_draw) * 0.05)
        return max(bias, 0.0)
    
    # Feature 8: Late Burst Index
    def late_burst_index(self, runner: Dict[str, Any]) -> float:
        """Calculate late-race acceleration capability"""
        sectionals = runner.get("sectional_times", {})
        last_200m = sectionals.get("last_200m")
        last_400m = sectionals.get("last_400m")
        
        if not last_200m or not last_400m:
            return 0.5
        
        # Compare last 200m to average of last 400m
        avg_200m = last_400m / 2
        burst = (avg_200m - last_200m) / avg_200m if avg_200m > 0 else 0
        
        return min(max(burst + 0.5, 0.0), 1.0)
    
    # Feature 9: Pace Map Position
    def pace_map_position(self, runner: Dict[str, Any], race: Dict[str, Any]) -> float:
        """Determine runner's position in pace map (leader/mid/closer)"""
        # Stub: Analyze early speed indicators
        form_string = runner.get("form", "0-0-0-0-0")
        positions = [int(p) if p.isdigit() else 10 for p in form_string.split("-")]
        
        # Leaders (early positions) get higher score in speed races
        avg_position = sum(positions[:3]) / 3 if positions else 5
        
        if avg_position <= 3:
            return 0.9  # Leader
        elif avg_position <= 6:
            return 0.6  # Mid-pack
        else:
            return 0.4  # Closer
    
    # Feature 10: Sectional Delta
    def sectional_delta(self, runner: Dict[str, Any]) -> float:
        """Calculate variance in sectional times"""
        sectionals = runner.get("sectional_times", {})
        times = [v for v in sectionals.values() if v is not None]
        
        if len(times) < 2:
            return 0.5
        
        # Lower variance = more consistent
        variance = sum((t - sum(times)/len(times))**2 for t in times) / len(times)
        consistency = 1.0 / (1.0 + variance)
        
        return min(consistency, 1.0)
    
    # Feature 11: Variance Score
    def variance_score(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Calculate performance variance over recent starts"""
        if not historical:
            return 0.5
        
        recent_positions = historical.get("recent_positions", [5, 5, 5])
        if len(recent_positions) < 2:
            return 0.5
        
        mean_pos = sum(recent_positions) / len(recent_positions)
        variance = sum((p - mean_pos)**2 for p in recent_positions) / len(recent_positions)
        
        # Lower variance = more reliable
        reliability = 1.0 / (1.0 + variance)
        return min(reliability, 1.0)
    
    # Feature 12: Trend Score
    def trend_score(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Calculate performance trend (improving/declining)"""
        form_string = runner.get("form", "5-5-5-5-5")
        positions = [int(p) if p.isdigit() else 10 for p in form_string.split("-")]
        
        if len(positions) < 3:
            return 0.5
        
        # Calculate trend: recent vs older
        recent_avg = sum(positions[:2]) / 2
        older_avg = sum(positions[2:4]) / 2 if len(positions) >= 4 else recent_avg
        
        # Improving = lower recent positions
        trend = (older_avg - recent_avg) / 10  # Normalize
        return min(max(trend + 0.5, 0.0), 1.0)
    
    # Feature 13: Freshness Penalty
    def freshness_penalty(self, runner: Dict[str, Any]) -> float:
        """Calculate penalty for long breaks or over-racing"""
        days_since_last = runner.get("last_start_days", 21)
        
        # Optimal freshness: 14-28 days
        if 14 <= days_since_last <= 28:
            return 1.0
        elif days_since_last < 14:
            # Too fresh/backing up
            return 1.0 - ((14 - days_since_last) * 0.03)
        else:
            # Too long a break
            return 1.0 - ((days_since_last - 28) * 0.01)
        
        return max(0.0, min(1.0, 1.0))
    
    # Feature 14: Course Affinity
    def course_affinity(self, runner: Dict[str, Any], race: Dict[str, Any], 
                       historical: Optional[Dict] = None) -> float:
        """Calculate runner's performance at this course"""
        if not historical:
            return 0.5
        
        course = race.get("course", "Unknown")
        course_stats = historical.get("course_stats", {}).get(course, {})
        
        wins = course_stats.get("wins", 0)
        starts = course_stats.get("starts", 1)
        
        win_rate = wins / starts if starts > 0 else 0.5
        return min(win_rate * 2, 1.0)  # Scale up
    
    # Feature 15: Jockey Strike Rate Adjusted
    def jockey_sr_adj(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Jockey strike rate adjusted for field quality"""
        if not historical:
            return 0.5
        
        jockey_stats = historical.get("jockey_stats", {})
        wins = jockey_stats.get("wins", 50)
        starts = jockey_stats.get("starts", 500)
        
        strike_rate = wins / starts if starts > 0 else 0.1
        return min(strike_rate * 5, 1.0)  # Scale to [0, 1]
    
    # Feature 16: Trainer Strike Rate Adjusted
    def trainer_sr_adj(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Trainer strike rate adjusted for field quality"""
        if not historical:
            return 0.5
        
        trainer_stats = historical.get("trainer_stats", {})
        wins = trainer_stats.get("wins", 100)
        starts = trainer_stats.get("starts", 800)
        
        strike_rate = wins / starts if starts > 0 else 0.125
        return min(strike_rate * 4, 1.0)  # Scale to [0, 1]
    
    # Feature 17: Odds Value Gap
    def odds_value_gap(self, runner: Dict[str, Any]) -> float:
        """Gap between model probability and market odds"""
        odds = runner.get("odds", 5.0)
        implied_prob = 1.0 / odds if odds > 0 else 0.2
        
        # Stub: Compare to model probability (would come from model)
        model_prob = 0.25  # Placeholder
        
        value_gap = model_prob - implied_prob
        return min(max(value_gap + 0.5, 0.0), 1.0)
    
    # Feature 18: Market Move 1h
    def market_move_1h(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Market movement in last hour"""
        if not historical:
            return 0.5
        
        current_odds = runner.get("odds", 5.0)
        odds_1h_ago = historical.get("odds_1h_ago", current_odds)
        
        # Positive movement = odds drifting (less money)
        movement = (current_odds - odds_1h_ago) / odds_1h_ago if odds_1h_ago > 0 else 0
        
        # Normalize: shortening odds (negative movement) = higher score
        return min(max(0.5 - movement, 0.0), 1.0)
    
    # Feature 19: Market Move 24h
    def market_move_24h(self, runner: Dict[str, Any], historical: Optional[Dict] = None) -> float:
        """Market movement in last 24 hours"""
        if not historical:
            return 0.5
        
        current_odds = runner.get("odds", 5.0)
        odds_24h_ago = historical.get("odds_24h_ago", current_odds)
        
        # Positive movement = odds drifting
        movement = (current_odds - odds_24h_ago) / odds_24h_ago if odds_24h_ago > 0 else 0
        
        # Normalize: shortening odds = higher score
        return min(max(0.5 - movement, 0.0), 1.0)
    
    # Feature 20: Combined Velocity Index
    def combined_velocity_index(self, features: Dict[str, float]) -> float:
        """Combine multiple velocity indicators into single index"""
        # Weighted combination of speed, pace, and momentum features
        speed_component = features.get("speed_normalized", 0.5) * 0.3
        pace_component = features.get("pace_map_position", 0.5) * 0.2
        burst_component = features.get("late_burst_index", 0.5) * 0.2
        trend_component = features.get("trend_score", 0.5) * 0.15
        market_component = (features.get("market_move_1h", 0.5) + 
                          features.get("market_move_24h", 0.5)) / 2 * 0.15
        
        combined = (speed_component + pace_component + burst_component + 
                   trend_component + market_component)
        
        return min(combined, 1.0)
    
    # Helper methods
    def _going_factor(self, going: str) -> float:
        """Convert going description to numeric factor"""
        going_map = {
            "Firm": 1.1,
            "Good": 1.0,
            "Good 4": 1.0,
            "Soft": 0.95,
            "Soft 5": 0.95,
            "Soft 6": 0.92,
            "Soft 7": 0.90,
            "Heavy": 0.85,
            "Heavy 8": 0.85,
            "Heavy 9": 0.82,
            "Heavy 10": 0.80
        }
        return going_map.get(going, 1.0)
    
    def get_feature_names(self) -> List[str]:
        """Return list of all feature names"""
        return self.feature_names


# Convenience function
def extract_features(runner: Dict[str, Any], race: Dict[str, Any], 
                    historical: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Extract all features for a runner"""
    engineer = FeatureEngineer()
    return engineer.extract_all_features(runner, race, historical)
