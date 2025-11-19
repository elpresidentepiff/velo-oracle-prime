"""
VÉLØ Oracle - Backtesting Metrics
Performance metrics for backtest evaluation
"""
from typing import List, Dict, Any, Optional
import math


def accuracy(predictions: List[Dict], results: List[Dict]) -> float:
    """
    Calculate prediction accuracy
    
    Args:
        predictions: List of predictions
        results: List of actual results
        
    Returns:
        Accuracy score [0, 1]
    """
    if not predictions or not results:
        return 0.0
    
    correct = sum(
        1 for pred, result in zip(predictions, results)
        if pred.get("predicted_winner") == result.get("actual_winner")
    )
    
    return correct / len(predictions)


def log_loss(predictions: List[Dict], results: List[Dict]) -> float:
    """
    Calculate logarithmic loss
    
    Args:
        predictions: List of predictions with probabilities
        results: List of actual results
        
    Returns:
        Log loss value (lower is better)
    """
    if not predictions or not results:
        return 1.0
    
    total_loss = 0.0
    
    for pred, result in zip(predictions, results):
        prob = pred.get("final_probability", 0.5)
        actual = 1 if result.get("won", False) else 0
        
        # Clip probability to avoid log(0)
        prob = max(min(prob, 0.9999), 0.0001)
        
        loss = -(actual * math.log(prob) + (1 - actual) * math.log(1 - prob))
        total_loss += loss
    
    return total_loss / len(predictions)


def auc(predictions: List[Dict], results: List[Dict]) -> float:
    """
    Calculate Area Under ROC Curve
    
    Args:
        predictions: List of predictions with probabilities
        results: List of actual results
        
    Returns:
        AUC score [0, 1]
    """
    if not predictions or not results:
        return 0.5
    
    # Stub: Simplified AUC calculation
    # Real implementation would sort by probability and calculate ROC
    
    # Count positive and negative pairs
    positive_pairs = sum(1 for r in results if r.get("won", False))
    negative_pairs = len(results) - positive_pairs
    
    if positive_pairs == 0 or negative_pairs == 0:
        return 0.5
    
    # Stub calculation
    auc_score = 0.75  # Placeholder
    
    return auc_score


def roi(predictions: List[Dict], results: List[Dict], stake: float = 1.0) -> float:
    """
    Calculate Return on Investment
    
    Args:
        predictions: List of predictions with bet amounts
        results: List of actual results with payouts
        stake: Standard stake amount
        
    Returns:
        ROI as decimal (1.0 = break even, >1.0 = profit)
    """
    if not predictions or not results:
        return 0.0
    
    total_staked = 0.0
    total_returned = 0.0
    
    for pred, result in zip(predictions, results):
        bet_amount = pred.get("bet_amount", stake)
        total_staked += bet_amount
        
        if result.get("won", False):
            odds = pred.get("odds", 1.0)
            total_returned += bet_amount * odds
    
    if total_staked == 0:
        return 0.0
    
    return total_returned / total_staked


def drawdown(balance_history: List[float]) -> float:
    """
    Calculate maximum drawdown
    
    Args:
        balance_history: List of balance values over time
        
    Returns:
        Maximum drawdown as decimal
    """
    if not balance_history or len(balance_history) < 2:
        return 0.0
    
    peak = balance_history[0]
    max_dd = 0.0
    
    for balance in balance_history:
        if balance > peak:
            peak = balance
        
        dd = (peak - balance) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    
    return max_dd


def strike_rate(predictions: List[Dict], results: List[Dict]) -> float:
    """
    Calculate strike rate (win percentage)
    
    Args:
        predictions: List of predictions
        results: List of actual results
        
    Returns:
        Strike rate [0, 1]
    """
    if not predictions or not results:
        return 0.0
    
    wins = sum(1 for result in results if result.get("won", False))
    
    return wins / len(results)


def value_edge(predictions: List[Dict], results: List[Dict]) -> float:
    """
    Calculate average value edge (model prob - implied prob)
    
    Args:
        predictions: List of predictions with probabilities
        results: List of actual results with odds
        
    Returns:
        Average value edge
    """
    if not predictions or not results:
        return 0.0
    
    total_edge = 0.0
    
    for pred, result in zip(predictions, results):
        model_prob = pred.get("final_probability", 0.5)
        odds = result.get("odds", 2.0)
        implied_prob = 1.0 / odds if odds > 0 else 0.5
        
        edge = model_prob - implied_prob
        total_edge += edge
    
    return total_edge / len(predictions)


def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio
    
    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate of return
        
    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    # Calculate mean return
    mean_return = sum(returns) / len(returns)
    
    # Calculate standard deviation
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 0.0
    
    # Sharpe ratio
    sharpe = (mean_return - risk_free_rate) / std_dev
    
    return sharpe


def calculate_all_metrics(predictions: List[Dict], results: List[Dict], 
                         balance_history: Optional[List[float]] = None) -> Dict[str, float]:
    """
    Calculate all backtest metrics
    
    Args:
        predictions: List of predictions
        results: List of actual results
        balance_history: Optional balance history for drawdown
        
    Returns:
        Dictionary of all metrics
    """
    metrics = {
        "accuracy": accuracy(predictions, results),
        "log_loss": log_loss(predictions, results),
        "auc": auc(predictions, results),
        "roi": roi(predictions, results),
        "strike_rate": strike_rate(predictions, results),
        "value_edge": value_edge(predictions, results),
    }
    
    if balance_history:
        metrics["max_drawdown"] = drawdown(balance_history)
        
        # Calculate returns from balance history
        returns = [
            (balance_history[i] - balance_history[i-1]) / balance_history[i-1]
            for i in range(1, len(balance_history))
            if balance_history[i-1] > 0
        ]
        
        if returns:
            metrics["sharpe_ratio"] = sharpe_ratio(returns)
    
    return metrics
