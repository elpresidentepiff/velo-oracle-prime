"""
VÉLØ v9.0++ CHAREX - NDS (Narrative Disruption Scan)

Filters out media hype, public bias, and false narratives.
Identifies horses that are overbet due to story rather than form.

Detects:
- Media darlings with inflated odds
- Comeback narratives without substance
- Trainer/jockey hype without stats
- Public sentiment distortion
"""

from typing import Dict, List, Optional, Tuple


class NarrativeDisruptionScan:
    """
    NDS - Narrative Disruption Scan
    
    Cuts through the noise of media narratives and public sentiment
    to identify horses whose odds don't match their actual chances.
    """
    
    def __init__(self):
        """Initialize NDS module."""
        self.name = "NDS"
        self.version = "v9.0++"
        
        # Red flag narratives
        self.RED_FLAG_NARRATIVES = [
            "COMEBACK_STORY",
            "MEDIA_DARLING",
            "TRAINER_HYPE",
            "BREEDING_BIAS",
            "OWNERSHIP_GLAMOUR"
        ]
    
    def scan_horse_narrative(self, horse: Dict, market_data: Optional[Dict] = None) -> Dict:
        """
        Scan a horse for narrative distortion.
        
        Args:
            horse: Horse data
            market_data: Optional market sentiment data
            
        Returns:
            Narrative analysis
        """
        narratives_detected = []
        distortion_score = 0.0
        
        # Check for comeback story
        if self._detect_comeback_narrative(horse):
            narratives_detected.append("COMEBACK_STORY")
            distortion_score += 0.3
        
        # Check for trainer hype without substance
        if self._detect_trainer_hype(horse):
            narratives_detected.append("TRAINER_HYPE")
            distortion_score += 0.25
        
        # Check for breeding bias
        if self._detect_breeding_bias(horse):
            narratives_detected.append("BREEDING_BIAS")
            distortion_score += 0.2
        
        # Determine if narrative is distorting odds
        is_distorted = distortion_score >= 0.4
        
        return {
            "horse_name": horse.get("name", "Unknown"),
            "narratives_detected": narratives_detected,
            "distortion_score": distortion_score,
            "is_narrative_distorted": is_distorted,
            "risk_level": self._calculate_risk_level(distortion_score),
            "tactical_note": self._generate_narrative_note(narratives_detected, is_distorted)
        }
    
    def _detect_comeback_narrative(self, horse: Dict) -> bool:
        """
        Detect if horse is being hyped as a comeback story.
        
        Args:
            horse: Horse data
            
        Returns:
            True if comeback narrative detected
        """
        form = horse.get("form", "")
        
        # Check for long absence followed by recent run
        # Pattern: "0" (non-runner) followed by sudden return
        if "0" in form and len(form) > 3:
            # Check if there's a recent run after absence
            if form[0] != "0" and "0" in form[1:]:
                return True
        
        return False
    
    def _detect_trainer_hype(self, horse: Dict) -> bool:
        """
        Detect if trainer has hype without backing stats.
        
        Args:
            horse: Horse data
            
        Returns:
            True if trainer hype detected
        """
        trainer_stats = horse.get("trainer_stats", {})
        trainer_roi = trainer_stats.get("roi", 0.0)
        
        # Hype without substance: low ROI but horse is well-backed
        # (In real implementation, would check market support vs stats)
        if trainer_roi < 5.0:
            return True
        
        return False
    
    def _detect_breeding_bias(self, horse: Dict) -> bool:
        """
        Detect if horse is overbet due to breeding/pedigree.
        
        Args:
            horse: Horse data
            
        Returns:
            True if breeding bias detected
        """
        # Placeholder: would check if sire/dam is famous but horse lacks form
        # For now, simple check
        form = horse.get("form", "")
        
        # If poor form but still backed (would need market data)
        if form and all(c in ["0", "5", "6", "7", "8", "9"] for c in form[:3] if c.isdigit()):
            return True
        
        return False
    
    def _calculate_risk_level(self, distortion_score: float) -> str:
        """
        Calculate risk level based on distortion score.
        
        Args:
            distortion_score: Narrative distortion score
            
        Returns:
            Risk level
        """
        if distortion_score >= 0.6:
            return "HIGH"
        elif distortion_score >= 0.4:
            return "MODERATE"
        else:
            return "LOW"
    
    def _generate_narrative_note(self, narratives: List[str], is_distorted: bool) -> str:
        """
        Generate tactical note about narrative risk.
        
        Args:
            narratives: List of detected narratives
            is_distorted: Whether odds are distorted
            
        Returns:
            Tactical note
        """
        if not narratives:
            return "No narrative distortion detected. Odds appear rational."
        
        if is_distorted:
            narrative_str = ", ".join(narratives)
            return f"⚠️ NARRATIVE RISK: {narrative_str}. Odds likely inflated by story, not form. FADE."
        else:
            return f"Minor narrative detected but not distorting odds significantly."
    
    def filter_narrative_distorted(self, horses: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate horses into clean and narrative-distorted groups.
        
        Args:
            horses: All horses
            
        Returns:
            Tuple of (clean_horses, distorted_horses)
        """
        clean = []
        distorted = []
        
        for horse in horses:
            scan_result = self.scan_horse_narrative(horse)
            
            if scan_result["is_narrative_distorted"]:
                distorted.append({
                    "horse": horse,
                    "narrative_scan": scan_result
                })
            else:
                clean.append({
                    "horse": horse,
                    "narrative_scan": scan_result
                })
        
        return clean, distorted
    
    def get_fade_zone_runners(self, horses: List[Dict]) -> List[Dict]:
        """
        Get horses that should be faded due to narrative distortion.
        
        Args:
            horses: All horses
            
        Returns:
            Horses to fade
        """
        _, distorted = self.filter_narrative_distorted(horses)
        
        # Sort by distortion score (highest first)
        distorted.sort(
            key=lambda x: x["narrative_scan"]["distortion_score"],
            reverse=True
        )
        
        return distorted


def main():
    """Test NDS module."""
    print("🔍 NDS - Narrative Disruption Scan")
    print("="*60)
    
    nds = NarrativeDisruptionScan()
    
    # Test horses
    test_horses = [
        {
            "name": "Comeback King",
            "form": "1000",  # Recent run after absence
            "trainer_stats": {"roi": 3.0}
        },
        {
            "name": "Solid Performer",
            "form": "2314",
            "trainer_stats": {"roi": 15.0}
        },
        {
            "name": "Hyped Youngster",
            "form": "0999",  # Poor form but famous breeding
            "trainer_stats": {"roi": 2.0}
        },
        {
            "name": "Consistent Runner",
            "form": "3243",
            "trainer_stats": {"roi": 12.0}
        }
    ]
    
    print(f"\n📊 Narrative Scan Results:")
    for horse in test_horses:
        scan = nds.scan_horse_narrative(horse)
        status = "❌ FADE" if scan["is_narrative_distorted"] else "✅ CLEAN"
        print(f"\n  {status} {horse['name']}")
        print(f"    Narratives: {', '.join(scan['narratives_detected']) if scan['narratives_detected'] else 'None'}")
        print(f"    Distortion Score: {scan['distortion_score']:.2f}")
        print(f"    Risk Level: {scan['risk_level']}")
        print(f"    Note: {scan['tactical_note']}")
    
    # Get fade zone
    fade_zone = nds.get_fade_zone_runners(test_horses)
    
    print(f"\n\n🚫 FADE ZONE RUNNERS ({len(fade_zone)}):")
    for item in fade_zone:
        horse = item["horse"]
        scan = item["narrative_scan"]
        print(f"  ❌ {horse['name']} - Distortion: {scan['distortion_score']:.2f}")


if __name__ == "__main__":
    main()

