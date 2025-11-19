"""
VÉLØ Oracle - Narrative Disruption Intelligence
Detect and analyze market narratives that may disrupt expected outcomes
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class NarrativeDisruptionDetector:
    """Detect market narratives and disruption risks"""
    
    def __init__(self):
        self.known_narratives = [
            "champion_return",
            "local_hero",
            "media_darling",
            "trainer_stable_star",
            "breeding_royalty",
            "comeback_story",
            "underdog_tale",
            "rivalry_match"
        ]
        
    def detect_market_story(self, race: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect dominant market narrative for a race
        
        Args:
            race: Race data dictionary
            
        Returns:
            Narrative analysis with disruption risk
        """
        logger.debug(f"Analyzing market narrative for race {race.get('race_id')}")
        
        # Extract race metadata
        race_name = race.get("race_name", "")
        is_group_race = race.get("is_group_race", False)
        prize_money = race.get("prize_money", 0)
        runners = race.get("runners", [])
        
        # Detect narrative type
        narrative = self._identify_narrative(race, runners)
        
        # Calculate disruption risk
        disruption_risk = self._calculate_disruption_risk(narrative, race, runners)
        
        # Identify narrative-driven runners
        narrative_runners = self._identify_narrative_runners(narrative, runners)
        
        result = {
            "story": narrative.get("type"),
            "description": narrative.get("description"),
            "disruption_risk": disruption_risk,
            "confidence": narrative.get("confidence", 0.0),
            "narrative_runners": narrative_runners,
            "market_bias": self._calculate_market_bias(narrative_runners, runners),
            "contrarian_opportunity": disruption_risk > 0.6,
            "analysis": narrative.get("analysis", "No strong narrative detected")
        }
        
        logger.debug(f"Narrative detected: {result['story']} (risk: {disruption_risk:.2f})")
        
        return result
    
    def _identify_narrative(self, race: Dict[str, Any], runners: List[Dict]) -> Dict[str, Any]:
        """Identify the dominant narrative in the race"""
        
        # Check for champion return narrative
        for runner in runners:
            if self._is_champion_return(runner):
                return {
                    "type": "champion_return",
                    "description": f"{runner.get('horse')} returns after layoff",
                    "confidence": 0.8,
                    "analysis": "Market may overvalue champion's return without considering fitness"
                }
        
        # Check for local hero narrative
        if self._has_local_hero(race, runners):
            return {
                "type": "local_hero",
                "description": "Local favorite with strong public support",
                "confidence": 0.7,
                "analysis": "Public sentiment may inflate odds beyond true ability"
            }
        
        # Check for media darling
        media_runner = self._find_media_darling(runners)
        if media_runner:
            return {
                "type": "media_darling",
                "description": f"{media_runner.get('horse')} heavily promoted in media",
                "confidence": 0.75,
                "analysis": "Media coverage creates public betting pressure"
            }
        
        # Check for breeding royalty
        for runner in runners:
            if self._is_breeding_royalty(runner):
                return {
                    "type": "breeding_royalty",
                    "description": f"{runner.get('horse')} from champion bloodlines",
                    "confidence": 0.65,
                    "analysis": "Pedigree appeal may not match race performance"
                }
        
        # No strong narrative
        return {
            "type": None,
            "description": "No dominant narrative detected",
            "confidence": 0.0,
            "analysis": "Market likely pricing on form and fundamentals"
        }
    
    def _calculate_disruption_risk(self, narrative: Dict, race: Dict, runners: List) -> float:
        """Calculate risk that narrative disrupts rational pricing"""
        
        if not narrative.get("type"):
            return 0.0
        
        base_risk = narrative.get("confidence", 0.5)
        
        # Amplify risk factors
        risk_multipliers = []
        
        # High-profile race increases narrative impact
        if race.get("is_group_race"):
            risk_multipliers.append(1.3)
        
        # Large prize money attracts public attention
        if race.get("prize_money", 0) > 500000:
            risk_multipliers.append(1.2)
        
        # Media coverage amplifies narrative
        if narrative.get("type") == "media_darling":
            risk_multipliers.append(1.4)
        
        # Calculate final risk
        final_risk = base_risk
        for multiplier in risk_multipliers:
            final_risk *= multiplier
        
        return min(final_risk, 1.0)
    
    def _identify_narrative_runners(self, narrative: Dict, runners: List) -> List[str]:
        """Identify which runners are driving the narrative"""
        narrative_runners = []
        
        narrative_type = narrative.get("type")
        
        if not narrative_type:
            return []
        
        # Find runners matching narrative
        for runner in runners:
            horse_name = runner.get("horse", "")
            
            if narrative_type == "champion_return" and self._is_champion_return(runner):
                narrative_runners.append(horse_name)
            
            elif narrative_type == "media_darling" and self._is_media_darling(runner):
                narrative_runners.append(horse_name)
            
            elif narrative_type == "breeding_royalty" and self._is_breeding_royalty(runner):
                narrative_runners.append(horse_name)
            
            elif narrative_type == "local_hero" and self._is_local_favorite(runner):
                narrative_runners.append(horse_name)
        
        return narrative_runners
    
    def _calculate_market_bias(self, narrative_runners: List[str], all_runners: List) -> float:
        """Calculate market bias toward narrative runners"""
        if not narrative_runners or not all_runners:
            return 0.0
        
        # Find narrative runners in field
        narrative_odds = []
        for runner in all_runners:
            if runner.get("horse") in narrative_runners:
                narrative_odds.append(runner.get("odds", 10.0))
        
        if not narrative_odds:
            return 0.0
        
        # Calculate average odds
        avg_narrative_odds = sum(narrative_odds) / len(narrative_odds)
        avg_field_odds = sum(r.get("odds", 10.0) for r in all_runners) / len(all_runners)
        
        # Bias = how much shorter narrative runners are priced
        bias = (avg_field_odds - avg_narrative_odds) / avg_field_odds if avg_field_odds > 0 else 0.0
        
        return max(min(bias, 1.0), -1.0)
    
    # Helper detection methods (stubs)
    
    def _is_champion_return(self, runner: Dict) -> bool:
        """Check if runner is a champion returning from layoff"""
        last_start_days = runner.get("last_start_days", 0)
        career_wins = runner.get("career_wins", 0)
        
        # Champion = 5+ wins and 90+ days since last start
        return career_wins >= 5 and last_start_days > 90
    
    def _has_local_hero(self, race: Dict, runners: List) -> bool:
        """Check if race has a local hero"""
        # Stub: Check if any runner is local to course
        course = race.get("course", "")
        
        for runner in runners:
            trainer = runner.get("trainer", "")
            # Simplified: Check if trainer name suggests local connection
            if course.lower() in trainer.lower():
                return True
        
        return False
    
    def _find_media_darling(self, runners: List) -> Optional[Dict]:
        """Find the media darling in the field"""
        # Stub: Look for low odds + high profile indicators
        for runner in runners:
            odds = runner.get("odds", 10.0)
            prize_money = runner.get("prize_money", 0)
            
            # Media darlings typically: short odds + high earnings
            if odds < 4.0 and prize_money > 1000000:
                return runner
        
        return None
    
    def _is_media_darling(self, runner: Dict) -> bool:
        """Check if runner is a media darling"""
        odds = runner.get("odds", 10.0)
        prize_money = runner.get("prize_money", 0)
        return odds < 4.0 and prize_money > 1000000
    
    def _is_breeding_royalty(self, runner: Dict) -> bool:
        """Check if runner is from champion bloodlines"""
        # Stub: Check for high-profile sire/dam
        horse_name = runner.get("horse", "")
        
        # Simplified: Check for common champion sire indicators in name
        royal_indicators = ["Justify", "Frankel", "Dubawi", "Galileo", "Tapit"]
        
        return any(indicator in horse_name for indicator in royal_indicators)
    
    def _is_local_favorite(self, runner: Dict) -> bool:
        """Check if runner is a local favorite"""
        # Stub: Simplified check
        odds = runner.get("odds", 10.0)
        return odds < 5.0


def detect_market_story(race: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to detect market narrative
    
    Args:
        race: Race data dictionary
        
    Returns:
        Narrative analysis
    """
    detector = NarrativeDisruptionDetector()
    return detector.detect_market_story(race)
