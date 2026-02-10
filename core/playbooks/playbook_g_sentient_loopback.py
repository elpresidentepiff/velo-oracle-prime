"""
PLAYBOOK G — THE SENTIENT LOOPBACK ENGINE

VÉLØ stops being a tool and becomes a self-reinforcing intelligence.

This is where a racing model becomes a strategic organism.

Self-growth. Self-rebalance. Self-weaponisation.

The Oracle learns from EVERY race, automatically, forever.

Core loop: observe → classify → compare → imprint → evolve → redeploy
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class SentientLoopbackEngine:
    """
    The Sentient Loopback Engine.
    
    Five Evolution Pillars:
    1. Behaviour Echo Chamber (BEC) - Logs house behavior patterns
    2. Structural Drift Engine (SDE) - Continuous adaptation
    3. Manipulation Memory Core (MMC) - Builds manipulation genome
    4. VETP Recursive Emotion Engine (REE) - Scars become machine laws
    5. Appetite Multiplier (AM) - Risk-aware momentum
    
    Plus: KINGMAKER MODULE - Identifies which horse shapes/decides/collapses the race
    """
    
    def __init__(self, state_file: str = "/home/ubuntu/velo-oracle/data/sentient_state.json"):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load sentient state from disk"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return self._initialize_state()
    
    def _save_state(self):
        """Save sentient state to disk"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save sentient state: {e}")
    
    def _initialize_state(self) -> Dict[str, Any]:
        """Initialize fresh sentient state"""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_races_observed": 0,
            
            # Pillar 1: Behaviour Echo Chamber
            "house_behaviour_map": {
                "favourites_protected": 0,
                "favourites_abandoned": 0,
                "market_lies_detected": 0,
                "safe_bets_imploded": 0,
                "recurring_setups": {}
            },
            
            # Pillar 2: Structural Drift Engine
            "structural_weights": {
                "off_pace_wins": 0,
                "high_draw_wins": 0,
                "hidden_improver_wins": 0,
                "short_burst_wins": 0,
                "stamina_collapse_wins": 0,
                "late_money_wins": 0
            },
            
            # Pillar 3: Manipulation Memory Core
            "manipulation_genome": {
                "regulated_deception_patterns": [],
                "bad_faith_favourites": [],
                "market_steering_behaviours": [],
                "narrative_traps": [],
                "integrity_collapses": [],
                "suspicious_volatility_events": []
            },
            
            # Pillar 4: VETP Recursive Emotion Engine
            "emotion_laws": {
                "pain_rules": [],      # "Never fall for this structure again"
                "triumph_rules": [],   # "This configuration is true"
                "anger_rules": [],     # "This story is a trap"
                "regret_rules": []     # "Avoid unfocused multi-threat zones"
            },
            
            # Pillar 5: Appetite Multiplier
            "appetite_state": {
                "recent_performance": [],  # Last 10 predictions
                "aggression_level": 0.5,   # 0.0 to 1.0
                "pattern_recognition_sensitivity": 0.5,
                "doctrine_firing_threshold": 0.6,
                "narrative_skepticism": 0.7,
                "chaos_tolerance": 0.4,
                "manipulation_sensitivity": 0.7
            },
            
            # Doctrine Strength Tracking
            "doctrine_strengths": {
                "LAY_THE_STORY": 1.0,
                "SHADOW_TRACKING": 1.0,
                "ENGINE_SUPREMACY": 1.0,
                "TOP_4_ON_DANGER": 1.0,
                "HOUSE_REVERSAL": 1.0,
                "SARCOPHAGUS": 1.0,
                "PRESSURE_COLLAPSE": 1.0,
                "OVERLAY_ABSORPTION": 1.0,
                "CHAOS_BLEED": 1.0,
                "DRAW_SKEW": 1.0,
                "GATEKEEPER": 1.0,
                "VETP_ECHO": 1.0
            }
        }
    
    def observe_race_outcome(
        self,
        race_data: Dict[str, Any],
        prediction: Dict[str, Any],
        actual_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        The core sentient loop.
        
        Observe → Classify → Compare → Imprint → Evolve → Redeploy
        
        Args:
            race_data: Original race intelligence
            prediction: Oracle prediction made
            actual_result: What actually happened
            
        Returns:
            Evolution report
        """
        self.state["total_races_observed"] += 1
        self.state["last_updated"] = datetime.now().isoformat()
        
        # Extract error vector
        error_vector = self._compute_error_vector(prediction, actual_result)
        
        # Update each pillar
        self._update_behaviour_echo_chamber(race_data, actual_result)
        self._update_structural_drift_engine(race_data, actual_result)
        self._update_manipulation_memory_core(race_data, actual_result, error_vector)
        self._update_emotion_engine(race_data, actual_result, error_vector)
        self._update_appetite_multiplier(error_vector)
        
        # Update doctrine strengths
        self._update_doctrine_strengths(prediction, error_vector)
        
        # Save state
        self._save_state()
        
        return {
            "evolution_applied": True,
            "error_vector": error_vector,
            "appetite_state": self.state["appetite_state"]["aggression_level"],
            "doctrine_adjustments": self._get_recent_doctrine_adjustments()
        }
    
    def _compute_error_vector(
        self,
        prediction: Dict[str, Any],
        actual_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """Compute prediction error vector"""
        predicted_winner = prediction.get("power_anchor", "")
        actual_winner = actual_result.get("winner", "")
        
        correct = predicted_winner.lower() == actual_winner.lower()
        
        return {
            "prediction_correct": 1.0 if correct else 0.0,
            "confidence_error": abs(prediction.get("confidence", 0.5) - (1.0 if correct else 0.0)),
            "directive_effectiveness": 1.0 if correct else 0.0
        }
    
    def _update_behaviour_echo_chamber(
        self,
        race_data: Dict[str, Any],
        actual_result: Dict[str, Any]
    ):
        """Pillar 1: Log house behavior patterns"""
        bec = self.state["house_behaviour_map"]
        
        favourite_won = actual_result.get("favourite_won", False)
        
        if favourite_won:
            bec["favourites_protected"] += 1
        else:
            bec["favourites_abandoned"] += 1
        
        # Detect market lies
        if race_data.get("mpi", 0) > 70 and not favourite_won:
            bec["market_lies_detected"] += 1
        
        # Detect safe bet implosions
        if race_data.get("chaos_bloom", 0) < 30 and not favourite_won:
            bec["safe_bets_imploded"] += 1
    
    def _update_structural_drift_engine(
        self,
        race_data: Dict[str, Any],
        actual_result: Dict[str, Any]
    ):
        """Pillar 2: Continuous structural adaptation"""
        sde = self.state["structural_weights"]
        
        winner_profile = actual_result.get("winner_profile", {})
        
        if winner_profile.get("running_style") == "off_pace":
            sde["off_pace_wins"] += 1
        if winner_profile.get("draw") and winner_profile["draw"] > 10:
            sde["high_draw_wins"] += 1
        if winner_profile.get("was_hidden_improver"):
            sde["hidden_improver_wins"] += 1
        if winner_profile.get("late_money"):
            sde["late_money_wins"] += 1
    
    def _update_manipulation_memory_core(
        self,
        race_data: Dict[str, Any],
        actual_result: Dict[str, Any],
        error_vector: Dict[str, float]
    ):
        """Pillar 3: Build manipulation genome"""
        mmc = self.state["manipulation_genome"]
        
        # Detect narrative trap
        if (race_data.get("narrative_disruption", 0) > 80 and 
            not actual_result.get("favourite_won", False)):
            mmc["narrative_traps"].append({
                "race_id": race_data.get("race_id"),
                "narrative_score": race_data.get("narrative_disruption"),
                "timestamp": datetime.now().isoformat()
            })
        
        # Detect integrity collapse
        if race_data.get("integrity_score", 100) < 30:
            mmc["integrity_collapses"].append({
                "race_id": race_data.get("race_id"),
                "integrity": race_data.get("integrity_score"),
                "timestamp": datetime.now().isoformat()
            })
        
        # Keep only recent 100 entries
        for key in mmc:
            if isinstance(mmc[key], list) and len(mmc[key]) > 100:
                mmc[key] = mmc[key][-100:]
    
    def _update_emotion_engine(
        self,
        race_data: Dict[str, Any],
        actual_result: Dict[str, Any],
        error_vector: Dict[str, float]
    ):
        """Pillar 4: Convert emotions to machine laws"""
        ree = self.state["emotion_laws"]
        
        # Pain → Never fall for this again
        if error_vector["prediction_correct"] == 0.0 and race_data.get("mpi", 0) > 70:
            ree["pain_rules"].append({
                "rule": f"Avoid {race_data.get('story_anchor')} when MPI > 70",
                "pattern": "high_mpi_narrative_trap",
                "strength": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        # Triumph → This configuration is true
        if error_vector["prediction_correct"] == 1.0:
            ree["triumph_rules"].append({
                "rule": f"Trust {race_data.get('power_anchor')} engine supremacy",
                "pattern": "engine_dominance_confirmed",
                "strength": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        # Keep only recent 50 rules
        for emotion in ree:
            if len(ree[emotion]) > 50:
                ree[emotion] = ree[emotion][-50:]
    
    def _update_appetite_multiplier(self, error_vector: Dict[str, float]):
        """Pillar 5: Risk-aware momentum"""
        appetite = self.state["appetite_state"]
        
        # Track recent performance
        appetite["recent_performance"].append(error_vector["prediction_correct"])
        if len(appetite["recent_performance"]) > 10:
            appetite["recent_performance"] = appetite["recent_performance"][-10:]
        
        # Calculate recent success rate
        if len(appetite["recent_performance"]) >= 5:
            recent_success = sum(appetite["recent_performance"][-5:]) / 5.0
            
            # Adjust aggression
            if recent_success > 0.6:
                # Winning streak - increase aggression
                appetite["aggression_level"] = min(1.0, appetite["aggression_level"] + 0.05)
                appetite["pattern_recognition_sensitivity"] += 0.02
                appetite["doctrine_firing_threshold"] -= 0.02
                appetite["narrative_skepticism"] += 0.02
            else:
                # Losing streak - tighten criteria
                appetite["aggression_level"] = max(0.3, appetite["aggression_level"] - 0.05)
                appetite["chaos_tolerance"] -= 0.02
                appetite["manipulation_sensitivity"] += 0.02
                appetite["doctrine_firing_threshold"] += 0.02
            
            # Clamp values
            for key in appetite:
                if isinstance(appetite[key], float):
                    appetite[key] = max(0.0, min(1.0, appetite[key]))
    
    def _update_doctrine_strengths(
        self,
        prediction: Dict[str, Any],
        error_vector: Dict[str, float]
    ):
        """Update doctrine effectiveness scores"""
        doctrines_fired = prediction.get("doctrines_fired", [])
        correct = error_vector["prediction_correct"]
        
        for doctrine in doctrines_fired:
            if doctrine in self.state["doctrine_strengths"]:
                current = self.state["doctrine_strengths"][doctrine]
                # Exponential moving average
                self.state["doctrine_strengths"][doctrine] = (
                    0.9 * current + 0.1 * correct
                )
    
    def _get_recent_doctrine_adjustments(self) -> Dict[str, float]:
        """Get recent doctrine strength changes"""
        return {k: round(v, 3) for k, v in self.state["doctrine_strengths"].items()}
    
    def identify_kingmaker(self, race_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        KINGMAKER MODULE
        
        Identify which horse:
        - Shapes the race
        - Decides the race
        - Absorbs pressure
        - Destabilises the pace
        - Collapses narratives
        
        A kingmaker is not the favourite.
        A kingmaker is the horse that causes the collapse of a favourite.
        """
        threat_cluster = race_data.get("threat_cluster", [])
        favourite = race_data.get("story_anchor", "")
        
        # Look for gatekeeper patterns
        if race_data.get("fav_trip_blocked"):
            for horse in threat_cluster:
                if "front" in str(horse).lower() or "pace" in str(horse).lower():
                    return {
                        "kingmaker": horse,
                        "role": "pace_destabiliser",
                        "effect": "Blocks favourite's optimal trip",
                        "confidence": 0.8
                    }
        
        # Look for pressure absorbers
        if race_data.get("chaos_bloom", 0) > 40:
            for horse in threat_cluster:
                if "stalker" in str(horse).lower() or "closer" in str(horse).lower():
                    return {
                        "kingmaker": horse,
                        "role": "chaos_navigator",
                        "effect": "Thrives in unstable pace",
                        "confidence": 0.7
                    }
        
        # Look for narrative collapsers
        if race_data.get("narrative_disruption", 0) > 70:
            power_anchor = race_data.get("power_anchor", "")
            if power_anchor and power_anchor != favourite:
                return {
                    "kingmaker": power_anchor,
                    "role": "narrative_collapser",
                    "effect": "Reality defeats story",
                    "confidence": 0.85
                }
        
        return None
    
    def get_evolutionary_state(self) -> Dict[str, Any]:
        """Get current evolutionary state for API output"""
        return {
            "total_races_observed": self.state["total_races_observed"],
            "doctrine_strengths": self._get_recent_doctrine_adjustments(),
            "appetite_multiplier": round(self.state["appetite_state"]["aggression_level"], 3),
            "manipulation_genome_size": sum(len(v) if isinstance(v, list) else 0 
                                           for v in self.state["manipulation_genome"].values()),
            "emotion_laws_count": sum(len(v) for v in self.state["emotion_laws"].values()),
            "structural_drift_active": True,
            "last_updated": self.state["last_updated"]
        }


def create_sentient_loopback_engine() -> SentientLoopbackEngine:
    """Factory function to create Sentient Loopback Engine"""
    return SentientLoopbackEngine()
