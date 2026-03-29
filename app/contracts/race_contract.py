"""
VÉLØ Oracle - Race Contract
Strict typing for race data
"""

from datetime import date, time

from pydantic import BaseModel, Field


class RaceContract(BaseModel):
    """Race data contract"""

    race_id: str = Field(..., description="Unique race identifier")
    course: str = Field(..., description="Race course/track")
    date: date = Field(..., description="Race date")
    race_time: time = Field(..., description="Race time")
    race_name: str | None = Field(None, description="Race name")
    distance: int = Field(..., gt=0, description="Race distance in meters")
    going: str = Field(..., description="Track condition")
    track_type: str | None = Field(None, description="Track type (turf/dirt)")
    race_class: str | None = Field(None, description="Race class")
    prize_money: float | None = Field(None, ge=0, description="Total prize money")
    field_size: int = Field(..., gt=0, description="Number of runners")

    class Config:
        json_schema_extra = {
            "example": {
                "race_id": "RC20251119001",
                "course": "Flemington",
                "date": "2025-11-19",
                "race_time": "15:00:00",
                "race_name": "Melbourne Cup",
                "distance": 3200,
                "going": "Good",
                "track_type": "turf",
                "race_class": "Group 1",
                "prize_money": 8000000.0,
                "field_size": 24,
            }
        }
