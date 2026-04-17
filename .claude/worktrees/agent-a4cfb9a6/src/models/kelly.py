"""
VÉLØ v10 - Kelly Criterion Stake Sizing
Optimal bet sizing using the Kelly criterion with fractional Kelly for safety

The Kelly criterion maximizes long-term growth rate:
f* = (p × odds - 1) / (odds - 1)

Where:
- f* = optimal fraction of bankroll to bet
- p = true win probability (from model)
- odds = decimal odds offered

Fractional Kelly (e.g., 1/3 Kelly) reduces variance while maintaining
most of the growth rate.
"""

import numpy as np
from typing import Optional
import logging

from ..core.settings import settings

logger = logging.getLogger("velo.kelly")


class KellyCriterion:
    """
    Kelly criterion stake sizing with fractional Kelly support
    """
    
    def __init__(self, fraction: float = None):
        """
        Initialize Kelly criterion calculator
        
        Args:
            fraction: Fraction of Kelly to use (0.0-1.0)
                     Default from settings (typically 0.33 for 1/3 Kelly)
        """
        self.fraction = fraction if fraction is not None else settings.FRACTIONAL_KELLY
        
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError(f"Kelly fraction must be in [0, 1], got {self.fraction}")
        
        logger.info(f"KellyCriterion initialized (fraction={self.fraction})")
    
    def calculate_full_kelly(self, p_model: float, odds: float) -> float:
        """
        Calculate full Kelly stake
        
        f* = (p × odds - 1) / (odds - 1)
        
        Args:
            p_model: Model probability of winning (0.0-1.0)
            odds: Decimal odds offered
        
        Returns:
            Optimal stake as fraction of bankroll (0.0-1.0)
            Returns 0.0 if no edge or invalid inputs
        """
        # Validate inputs
        if not (0.0 < p_model < 1.0):
            logger.warning(f"Invalid p_model: {p_model}, returning 0")
            return 0.0
        
        if odds <= 1.0:
            logger.warning(f"Invalid odds: {odds}, returning 0")
            return 0.0
        
        # Calculate Kelly fraction
        numerator = p_model * odds - 1.0
        denominator = odds - 1.0
        
        f_kelly = numerator / denominator
        
        # Kelly should be positive (we have edge) and <= 1.0
        # Negative Kelly means no edge (don't bet)
        # Kelly > 1.0 is theoretically possible but practically dangerous
        if f_kelly < 0.0:
            return 0.0
        
        if f_kelly > 1.0:
            logger.warning(f"Full Kelly > 1.0 ({f_kelly:.3f}), capping at 1.0")
            return 1.0
        
        return f_kelly
    
    def calculate_fractional_kelly(
        self,
        p_model: float,
        odds: float,
        fraction: Optional[float] = None
    ) -> float:
        """
        Calculate fractional Kelly stake
        
        f_fractional = fraction × f_kelly
        
        Args:
            p_model: Model probability of winning
            odds: Decimal odds offered
            fraction: Kelly fraction to use (overrides default)
        
        Returns:
            Recommended stake as fraction of bankroll
        """
        f_kelly = self.calculate_full_kelly(p_model, odds)
        
        fraction = fraction if fraction is not None else self.fraction
        
        return fraction * f_kelly
    
    def calculate_stake(
        self,
        p_model: float,
        odds: float,
        bankroll: float,
        fraction: Optional[float] = None,
        min_stake: float = 0.0,
        max_stake: Optional[float] = None
    ) -> float:
        """
        Calculate actual stake amount in currency units
        
        Args:
            p_model: Model probability of winning
            odds: Decimal odds offered
            bankroll: Current bankroll
            fraction: Kelly fraction to use (overrides default)
            min_stake: Minimum stake (e.g., £2 minimum bet)
            max_stake: Maximum stake (e.g., £1000 bet limit)
        
        Returns:
            Stake amount in currency units
        """
        # Calculate fractional Kelly
        f_kelly = self.calculate_fractional_kelly(p_model, odds, fraction)
        
        # Convert to currency
        stake = f_kelly * bankroll
        
        # Apply min/max constraints
        if stake < min_stake:
            # If recommended stake is below minimum, don't bet
            return 0.0
        
        if max_stake is not None and stake > max_stake:
            stake = max_stake
        
        return stake
    
    def calculate_edge(self, p_model: float, odds: float) -> float:
        """
        Calculate expected edge (EV - 1)
        
        Edge = p_model × odds - 1
        
        Positive edge means profitable bet in expectation
        
        Args:
            p_model: Model probability of winning
            odds: Decimal odds offered
        
        Returns:
            Expected edge (0.1 = 10% edge)
        """
        return p_model * odds - 1.0
    
    def calculate_ev(self, p_model: float, odds: float) -> float:
        """
        Calculate expected value per unit staked
        
        EV = p_model × odds
        
        Args:
            p_model: Model probability of winning
            odds: Decimal odds offered
        
        Returns:
            Expected value (1.1 = 10% profit expectation)
        """
        return p_model * odds
    
    def calculate_roi(self, p_model: float, odds: float) -> float:
        """
        Calculate expected ROI percentage
        
        ROI% = (EV - 1) × 100
        
        Args:
            p_model: Model probability of winning
            odds: Decimal odds offered
        
        Returns:
            Expected ROI as percentage (10.0 = 10% ROI)
        """
        edge = self.calculate_edge(p_model, odds)
        return edge * 100.0
    
    def should_bet(
        self,
        p_model: float,
        odds: float,
        min_edge: Optional[float] = None
    ) -> bool:
        """
        Determine if a bet should be placed
        
        Args:
            p_model: Model probability
            odds: Decimal odds
            min_edge: Minimum edge required (default from settings)
        
        Returns:
            True if bet has sufficient edge
        """
        edge = self.calculate_edge(p_model, odds)
        
        min_edge = min_edge if min_edge is not None else settings.CONFIDENCE_THRESHOLD
        
        return edge >= min_edge
    
    def growth_rate(self, p_model: float, odds: float, fraction: Optional[float] = None) -> float:
        """
        Calculate expected log growth rate with fractional Kelly
        
        This is the expected long-term growth rate of bankroll
        
        Args:
            p_model: Model probability
            odds: Decimal odds
            fraction: Kelly fraction
        
        Returns:
            Expected log growth rate per bet
        """
        f = self.calculate_fractional_kelly(p_model, odds, fraction)
        
        if f <= 0:
            return 0.0
        
        # Expected log growth
        # E[log(1 + f × (odds - 1))] when win
        # E[log(1 - f)] when lose
        win_growth = np.log(1.0 + f * (odds - 1.0))
        lose_growth = np.log(1.0 - f)
        
        expected_growth = p_model * win_growth + (1.0 - p_model) * lose_growth
        
        return expected_growth

