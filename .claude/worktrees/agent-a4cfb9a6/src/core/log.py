"""
VÉLØ v10 - Structured Logging
Centralized logging with run_id tracking and JSON formatting
"""

import json
import logging
import logging.config
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from .settings import settings


# Generate unique run ID for this execution
_RUN_ID = os.environ.get("VELO_RUN_ID", str(uuid.uuid4())[:8])


def setup_logging(config_path: Optional[str] = None) -> None:
    """
    Initialize logging configuration
    
    Args:
        config_path: Path to logging config JSON file (optional)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if config_path and Path(config_path).exists():
        # Load from JSON config
        with open(config_path) as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        # Basic configuration
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper()),
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_dir / "velo.log")
            ]
        )
    
    # Reduce noise from SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger("velo")
    logger.info(f"VÉLØ v10 initialized [run_id={_RUN_ID}]")


def event(name: str, **kwargs: Any) -> None:
    """
    Log a structured event with metadata
    
    Args:
        name: Event name (e.g., "start_analyze", "overlay_found")
        **kwargs: Additional event metadata
    """
    payload = {
        "evt": name,
        "ts": time.time(),
        "run_id": _RUN_ID,
        **kwargs
    }
    
    logger = logging.getLogger("velo")
    logger.info(json.dumps(payload))


def get_run_id() -> str:
    """Get the current run ID"""
    return _RUN_ID


class EventLogger:
    """
    Context manager for logging start/end events
    
    Usage:
        with EventLogger("analyze_race") as log:
            # do work
            log.info(horses=12, overlays=3)
    """
    
    def __init__(self, operation: str, **initial_data: Any):
        self.operation = operation
        self.initial_data = initial_data
        self.start_time = None
        self.logger = logging.getLogger("velo")
    
    def __enter__(self) -> "EventLogger":
        self.start_time = time.time()
        event(f"start_{self.operation}", **self.initial_data)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            event(
                f"done_{self.operation}",
                duration_sec=round(duration, 3),
                status="success"
            )
        else:
            event(
                f"error_{self.operation}",
                duration_sec=round(duration, 3),
                status="error",
                error_type=exc_type.__name__,
                error_msg=str(exc_val)
            )
        
        return False  # Don't suppress exceptions
    
    def info(self, **data: Any) -> None:
        """Log additional info during operation"""
        event(f"info_{self.operation}", **data)
    
    def warn(self, **data: Any) -> None:
        """Log warning during operation"""
        event(f"warn_{self.operation}", **data)


def log_overlay(
    runner: str,
    p_model: float,
    p_market: float,
    odds: float,
    edge: float,
    stake: float
) -> None:
    """
    Log an overlay detection event
    
    Args:
        runner: Horse name
        p_model: Model probability
        p_market: Market-implied probability
        odds: Decimal odds
        edge: Expected edge
        stake: Recommended stake fraction
    """
    event(
        "overlay_detected",
        runner=runner,
        p_model=round(p_model, 4),
        p_market=round(p_market, 4),
        odds=round(odds, 2),
        edge=round(edge, 4),
        stake=round(stake, 4)
    )


def log_bet_placed(
    runner: str,
    odds: float,
    stake: float,
    bet_type: str = "win"
) -> None:
    """
    Log a bet placement event
    
    Args:
        runner: Horse name
        odds: Decimal odds
        stake: Stake amount
        bet_type: Type of bet (win/place/each-way)
    """
    event(
        "bet_placed",
        runner=runner,
        odds=round(odds, 2),
        stake=round(stake, 2),
        bet_type=bet_type
    )


def log_result(
    runner: str,
    position: int,
    won: bool,
    profit: float
) -> None:
    """
    Log a race result
    
    Args:
        runner: Horse name
        position: Finishing position
        won: Whether bet won
        profit: Profit/loss amount
    """
    event(
        "race_result",
        runner=runner,
        position=position,
        won=won,
        profit=round(profit, 2)
    )

