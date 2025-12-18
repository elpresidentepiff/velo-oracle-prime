#!/usr/bin/env python3
"""
VELO v12 Lean Benter-Style Value Overlay

Implements ONLY:
1. Probability calibration (Platt scaling / isotonic regression)
2. Value edge calculation: edge = p_model - p_market
3. Capped fractional Kelly staking

Does NOT implement:
- Full Benter iteration
- Multi-stage weight re-estimation
- Complex optimization loops

Gated by:
- DecisionPolicy (chassis constraints)
- ADLG (learning gate)

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class CalibrationMethod(Enum):
    """Calibration method."""
    PLATT = "platt"
    ISOTONIC = "isotonic"
    NONE = "none"


@dataclass
class ValueEdge:
    """Value edge calculation result."""
    runner_id: str
    p_model: float  # Model probability
    p_market: float  # Market implied probability
    edge: float  # p_model - p_market
    has_value: bool  # edge > threshold
    
    def to_dict(self) -> Dict:
        return {
            'runner_id': self.runner_id,
            'p_model': self.p_model,
            'p_market': self.p_market,
            'edge': self.edge,
            'has_value': self.has_value
        }


@dataclass
class StakeRecommendation:
    """Stake recommendation."""
    runner_id: str
    edge: float
    kelly_fraction: float
    stake_pct: float  # % of bankroll
    capped_stake_pct: float  # After applying cap
    
    def to_dict(self) -> Dict:
        return {
            'runner_id': self.runner_id,
            'edge': self.edge,
            'kelly_fraction': self.kelly_fraction,
            'stake_pct': self.stake_pct,
            'capped_stake_pct': self.capped_stake_pct
        }


class ValueOverlay:
    """
    Lean Benter-Style Value Overlay.
    
    Implements:
    1. Probability calibration
    2. Value edge vs market
    3. Capped fractional Kelly
    """
    
    # Configuration
    EDGE_THRESHOLD = 0.05  # Minimum edge to consider (5%)
    KELLY_FRACTION = 0.25  # Fractional Kelly (25% of full Kelly)
    MAX_STAKE_PCT = 0.05  # Maximum stake (5% of bankroll)
    MIN_STAKE_PCT = 0.01  # Minimum stake (1% of bankroll)
    
    def __init__(
        self,
        calibration_method: CalibrationMethod = CalibrationMethod.PLATT
    ):
        self.calibration_method = calibration_method
        logger.info(f"Value Overlay initialized: calibration={calibration_method.value}")
    
    def calculate_value_edges(
        self,
        model_probabilities: Dict[str, float],
        market_odds: Dict[str, float]
    ) -> List[ValueEdge]:
        """
        Calculate value edges for all runners.
        
        Args:
            model_probabilities: {runner_id: p_win}
            market_odds: {runner_id: odds_decimal}
            
        Returns:
            List of ValueEdge objects
        """
        edges = []
        
        for runner_id, p_model in model_probabilities.items():
            # Get market odds
            odds = market_odds.get(runner_id)
            if odds is None or odds <= 1.0:
                logger.warning(f"Invalid odds for {runner_id}: {odds}")
                continue
            
            # Convert odds to implied probability
            p_market = 1.0 / odds
            
            # Calculate edge
            edge = p_model - p_market
            has_value = edge >= self.EDGE_THRESHOLD
            
            value_edge = ValueEdge(
                runner_id=runner_id,
                p_model=p_model,
                p_market=p_market,
                edge=edge,
                has_value=has_value
            )
            
            edges.append(value_edge)
            
            if has_value:
                logger.info(f"Value found: {runner_id} edge={edge:.3f} (p_model={p_model:.3f}, p_market={p_market:.3f})")
        
        return edges
    
    def calculate_stakes(
        self,
        value_edges: List[ValueEdge],
        market_odds: Dict[str, float]
    ) -> List[StakeRecommendation]:
        """
        Calculate stake recommendations using capped fractional Kelly.
        
        Args:
            value_edges: List of ValueEdge objects
            market_odds: {runner_id: odds_decimal}
            
        Returns:
            List of StakeRecommendation objects
        """
        stakes = []
        
        for edge_obj in value_edges:
            if not edge_obj.has_value:
                continue
            
            runner_id = edge_obj.runner_id
            edge = edge_obj.edge
            p_model = edge_obj.p_model
            
            # Get market odds
            odds = market_odds.get(runner_id, 0)
            if odds <= 1.0:
                continue
            
            # Kelly formula: f = (bp - q) / b
            # where:
            #   b = odds - 1 (net odds)
            #   p = p_model (our probability)
            #   q = 1 - p (probability of losing)
            b = odds - 1.0
            p = p_model
            q = 1.0 - p
            
            # Full Kelly
            kelly_full = (b * p - q) / b
            
            # Fractional Kelly
            kelly_fraction = kelly_full * self.KELLY_FRACTION
            
            # Cap stake
            stake_pct = max(self.MIN_STAKE_PCT, min(kelly_fraction, self.MAX_STAKE_PCT))
            
            recommendation = StakeRecommendation(
                runner_id=runner_id,
                edge=edge,
                kelly_fraction=kelly_fraction,
                stake_pct=kelly_fraction,
                capped_stake_pct=stake_pct
            )
            
            stakes.append(recommendation)
            
            logger.info(f"Stake: {runner_id} edge={edge:.3f} kelly={kelly_fraction:.3f} capped={stake_pct:.3f}")
        
        return stakes
    
    def calibrate_probabilities(
        self,
        raw_probabilities: Dict[str, float],
        calibration_params: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Calibrate model probabilities.
        
        Args:
            raw_probabilities: {runner_id: raw_p_win}
            calibration_params: Calibration parameters (optional)
            
        Returns:
            {runner_id: calibrated_p_win}
        """
        if self.calibration_method == CalibrationMethod.NONE:
            return raw_probabilities
        
        if self.calibration_method == CalibrationMethod.PLATT:
            return self._platt_calibration(raw_probabilities, calibration_params)
        
        if self.calibration_method == CalibrationMethod.ISOTONIC:
            return self._isotonic_calibration(raw_probabilities, calibration_params)
        
        return raw_probabilities
    
    def _platt_calibration(
        self,
        raw_probabilities: Dict[str, float],
        params: Optional[Dict]
    ) -> Dict[str, float]:
        """
        Platt scaling calibration.
        
        Platt scaling: p_calibrated = 1 / (1 + exp(A * log(p / (1-p)) + B))
        
        Simplified version: p_calibrated = sigmoid(A * logit(p) + B)
        """
        if params is None:
            # Default parameters (identity transformation)
            A = 1.0
            B = 0.0
        else:
            A = params.get('A', 1.0)
            B = params.get('B', 0.0)
        
        calibrated = {}
        
        for runner_id, p_raw in raw_probabilities.items():
            # Clip to avoid log(0)
            p_clipped = max(0.001, min(0.999, p_raw))
            
            # Logit transformation
            logit_p = math.log(p_clipped / (1.0 - p_clipped))
            
            # Apply Platt scaling
            scaled_logit = A * logit_p + B
            
            # Sigmoid (inverse logit)
            p_calibrated = 1.0 / (1.0 + math.exp(-scaled_logit))
            
            calibrated[runner_id] = p_calibrated
        
        return calibrated
    
    def _isotonic_calibration(
        self,
        raw_probabilities: Dict[str, float],
        params: Optional[Dict]
    ) -> Dict[str, float]:
        """
        Isotonic regression calibration.
        
        Requires fitted isotonic regressor (not implemented here - placeholder).
        """
        logger.warning("Isotonic calibration not yet implemented - using raw probabilities")
        return raw_probabilities


def calculate_value_overlay(
    model_probabilities: Dict[str, float],
    market_odds: Dict[str, float],
    calibration_method: CalibrationMethod = CalibrationMethod.PLATT,
    calibration_params: Optional[Dict] = None
) -> tuple[List[ValueEdge], List[StakeRecommendation]]:
    """
    Convenience function to calculate value overlay.
    
    Args:
        model_probabilities: {runner_id: p_win}
        market_odds: {runner_id: odds_decimal}
        calibration_method: Calibration method
        calibration_params: Calibration parameters
        
    Returns:
        (value_edges, stake_recommendations)
    """
    overlay = ValueOverlay(calibration_method)
    
    # Calibrate probabilities
    calibrated_probs = overlay.calibrate_probabilities(
        model_probabilities,
        calibration_params
    )
    
    # Calculate value edges
    edges = overlay.calculate_value_edges(calibrated_probs, market_odds)
    
    # Calculate stakes
    stakes = overlay.calculate_stakes(edges, market_odds)
    
    return edges, stakes


if __name__ == "__main__":
    # Example usage
    model_probabilities = {
        'r1': 0.35,  # Model thinks 35% chance
        'r2': 0.25,
        'r3': 0.15,
        'r4': 0.10
    }
    
    market_odds = {
        'r1': 4.0,  # Market implies 25% (1/4.0)
        'r2': 5.0,  # Market implies 20% (1/5.0)
        'r3': 8.0,  # Market implies 12.5% (1/8.0)
        'r4': 12.0  # Market implies 8.3% (1/12.0)
    }
    
    edges, stakes = calculate_value_overlay(model_probabilities, market_odds)
    
    print("\n=== VALUE EDGES ===")
    for edge in edges:
        print(f"{edge.runner_id}: edge={edge.edge:.3f} ({'VALUE' if edge.has_value else 'no value'})")
    
    print("\n=== STAKE RECOMMENDATIONS ===")
    for stake in stakes:
        print(f"{stake.runner_id}: {stake.capped_stake_pct:.2%} of bankroll (edge={stake.edge:.3f})")
