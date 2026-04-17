"""
VÉLØ v10.1 - Training Metrics
==============================

Comprehensive metrics for Benter model evaluation.
Includes: AUC, Brier, LogLoss, A/E, IV, ROI@K, drawdown.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, 
    brier_score_loss, 
    log_loss,
    accuracy_score
)

logger = logging.getLogger(__name__)


class ModelMetrics:
    """
    Comprehensive metrics for model evaluation.
    
    Metrics computed:
    - AUC (Area Under ROC Curve)
    - Brier Score (calibration metric)
    - Log Loss (cross-entropy)
    - A/E (Actual vs Expected)
    - IV (Impact Value correlation)
    - ROI@K (Return on Investment at top K%)
    - Max Drawdown
    - Sharpe Ratio
    """
    
    def __init__(self):
        """Initialize metrics calculator."""
        logger.info("ModelMetrics initialized")
    
    def compute_all_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        odds: np.ndarray = None,
        race_ids: np.ndarray = None
    ) -> Dict[str, float]:
        """
        Compute all evaluation metrics.
        
        Args:
            y_true: True labels (0 or 1 for win)
            y_pred: Predicted probabilities (0-1)
            odds: Market odds (optional, for A/E and ROI)
            race_ids: Race identifiers (optional, for race-level metrics)
        
        Returns:
            Dictionary of metrics
        """
        logger.info("Computing all metrics...")
        
        metrics = {}
        
        # Classification metrics
        metrics['auc'] = self.compute_auc(y_true, y_pred)
        metrics['brier_score'] = self.compute_brier(y_true, y_pred)
        metrics['log_loss'] = self.compute_log_loss(y_true, y_pred)
        metrics['accuracy'] = accuracy_score(y_true, (y_pred > 0.5).astype(int))
        
        # Calibration metrics
        calibration = self.compute_calibration_error(y_true, y_pred)
        metrics['calibration_error'] = calibration['mean_error']
        metrics['max_calibration_error'] = calibration['max_error']
        
        # Racing-specific metrics
        if odds is not None:
            metrics['ae_ratio'] = self.compute_ae_ratio(y_true, y_pred, odds)
            metrics['roi_all'] = self.compute_roi(y_true, odds)
            metrics['roi_top10'] = self.compute_roi_at_k(y_true, y_pred, odds, k=0.10)
            metrics['roi_top20'] = self.compute_roi_at_k(y_true, y_pred, odds, k=0.20)
            metrics['roi_top30'] = self.compute_roi_at_k(y_true, y_pred, odds, k=0.30)
        
        # Risk metrics
        if odds is not None:
            drawdown_metrics = self.compute_drawdown(y_true, y_pred, odds)
            metrics['max_drawdown'] = drawdown_metrics['max_drawdown']
            metrics['sharpe_ratio'] = drawdown_metrics['sharpe_ratio']
        
        logger.info(f"Metrics computed: AUC={metrics['auc']:.4f}, Brier={metrics['brier_score']:.4f}")
        
        return metrics
    
    def compute_auc(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Compute Area Under ROC Curve.
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
        
        Returns:
            AUC score (0-1, higher is better)
        """
        try:
            auc = roc_auc_score(y_true, y_pred)
            return auc
        except Exception as e:
            logger.error(f"AUC computation failed: {e}")
            return 0.0
    
    def compute_brier(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Compute Brier Score (calibration metric).
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
        
        Returns:
            Brier score (0-1, lower is better)
        """
        try:
            brier = brier_score_loss(y_true, y_pred)
            return brier
        except Exception as e:
            logger.error(f"Brier score computation failed: {e}")
            return 1.0
    
    def compute_log_loss(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Compute Log Loss (cross-entropy).
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
        
        Returns:
            Log loss (lower is better)
        """
        try:
            # Clip predictions to avoid log(0)
            y_pred_clipped = np.clip(y_pred, 1e-15, 1 - 1e-15)
            loss = log_loss(y_true, y_pred_clipped)
            return loss
        except Exception as e:
            logger.error(f"Log loss computation failed: {e}")
            return 10.0
    
    def compute_calibration_error(
        self, 
        y_true: np.ndarray, 
        y_pred: np.ndarray,
        n_bins: int = 10
    ) -> Dict[str, float]:
        """
        Compute calibration error (Expected Calibration Error).
        
        Measures how well predicted probabilities match actual outcomes.
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
            n_bins: Number of bins for calibration curve
        
        Returns:
            Dictionary with mean_error and max_error
        """
        # Create bins
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(y_pred, bins) - 1
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)
        
        bin_errors = []
        
        for i in range(n_bins):
            mask = bin_indices == i
            if mask.sum() > 0:
                bin_pred = y_pred[mask].mean()
                bin_true = y_true[mask].mean()
                bin_error = abs(bin_pred - bin_true)
                bin_errors.append(bin_error)
        
        mean_error = np.mean(bin_errors) if bin_errors else 0.0
        max_error = np.max(bin_errors) if bin_errors else 0.0
        
        return {
            'mean_error': mean_error,
            'max_error': max_error,
            'n_bins': len(bin_errors)
        }
    
    def compute_ae_ratio(
        self, 
        y_true: np.ndarray, 
        y_pred: np.ndarray,
        odds: np.ndarray
    ) -> float:
        """
        Compute Actual vs Expected (A/E) ratio.
        
        A/E > 1.0 means model outperforms market.
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
            odds: Market odds
        
        Returns:
            A/E ratio
        """
        # Market implied probability
        market_prob = 1.0 / odds
        
        # Actual win rate
        actual = y_true.mean()
        
        # Expected win rate from market
        expected = market_prob.mean()
        
        # A/E ratio
        ae = actual / expected if expected > 0 else 0.0
        
        return ae
    
    def compute_roi(self, y_true: np.ndarray, odds: np.ndarray) -> float:
        """
        Compute Return on Investment (ROI).
        
        Args:
            y_true: True labels (1 if won)
            odds: Market odds
        
        Returns:
            ROI as percentage
        """
        # Total staked (1 unit per bet)
        total_staked = len(y_true)
        
        # Total returns (odds * stake for winners)
        total_returns = (y_true * odds).sum()
        
        # Profit
        profit = total_returns - total_staked
        
        # ROI percentage
        roi = (profit / total_staked) * 100
        
        return roi
    
    def compute_roi_at_k(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        odds: np.ndarray,
        k: float = 0.10
    ) -> float:
        """
        Compute ROI at top K% of predictions.
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
            odds: Market odds
            k: Top K fraction (e.g., 0.10 for top 10%)
        
        Returns:
            ROI for top K% selections
        """
        # Sort by predicted probability (descending)
        sorted_indices = np.argsort(y_pred)[::-1]
        
        # Select top K%
        n_select = max(1, int(len(y_pred) * k))
        top_k_indices = sorted_indices[:n_select]
        
        # Compute ROI on top K selections
        roi = self.compute_roi(y_true[top_k_indices], odds[top_k_indices])
        
        return roi
    
    def compute_drawdown(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        odds: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute maximum drawdown and Sharpe ratio.
        
        Args:
            y_true: True labels
            y_pred: Predicted probabilities
            odds: Market odds
        
        Returns:
            Dictionary with max_drawdown and sharpe_ratio
        """
        # Compute bet outcomes (profit/loss per bet)
        outcomes = np.where(y_true == 1, odds - 1, -1)
        
        # Cumulative returns
        cumulative = np.cumsum(outcomes)
        
        # Running maximum
        running_max = np.maximum.accumulate(cumulative)
        
        # Drawdown
        drawdown = running_max - cumulative
        
        # Maximum drawdown
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        # Sharpe ratio (mean return / std of returns)
        mean_return = np.mean(outcomes)
        std_return = np.std(outcomes)
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
        
        return {
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'mean_return': mean_return,
            'std_return': std_return
        }
    
    def print_metrics_report(self, metrics: Dict[str, float]):
        """
        Print formatted metrics report.
        
        Args:
            metrics: Dictionary of metrics
        """
        print("\n" + "="*60)
        print("MODEL EVALUATION METRICS")
        print("="*60)
        
        print("\n📊 Classification Metrics:")
        print(f"  AUC:              {metrics.get('auc', 0):.4f}")
        print(f"  Brier Score:      {metrics.get('brier_score', 0):.4f}")
        print(f"  Log Loss:         {metrics.get('log_loss', 0):.4f}")
        print(f"  Accuracy:         {metrics.get('accuracy', 0):.4f}")
        
        print("\n🎯 Calibration Metrics:")
        print(f"  Calibration Error: {metrics.get('calibration_error', 0):.4f}")
        print(f"  Max Cal Error:     {metrics.get('max_calibration_error', 0):.4f}")
        
        if 'ae_ratio' in metrics:
            print("\n🏇 Racing Metrics:")
            print(f"  A/E Ratio:        {metrics.get('ae_ratio', 0):.4f}")
            print(f"  ROI (All):        {metrics.get('roi_all', 0):.2f}%")
            print(f"  ROI (Top 10%):    {metrics.get('roi_top10', 0):.2f}%")
            print(f"  ROI (Top 20%):    {metrics.get('roi_top20', 0):.2f}%")
            print(f"  ROI (Top 30%):    {metrics.get('roi_top30', 0):.2f}%")
        
        if 'max_drawdown' in metrics:
            print("\n⚠️  Risk Metrics:")
            print(f"  Max Drawdown:     {metrics.get('max_drawdown', 0):.2f} units")
            print(f"  Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):.4f}")
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    # Test metrics
    logging.basicConfig(level=logging.INFO)
    
    # Create sample data
    np.random.seed(42)
    n_samples = 1000
    
    y_true = np.random.binomial(1, 0.15, n_samples)  # 15% win rate
    y_pred = np.random.beta(2, 10, n_samples)  # Predicted probabilities
    odds = np.random.uniform(3.0, 20.0, n_samples)  # Market odds
    
    metrics_calc = ModelMetrics()
    metrics = metrics_calc.compute_all_metrics(y_true, y_pred, odds)
    
    metrics_calc.print_metrics_report(metrics)
