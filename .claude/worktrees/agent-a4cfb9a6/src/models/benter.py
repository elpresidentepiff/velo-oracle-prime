"""
VÉLØ v10 - Production Benter Model
Clean implementation of Bill Benter's fundamental × public model combiner

Based on:
- "Computer Based Horse Race Handicapping and Wagering Systems" (1994)
- Annotated Benter Paper (Acta Machina, 2024)
- Hong Kong Jockey Club data (1979-2023)

The Benter model combines:
1. Fundamental model (form, ratings, connections) → p_fundamental
2. Public odds model (market wisdom) → p_public
3. Weighted combination → p_model = α × p_fundamental + β × p_public

Typical weights: α=0.9, β=1.1
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

from ..modules.contracts import Runner, Racecard, Odds
from ..core.settings import settings

logger = logging.getLogger("velo.benter")


class BenterModel:
    """
    Production Benter model for probability estimation
    
    Combines fundamental analysis with public odds to produce
    superior probability estimates
    """
    
    def __init__(self, alpha: float = None, beta: float = None):
        """
        Initialize Benter model
        
        Args:
            alpha: Weight for fundamental model (default from settings)
            beta: Weight for public odds model (default from settings)
        """
        self.alpha = alpha if alpha is not None else settings.ALPHA
        self.beta = beta if beta is not None else settings.BETA
        
        logger.info(f"BenterModel initialized (α={self.alpha}, β={self.beta})")
    
    def estimate_fundamental(self, runner: Runner, racecard: Racecard) -> float:
        """
        Estimate win probability from fundamental factors
        
        Uses:
        - Official Rating (OR)
        - Timeform Speed Figure (TS)
        - Racing Post Rating (RPR)
        - Jockey/Trainer strike rates
        - Recent form
        
        Args:
            runner: Runner to analyze
            racecard: Full racecard for context
        
        Returns:
            Fundamental win probability (0.0-1.0)
        """
        # Collect rating features
        features = []
        
        # Official Rating (normalized)
        if runner.or_rating:
            features.append(runner.or_rating / 100.0)
        
        # Timeform Speed Figure (normalized)
        if runner.ts:
            features.append(runner.ts / 100.0)
        
        # Racing Post Rating (normalized)
        if runner.rpr:
            features.append(runner.rpr / 100.0)
        
        # Jockey strike rate (5-year)
        if runner.jockey_sr5y:
            features.append(runner.jockey_sr5y)
        
        # Trainer strike rate (5-year)
        if runner.trainer_sr5y:
            features.append(runner.trainer_sr5y)
        
        # Form score (wins in last 6 runs)
        if runner.last6:
            wins = sum(1 for pos in runner.last6 if pos == '1')
            form_score = wins / len(runner.last6)
            features.append(form_score)
        
        # If no features available, return uniform probability
        if not features:
            return 1.0 / racecard.num_runners if racecard.num_runners else 0.0
        
        # Simple linear combination (can be replaced with trained model)
        raw_score = np.mean(features)
        
        # Convert to probability (logistic transform)
        # This ensures output is in (0, 1)
        p_fundamental = 1.0 / (1.0 + np.exp(-5.0 * (raw_score - 0.5)))
        
        return p_fundamental
    
    def estimate_public(self, odds: Odds) -> float:
        """
        Estimate win probability from public odds (market wisdom)
        
        Uses Betfair odds if available, otherwise bookmaker odds
        
        Args:
            odds: Odds object for runner
        
        Returns:
            Public (market-implied) win probability (0.0-1.0)
        """
        # Prefer Betfair odds (more efficient market)
        if odds.bf_win and odds.bf_win > 0:
            return 1.0 / odds.bf_win
        
        # Fallback to bookmaker win odds
        if odds.win and odds.win > 0:
            return 1.0 / odds.win
        
        # No odds available
        return 0.0
    
    def combine(
        self,
        p_fundamental: float,
        p_public: float,
        normalize: bool = True
    ) -> float:
        """
        Combine fundamental and public probabilities using Benter weights
        
        p_model = α × p_fundamental + β × p_public
        
        Args:
            p_fundamental: Fundamental probability
            p_public: Public (market) probability
            normalize: Whether to normalize to ensure sum = 1.0
        
        Returns:
            Combined probability
        """
        p_combined = self.alpha * p_fundamental + self.beta * p_public
        
        # Ensure probability is in valid range
        p_combined = max(0.0, min(1.0, p_combined))
        
        return p_combined
    
    def estimate_race(
        self,
        racecard: Racecard,
        odds_book: Dict[str, Odds]
    ) -> Dict[str, float]:
        """
        Estimate win probabilities for all runners in a race
        
        Args:
            racecard: Complete racecard
            odds_book: Current odds for all runners
        
        Returns:
            Dict mapping runner name to win probability
        """
        probabilities = {}
        
        for runner in racecard.runners:
            # Get odds for this runner
            odds = odds_book.get(runner.name)
            
            if not odds:
                logger.warning(f"No odds for {runner.name}, skipping")
                continue
            
            # Estimate fundamental probability
            p_fundamental = self.estimate_fundamental(runner, racecard)
            
            # Estimate public probability
            p_public = self.estimate_public(odds)
            
            # Combine using Benter weights
            p_model = self.combine(p_fundamental, p_public, normalize=False)
            
            probabilities[runner.name] = p_model
        
        # Normalize probabilities to sum to 1.0
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {
                name: prob / total
                for name, prob in probabilities.items()
            }
        
        return probabilities
    
    def calibrate(
        self,
        historical_races: List[Tuple[Racecard, Dict[str, Odds], str]],
        alpha_range: Tuple[float, float] = (0.5, 1.5),
        beta_range: Tuple[float, float] = (0.5, 1.5),
        steps: int = 10
    ) -> Tuple[float, float]:
        """
        Calibrate α and β weights using historical data
        
        Finds weights that minimize log loss on historical results
        
        Args:
            historical_races: List of (racecard, odds_book, winner_name) tuples
            alpha_range: Range of α values to search
            beta_range: Range of β values to search
            steps: Number of steps in grid search
        
        Returns:
            Tuple of (best_alpha, best_beta)
        """
        logger.info(f"Calibrating Benter model on {len(historical_races)} races")
        
        best_alpha = self.alpha
        best_beta = self.beta
        best_loss = float('inf')
        
        alphas = np.linspace(alpha_range[0], alpha_range[1], steps)
        betas = np.linspace(beta_range[0], beta_range[1], steps)
        
        for alpha in alphas:
            for beta in betas:
                # Temporarily set weights
                self.alpha = alpha
                self.beta = beta
                
                # Calculate log loss
                total_loss = 0.0
                count = 0
                
                for racecard, odds_book, winner in historical_races:
                    probs = self.estimate_race(racecard, odds_book)
                    
                    if winner in probs:
                        p_winner = probs[winner]
                        # Log loss for this race
                        loss = -np.log(max(p_winner, 1e-10))
                        total_loss += loss
                        count += 1
                
                avg_loss = total_loss / count if count > 0 else float('inf')
                
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    best_alpha = alpha
                    best_beta = beta
        
        # Set best weights
        self.alpha = best_alpha
        self.beta = best_beta
        
        logger.info(f"Calibration complete: α={best_alpha:.2f}, β={best_beta:.2f}, loss={best_loss:.4f}")
        
        return best_alpha, best_beta

