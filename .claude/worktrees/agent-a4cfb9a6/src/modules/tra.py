"""
VÉLØ v9.0++ CHAREX - TRA (Trip Resistance Analyzer)

Detects horses that had unlucky runs (bad trips) in previous races
and are likely to improve with a cleaner passage.

Analyzes:
- Traffic problems in running
- Wide trips / extra ground covered
- Interference / checked in running
- Missed breaks / slow starts
"""

from typing import Dict, List, Optional


class TripResistanceAnalyzer:
    """
    TRA - Trip Resistance Analyzer
    
    Identifies horses whose recent form is better than it appears
    due to unlucky trips or racing circumstances.
    """
    
    def __init__(self):
        """Initialize TRA module."""
        self.name = "TRA"
        self.version = "v9.0++"
        
        # Trip issue indicators
        self.TRIP_ISSUES = [
            "WIDE_TRIP",
            "TRAFFIC_PROBLEMS",
            "SLOW_START",
            "INTERFERENCE",
            "CHECKED"
        ]
    
    def analyze_trip_history(self, horse: Dict) -> Dict:
        """
        Analyze a horse's recent trip history for unlucky runs.
        
        Args:
            horse: Horse data with race comments/notes
            
        Returns:
            Trip analysis
        """
        # In real implementation, would parse race comments
        # For now, use placeholder logic based on form patterns
        
        form = horse.get("form", "")
        race_comments = horse.get("race_comments", [])
        
        # Detect trip issues
        trip_issues = self._detect_trip_issues(form, race_comments)
        
        # Calculate unlucky run score
        unlucky_score = len(trip_issues) * 0.25
        unlucky_score = min(1.0, unlucky_score)
        
        # Determine if horse is "better than form"
        is_better_than_form = unlucky_score >= 0.5
        
        # Calculate improvement potential
        improvement_potential = self._calculate_improvement_potential(
            unlucky_score,
            form
        )
        
        return {
            "horse_name": horse.get("name", "Unknown"),
            "trip_issues_detected": trip_issues,
            "unlucky_run_score": unlucky_score,
            "is_better_than_form": is_better_than_form,
            "improvement_potential": improvement_potential,
            "tactical_note": self._generate_trip_note(trip_issues, is_better_than_form)
        }
    
    def _detect_trip_issues(self, form: str, race_comments: List[str]) -> List[str]:
        """
        Detect trip issues from form and comments.
        
        Args:
            form: Form string
            race_comments: List of race comments
            
        Returns:
            List of detected trip issues
        """
        issues = []
        
        # Parse race comments for keywords (simplified)
        for comment in race_comments:
            comment_lower = comment.lower()
            
            if any(word in comment_lower for word in ["wide", "outside", "no cover"]):
                issues.append("WIDE_TRIP")
            
            if any(word in comment_lower for word in ["traffic", "blocked", "hampered"]):
                issues.append("TRAFFIC_PROBLEMS")
            
            if any(word in comment_lower for word in ["slow", "missed break", "dwelt"]):
                issues.append("SLOW_START")
            
            if any(word in comment_lower for word in ["interference", "bumped", "checked"]):
                issues.append("INTERFERENCE")
        
        # If no comments, use form patterns as proxy
        if not issues and form:
            # Pattern: recent poor run after good runs might indicate bad trip
            if len(form) >= 3:
                recent = [int(c) for c in form[:3] if c.isdigit()]
                if len(recent) == 3 and recent[0] > 5 and recent[1] <= 4:
                    issues.append("TRAFFIC_PROBLEMS")  # Assumption
        
        return list(set(issues))  # Remove duplicates
    
    def _calculate_improvement_potential(self, unlucky_score: float, form: str) -> float:
        """
        Calculate potential for improvement with cleaner trip.
        
        Args:
            unlucky_score: Unlucky run score
            form: Form string
            
        Returns:
            Improvement potential (0.0 to 1.0)
        """
        # Base potential from unlucky score
        potential = unlucky_score
        
        # Boost if horse has shown ability before
        if form:
            good_runs = sum(1 for c in form if c.isdigit() and int(c) <= 3)
            if good_runs >= 2:
                potential += 0.2
        
        return min(1.0, potential)
    
    def _generate_trip_note(self, issues: List[str], is_better: bool) -> str:
        """
        Generate tactical note about trip analysis.
        
        Args:
            issues: Detected trip issues
            is_better: Whether horse is better than form
            
        Returns:
            Tactical note
        """
        if not issues:
            return "No significant trip issues detected. Form is reliable."
        
        if is_better:
            issues_str = ", ".join(issues)
            return f"⚠️ TRIP UPGRADE: {issues_str} in recent runs. Horse better than form suggests. Expect improvement."
        else:
            return f"Minor trip issues detected but not significant enough to upgrade."
    
    def get_trip_upgraded_horses(self, horses: List[Dict]) -> List[Dict]:
        """
        Get horses that deserve a trip upgrade.
        
        Args:
            horses: All horses
            
        Returns:
            Horses with trip upgrade potential
        """
        upgraded = []
        
        for horse in horses:
            analysis = self.analyze_trip_history(horse)
            
            if analysis["is_better_than_form"]:
                upgraded.append({
                    "horse": horse,
                    "trip_analysis": analysis
                })
        
        # Sort by improvement potential
        upgraded.sort(
            key=lambda x: x["trip_analysis"]["improvement_potential"],
            reverse=True
        )
        
        return upgraded
    
    def apply_trip_filter(self, horses: List[Dict], upgrade_threshold: float = 0.5) -> List[Dict]:
        """
        Apply trip resistance filter to identify horses with clean trip potential.
        
        Args:
            horses: All horses
            upgrade_threshold: Minimum score for trip upgrade
            
        Returns:
            Horses that pass trip filter
        """
        passed = []
        
        for horse in horses:
            analysis = self.analyze_trip_history(horse)
            
            # Include if either:
            # 1. No trip issues (reliable form)
            # 2. Trip upgrade potential
            if (not analysis["trip_issues_detected"] or 
                analysis["improvement_potential"] >= upgrade_threshold):
                passed.append({
                    "horse": horse,
                    "trip_analysis": analysis
                })
        
        return passed


def main():
    """Test TRA module."""
    print("🏇 TRA - Trip Resistance Analyzer")
    print("="*60)
    
    tra = TripResistanceAnalyzer()
    
    # Test horses
    test_horses = [
        {
            "name": "Unlucky Runner",
            "form": "6214",
            "race_comments": [
                "Wide throughout, no cover",
                "Hampered at 2f out, stayed on"
            ]
        },
        {
            "name": "Clean Trip Horse",
            "form": "2314",
            "race_comments": [
                "Smooth passage, ran on"
            ]
        },
        {
            "name": "Traffic Victim",
            "form": "7123",
            "race_comments": [
                "Blocked at crucial stage",
                "Checked when making run"
            ]
        },
        {
            "name": "Consistent Runner",
            "form": "3243",
            "race_comments": []
        }
    ]
    
    print(f"\n📊 Trip Analysis Results:")
    for horse in test_horses:
        analysis = tra.analyze_trip_history(horse)
        status = "⚠️ UPGRADE" if analysis["is_better_than_form"] else "✅ RELIABLE"
        print(f"\n  {status} {horse['name']}")
        print(f"    Trip Issues: {', '.join(analysis['trip_issues_detected']) if analysis['trip_issues_detected'] else 'None'}")
        print(f"    Unlucky Score: {analysis['unlucky_run_score']:.2f}")
        print(f"    Improvement Potential: {analysis['improvement_potential']:.2f}")
        print(f"    Note: {analysis['tactical_note']}")
    
    # Get upgraded horses
    upgraded = tra.get_trip_upgraded_horses(test_horses)
    
    print(f"\n\n⚠️ TRIP UPGRADED HORSES ({len(upgraded)}):")
    for item in upgraded:
        horse = item["horse"]
        analysis = item["trip_analysis"]
        print(f"  ⚠️ {horse['name']} - Potential: {analysis['improvement_potential']:.2f}")


if __name__ == "__main__":
    main()

