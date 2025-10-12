"""
VÉLØ v9.0++ CHAREX - PRSCL (Post-Race Self-Critique Loop)

Genesis Protocol learning system that analyzes prediction accuracy
and adjusts weights/thresholds based on outcomes.

Implements:
- Prediction vs outcome comparison
- Module performance tracking
- Weight adjustment recommendations
- Pattern recognition from errors
"""

import json
from typing import Dict, List, Optional
from datetime import datetime


class PostRaceSelfCritiqueLoop:
    """
    PRSCL - Post-Race Self-Critique Loop
    
    The Genesis Protocol's learning engine. Analyzes every prediction,
    identifies errors, and recommends system improvements.
    """
    
    def __init__(self):
        """Initialize PRSCL module."""
        self.name = "PRSCL"
        self.version = "v9.0++"
        
        # Performance tracking
        self.critiques = []
        
        # Module performance scores
        self.module_scores = {
            "SQPE": {"correct": 0, "total": 0},
            "V9PM": {"correct": 0, "total": 0},
            "TIE": {"correct": 0, "total": 0},
            "SSM": {"correct": 0, "total": 0},
            "BOP": {"correct": 0, "total": 0},
            "NDS": {"correct": 0, "total": 0},
            "DLV": {"correct": 0, "total": 0},
            "TRA": {"correct": 0, "total": 0}
        }
    
    def critique_prediction(self, prediction: Dict, actual_result: Dict) -> Dict:
        """
        Perform post-race critique of a prediction.
        
        Args:
            prediction: Original VÉLØ verdict
            actual_result: Actual race result
            
        Returns:
            Critique analysis
        """
        critique_id = f"CRITIQUE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Extract key predictions
        predicted_winner = prediction.get("velo_verdict", {}).get("top_strike_selection")
        confidence = prediction.get("confidence_index", 0)
        
        # Extract actual result
        actual_winner = actual_result.get("winner")
        actual_positions = actual_result.get("positions", {})
        
        # Evaluate prediction accuracy
        winner_correct = (predicted_winner == actual_winner)
        
        # Check if predicted horse placed
        predicted_position = actual_positions.get(predicted_winner, 999)
        placed = (predicted_position <= 3)
        
        # Calculate accuracy score
        if winner_correct:
            accuracy_score = 1.0
        elif placed:
            accuracy_score = 0.6
        else:
            accuracy_score = 0.0
        
        # Analyze what went wrong (if applicable)
        error_analysis = self._analyze_errors(
            prediction,
            actual_result,
            winner_correct,
            placed
        )
        
        # Generate learning points
        learning_points = self._generate_learning_points(
            prediction,
            actual_result,
            error_analysis
        )
        
        # Recommend adjustments
        adjustments = self._recommend_adjustments(error_analysis, confidence)
        
        critique = {
            "critique_id": critique_id,
            "timestamp": datetime.now().isoformat(),
            "prediction_summary": {
                "predicted_winner": predicted_winner,
                "confidence": confidence
            },
            "actual_result": {
                "winner": actual_winner,
                "predicted_position": predicted_position
            },
            "outcome": {
                "winner_correct": winner_correct,
                "placed": placed,
                "accuracy_score": accuracy_score
            },
            "error_analysis": error_analysis,
            "learning_points": learning_points,
            "recommended_adjustments": adjustments
        }
        
        # Store critique
        self.critiques.append(critique)
        
        return critique
    
    def _analyze_errors(self, prediction: Dict, result: Dict, 
                       winner_correct: bool, placed: bool) -> Dict:
        """
        Analyze what went wrong in the prediction.
        
        Args:
            prediction: Original prediction
            result: Actual result
            winner_correct: Whether winner was correct
            placed: Whether selection placed
            
        Returns:
            Error analysis
        """
        errors = []
        
        if not winner_correct:
            # Identify potential error sources
            
            # Check if confidence was too high
            confidence = prediction.get("confidence_index", 0)
            if confidence >= 80:
                errors.append({
                    "type": "OVERCONFIDENCE",
                    "description": f"Confidence was {confidence}% but selection failed",
                    "affected_module": "V9PM"
                })
            
            # Check if filters missed something
            if not placed:
                errors.append({
                    "type": "FILTER_FAILURE",
                    "description": "Selection failed to place - filters may have missed key factor",
                    "affected_module": "FIVE_FILTERS"
                })
            
            # Check if pace analysis was wrong
            strategic_notes = prediction.get("strategic_notes", {})
            if "SSM" in strategic_notes:
                errors.append({
                    "type": "PACE_MISJUDGMENT",
                    "description": "Pace scenario may have been misjudged",
                    "affected_module": "SSM"
                })
        
        return {
            "error_count": len(errors),
            "errors": errors
        }
    
    def _generate_learning_points(self, prediction: Dict, result: Dict, 
                                  error_analysis: Dict) -> List[str]:
        """
        Generate learning points from the outcome.
        
        Args:
            prediction: Original prediction
            result: Actual result
            error_analysis: Error analysis
            
        Returns:
            List of learning points
        """
        learning_points = []
        
        for error in error_analysis.get("errors", []):
            if error["type"] == "OVERCONFIDENCE":
                learning_points.append(
                    "Reduce confidence threshold when multiple risk factors present"
                )
            
            elif error["type"] == "FILTER_FAILURE":
                learning_points.append(
                    "Review filter thresholds - may be too lenient"
                )
            
            elif error["type"] == "PACE_MISJUDGMENT":
                learning_points.append(
                    "Improve pace scenario prediction accuracy"
                )
        
        # Always add general learning point
        learning_points.append(
            "Continue tracking patterns across more races for statistical significance"
        )
        
        return learning_points
    
    def _recommend_adjustments(self, error_analysis: Dict, confidence: int) -> List[Dict]:
        """
        Recommend system adjustments based on errors.
        
        Args:
            error_analysis: Error analysis
            confidence: Original confidence level
            
        Returns:
            List of recommended adjustments
        """
        adjustments = []
        
        for error in error_analysis.get("errors", []):
            if error["type"] == "OVERCONFIDENCE":
                adjustments.append({
                    "module": "V9PM",
                    "parameter": "confidence_multiplier",
                    "current_value": 1.0,
                    "recommended_value": 0.9,
                    "reason": "Reduce confidence when high-risk factors present"
                })
            
            elif error["type"] == "FILTER_FAILURE":
                adjustments.append({
                    "module": "FIVE_FILTERS",
                    "parameter": "pass_threshold",
                    "current_value": 0.6,
                    "recommended_value": 0.7,
                    "reason": "Tighten filter thresholds to reduce false positives"
                })
        
        return adjustments
    
    def get_module_performance(self, module_name: str) -> Dict:
        """
        Get performance stats for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Performance statistics
        """
        if module_name not in self.module_scores:
            return {"error": "Module not found"}
        
        stats = self.module_scores[module_name]
        
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
        
        return {
            "module": module_name,
            "correct_predictions": stats["correct"],
            "total_predictions": stats["total"],
            "accuracy_percentage": round(accuracy, 2)
        }
    
    def get_overall_performance(self) -> Dict:
        """
        Get overall system performance.
        
        Returns:
            Overall performance statistics
        """
        total_critiques = len(self.critiques)
        
        if total_critiques == 0:
            return {
                "total_predictions": 0,
                "accuracy": 0.0,
                "message": "No predictions critiqued yet"
            }
        
        # Calculate overall accuracy
        total_accuracy = sum(c["outcome"]["accuracy_score"] for c in self.critiques)
        avg_accuracy = (total_accuracy / total_critiques) * 100
        
        # Count wins and places
        wins = sum(1 for c in self.critiques if c["outcome"]["winner_correct"])
        places = sum(1 for c in self.critiques if c["outcome"]["placed"])
        
        return {
            "total_predictions": total_critiques,
            "wins": wins,
            "places": places,
            "win_rate": round(wins / total_critiques * 100, 2),
            "place_rate": round(places / total_critiques * 100, 2),
            "average_accuracy": round(avg_accuracy, 2)
        }
    
    def generate_critique_report(self, critique_id: str) -> str:
        """
        Generate human-readable critique report.
        
        Args:
            critique_id: ID of the critique
            
        Returns:
            Formatted report
        """
        critique = next((c for c in self.critiques if c["critique_id"] == critique_id), None)
        
        if not critique:
            return "Critique not found"
        
        report = []
        report.append("="*60)
        report.append(f"VÉLØ POST-RACE CRITIQUE: {critique_id}")
        report.append("="*60)
        
        report.append(f"\nPREDICTION:")
        report.append(f"  Winner: {critique['prediction_summary']['predicted_winner']}")
        report.append(f"  Confidence: {critique['prediction_summary']['confidence']}%")
        
        report.append(f"\nACTUAL RESULT:")
        report.append(f"  Winner: {critique['actual_result']['winner']}")
        report.append(f"  Our Selection Finished: {critique['actual_result']['predicted_position']}")
        
        report.append(f"\nOUTCOME:")
        outcome = critique['outcome']
        status = "✅ WIN" if outcome['winner_correct'] else "⚠️ PLACE" if outcome['placed'] else "❌ MISS"
        report.append(f"  Status: {status}")
        report.append(f"  Accuracy Score: {outcome['accuracy_score']:.2f}")
        
        if critique['error_analysis']['errors']:
            report.append(f"\nERROR ANALYSIS:")
            for error in critique['error_analysis']['errors']:
                report.append(f"  - {error['type']}: {error['description']}")
        
        report.append(f"\nLEARNING POINTS:")
        for point in critique['learning_points']:
            report.append(f"  • {point}")
        
        if critique['recommended_adjustments']:
            report.append(f"\nRECOMMENDED ADJUSTMENTS:")
            for adj in critique['recommended_adjustments']:
                report.append(f"  • {adj['module']}.{adj['parameter']}: {adj['current_value']} → {adj['recommended_value']}")
                report.append(f"    Reason: {adj['reason']}")
        
        report.append("\n" + "="*60)
        
        return "\n".join(report)


def main():
    """Test PRSCL module."""
    print("🔄 PRSCL - Post-Race Self-Critique Loop")
    print("="*60)
    
    prscl = PostRaceSelfCritiqueLoop()
    
    # Test prediction
    test_prediction = {
        "velo_verdict": {
            "top_strike_selection": "Hidden Gem"
        },
        "confidence_index": 86,
        "strategic_notes": {
            "SSM_convergence": "Pace analysis complete"
        }
    }
    
    # Test result (selection placed 2nd)
    test_result = {
        "winner": "Swift Dancer",
        "positions": {
            "Swift Dancer": 1,
            "Hidden Gem": 2,
            "Desert Storm": 3
        }
    }
    
    # Perform critique
    critique = prscl.critique_prediction(test_prediction, test_result)
    
    # Generate report
    report = prscl.generate_critique_report(critique["critique_id"])
    print(f"\n{report}")
    
    # Get overall performance
    performance = prscl.get_overall_performance()
    print(f"\n📊 Overall Performance:")
    print(json.dumps(performance, indent=2))


if __name__ == "__main__":
    main()

