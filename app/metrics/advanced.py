"""
VÉLØ Oracle - Advanced Metrics
Advanced performance and calibration metrics
"""
import numpy as np
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calibration_error(
    y_true: List[float],
    y_pred: List[float],
    n_bins: int = 10
) -> float:
    """
    Calculate Expected Calibration Error (ECE)
    
    Args:
        y_true: True labels (0 or 1)
        y_pred: Predicted probabilities
        n_bins: Number of bins for calibration
        
    Returns:
        Calibration error (0-1, lower is better)
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # Create bins
    bins = np.linspace(0, 1, n_bins + 1)
    
    ece = 0.0
    
    for i in range(n_bins):
        # Find predictions in this bin
        bin_mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
        
        if np.sum(bin_mask) > 0:
            # Average predicted probability in bin
            bin_pred = np.mean(y_pred[bin_mask])
            
            # Actual frequency in bin
            bin_true = np.mean(y_true[bin_mask])
            
            # Weighted contribution to ECE
            bin_weight = np.sum(bin_mask) / len(y_pred)
            ece += bin_weight * abs(bin_pred - bin_true)
    
    return ece


def probability_sharpness(y_pred: List[float]) -> float:
    """
    Calculate probability sharpness (confidence)
    
    Measures how confident predictions are (distance from 0.5)
    
    Args:
        y_pred: Predicted probabilities
        
    Returns:
        Sharpness score (0-1, higher is sharper/more confident)
    """
    y_pred = np.array(y_pred)
    
    # Distance from 0.5 (indecision)
    distances = np.abs(y_pred - 0.5)
    
    # Average distance, scaled to 0-1
    sharpness = np.mean(distances) * 2
    
    return sharpness


def brier_score(y_true: List[float], y_pred: List[float]) -> float:
    """
    Calculate Brier score
    
    Measures accuracy of probabilistic predictions
    
    Args:
        y_true: True labels (0 or 1)
        y_pred: Predicted probabilities
        
    Returns:
        Brier score (0-1, lower is better)
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    return np.mean((y_pred - y_true) ** 2)


def edge_consistency(
    edges: List[float],
    outcomes: List[int]
) -> float:
    """
    Calculate edge consistency score
    
    Measures how consistently positive edges lead to wins
    
    Args:
        edges: List of edge values
        outcomes: List of outcomes (1=win, 0=loss)
        
    Returns:
        Consistency score (0-1, higher is better)
    """
    edges = np.array(edges)
    outcomes = np.array(outcomes)
    
    # Filter to positive edges only
    positive_mask = edges > 0
    
    if np.sum(positive_mask) == 0:
        return 0.0
    
    positive_edges = edges[positive_mask]
    positive_outcomes = outcomes[positive_mask]
    
    # Win rate for positive edges
    win_rate = np.mean(positive_outcomes)
    
    # Correlation between edge magnitude and outcome
    if len(positive_edges) > 1:
        correlation = np.corrcoef(positive_edges, positive_outcomes)[0, 1]
        correlation = max(0, correlation)  # Clip negative correlations to 0
    else:
        correlation = 0.0
    
    # Combine win rate and correlation
    consistency = (win_rate * 0.7) + (correlation * 0.3)
    
    return consistency


def market_alignment_score(
    model_probs: List[float],
    market_probs: List[float]
) -> float:
    """
    Calculate market alignment score
    
    Measures how aligned model is with market
    
    Args:
        model_probs: Model probabilities
        market_probs: Market implied probabilities
        
    Returns:
        Alignment score (0-1, higher = more aligned)
    """
    model_probs = np.array(model_probs)
    market_probs = np.array(market_probs)
    
    # Calculate correlation
    if len(model_probs) > 1:
        correlation = np.corrcoef(model_probs, market_probs)[0, 1]
        correlation = max(0, min(correlation, 1))  # Clip to [0, 1]
    else:
        correlation = 0.5
    
    # Calculate average absolute difference
    avg_diff = np.mean(np.abs(model_probs - market_probs))
    
    # Alignment score (high correlation, low difference)
    alignment = (correlation * 0.6) + ((1 - avg_diff) * 0.4)
    
    return alignment


def signal_redundancy_index(
    signals: Dict[str, List[float]]
) -> float:
    """
    Calculate signal redundancy index
    
    Measures how redundant/correlated different signals are
    
    Args:
        signals: Dictionary of signal names to signal values
        
    Returns:
        Redundancy index (0-1, higher = more redundant)
    """
    if len(signals) < 2:
        return 0.0
    
    signal_arrays = [np.array(values) for values in signals.values()]
    
    # Calculate pairwise correlations
    correlations = []
    
    for i in range(len(signal_arrays)):
        for j in range(i + 1, len(signal_arrays)):
            if len(signal_arrays[i]) > 1:
                corr = np.corrcoef(signal_arrays[i], signal_arrays[j])[0, 1]
                correlations.append(abs(corr))  # Use absolute correlation
    
    if not correlations:
        return 0.0
    
    # Average absolute correlation
    redundancy = np.mean(correlations)
    
    return redundancy


def calculate_all_advanced_metrics(
    y_true: List[float],
    y_pred: List[float],
    edges: List[float] = None,
    market_probs: List[float] = None,
    signals: Dict[str, List[float]] = None
) -> Dict[str, float]:
    """
    Calculate all advanced metrics
    
    Args:
        y_true: True labels
        y_pred: Predicted probabilities
        edges: Optional edge values
        market_probs: Optional market probabilities
        signals: Optional signal dictionary
        
    Returns:
        Dictionary of all metrics
    """
    metrics = {
        "calibration_error": calibration_error(y_true, y_pred),
        "probability_sharpness": probability_sharpness(y_pred),
        "brier_score": brier_score(y_true, y_pred)
    }
    
    if edges is not None:
        metrics["edge_consistency"] = edge_consistency(edges, y_true)
    
    if market_probs is not None:
        metrics["market_alignment"] = market_alignment_score(y_pred, market_probs)
    
    if signals is not None:
        metrics["signal_redundancy"] = signal_redundancy_index(signals)
    
    return metrics
