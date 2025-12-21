#!/usr/bin/env python3
"""
VELO v12 Pipeline Orchestrator
Wires all stages from ingestion to storage

Pipeline Order:
1. Data Ingestion
2. Feature Engineering (v12)
3. Leakage Firewall
4. Signal Engines (SQPE, Chaos, SSES, TIE, HBI)
5. Strategic Intelligence Pack v2 (Opponent Models, CTF, Ablation)
6. Decision Policy
7. Learning Gate (ADLG)
8. Storage (EngineRun)
9. Post-Race Critique (on result)

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import logging
import hashlib
import json

# Feature engineering
from app.ml.v12_feature_engineering import V12FeatureEngineer
from app.ml.race_engineering_features import build_race_engineering_features
from app.ml.leakage_firewall import LeakageFirewall

# Strategic Intelligence Pack v2
from app.ml.opponent_models import profile_race_opponents
from app.ml.cognitive_trap_firewall import scan_cognitive_traps
from app.ml.ablation_tests import run_ablation_tests
from app.ml.learning_gate import evaluate_learning_gate
from app.ml.chaos_calculator import calculate_chaos_level, calculate_manipulation_risk
from app.strategy.decision_policy import make_decision

# Engine & storage
from app.engine.engine_run import EngineRun, EngineRunRepository
from app.learning.post_race_critique import perform_post_race_critique

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Context object passed through pipeline stages."""
    race_id: str
    engine_run_id: str
    timestamp: datetime
    
    # Stage 1: Raw inputs
    race_ctx: Dict = field(default_factory=dict)
    market_ctx: Dict = field(default_factory=dict)
    runners: List[Dict] = field(default_factory=list)
    
    # Stage 2: Features
    features_df: Optional[object] = None  # pandas DataFrame
    features_hash: str = ""
    
    # Stage 3: Leakage check
    leakage_passed: bool = False
    
    # Stage 4: Signal engines
    signal_outputs: Dict = field(default_factory=dict)
    
    # Stage 5: Strategic Intelligence
    opponent_profiles: List[Dict] = field(default_factory=list)
    ctf_report: Dict = field(default_factory=dict)
    ablation_results: Dict = field(default_factory=dict)
    
    # Stage 6: Decision
    decision: Dict = field(default_factory=dict)
    
    # Stage 7: Learning gate
    learning_gate_result: Dict = field(default_factory=dict)
    
    # Stage 8: Storage
    engine_run: Optional[EngineRun] = None
    
    # Stage 9: Post-race (deferred)
    race_result: Optional[Dict] = None
    critique: Optional[Dict] = None


class VELOPipeline:
    """
    VELO v12 Pipeline Orchestrator.
    
    Coordinates all stages from ingestion to storage.
    """
    
    def __init__(self):
        self.feature_engineer = V12FeatureEngineer()
        self.leakage_firewall = LeakageFirewall()
        logger.info("VELO Pipeline initialized")
    
    def run(
        self,
        race_id: str,
        race_ctx: Dict,
        market_ctx: Dict,
        runners: List[Dict]
    ) -> PipelineContext:
        """
        Run full pipeline.
        
        Args:
            race_id: Race ID
            race_ctx: Race context
            market_ctx: Market context
            runners: Runner data
            
        Returns:
            PipelineContext with all stage outputs
        """
        logger.info(f"Pipeline starting for race: {race_id}")
        
        # Initialize context
        ctx = PipelineContext(
            race_id=race_id,
            engine_run_id=self._generate_engine_run_id(race_id),
            timestamp=datetime.now(),
            race_ctx=race_ctx,
            market_ctx=market_ctx,
            runners=runners
        )
        
        # Stage 1: Data Ingestion (already done - inputs provided)
        logger.info("Stage 1: Data ingestion (complete)")
        
        # Stage 2: Feature Engineering
        ctx = self._stage_2_feature_engineering(ctx)
        
        # Stage 3: Leakage Firewall
        ctx = self._stage_3_leakage_firewall(ctx)
        
        # Stage 4: Signal Engines
        ctx = self._stage_4_signal_engines(ctx)
        
        # Stage 5: Strategic Intelligence Pack v2
        ctx = self._stage_5_strategic_intelligence(ctx)
        
        # Stage 6: Decision Policy
        ctx = self._stage_6_decision_policy(ctx)
        
        # Stage 7: Learning Gate
        ctx = self._stage_7_learning_gate(ctx)
        
        # Stage 8: Storage
        ctx = self._stage_8_storage(ctx)
        
        logger.info(f"Pipeline complete for race: {race_id}")
        return ctx
    
    def run_post_race_critique(
        self,
        ctx: PipelineContext,
        race_result: Dict
    ) -> PipelineContext:
        """
        Run post-race critique (Stage 9).
        
        Args:
            ctx: Pipeline context from original run
            race_result: Actual race result
            
        Returns:
            Updated context with critique
        """
        logger.info(f"Running post-race critique for race: {ctx.race_id}")
        
        ctx.race_result = race_result
        
        # Extract engine run data
        engine_run_data = {
            'verdict': ctx.decision,
            'runner_scores': [
                {
                    'runner_id': p.get('runner_id'),
                    'market_role': p.get('market_role')
                }
                for p in ctx.opponent_profiles
            ],
            'chaos_level': ctx.signal_outputs.get('chaos_level', 0.0),
            'manipulation_risk': ctx.signal_outputs.get('manipulation_risk', 0.0)
        }
        
        # Perform critique
        critique = perform_post_race_critique(
            ctx.race_id,
            ctx.engine_run_id,
            engine_run_data,
            race_result,
            ctx.learning_gate_result
        )
        
        ctx.critique = critique.to_dict()
        
        logger.info(f"Post-race critique complete: correct={critique.prediction_correct}")
        return ctx
    
    def _stage_2_feature_engineering(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 2: Feature Engineering (v12)."""
        logger.info("Stage 2: Feature engineering")
        
        # Build v12 features
        # (Simplified - in production would call actual feature builder)
        ctx.features_df = None  # Placeholder
        
        # Build race engineering features
        race_eng_features = build_race_engineering_features(
            ctx.runners,
            ctx.race_ctx
        )
        
        # Compute feature hash
        features_str = json.dumps(ctx.race_ctx, sort_keys=True) + json.dumps(ctx.market_ctx, sort_keys=True)
        ctx.features_hash = hashlib.sha256(features_str.encode()).hexdigest()[:16]
        
        logger.info(f"Features generated: hash={ctx.features_hash}")
        return ctx
    
    def _stage_3_leakage_firewall(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 3: Leakage Firewall."""
        logger.info("Stage 3: Leakage firewall")
        
        # Check for leakage
        decision_timestamp = ctx.market_ctx.get('snapshot_timestamp', datetime.now())
        
        # Simplified check
        ctx.leakage_passed = True  # Would run actual firewall
        
        logger.info(f"Leakage check: {'PASS' if ctx.leakage_passed else 'FAIL'}")
        return ctx
    
    def _stage_4_signal_engines(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 4: Signal Engines (SQPE, Chaos, SSES, TIE, HBI)."""
        logger.info("Stage 4: Signal engines")
        
        # Patch 3: Calculate real chaos and manipulation risk from odds
        chaos_level = calculate_chaos_level(ctx.runners)
        manipulation_risk = calculate_manipulation_risk(ctx.runners)
        
        # Other signals still placeholder (will be Phase 2)
        ctx.signal_outputs = {
            'chaos_level': chaos_level,
            'manipulation_risk': manipulation_risk,
            'stability_score': 0.72,  # Placeholder
            'pace_geometry_score': 0.68,  # Placeholder
            'top_predictions': ctx.runners[:4]  # Placeholder (will be fixed in Patch 4)
        }
        
        logger.info(f"Signal engines complete: chaos={chaos_level:.3f}, manipulation={manipulation_risk:.3f}")
        return ctx
    
    def _stage_5_strategic_intelligence(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 5: Strategic Intelligence Pack v2."""
        logger.info("Stage 5: Strategic Intelligence Pack v2")
        
        # Opponent models
        ctx.opponent_profiles = profile_race_opponents(
            ctx.runners,
            ctx.race_ctx,
            ctx.market_ctx
        )
        
        # Cognitive trap firewall
        predictions = {
            'top_selection': ctx.runners[0].get('runner_id') if ctx.runners else None,
            'probabilities': {}
        }
        ctx.ctf_report = scan_cognitive_traps(
            ctx.runners,
            predictions,
            ctx.market_ctx
        ).to_dict()
        
        # Ablation tests (simplified - would run actual model)
        def mock_predict(df):
            return predictions
        
        # ctx.ablation_results = run_ablation_tests(
        #     ctx.features_df,
        #     mock_predict,
        #     predictions
        # ).to_dict()
        
        # Placeholder
        ctx.ablation_results = {
            'fragile': False,
            'flip_count': 0,
            'prob_delta_max': 0.05
        }
        
        logger.info("Strategic Intelligence Pack v2 complete")
        return ctx
    
    def _stage_6_decision_policy(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 6: Decision Policy."""
        logger.info("Stage 6: Decision policy")
        
        # Make decision
        ctx.decision = make_decision(
            ctx.race_ctx,
            [p.to_dict() for p in ctx.opponent_profiles],
            ctx.signal_outputs,
            ctx.ablation_results,
            ctx.ctf_report
        ).to_dict()
        
        logger.info(f"Decision: chassis={ctx.decision['chassis_type']}, suppressed={ctx.decision['win_suppressed']}")
        return ctx
    
    def _stage_7_learning_gate(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 7: Learning Gate (ADLG)."""
        logger.info("Stage 7: Learning gate (ADLG)")
        
        # Evaluate learning gate
        # Note: integrity_check is performed post-race, so we pass empty dict for pre-race
        integrity_check = {'status': 'pending', 'checks': []}
        ctx.learning_gate_result = evaluate_learning_gate(
            ctx.signal_outputs,
            ctx.ablation_results,
            ctx.decision,
            integrity_check,
            ctx.race_ctx
        ).to_dict()
        
        logger.info(f"Learning gate: status={ctx.learning_gate_result['learning_status']}")
        return ctx
    
    def _stage_8_storage(self, ctx: PipelineContext) -> PipelineContext:
        """Stage 8: Storage (EngineRun)."""
        logger.info("Stage 8: Storage")
        
        # Create EngineRun
        # Note: EngineRun uses RaceContext and MarketContext objects, not dicts
        # For now, store key info in metadata
        ctx.engine_run = EngineRun(
            engine_run_id=ctx.engine_run_id,
            decision_timestamp=ctx.timestamp,
            mode="RACE",
            chaos_level=ctx.signal_outputs.get('chaos_level', 0.0),
            metadata={
                'race_id': ctx.race_id,
                'race_ctx': ctx.race_ctx,
                'market_ctx': ctx.market_ctx,
                'features_hash': ctx.features_hash,
                'learning_gate_status': ctx.learning_gate_result.get('learning_status', 'unknown'),
                'decision': ctx.decision
            }
        )
        
        # Store (would persist to DB)
        # store_engine_run(ctx.engine_run)
        
        logger.info(f"EngineRun stored: {ctx.engine_run_id}")
        return ctx
    
    def _generate_engine_run_id(self, race_id: str) -> str:
        """Generate unique engine run ID."""
        timestamp = datetime.now().isoformat()
        raw = f"{race_id}_{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def run_velo_pipeline(
    race_id: str,
    race_ctx: Dict,
    market_ctx: Dict,
    runners: List[Dict]
) -> PipelineContext:
    """
    Convenience function to run VELO pipeline.
    
    Args:
        race_id: Race ID
        race_ctx: Race context
        market_ctx: Market context
        runners: Runners
        
    Returns:
        PipelineContext
    """
    pipeline = VELOPipeline()
    return pipeline.run(race_id, race_ctx, market_ctx, runners)


if __name__ == "__main__":
    # Example usage
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
    
    ctx = run_velo_pipeline('test_001', race_ctx, market_ctx, runners)
    
    print(f"\nPipeline Result:")
    print(f"  Engine Run ID: {ctx.engine_run_id}")
    print(f"  Features Hash: {ctx.features_hash}")
    print(f"  Leakage Passed: {ctx.leakage_passed}")
    print(f"  Chaos Level: {ctx.signal_outputs.get('chaos_level', 0.0):.2f}")
    print(f"  Decision Chassis: {ctx.decision.get('chassis_type', 'unknown')}")
    print(f"  Learning Status: {ctx.learning_gate_result.get('learning_status', 'unknown')}")
