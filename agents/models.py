"""
Pydantic models for LangGraph agent orchestration

These models define the data contracts for agent tool inputs/outputs
and the shared state that flows through the agent graph.

Version: 1.0.0
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ============================================================================
# RACE AND RUNNER MODELS
# ============================================================================

class Runner(BaseModel):
    """Runner (horse) data model"""
    runner_id: str
    horse: str
    weight_lbs: int
    jockey: str
    trainer: str
    odds_live: float
    claims_lbs: int = 0
    stall: Optional[int] = None
    OR: Optional[int] = None
    TS: Optional[int] = None
    RPR: Optional[int] = None
    owner: Optional[str] = None
    headgear: Optional[str] = None
    run_style: Optional[str] = None
    comments: Optional[str] = None


class Race(BaseModel):
    """Race data model"""
    race_id: str
    course: str
    race_date: str  # YYYY-MM-DD
    off_time: str
    race_type: str
    distance: int  # distance in yards
    going: str
    field_size: int
    batch_status: str = "validated"
    runners: List[Runner] = Field(default_factory=list)


# ============================================================================
# TOOL INPUT/OUTPUT MODELS
# ============================================================================

class ScoutInput(BaseModel):
    """Input for Scout agent"""
    date: str = Field(..., description="Race date in YYYY-MM-DD format")


class ScoutOutput(BaseModel):
    """Output from Scout agent"""
    races: List[Race] = Field(default_factory=list)
    count: int = Field(..., description="Number of races found")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ValidateInput(BaseModel):
    """Input for Validate agent"""
    races: List[Race]


class ValidateOutput(BaseModel):
    """Output from Validate agent"""
    valid_races: List[Race] = Field(default_factory=list)
    invalid_races: List[Dict[str, Any]] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


class AnalyzeInput(BaseModel):
    """Input for Analyze agent"""
    race_id: str
    runners: List[Runner]


class AnalyzeOutput(BaseModel):
    """Output from Analyze agent"""
    race_id: str
    predictions: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    execution_time_ms: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CriticInput(BaseModel):
    """Input for Critic agent"""
    race_id: str
    analyze_output: AnalyzeOutput


class LearningEvent(BaseModel):
    """Learning event for feedback loop"""
    event_id: str = Field(default_factory=lambda: f"evt_{datetime.utcnow().timestamp()}")
    race_id: str
    event_type: str = Field(..., description="Type: prediction_accuracy, data_quality, anomaly")
    severity: str = Field(default="info", description="Severity: info, warning, error")
    feedback: Dict[str, Any] = Field(default_factory=dict)
    prediction_quality_score: Optional[float] = None
    data_completeness_score: Optional[float] = None
    execution_time_ms: Optional[int] = None
    anomalies: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CriticOutput(BaseModel):
    """Output from Critic agent"""
    race_id: str
    learning_event: LearningEvent


class ArchiveInput(BaseModel):
    """Input for Archive agent"""
    race_id: str
    run_id: str
    analyze_output: AnalyzeOutput
    learning_event: LearningEvent


class ArchiveOutput(BaseModel):
    """Output from Archive agent"""
    race_id: str
    run_id: str
    success: bool
    error: Optional[str] = None


# ============================================================================
# AGENT STATE MODEL
# ============================================================================

class AgentState(BaseModel):
    """Shared state that flows through the agent graph"""
    # Input
    date: str
    dry_run: bool = False
    
    # Scout output
    races: List[Race] = Field(default_factory=list)
    races_count: int = 0
    
    # Validate output
    valid_races: List[Race] = Field(default_factory=list)
    invalid_races: List[Dict[str, Any]] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    
    # Analyze output (per race)
    analyze_results: Dict[str, AnalyzeOutput] = Field(default_factory=dict)
    
    # Critic output (per race)
    critic_results: Dict[str, CriticOutput] = Field(default_factory=dict)
    
    # Archive output (per race)
    archive_results: Dict[str, ArchiveOutput] = Field(default_factory=dict)
    
    # Summary metrics
    races_processed: int = 0
    successes: int = 0
    failures: int = 0
    failure_details: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Execution metadata
    run_id: str = Field(default_factory=lambda: f"run_{datetime.utcnow().timestamp()}")
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_time_seconds: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# SUMMARY OUTPUT MODEL
# ============================================================================

class AgentRunSummary(BaseModel):
    """Final summary output from agent run"""
    run_id: str
    date: str
    races_processed: int
    successes: int
    failures: int
    total_time_seconds: float
    failure_details: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
