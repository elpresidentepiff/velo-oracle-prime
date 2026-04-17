"""
VÉLØ Oracle - Race Card Schema
Comprehensive race card data model
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date, time
from .runner import RunnerSchema


class RaceCardSchema(BaseModel):
    """Complete race card with all runners and metadata"""
    race_id: str = Field(..., description="Unique race identifier")
    course: str = Field(..., min_length=1, max_length=100, description="Race course/venue name")
    date: date = Field(..., description="Race date")
    time: time = Field(..., description="Race scheduled time")
    distance: int = Field(..., ge=800, le=4000, description="Race distance in meters")
    going: str = Field(..., max_length=50, description="Track condition (e.g., 'Good', 'Soft 7')")
    runners: List[RunnerSchema] = Field(..., min_items=2, max_items=24, description="List of runners")
    
    # Optional race metadata
    race_name: Optional[str] = Field(None, max_length=200, description="Race name/title")
    race_number: Optional[int] = Field(None, ge=1, le=12, description="Race number on card")
    race_class: Optional[str] = Field(None, max_length=50, description="Race class/grade")
    prize_money: Optional[float] = Field(None, ge=0, description="Total prize pool")
    track_type: Optional[str] = Field(None, max_length=20, description="Track type (e.g., 'Turf', 'Dirt', 'Synthetic')")
    track_direction: Optional[str] = Field(None, max_length=20, description="Track direction (e.g., 'Clockwise', 'Anti-clockwise')")
    rail_position: Optional[str] = Field(None, max_length=20, description="Rail position (e.g., 'True', '+3m')")
    weather: Optional[str] = Field(None, max_length=50, description="Weather conditions")
    temperature: Optional[float] = Field(None, ge=-10, le=50, description="Temperature in Celsius")
    
    # Race type flags
    is_handicap: Optional[bool] = Field(False, description="Is this a handicap race")
    is_stakes: Optional[bool] = Field(False, description="Is this a stakes race")
    is_group_race: Optional[bool] = Field(False, description="Is this a group/graded race")
    group_level: Optional[int] = Field(None, ge=1, le=3, description="Group level (1, 2, or 3)")
    
    # Timing metadata
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "race_id": "RC20251119001",
                "course": "Flemington",
                "date": "2025-11-19",
                "time": "15:00:00",
                "distance": 1600,
                "going": "Good 4",
                "race_name": "Emirates Melbourne Cup",
                "race_number": 7,
                "race_class": "Group 1",
                "prize_money": 8000000.0,
                "track_type": "Turf",
                "track_direction": "Clockwise",
                "rail_position": "True",
                "weather": "Sunny",
                "temperature": 22.5,
                "is_handicap": True,
                "is_stakes": True,
                "is_group_race": True,
                "group_level": 1,
                "runners": [
                    {
                        "runner_id": "R001",
                        "horse": "Without A Fight",
                        "age": 5,
                        "weight": 57.5,
                        "trainer": "Chris Waller",
                        "jockey": "James McDonald",
                        "odds": 5.50,
                        "draw": 12,
                        "form": "1-2-1-3-1"
                    }
                ]
            }
        }
