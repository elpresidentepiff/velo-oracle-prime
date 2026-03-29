"""
VÉLØ Oracle - Backtesting Package
Complete backtesting framework for model validation
"""

from .engine import BacktestEngine, create_backtest
from .metrics import (
    accuracy,
    auc,
    calculate_all_metrics,
    drawdown,
    log_loss,
    roi,
    sharpe_ratio,
    strike_rate,
    value_edge,
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
