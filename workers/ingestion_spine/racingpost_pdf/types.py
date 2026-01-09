"""
Racing Post PDF Parser - Type Definitions
Pydantic models for Meeting, Race, Runner, and ParseReport.
"""

from datetime import date, time
from typing import Any, Optional

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    """Top-4 prediction for a race"""
    runner_number: int
    horse_name: str
    score: float = 0.0


class Runner(BaseModel):
    """Canonical runner data from PDF parse"""
    # Identity
    cloth_no: Optional[int] = None
    runner_number: int = Field(..., description="Runner number in race (1, 2, 3, etc.)")
    name: str = Field(..., description="Horse name")
    
    # Core attributes
    age: Optional[int] = Field(None, description="Age in years (2-15)")
    sex: Optional[str] = None
    weight: Optional[str] = None
    
    # Days since last run (NOT age!)
    days_since_run: Optional[int] = Field(None, description="Days since last run (separate from age)")
    
    # Ratings
    or_rating: Optional[int] = Field(None, description="Official Rating")
    rpr: Optional[int] = Field(None, description="Racing Post Rating")
    ts: Optional[int] = Field(None, description="Timeform Speed figure")
    
    # People
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    owner: Optional[str] = None
    
    # Other
    draw: Optional[int] = None
    headgear: Optional[str] = None
    form_figures: Optional[str] = None
    
    # Raw data from source
    raw: dict[str, Any] = Field(default_factory=dict)


class Race(BaseModel):
    """Canonical race data from PDF parse"""
    # Identity
    race_id: str = Field(..., description="Unique race identifier")
    race_number: Optional[int] = None
    
    # Core race data
    course: str
    off_time: time
    race_name: Optional[str] = None
    race_type: Optional[str] = None
    
    # Distance (canonical source of truth)
    distance_text: str = Field(..., description="Original distance text from PDF")
    distance_yards: Optional[int] = Field(None, description="Canonical distance in yards")
    distance_furlongs: Optional[float] = Field(None, description="Distance in furlongs (derived)")
    distance_meters: Optional[int] = Field(None, description="Distance in meters (derived)")
    
    # Other race attributes
    class_band: Optional[str] = None
    going: Optional[str] = None
    prize: Optional[str] = None
    
    # Runners
    runners: list[Runner] = Field(default_factory=list)
    runners_count: int = Field(..., description="Declared runner count from PDF")
    has_non_runners: bool = Field(default=False, description="True if non-runners marker found")
    
    # Predictions (optional)
    top_4_predictions: list[Prediction] = Field(default_factory=list)
    
    # Raw data from source
    raw: dict[str, Any] = Field(default_factory=dict)


class Meeting(BaseModel):
    """Canonical meeting data from PDF parse"""
    # Meeting identity
    course_code: str
    course_name: str
    meeting_date: date
    
    # Races
    races: list[Race] = Field(default_factory=list)
    
    # Metadata
    source: str = Field(default="racing_post", description="Data source")
    parsed_at: Optional[str] = None
    
    # Raw metadata
    raw: dict[str, Any] = Field(default_factory=dict)


class ParseError(BaseModel):
    """Parse error with context"""
    severity: str = Field(..., description="error | warning | info")
    message: str
    location: Optional[str] = Field(None, description="Where in PDF (page, race, etc.)")
    raw_context: Optional[str] = Field(None, description="Raw text context")


class ParseReport(BaseModel):
    """Report on parse success/failures"""
    success: bool
    meeting: Optional[Meeting] = None
    errors: list[ParseError] = Field(default_factory=list)
    warnings: list[ParseError] = Field(default_factory=list)
    
    # Statistics
    stats: dict[str, Any] = Field(default_factory=dict)
    
    # Input files processed
    input_files: list[str] = Field(default_factory=list)
