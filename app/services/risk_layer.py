"""
VÉLØ Oracle - Risk Layer
Edge calculation and risk classification for betting decisions
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# Risk thresholds
EDGE_THRESHOLDS = {
    "NO_BET": 0.0,      # No edge or negative edge
    "LOW": 0.03,        # 3% edge minimum
    "MEDIUM": 0.08,     # 8% edge
    "HIGH": 0.15        # 15%+ edge
}


def compute_edge(model_prob: float, market_odds: float) -> float:
    """
    Compute betting edge (model probability vs market implied probability)
    
    Args:
        model_prob: Model's win probability [0, 1]
        market_odds: Market odds (decimal format, e.g., 5.0)
        
    Returns:
        Edge value (positive = overlay, negative = underlay)
        
    Example:
        >>> compute_edge(0.25, 5.0)  # Model: 25%, Market: 20%
        0.05  # 5% edge
    """
    if market_odds <= 0:
        logger.warning(f"Invalid market odds: {market_odds}")
        return 0.0
    
    # Market implied probability
    market_prob = 1.0 / market_odds
    
    # Edge = model probability - market probability
    edge = model_prob - market_prob
    
    return edge


def classify_risk(edge: float) -> str:
    """
    Classify risk band based on edge
    
    Args:
        edge: Betting edge value
        
    Returns:
        Risk classification: NO_BET | LOW | MEDIUM | HIGH
        
    Risk Bands:
        - NO_BET: edge < 0% (no edge or negative)
        - LOW: 3% <= edge < 8%
        - MEDIUM: 8% <= edge < 15%
        - HIGH: edge >= 15%
    """
    if edge < EDGE_THRESHOLDS["NO_BET"]:
        return "NO_BET"
    elif edge < EDGE_THRESHOLDS["LOW"]:
        return "NO_BET"  # Below minimum threshold
    elif edge < EDGE_THRESHOLDS["MEDIUM"]:
        return "LOW"
    elif edge < EDGE_THRESHOLDS["HIGH"]:
        return "MEDIUM"
    else:
        return "HIGH"


def compute_kelly_stake(
    edge: float,
    odds: float,
    kelly_fraction: float = 0.25
) -> float:
    """
    Compute Kelly Criterion stake size
    
    Args:
        edge: Betting edge
        odds: Decimal odds
        kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
        
    Returns:
        Stake size as fraction of bankroll [0, 1]
    """
    if edge <= 0 or odds <= 1.0:
        return 0.0
    
    # Kelly formula: f = (bp - q) / b
    # where b = odds - 1, p = model prob, q = 1 - p
    b = odds - 1.0
    model_prob = edge + (1.0 / odds)  # Reverse calculate model prob
    
    kelly = (b * model_prob - (1 - model_prob)) / b
    
    # Apply fraction and clip to reasonable range
    stake = max(0.0, min(kelly * kelly_fraction, 0.20))  # Max 20% of bankroll
    
    return stake


def calculate_risk_metrics(
    model_prob: float,
    market_odds: float,
    confidence: float = 0.75,
    kelly_fraction: float = 0.25
) -> Dict[str, Any]:
    """
    Calculate comprehensive risk metrics
    
    Args:
        model_prob: Model win probability
        market_odds: Market odds
        confidence: Model confidence level
        kelly_fraction: Kelly fraction to use
        
    Returns:
        Dictionary with edge, risk_band, kelly_stake, and other metrics
    """
    edge = compute_edge(model_prob, market_odds)
    risk_band = classify_risk(edge)
    kelly_stake = compute_kelly_stake(edge, market_odds, kelly_fraction)
    
    market_prob = 1.0 / market_odds if market_odds > 0 else 0.0
    
    # Expected value
    ev = (model_prob * market_odds) - 1.0
    
    # Confidence-adjusted edge
    adjusted_edge = edge * confidence
    
    return {
        "edge": edge,
        "risk_band": risk_band,
        "kelly_stake": kelly_stake,
        "expected_value": ev,
        "adjusted_edge": adjusted_edge,
        "model_probability": model_prob,
        "market_probability": market_prob,
        "confidence": confidence,
        "should_bet": risk_band != "NO_BET"
    }


def evaluate_betting_opportunity(
    runner: Dict[str, Any],
    model_prob: float,
    confidence: float = 0.75
) -> Dict[str, Any]:
    """
    Evaluate complete betting opportunity for a runner
    
    Args:
        runner: Runner data dictionary with odds
        model_prob: Model probability
        confidence: Model confidence
        
    Returns:
        Complete risk evaluation
    """
    market_odds = runner.get("odds", 5.0)
    
    risk_metrics = calculate_risk_metrics(
        model_prob=model_prob,
        market_odds=market_odds,
        confidence=confidence
    )
    
    # Add runner context
    risk_metrics["runner_name"] = runner.get("horse", "Unknown")
    risk_metrics["market_odds"] = market_odds
    
    # Recommendation
    if risk_metrics["risk_band"] == "HIGH":
        risk_metrics["recommendation"] = "STRONG BET"
    elif risk_metrics["risk_band"] == "MEDIUM":
        risk_metrics["recommendation"] = "MODERATE BET"
    elif risk_metrics["risk_band"] == "LOW":
        risk_metrics["recommendation"] = "SMALL BET"
    else:
        risk_metrics["recommendation"] = "PASS"
    
    return risk_metrics


def batch_risk_evaluation(
    runners: list,
    model_probs: list,
    confidence: float = 0.75
) -> list:
    """
    Evaluate risk for multiple runners
    
    Args:
        runners: List of runner dictionaries
        model_probs: List of model probabilities
        confidence: Model confidence
        
    Returns:
        List of risk evaluations
    """
    evaluations = []
    
    for runner, prob in zip(runners, model_probs):
        eval_result = evaluate_betting_opportunity(runner, prob, confidence)
        evaluations.append(eval_result)
    
    return evaluations


def get_risk_thresholds() -> Dict[str, float]:
    """Get current risk thresholds"""
    return EDGE_THRESHOLDS.copy()


def set_risk_thresholds(
    no_bet: float = None,
    low: float = None,
    medium: float = None,
    high: float = None
) -> None:
    """
    Update risk thresholds (use with caution)
    
    Args:
        no_bet: Minimum edge for any bet
        low: Threshold for low risk
        medium: Threshold for medium risk
        high: Threshold for high risk
    """
    global EDGE_THRESHOLDS
    
    if no_bet is not None:
        EDGE_THRESHOLDS["NO_BET"] = no_bet
    if low is not None:
        EDGE_THRESHOLDS["LOW"] = low
    if medium is not None:
        EDGE_THRESHOLDS["MEDIUM"] = medium
    if high is not None:
        EDGE_THRESHOLDS["HIGH"] = high
    
    logger.info(f"Risk thresholds updated: {EDGE_THRESHOLDS}")
