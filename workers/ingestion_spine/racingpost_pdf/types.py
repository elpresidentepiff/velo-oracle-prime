"""
Racing Post PDF Parser - Type Definitions
Pydantic models for Meeting, Race, Runner, and ParseReport.
"""

from datetime import date, time
from typing import Any

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    """Top-4 prediction for a race"""

    runner_number: int
    horse_name: str
    score: float = 0.0


class Runner(BaseModel):
    """Canonical runner data from PDF parse"""

    # Identity
    cloth_no: int | None = None
    runner_number: int = Field(..., description="Runner number in race (1, 2, 3, etc.)")
    name: str = Field(..., description="Horse name")

    # Core attributes
    age: int | None = Field(None, description="Age in years (2-15)")
    sex: str | None = None
    weight: str | None = None

    # Days since last run
    days_since_run: int | None = Field(None, description="Days since last run")

    # Ratings
    or_rating: int | None = Field(None, description="Official Rating")
    rpr: int | None = Field(None, description="Racing Post Rating")
    ts: int | None = Field(None, description="Topspeed Rating")

    # People
    jockey: str | None = None
    trainer: str | None = None
    owner: str | None = None

    # Other
    draw: int | None = None
    headgear: str | None = None
    form_figures: str | None = None
    
    # Plot Intelligence
    comment: str | None = Field(None, description="Spotlight prose comment")
    postdata_pick: bool = False
    topspeed_pick: bool = False
    best_winning_life: int | None = Field(None, description="Highest OR horse has won off")
    or_delta_to_best_win: int | None = Field(None, description="Today OR - Best Winning Life")
    plot_conviction: float = Field(0.0, description="Final calculated plot score 0.0-1.0")
    star_rating: int = Field(0, description="0-3 stars based on plot conviction")

    # Raw data from source
    raw: dict[str, Any] = Field(default_factory=dict)


class Race(BaseModel):
    """Canonical race data from PDF parse"""

    # Identity
    race_id: str = Field(..., description="Unique race identifier")
    race_number: int | None = None

    # Core race data
    course: str
    off_time: time
    race_name: str | None = None
    race_type: str | None = None

    # Distance
    distance_text: str = Field(..., description="Original distance text from PDF")
    distance_yards: int | None = Field(None, description="Canonical distance in yards")
    distance_furlongs: float | None = Field(None, description="Distance in furlongs")
    distance_meters: int | None = Field(None, description="Distance in meters")

    # Other race attributes
    class_band: str | None = None
    going: str | None = None
    prize: str | None = None
    spotlight_verdict: str | None = None

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
    parsed_at: str | None = None

    # Raw metadata
    raw: dict[str, Any] = Field(default_factory=dict)


class ParseError(BaseModel):
    """Parse error with context"""

    severity: str = Field(..., description="error | warning | info")
    message: str
    location: str | None = Field(None, description="Where in PDF")
    raw_context: str | None = Field(None, description="Raw text context")


class ParseReport(BaseModel):
    """Report on parse success/failures"""

    success: bool
    meeting: Meeting | None = None
    errors: list[ParseError] = Field(default_factory=list)
    warnings: list[ParseError] = Field(default_factory=list)

    # Statistics
    stats: dict[str, Any] = Field(default_factory=dict)

    # Input files processed
    input_files: list[str] = Field(default_factory=list)
