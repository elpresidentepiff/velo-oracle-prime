"""
VÉLØ Oracle - Backtesting Package
Complete backtesting framework for model validation
"""
from .engine import BacktestEngine, create_backtest
from .metrics import (
    accuracy,
    log_loss,
    auc,
    roi,
    drawdown,
    strike_rate,
    value_edge,
    sharpe_ratio,
    calculate_all_metrics
)
from .runner import BacktestRunner, run_backtest, run_quick_backtest

__all__ = [
    # Engine
    "BacktestEngine",
    "create_backtest",
    
    # Metrics
    "accuracy",
    "log_loss",
    "auc",
    "roi",
    "drawdown",
    "strike_rate",
    "value_edge",
    "sharpe_ratio",
    "calculate_all_metrics",
    
    # Runner
    "BacktestRunner",
    "run_backtest",
    "run_quick_backtest",
]
