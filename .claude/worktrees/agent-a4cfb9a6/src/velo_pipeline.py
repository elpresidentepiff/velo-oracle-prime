"""
VÉLØ Integrated Prediction Pipeline
Combines LightGBM core predictor with RPD-C tags, quarantine gates, and market constraints.
"""

import numpy as np
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from train_model import VeloPredictor
from feature_engineering import FeatureEngineer


class VeloPipeline:
    """
    End-to-end VÉLØ prediction pipeline.
    
    Workflow:
    1. Extract 61 features from race data
    2. Generate ML probabilities (p_win, p_top4)
    3. Apply RPD-C tagging logic
    4. Run quarantine gates
    5. Generate final verdict with confidence
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize pipeline with trained models.
        
        Args:
            model_path: Path to trained model pickle file
        """
        self.feature_engineer = FeatureEngineer()
        self.predictor = VeloPredictor()
        
        if model_path is None:
            model_path = "/home/ubuntu/velo-oracle-prime/models/velo_predictor_v1.pkl"
        
        if Path(model_path).exists():
            self.predictor.load(model_path)
            print(f"✅ Loaded VÉLØ predictor from {model_path}")
        else:
            print(f"⚠️  Model not found at {model_path}. Train model first.")
    
    def predict_race(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate predictions for entire race.
        
        Args:
            race_data: Dict with 'runners' list and race context
        
        Returns:
            Verdict dict with top strike, confidence, and runner analysis
        """
        # Extract features for all runners
        X = self.feature_engineer.extract_race_features(race_data)
        
        # Generate ML probabilities
        ml_predictions = self.predictor.predict(X)
        
        # Analyze each runner
        runners = race_data.get('runners', [])
        runner_analysis = []
        
        for i, runner in enumerate(runners):
            analysis = self._analyze_runner(
                runner=runner,
                p_win=ml_predictions['p_win'][i],
                p_top4=ml_predictions['p_top4'][i],
                race_context=race_data
            )
            runner_analysis.append(analysis)
        
        # Sort by combined score
        runner_analysis.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Apply quarantine gates
        quarantine_result = self._check_quarantine(race_data, runner_analysis)
        
        if quarantine_result['quarantined']:
            return {
                'status': 'QUARANTINE',
                'reason': quarantine_result['reason'],
                'gates_failed': quarantine_result['gates_failed'],
                'runners': runner_analysis,
            }
        
        # Generate verdict
        verdict = self._generate_verdict(race_data, runner_analysis)
        
        return verdict
    
    def _analyze_runner(
        self,
        runner: Dict[str, Any],
        p_win: float,
        p_top4: float,
        race_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze single runner combining ML and rule-based logic.
        
        Returns:
            Analysis dict with RPD tag, scores, and rationale
        """
        # RPD-C tagging
        rpd_tag = self._assign_rpd_tag(runner, p_win, p_top4, race_context)
        
        # Combined score (ML + rules)
        combined_score = self._calculate_combined_score(runner, p_win, p_top4, rpd_tag)
        
        # Confidence factors
        confidence_factors = self._get_confidence_factors(runner, race_context)
        
        return {
            'name': runner.get('name', 'Unknown'),
            'p_win': float(p_win),
            'p_top4': float(p_top4),
            'rpd_tag': rpd_tag,
            'combined_score': combined_score,
            'confidence_factors': confidence_factors,
            'odds': runner.get('odds', 999.0),
            'postdata_pick': runner.get('postdata_pick', False),
            'topspeed_pick': runner.get('topspeed_pick', False),
        }
    
    def _assign_rpd_tag(
        self,
        runner: Dict[str, Any],
        p_win: float,
        p_top4: float,
        race_context: Dict[str, Any]
    ) -> str:
        """
        Assign RPD-C tag based on ML probabilities and signals.
        
        Tags:
        - T (Target): High probability + positive signals
        - H (Hold): Moderate probability
        - P (Prep): Low probability + prep signals
        - S (Swerve): Negative signals
        - E (Eliminate): Hard eliminate
        """
        # Count positive signals
        positive_signals = 0
        
        if p_win > 0.15:
            positive_signals += 2
        elif p_win > 0.08:
            positive_signals += 1
        
        if runner.get('postdata_pick'):
            positive_signals += 1
        if runner.get('topspeed_pick'):
            positive_signals += 1
        if runner.get('first_choice_jockey_flag'):
            positive_signals += 1
        if runner.get('class_drop_flag'):
            positive_signals += 1
        if runner.get('c_d_win_count', 0) >= 2:
            positive_signals += 1
        
        # Count negative signals
        negative_signals = 0
        
        if runner.get('form_decline_flag'):
            negative_signals += 1
        if runner.get('days_since_last_run', 0) > 90:
            negative_signals += 1
        if runner.get('class_rise_flag'):
            negative_signals += 1
        
        # Assign tag
        if positive_signals >= 4:
            return 'T'  # Target
        elif positive_signals >= 3:
            return 'H'  # Hold
        elif negative_signals >= 2:
            return 'S'  # Swerve
        elif runner.get('days_since_last_run', 0) > 60 and p_win < 0.05:
            return 'P'  # Prep
        elif p_win < 0.02:
            return 'E'  # Eliminate
        else:
            return 'H'  # Default to Hold
    
    def _calculate_combined_score(
        self,
        runner: Dict[str, Any],
        p_win: float,
        p_top4: float,
        rpd_tag: str
    ) -> float:
        """
        Calculate combined score from ML probabilities and RPD tag.
        
        Formula:
        - Base: p_win * 0.6 + p_top4 * 0.4
        - RPD multiplier: T=1.2, H=1.0, P=0.5, S=0.3, E=0.1
        """
        base_score = p_win * 0.6 + p_top4 * 0.4
        
        rpd_multipliers = {
            'T': 1.2,
            'H': 1.0,
            'P': 0.5,
            'S': 0.3,
            'E': 0.1,
        }
        
        multiplier = rpd_multipliers.get(rpd_tag, 1.0)
        
        return base_score * multiplier
    
    def _get_confidence_factors(
        self,
        runner: Dict[str, Any],
        race_context: Dict[str, Any]
    ) -> List[str]:
        """Get list of confidence-boosting factors."""
        factors = []
        
        if runner.get('postdata_pick') and runner.get('topspeed_pick'):
            factors.append('Consensus pick')
        if runner.get('c_d_win_count', 0) >= 2:
            factors.append('C&D winner')
        if runner.get('class_drop_flag'):
            factors.append('Class drop')
        if runner.get('first_choice_jockey_flag'):
            factors.append('First-choice jockey')
        if race_context.get('going') == 'STANDARD':
            factors.append('AW standard going')
        
        return factors
    
    def _check_quarantine(
        self,
        race_data: Dict[str, Any],
        runner_analysis: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check quarantine gates Q5-Q9.
        
        Returns:
            Dict with quarantine status and reason
        """
        gates_failed = []
        
        # Q5: Heavy/soft going + large field
        going = race_data.get('going', 'GOOD')
        field_size = len(race_data.get('runners', []))
        
        if going in ['HEAVY', 'SOFT'] and field_size >= 12:
            gates_failed.append('Q5')
        
        # Q6: Very small field (<5 runners)
        if field_size < 5:
            gates_failed.append('Q6')
        
        # Q7: Maiden with no form data
        race_type = race_data.get('race_type', '')
        if 'MAIDEN' in race_type.upper():
            has_form = any(r.get('rpr_last_3_avg', 0) > 0 for r in race_data.get('runners', []))
            if not has_form:
                gates_failed.append('Q7')
        
        # Q8: Market chaos (no clear favourite)
        top_runner = runner_analysis[0] if runner_analysis else None
        if top_runner and top_runner['p_win'] < 0.10:
            gates_failed.append('Q8')
        
        # Q9: Conflicting picks + high chaos
        chaos_rating = race_data.get('chaos_rating', 0)
        if chaos_rating >= 4:
            top_picks = [r for r in runner_analysis[:3] if r.get('postdata_pick') or r.get('topspeed_pick')]
            if len(top_picks) < 2:
                gates_failed.append('Q9')
        
        quarantined = len(gates_failed) > 0
        
        return {
            'quarantined': quarantined,
            'gates_failed': gates_failed,
            'reason': f"Quarantine gates failed: {', '.join(gates_failed)}" if quarantined else None
        }
    
    def _generate_verdict(
        self,
        race_data: Dict[str, Any],
        runner_analysis: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate final verdict with top strike and confidence.
        
        Returns:
            Verdict dict with recommendation
        """
        top_runner = runner_analysis[0]
        second_runner = runner_analysis[1] if len(runner_analysis) > 1 else None
        
        # Determine confidence
        confidence = self._calculate_confidence(top_runner, race_data)
        
        # Build verdict
        verdict = {
            'status': 'STRIKE',
            'top_strike': top_runner['name'],
            'confidence': confidence,
            'p_win': top_runner['p_win'],
            'p_top4': top_runner['p_top4'],
            'rpd_tag': top_runner['rpd_tag'],
            'odds': top_runner['odds'],
            'rationale': self._build_rationale(top_runner),
            'danger': second_runner['name'] if second_runner else None,
            'runners': runner_analysis,
        }
        
        return verdict
    
    def _calculate_confidence(
        self,
        top_runner: Dict[str, Any],
        race_data: Dict[str, Any]
    ) -> str:
        """
        Calculate confidence level (HIGH/MEDIUM/LOW).
        
        Logic:
        - HIGH: p_win > 0.25 + consensus + AW/small field
        - MEDIUM: p_win > 0.15 + consensus OR AW
        - LOW: p_win > 0.08 OR conflicting signals
        """
        p_win = top_runner['p_win']
        consensus = top_runner.get('postdata_pick') and top_runner.get('topspeed_pick')
        going = race_data.get('going', 'GOOD')
        field_size = len(race_data.get('runners', []))
        chaos = race_data.get('chaos_rating', 0)
        
        # HIGH confidence
        if p_win > 0.25 and consensus and (going == 'STANDARD' or field_size <= 6):
            return 'HIGH'
        
        # MEDIUM confidence
        if (p_win > 0.15 and consensus) or (p_win > 0.20 and going == 'STANDARD'):
            return 'MEDIUM'
        
        # LOW confidence
        if p_win > 0.08 or chaos >= 4:
            return 'LOW'
        
        return 'LOW'
    
    def _build_rationale(self, runner: Dict[str, Any]) -> str:
        """Build human-readable rationale for strike."""
        factors = runner.get('confidence_factors', [])
        
        rationale_parts = [
            f"ML probability: {runner['p_win']:.1%} win, {runner['p_top4']:.1%} top-4",
            f"RPD tag: {runner['rpd_tag']}",
        ]
        
        if factors:
            rationale_parts.append(f"Factors: {', '.join(factors)}")
        
        return " | ".join(rationale_parts)


def main():
    """Test integrated pipeline."""
    
    print("=" * 80)
    print("VÉLØ Integrated Pipeline Test")
    print("=" * 80)
    print()
    
    # Create pipeline
    pipeline = VeloPipeline()
    
    # Create sample race
    from feature_engineering import create_sample_runner
    
    race_data = {
        'going': 'STANDARD',
        'distance': '2m',
        'race_type': 'Novices Hurdle',
        'chaos_rating': 2,
        'runners': []
    }
    
    # Add 8 runners with varying quality
    for i in range(8):
        runner = create_sample_runner()
        runner['name'] = f"Horse_{i+1}"
        runner['postdata_pick'] = (i == 0)  # First horse is Postdata pick
        runner['topspeed_pick'] = (i == 0)  # First horse is Topspeed pick
        runner['rpr_last_3_avg'] = 120 - (i * 5)  # Declining form
        runner['odds'] = 2.0 + (i * 1.5)
        race_data['runners'].append(runner)
    
    # Generate prediction
    verdict = pipeline.predict_race(race_data)
    
    # Display results
    print("VERDICT:")
    print(f"  Status: {verdict['status']}")
    
    if verdict['status'] == 'QUARANTINE':
        print(f"  Reason: {verdict['reason']}")
        print(f"  Gates failed: {verdict['gates_failed']}")
    else:
        print(f"  Top Strike: {verdict['top_strike']}")
        print(f"  Confidence: {verdict['confidence']}")
        print(f"  p(win): {verdict['p_win']:.3f}")
        print(f"  p(top4): {verdict['p_top4']:.3f}")
        print(f"  RPD Tag: {verdict['rpd_tag']}")
        print(f"  Odds: {verdict['odds']:.1f}")
        print(f"  Rationale: {verdict['rationale']}")
        if verdict.get('danger'):
            print(f"  Danger: {verdict['danger']}")
    
    print()
    print("Top 3 Runners:")
    for i, runner in enumerate(verdict['runners'][:3], 1):
        print(f"  {i}. {runner['name']}")
        print(f"     p(win)={runner['p_win']:.3f}, p(top4)={runner['p_top4']:.3f}")
        print(f"     RPD={runner['rpd_tag']}, Score={runner['combined_score']:.3f}")
    
    print()
    print("✅ Integrated pipeline working")


if __name__ == "__main__":
    main()
