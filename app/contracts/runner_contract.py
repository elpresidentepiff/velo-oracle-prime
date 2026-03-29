"""
VÉLØ Oracle - Runner Contract
Strict typing for runner data
"""

from pydantic import BaseModel, Field


class RunnerContract(BaseModel):
    """Runner data contract"""

    runner_id: str = Field(..., description="Unique runner identifier")
    horse: str = Field(..., description="Horse name")
    trainer: str = Field(..., description="Trainer name")
    jockey: str = Field(..., description="Jockey name")
    age: int = Field(..., gt=0, le=15, description="Horse age")
    weight: float = Field(..., gt=0, description="Allocated weight (kg)")
    draw: int = Field(..., gt=0, description="Barrier draw")
    odds: float = Field(..., gt=0, description="Current odds")
    form: str | None = Field(None, description="Recent form string")
    last_start_days: int | None = Field(None, ge=0, description="Days since last start")
    career_starts: int | None = Field(None, ge=0, description="Career starts")
    career_wins: int | None = Field(None, ge=0, description="Career wins")
    speed_ratings: dict[str, float] | None = Field(None, description="Speed ratings")
    sectional_times: dict[str, float] | None = Field(None, description="Sectional times")
    gear_changes: str | None = Field(None, description="Gear changes")

    class Config:
        json_schema_extra = {
            "example": {
                "runner_id": "R001",
                "horse": "Without A Fight",
                "trainer": "Chris Waller",
                "jockey": "James McDonald",
                "age": 4,
                "weight": 57.5,
                "draw": 5,
                "odds": 3.5,
                "form": "1-2-1-3-2",
                "last_start_days": 21,
                "career_starts": 15,
                "career_wins": 8,
                "speed_ratings": {"adjusted": 120},
                "sectional_times": {"last_200m": 11.2},
                "gear_changes": "Blinkers On",
            }
        }
