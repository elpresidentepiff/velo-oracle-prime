"""
VÉLØ Oracle - Runner Schema
Comprehensive runner data model for horse racing predictions
"""

from pydantic import BaseModel, Field


class SectionalTimes(BaseModel):
    """Sectional timing data for race analysis"""

    first_200m: float | None = Field(None, description="First 200m time in seconds")
    first_400m: float | None = Field(None, description="First 400m time in seconds")
    first_600m: float | None = Field(None, description="First 600m time in seconds")
    first_800m: float | None = Field(None, description="First 800m time in seconds")
    last_600m: float | None = Field(None, description="Last 600m time in seconds")
    last_400m: float | None = Field(None, description="Last 400m time in seconds")
    last_200m: float | None = Field(None, description="Last 200m time in seconds")


class SpeedRatings(BaseModel):
    """Speed rating metrics for runner performance"""

    timeform: int | None = Field(None, ge=0, le=150, description="Timeform rating")
    beyer: int | None = Field(None, ge=0, le=150, description="Beyer Speed Figure")
    rpr: int | None = Field(None, ge=0, le=150, description="Racing Post Rating")
    official: int | None = Field(None, ge=0, le=150, description="Official rating")
    adjusted: float | None = Field(None, description="VÉLØ adjusted speed rating")


class RunnerSchema(BaseModel):
    """Individual runner in a race"""

    runner_id: str = Field(..., description="Unique runner identifier")
    horse: str = Field(..., min_length=1, max_length=100, description="Horse name")
    age: int = Field(..., ge=2, le=15, description="Horse age in years")
    weight: float = Field(..., ge=45.0, le=75.0, description="Carried weight in kg")
    trainer: str = Field(..., min_length=1, max_length=100, description="Trainer name")
    jockey: str = Field(..., min_length=1, max_length=100, description="Jockey name")
    odds: float = Field(..., gt=0, description="Current odds (decimal format)")
    draw: int = Field(..., ge=1, le=24, description="Barrier/gate draw position")
    form: str = Field(..., max_length=20, description="Recent form string (e.g., '1-2-3-4-5')")

    # Optional advanced fields
    speed_ratings: SpeedRatings | None = Field(None, description="Speed rating metrics")
    sectional_times: SectionalTimes | None = Field(None, description="Sectional timing data")

    # Additional metadata
    silk_color: str | None = Field(None, max_length=50, description="Jockey silk colors")
    gear: str | None = Field(None, max_length=50, description="Gear/equipment (e.g., 'B, T')")
    comment: str | None = Field(None, max_length=500, description="Steward or form comment")
    last_start_days: int | None = Field(None, ge=0, description="Days since last race")
    career_starts: int | None = Field(None, ge=0, description="Total career starts")
    career_wins: int | None = Field(None, ge=0, description="Total career wins")
    career_places: int | None = Field(None, ge=0, description="Total career places (2nd/3rd)")
    prize_money: float | None = Field(None, ge=0, description="Total career prize money")

    class Config:
        json_schema_extra = {
            "example": {
                "runner_id": "R001",
                "horse": "Winx",
                "age": 6,
                "weight": 58.5,
                "trainer": "Chris Waller",
                "jockey": "Hugh Bowman",
                "odds": 1.50,
                "draw": 4,
                "form": "1-1-1-1-1",
                "speed_ratings": {"timeform": 130, "beyer": 125, "rpr": 128, "official": 126, "adjusted": 132.5},
                "sectional_times": {"first_400m": 24.5, "last_600m": 34.2, "last_200m": 11.3},
                "last_start_days": 21,
                "career_starts": 43,
                "career_wins": 37,
                "career_places": 4,
                "prize_money": 26451174.0,
            }
        }
