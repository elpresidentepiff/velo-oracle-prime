from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Runner(BaseModel):
    horse_name: str = Field(..., description="Standardized name of the horse")
    saddle_cloth: Optional[int] = None
    draw: Optional[int] = None
    trainer: Optional[str] = None
    jockey: Optional[str] = None
    age: Optional[int] = None
    sire: Optional[str] = None
    dam: Optional[str] = None
    weight: Optional[str] = None
    weight_lbs: Optional[int] = None
    odds: Optional[float] = None
    form_string: Optional[str] = None
    official_rating: Optional[int] = None
    rpr: Optional[int] = None
    topspeed: Optional[int] = None
    
    # Analysis fields (populated later)
    days_since_run: Optional[int] = None
    form_trajectory: Optional[str] = None

class Race(BaseModel):
    race_id: str
    venue: str
    date: str
    time: str
    title: Optional[str] = None
    distance: Optional[str] = None
    going: Optional[str] = None
    race_class: Optional[str] = None
    classification: Optional[str] = None
    prize_money: Optional[str] = None
    runners: List[Runner] = []
    pace_monitor: Optional[str] = None
    
    # Analysis fields
    pace_scenario: Optional[str] = None
    verdict: Optional[str] = None

class RaceCard(BaseModel):
    venue: str
    date: str
    races: Dict[str, Race] = {} # Keyed by time (e.g., "15:55")
