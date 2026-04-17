"""
VETP Layer 1 Schemas

Clean IO for the Event Memory system.
"""

from datetime import date, time, datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class KeyRival(BaseModel):
    """A key rival in the race"""
    name: str
    sp: Optional[float] = None
    profile: Optional[str] = None


class VETPEventIn(BaseModel):
    """Input schema for creating/updating a VETP event"""
    
    event_id: str = Field(..., description="Unique identifier (e.g. 2025-12-03_KEM_19:40_MESAAFI)")

    # Race metadata
    date: date
    course: str
    off_time: Optional[time] = None
    code: str = Field(..., description="Flat-AW / Flat-Turf / Hurdle / Chase / NHF")
    race_class: Optional[str] = Field(None, description="C4, C5, G1, G2, etc")
    field_size: Optional[int] = None

    # Track conditions
    going: Optional[str] = None
    pace_shape_pre: Optional[str] = Field(None, description="Expected: Even / Strong / Crawl / Unknown")
    pace_shape_actual: Optional[str] = Field(None, description="Observed: Even / Burn-Up / Crawl / Stop-Start")

    # Favorite analysis
    fav_name: Optional[str] = None
    fav_sp: Optional[float] = None
    fav_profile: Optional[str] = None

    # Key rivals
    key_rivals: Optional[List[KeyRival]] = None

    # Our play
    our_play_type: Optional[str] = Field(None, description="Back-win / Back-place / Lay-fav / Dutch / No-bet")
    our_play_horses: Optional[List[str]] = None
    our_play_stakes: Optional[str] = Field(None, description="bank-heavy / probe / token")

    # Result
    winner: Optional[str] = None
    places: Optional[List[str]] = None
    pnl_units: Optional[float] = Field(None, description="Profit/loss in units")
    read_race_right: Optional[str] = Field(None, description="Yes / No / Partial")

    # Behavioral analysis
    behaviour_flags: Optional[List[str]] = Field(
        None, 
        description="fake_fav, non_trier_suspected, pace_misread, jockey_star_turn, etc"
    )
    market_story: Optional[str] = Field(None, description="What the market wanted everyone to believe")
    reality_story: Optional[str] = Field(None, description="What actually happened on the track")

    # Learning
    key_learning: Optional[str] = Field(None, description="1-3 sentences in human language")
    
    # Rule extraction
    rule_trigger: Optional[str] = Field(None, description="When this pattern appears...")
    rule_action: Optional[str] = Field(None, description="...do this")
    rule_confidence: Optional[str] = Field(None, description="Low / Med / High")

    # Emotion
    emotion_tag: Optional[str] = Field(None, description="rage, smug, sickener, lesson, robbery, masterpiece")
    
    # Raw metadata
    raw_meta: Optional[Dict[str, Any]] = None


class VETPEventOut(VETPEventIn):
    """Output schema including database fields"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2
        # orm_mode = True  # Pydantic v1


class VETPEventSummary(BaseModel):
    """Lightweight summary for lists"""
    id: int
    event_id: str
    date: date
    course: str
    code: str
    emotion_tag: Optional[str]
    pnl_units: Optional[float]
    read_race_right: Optional[str]
    
    class Config:
        from_attributes = True
