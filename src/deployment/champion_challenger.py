"""
VÉLØ Oracle - Champion/Challenger Deployment Framework

This module implements a production-safe deployment pattern where:
- Champion: Current production model (serves 100% of live bets)
- Challengers: Alternative models (shadow mode - predictions logged but not executed)

Based on research from DataRobot MLOps and industry best practices.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """Represents a single model prediction."""
    model_name: str
    race_id: str
    horse_name: str
    predicted_probability: float
    recommended_bet: bool
    stake: float
    odds: float
    timestamp: str
    metadata: Dict[str, Any]


@dataclass
class BetResult:
    """Represents the outcome of a bet."""
    prediction: Prediction
    actual_result: str  # 'win', 'place', 'lose'
    profit_loss: float
    roi: float


class ModelInterface:
    """Abstract interface that all models (Champion and Challengers) must implement."""
    
    def __init__(self, name: str):
        self.name = name
        self.predictions_made = 0
        self.total_roi = 0.0
        self.total_profit = 0.0
        
    def predict(self, race_data: pd.DataFrame) -> List[Prediction]:
        """
        Make predictions for a race.
        
        Args:
            race_data: DataFrame containing race information
            
        Returns:
            List of Prediction objects
        """
        raise NotImplementedError("Subclasses must implement predict()")
    
    def get_stats(self) -> Dict[str, float]:
        """Return current performance statistics."""
        return {
            'predictions_made': self.predictions_made,
            'total_roi': self.total_roi,
            'total_profit': self.total_profit,
            'avg_roi': self.total_roi / max(1, self.predictions_made)
        }


class ChampionChallengerFramework:
    """
    Manages Champion/Challenger deployment pattern.
    
    The champion model serves all production traffic.
    Challenger models run in shadow mode for performance comparison.
    """
    
    def __init__(
        self,
        champion: ModelInterface,
        challengers: List[ModelInterface],
        results_dir: str = "/home/ubuntu/velo-oracle/results/champion_challenger"
    ):
        """
        Initialize the Champion/Challenger framework.
        
        Args:
            champion: The current production model
            challengers: List of alternative models to evaluate (max 3 recommended)
            results_dir: Directory to store prediction logs and performance data
        """
        self.champion = champion
        self.challengers = challengers
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self.champion_predictions = []
        self.challenger_predictions = {c.name: [] for c in challengers}
        self.results = []
        
        logger.info(f"Champion/Challenger Framework initialized")
        logger.info(f"Champion: {champion.name}")
        logger.info(f"Challengers: {[c.name for c in challengers]}")
    
    def predict(self, race_data: pd.DataFrame, race_id: str) -> List[Prediction]:
        """
        Generate predictions from champion and all challengers.
        
        Only champion predictions are returned for live execution.
        Challenger predictions are logged for analysis.
        
        Args:
            race_data: DataFrame containing race information
            race_id: Unique identifier for the race
            
        Returns:
            List of champion predictions (for live execution)
        """
        logger.info(f"Processing race {race_id}")
        
        # Champion makes predictions (LIVE)
        champion_preds = self.champion.predict(race_data)
        self.champion_predictions.extend(champion_preds)
        logger.info(f"Champion ({self.champion.name}) made {len(champion_preds)} predictions")
        
        # Challengers make predictions (SHADOW MODE)
        for challenger in self.challengers:
            try:
                challenger_preds = challenger.predict(race_data)
                self.challenger_predictions[challenger.name].extend(challenger_preds)
                logger.info(f"Challenger ({challenger.name}) made {len(challenger_preds)} predictions (shadow)")
            except Exception as e:
                logger.error(f"Challenger {challenger.name} failed: {e}")
        
        # Save predictions to disk
        self._save_predictions(race_id)
        
        # Return only champion predictions for live execution
        return champion_preds
    
    def record_result(self, race_id: str, results: Dict[str, str]):
        """
        Record actual race results and calculate performance metrics.
        
        Args:
            race_id: Unique identifier for the race
            results: Dict mapping horse names to results ('win', 'place', 'lose')
        """
        logger.info(f"Recording results for race {race_id}")
        
        # Evaluate champion predictions
        champion_race_preds = [p for p in self.champion_predictions if p.race_id == race_id]
        for pred in champion_race_preds:
            actual = results.get(pred.horse_name, 'lose')
            profit_loss = self._calculate_profit_loss(pred, actual)
            roi = profit_loss / pred.stake if pred.stake > 0 else 0.0
            
            bet_result = BetResult(
                prediction=pred,
                actual_result=actual,
                profit_loss=profit_loss,
                roi=roi
            )
            self.results.append(bet_result)
            
            # Update champion stats
            self.champion.predictions_made += 1
            self.champion.total_profit += profit_loss
            self.champion.total_roi += roi
        
        # Evaluate challenger predictions (shadow)
        for challenger in self.challengers:
            challenger_race_preds = [
                p for p in self.challenger_predictions[challenger.name] 
                if p.race_id == race_id
            ]
            for pred in challenger_race_preds:
                actual = results.get(pred.horse_name, 'lose')
                profit_loss = self._calculate_profit_loss(pred, actual)
                roi = profit_loss / pred.stake if pred.stake > 0 else 0.0
                
                # Update challenger stats
                challenger.predictions_made += 1
                challenger.total_profit += profit_loss
                challenger.total_roi += roi
        
        # Save updated results
        self._save_results()
    
    def _calculate_profit_loss(self, pred: Prediction, actual: str) -> float:
        """Calculate profit/loss for a prediction."""
        if not pred.recommended_bet:
            return 0.0
        
        if actual == 'win':
            return pred.stake * (pred.odds - 1)  # Profit
        else:
            return -pred.stake  # Loss
    
    def _save_predictions(self, race_id: str):
        """Save predictions to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.results_dir / f"predictions_{race_id}_{timestamp}.json"
        
        data = {
            'race_id': race_id,
            'timestamp': timestamp,
            'champion': {
                'name': self.champion.name,
                'predictions': [asdict(p) for p in self.champion_predictions if p.race_id == race_id]
            },
            'challengers': {
                c.name: [asdict(p) for p in self.challenger_predictions[c.name] if p.race_id == race_id]
                for c in self.challengers
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_results(self):
        """Save all results to JSON file."""
        filepath = self.results_dir / "all_results.json"
        
        data = {
            'champion': {
                'name': self.champion.name,
                'stats': self.champion.get_stats(),
                'results': [asdict(r) for r in self.results]
            },
            'challengers': {
                c.name: {
                    'stats': c.get_stats()
                }
                for c in self.challengers
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_comparison_report(self) -> pd.DataFrame:
        """
        Generate a comparison report of champion vs challengers.
        
        Returns:
            DataFrame with performance metrics for all models
        """
        models_data = []
        
        # Champion stats
        champion_stats = self.champion.get_stats()
        champion_stats['model'] = self.champion.name
        champion_stats['role'] = 'Champion (LIVE)'
        models_data.append(champion_stats)
        
        # Challenger stats
        for challenger in self.challengers:
            challenger_stats = challenger.get_stats()
            challenger_stats['model'] = challenger.name
            challenger_stats['role'] = 'Challenger (Shadow)'
            models_data.append(challenger_stats)
        
        df = pd.DataFrame(models_data)
        
        # Calculate additional metrics
        if len(df) > 0:
            df['sharpe_ratio'] = df.apply(self._calculate_sharpe, axis=1)
            df['win_rate'] = df['predictions_made'].apply(lambda x: 0.0)  # Placeholder
        
        # Sort by average ROI
        df = df.sort_values('avg_roi', ascending=False)
        
        # Save report
        report_path = self.results_dir / "performance_comparison.csv"
        df.to_csv(report_path, index=False)
        logger.info(f"Comparison report saved to {report_path}")
        
        return df
    
    def _calculate_sharpe(self, row: pd.Series) -> float:
        """Calculate Sharpe ratio for a model (placeholder)."""
        # TODO: Implement proper Sharpe ratio calculation
        return 0.0
    
    def should_promote_challenger(self, min_predictions: int = 100, min_roi_improvement: float = 0.05) -> Optional[str]:
        """
        Determine if a challenger should be promoted to champion.
        
        Args:
            min_predictions: Minimum number of predictions required for promotion
            min_roi_improvement: Minimum ROI improvement required (e.g., 0.05 = 5%)
            
        Returns:
            Name of challenger to promote, or None
        """
        champion_stats = self.champion.get_stats()
        champion_roi = champion_stats['avg_roi']
        
        best_challenger = None
        best_roi = champion_roi
        
        for challenger in self.challengers:
            stats = challenger.get_stats()
            
            # Check if challenger has enough predictions
            if stats['predictions_made'] < min_predictions:
                continue
            
            # Check if challenger beats champion by required margin
            if stats['avg_roi'] > best_roi + min_roi_improvement:
                best_challenger = challenger.name
                best_roi = stats['avg_roi']
        
        if best_challenger:
            improvement = ((best_roi - champion_roi) / abs(champion_roi)) * 100
            logger.info(f"Challenger {best_challenger} recommended for promotion")
            logger.info(f"ROI improvement: {improvement:.2f}%")
        
        return best_challenger
    
    def promote_challenger(self, challenger_name: str):
        """
        Promote a challenger to champion status.
        
        This is a manual operation that requires approval.
        
        Args:
            challenger_name: Name of the challenger to promote
        """
        # Find the challenger
        challenger = next((c for c in self.challengers if c.name == challenger_name), None)
        
        if not challenger:
            raise ValueError(f"Challenger {challenger_name} not found")
        
        logger.warning(f"PROMOTION: {challenger_name} -> Champion")
        logger.warning(f"Previous champion: {self.champion.name} -> Demoted to challenger")
        
        # Swap champion and challenger
        old_champion = self.champion
        self.champion = challenger
        self.challengers = [c for c in self.challengers if c.name != challenger_name]
        self.challengers.append(old_champion)
        
        # Log the promotion
        promotion_log = {
            'timestamp': datetime.now().isoformat(),
            'new_champion': challenger_name,
            'old_champion': old_champion.name,
            'reason': 'Manual promotion based on performance'
        }
        
        log_path = self.results_dir / "promotion_log.json"
        with open(log_path, 'a') as f:
            f.write(json.dumps(promotion_log) + '\n')
        
        logger.info("Promotion complete")

