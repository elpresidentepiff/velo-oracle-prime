#!/usr/bin/env python3
"""
VELO v12 Integration Tests for Acceptance Criteria

Tests the 4 critical acceptance criteria:
1. High manipulation => ADLG = rejected (no learning write)
2. Ablation flips top selection => ADLG = quarantined
3. Liquidity anchor in chaos => DecisionPolicy disallows WIN by default
4. Release_Horse + Intent_Win + NOT manipulated + ablation stable => WIN allowed

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import unittest
from typing import Dict, List

# Import pipeline components
from app.ml.learning_gate import evaluate_learning_gate, LearningStatus
from app.strategy.decision_policy import make_decision, BetChassisType
from app.ml.opponent_models import OpponentProfile, IntentClass, MarketRole


class TestAcceptanceCriteria(unittest.TestCase):
    """Integration tests for acceptance criteria."""
    
    def test_acceptance_1_high_manipulation_rejects_learning(self):
        """
        Acceptance Test 1: High manipulation => ADLG = rejected
        
        When manipulation_risk >= 0.60, learning gate should reject.
        """
        # Arrange
        signal_outputs = {
            'chaos_level': 0.50,
            'manipulation_risk': 0.70,  # HIGH manipulation
            'stability_score': 0.75
        }
        
        ablation_results = {
            'fragile': False,
            'flip_count': 0
        }
        
        decision = {
            'chassis_type': 'Top_4_Structure',
            'win_suppressed': True
        }
        
        # Act
        gate_result = evaluate_learning_gate(
            signal_outputs,
            ablation_results,
            decision
        )
        
        # Assert
        self.assertEqual(
            gate_result.learning_status,
            LearningStatus.REJECTED,
            "High manipulation should result in REJECTED learning status"
        )
        self.assertIn(
            'manipulation',
            gate_result.rejection_reason.lower(),
            "Rejection reason should mention manipulation"
        )
    
    def test_acceptance_2_ablation_flip_quarantines_learning(self):
        """
        Acceptance Test 2: Ablation flips selection => ADLG = quarantined
        
        When ablation is fragile (flip_count >= 2), learning should be quarantined.
        """
        # Arrange
        signal_outputs = {
            'chaos_level': 0.40,
            'manipulation_risk': 0.25,
            'stability_score': 0.70
        }
        
        ablation_results = {
            'fragile': True,  # FRAGILE
            'flip_count': 2,
            'prob_delta_max': 0.18
        }
        
        decision = {
            'chassis_type': 'Win_Overlay',
            'win_suppressed': False
        }
        
        # Act
        gate_result = evaluate_learning_gate(
            signal_outputs,
            ablation_results,
            decision
        )
        
        # Assert
        self.assertEqual(
            gate_result.learning_status,
            LearningStatus.QUARANTINED,
            "Fragile ablation should result in QUARANTINED learning status"
        )
        self.assertIn(
            'ablation',
            gate_result.quarantine_reason.lower(),
            "Quarantine reason should mention ablation"
        )
    
    def test_acceptance_3_liquidity_anchor_chaos_suppresses_win(self):
        """
        Acceptance Test 3: Liquidity anchor in chaos => DecisionPolicy disallows WIN
        
        In chaos race, if top selection is Liquidity_Anchor, WIN should be suppressed.
        """
        # Arrange
        race_ctx = {
            'race_id': 'test_chaos_001'
        }
        
        runner_profiles = [
            {
                'runner_id': 'r1',
                'horse_name': 'Horse A',
                'market_role': 'Liquidity_Anchor',  # LIQUIDITY ANCHOR
                'intent_class': 'Win',
                'final_score': 0.85
            },
            {
                'runner_id': 'r2',
                'horse_name': 'Horse B',
                'market_role': 'Noise',
                'intent_class': 'Place',
                'final_score': 0.75
            }
        ]
        
        engine_outputs = {
            'chaos_level': 0.65,  # CHAOS race
            'manipulation_risk': 0.30,
            'stability_score': 0.70,
            'pace_geometry_score': 0.65,
            'top_predictions': runner_profiles
        }
        
        ablation_results = {
            'fragile': False,
            'flip_count': 0
        }
        
        ctf_report = {
            'decision_adjusted': False
        }
        
        # Act
        decision = make_decision(
            race_ctx,
            runner_profiles,
            engine_outputs,
            ablation_results,
            ctf_report
        )
        
        # Assert
        self.assertTrue(
            decision.win_suppressed,
            "WIN should be suppressed for Liquidity_Anchor in chaos race"
        )
        self.assertNotEqual(
            decision.chassis_type,
            BetChassisType.WIN_OVERLAY,
            "Chassis should NOT be Win_Overlay for Liquidity_Anchor in chaos"
        )
        self.assertEqual(
            decision.chassis_type,
            BetChassisType.TOP_4_STRUCTURE,
            "Chassis should default to Top_4_Structure in chaos"
        )
    
    def test_acceptance_4_release_horse_win_conditions_allow_win(self):
        """
        Acceptance Test 4: Release_Horse + Intent_Win + NOT manipulated + ablation stable => WIN allowed
        
        When ALL conditions met, WIN overlay should be allowed.
        """
        # Arrange
        race_ctx = {
            'race_id': 'test_release_001'
        }
        
        runner_profiles = [
            {
                'runner_id': 'r1',
                'horse_name': 'Horse A',
                'market_role': 'Release_Horse',  # RELEASE HORSE
                'intent_class': 'Win',  # INTENT WIN
                'final_score': 0.85
            },
            {
                'runner_id': 'r2',
                'horse_name': 'Horse B',
                'market_role': 'Noise',
                'intent_class': 'Place',
                'final_score': 0.75
            }
        ]
        
        engine_outputs = {
            'chaos_level': 0.65,  # Chaos race
            'manipulation_risk': 0.25,  # NOT manipulated (< 0.60)
            'stability_score': 0.70,
            'pace_geometry_score': 0.65,
            'top_predictions': runner_profiles
        }
        
        ablation_results = {
            'fragile': False,  # Ablation STABLE
            'flip_count': 0
        }
        
        ctf_report = {
            'decision_adjusted': False  # CTF NOT adjusted
        }
        
        # Act
        decision = make_decision(
            race_ctx,
            runner_profiles,
            engine_outputs,
            ablation_results,
            ctf_report
        )
        
        # Assert
        self.assertFalse(
            decision.win_suppressed,
            "WIN should NOT be suppressed when all conditions met"
        )
        self.assertEqual(
            decision.chassis_type,
            BetChassisType.WIN_OVERLAY,
            "Chassis should be Win_Overlay when Release + Intent + Clean + Stable"
        )
        self.assertEqual(
            decision.top_strike_selection,
            'r1',
            "Top strike should be the Release_Horse"
        )
    
    def test_acceptance_4_partial_conditions_suppress_win(self):
        """
        Acceptance Test 4 (negative): Missing one condition => WIN suppressed
        
        If ANY condition fails, WIN should be suppressed.
        """
        # Arrange: Same as test_acceptance_4 but with manipulation HIGH
        race_ctx = {
            'race_id': 'test_release_002'
        }
        
        runner_profiles = [
            {
                'runner_id': 'r1',
                'horse_name': 'Horse A',
                'market_role': 'Release_Horse',
                'intent_class': 'Win',
                'final_score': 0.85
            }
        ]
        
        engine_outputs = {
            'chaos_level': 0.65,
            'manipulation_risk': 0.70,  # MANIPULATED (>= 0.60)
            'stability_score': 0.70,
            'pace_geometry_score': 0.65,
            'top_predictions': runner_profiles
        }
        
        ablation_results = {
            'fragile': False,
            'flip_count': 0
        }
        
        ctf_report = {
            'decision_adjusted': False
        }
        
        # Act
        decision = make_decision(
            race_ctx,
            runner_profiles,
            engine_outputs,
            ablation_results,
            ctf_report
        )
        
        # Assert
        self.assertTrue(
            decision.win_suppressed,
            "WIN should be suppressed when manipulation detected"
        )
        self.assertIn(
            'manipulation',
            decision.suppression_reason.lower(),
            "Suppression reason should mention manipulation"
        )


class TestPipelineIntegration(unittest.TestCase):
    """Integration tests for full pipeline."""
    
    def test_pipeline_end_to_end(self):
        """
        Test full pipeline execution from ingestion to storage.
        """
        from app.pipeline.orchestrator import run_velo_pipeline
        
        # Arrange
        race_ctx = {
            'race_id': 'test_001',
            'course': 'Newmarket',
            'distance': 1200,
            'class_level': 85
        }
        
        market_ctx = {
            'snapshot_timestamp': '2025-12-17T14:00:00'
        }
        
        runners = [
            {
                'runner_id': 'r1',
                'horse_name': 'Horse A',
                'trainer': 'Trainer X',
                'odds_decimal': 3.5,
                'is_favorite': True
            },
            {
                'runner_id': 'r2',
                'horse_name': 'Horse B',
                'trainer': 'Trainer Y',
                'odds_decimal': 5.0,
                'is_favorite': False
            }
        ]
        
        # Act
        ctx = run_velo_pipeline('test_001', race_ctx, market_ctx, runners)
        
        # Assert
        self.assertIsNotNone(ctx.engine_run_id, "Engine run ID should be generated")
        self.assertIsNotNone(ctx.features_hash, "Features hash should be generated")
        self.assertTrue(ctx.leakage_passed, "Leakage check should pass")
        self.assertIn('chaos_level', ctx.signal_outputs, "Signal outputs should include chaos_level")
        self.assertIsNotNone(ctx.decision, "Decision should be generated")
        self.assertIn('learning_status', ctx.learning_gate_result, "Learning gate should produce status")
        self.assertIsNotNone(ctx.engine_run, "EngineRun should be created")


def run_tests():
    """Run all integration tests."""
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
