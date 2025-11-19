"""
VÉLØ Oracle - Narrative Contract
Strict typing for narrative data
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class NarrativeContract(BaseModel):
    """Narrative data contract"""
    race_id: str
    narrative_type: str
    confidence: float = Field(..., ge=0, le=1)
    disruption_risk: float = Field(..., ge=0, le=1)
    description: Optional[str] = None
    affected_runners: List[str] = Field(default_factory=list)


class PredictionContract(BaseModel):
    """Prediction output contract"""
    runner_id: str
    runner_name: str
    sqpe_score: float = Field(..., ge=0, le=1)
    tie_signal: float = Field(..., ge=0, le=1)
    longshot_score: float = Field(..., ge=0, le=1)
    final_probability: float = Field(..., ge=0, le=1)
    edge: float
    risk_band: str
    kelly_stake: float = Field(..., ge=0, le=1)
    expected_value: float
