"""
VÉLØ Oracle - Market Contract
Strict typing for market data
"""

from datetime import datetime

from pydantic import BaseModel, Field


class OddsMovement(BaseModel):
    """Odds movement data"""

    timestamp: datetime
    odds: float = Field(..., gt=0)
    volume: int | None = Field(None, ge=0)


class MarketContract(BaseModel):
    """Market data contract"""

    race_id: str
    runner_id: str
    current_odds: float = Field(..., gt=0)
    opening_odds: float | None = Field(None, gt=0)
    odds_history: list[OddsMovement] = Field(default_factory=list)
    total_volume: int | None = Field(None, ge=0)
    market_percentage: float | None = Field(None, ge=0)
