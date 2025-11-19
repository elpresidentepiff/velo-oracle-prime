"""
VÉLØ Oracle - Market Contract
Strict typing for market data
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class OddsMovement(BaseModel):
    """Odds movement data"""
    timestamp: datetime
    odds: float = Field(..., gt=0)
    volume: Optional[int] = Field(None, ge=0)


class MarketContract(BaseModel):
    """Market data contract"""
    race_id: str
    runner_id: str
    current_odds: float = Field(..., gt=0)
    opening_odds: Optional[float] = Field(None, gt=0)
    odds_history: List[OddsMovement] = Field(default_factory=list)
    total_volume: Optional[int] = Field(None, ge=0)
    market_percentage: Optional[float] = Field(None, ge=0)
