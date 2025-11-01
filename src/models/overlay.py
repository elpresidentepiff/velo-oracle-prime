"""
VÉLØ v10 - Overlay Selector
Identifies and ranks value betting opportunities (overlays)

An overlay exists when:
p_model > p_market (model thinks horse is better than market does)

The overlay selector:
1. Compares model probabilities to market probabilities
2. Calculates expected edge for each runner
3. Ranks overlays by expected lift (edge × confidence)
4. Filters by minimum edge threshold
5. Returns sorted list of betting opportunities
"""

from typing import List, Dict, Optional
import logging

from ..modules.contracts import Overlay, Racecard, Odds, BetType
from ..core.settings import settings
from .kelly import KellyCriterion

logger = logging.getLogger("velo.overlay")


class OverlaySelector:
    """
    Identifies and ranks value betting opportunities
    """
    
    def __init__(
        self,
        min_edge: float = None,
        min_odds: float = None,
        max_odds: float = None,
        kelly_fraction: float = None
    ):
        """
        Initialize overlay selector
        
        Args:
            min_edge: Minimum edge to consider (default from settings)
            min_odds: Minimum odds to consider (default from settings)
            max_odds: Maximum odds to consider (default from settings)
            kelly_fraction: Kelly fraction for stake sizing (default from settings)
        """
        self.min_edge = min_edge if min_edge is not None else settings.CONFIDENCE_THRESHOLD
        self.min_odds = min_odds if min_odds is not None else settings.MIN_ODDS
        self.max_odds = max_odds if max_odds is not None else settings.MAX_ODDS
        
        self.kelly = KellyCriterion(fraction=kelly_fraction)
        
        logger.info(
            f"OverlaySelector initialized "
            f"(min_edge={self.min_edge}, odds_range=[{self.min_odds}, {self.max_odds}])"
        )
    
    def find_overlays(
        self,
        probabilities: Dict[str, float],
        odds_book: Dict[str, Odds],
        racecard: Optional[Racecard] = None
    ) -> List[Overlay]:
        """
        Find all overlays in a race
        
        Args:
            probabilities: Model probabilities for each runner
            odds_book: Current odds for each runner
            racecard: Optional racecard for additional context
        
        Returns:
            List of Overlay objects, sorted by expected lift (descending)
        """
        overlays = []
        
        for runner_name, p_model in probabilities.items():
            # Get odds for this runner
            odds = odds_book.get(runner_name)
            
            if not odds:
                logger.debug(f"No odds for {runner_name}, skipping")
                continue
            
            # Determine which odds to use (prefer Betfair)
            decimal_odds = odds.bf_win if odds.bf_win else odds.win
            
            if not decimal_odds:
                logger.debug(f"No valid odds for {runner_name}, skipping")
                continue
            
            # Filter by odds range
            if decimal_odds < self.min_odds or decimal_odds > self.max_odds:
                logger.debug(
                    f"{runner_name}: odds {decimal_odds:.2f} outside range "
                    f"[{self.min_odds}, {self.max_odds}]"
                )
                continue
            
            # Calculate market probability
            p_market = 1.0 / decimal_odds
            
            # Calculate edge
            edge = self.kelly.calculate_edge(p_model, decimal_odds)
            
            # Filter by minimum edge
            if edge < self.min_edge:
                logger.debug(
                    f"{runner_name}: edge {edge:.4f} below threshold {self.min_edge}"
                )
                continue
            
            # Calculate Kelly stake
            stake_fraction = self.kelly.calculate_fractional_kelly(p_model, decimal_odds)
            
            # Calculate confidence (how much better is our model than market?)
            confidence = p_model - p_market
            
            # Create overlay
            overlay = Overlay(
                runner=runner_name,
                p_model=p_model,
                p_market=p_market,
                odds=decimal_odds,
                edge=edge,
                stake_fraction=stake_fraction,
                confidence=confidence,
                bet_type=BetType.WIN
            )
            
            overlays.append(overlay)
            
            logger.info(
                f"Overlay found: {runner_name} @ {decimal_odds:.2f} "
                f"(p_model={p_model:.3f}, p_market={p_market:.3f}, "
                f"edge={edge:.3f}, stake={stake_fraction:.3f})"
            )
        
        # Sort by expected lift (edge × confidence)
        # Prioritize bets with both high edge AND high confidence
        overlays.sort(key=lambda x: x.edge * x.confidence, reverse=True)
        
        return overlays
    
    def select_best(
        self,
        overlays: List[Overlay],
        max_bets: int = 1,
        max_exposure: float = 0.1
    ) -> List[Overlay]:
        """
        Select best overlays subject to constraints
        
        Args:
            overlays: List of all overlays (pre-sorted)
            max_bets: Maximum number of bets to place in one race
            max_exposure: Maximum total stake as fraction of bankroll
        
        Returns:
            Selected overlays (subset of input)
        """
        if not overlays:
            return []
        
        selected = []
        total_stake = 0.0
        
        for overlay in overlays:
            # Check if we've hit max bets
            if len(selected) >= max_bets:
                break
            
            # Check if adding this bet would exceed max exposure
            if total_stake + overlay.stake_fraction > max_exposure:
                logger.info(
                    f"Skipping {overlay.runner}: would exceed max exposure "
                    f"({total_stake + overlay.stake_fraction:.3f} > {max_exposure})"
                )
                continue
            
            # Add to selected
            selected.append(overlay)
            total_stake += overlay.stake_fraction
        
        logger.info(
            f"Selected {len(selected)} overlays "
            f"(total exposure: {total_stake:.3f})"
        )
        
        return selected
    
    def rank_by_metric(
        self,
        overlays: List[Overlay],
        metric: str = "lift"
    ) -> List[Overlay]:
        """
        Rank overlays by different metrics
        
        Args:
            overlays: List of overlays
            metric: Ranking metric
                - "lift": edge × confidence (default)
                - "edge": raw edge
                - "roi": expected ROI
                - "confidence": model confidence
                - "stake": recommended stake
        
        Returns:
            Sorted list of overlays
        """
        if metric == "lift":
            key = lambda x: x.edge * x.confidence
        elif metric == "edge":
            key = lambda x: x.edge
        elif metric == "roi":
            key = lambda x: x.roi()
        elif metric == "confidence":
            key = lambda x: x.confidence
        elif metric == "stake":
            key = lambda x: x.stake_fraction
        else:
            logger.warning(f"Unknown metric '{metric}', using 'lift'")
            key = lambda x: x.edge * x.confidence
        
        return sorted(overlays, key=key, reverse=True)
    
    def filter_by_confidence(
        self,
        overlays: List[Overlay],
        min_confidence: float
    ) -> List[Overlay]:
        """
        Filter overlays by minimum confidence
        
        Args:
            overlays: List of overlays
            min_confidence: Minimum p_model - p_market
        
        Returns:
            Filtered list
        """
        return [
            overlay for overlay in overlays
            if overlay.confidence >= min_confidence
        ]
    
    def filter_by_roi(
        self,
        overlays: List[Overlay],
        min_roi: float
    ) -> List[Overlay]:
        """
        Filter overlays by minimum expected ROI
        
        Args:
            overlays: List of overlays
            min_roi: Minimum ROI percentage
        
        Returns:
            Filtered list
        """
        return [
            overlay for overlay in overlays
            if overlay.roi() >= min_roi
        ]

