"""
VETP Layer 1 Schemas

Clean IO for the Event Memory system.
"""

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field


class KeyRival(BaseModel):
    """A key rival in the race"""

    name: str
    sp: float | None = None
    profile: str | None = None


class VETPEventIn(BaseModel):
    """Input schema for creating/updating a VETP event"""

    event_id: str = Field(..., description="Unique identifier (e.g. 2025-12-03_KEM_19:40_MESAAFI)")

    # Race metadata
    date: date
    course: str
    off_time: time | None = None
    code: str = Field(..., description="Flat-AW / Flat-Turf / Hurdle / Chase / NHF")
    race_class: str | None = Field(None, description="C4, C5, G1, G2, etc")
    field_size: int | None = None

    # Track conditions
    going: str | None = None
    pace_shape_pre: str | None = Field(None, description="Expected: Even / Strong / Crawl / Unknown")
    pace_shape_actual: str | None = Field(None, description="Observed: Even / Burn-Up / Crawl / Stop-Start")

    # Favorite analysis
    fav_name: str | None = None
    fav_sp: float | None = None
    fav_profile: str | None = None

    # Key rivals
    key_rivals: list[KeyRival] | None = None

    # Our play
    our_play_type: str | None = Field(None, description="Back-win / Back-place / Lay-fav / Dutch / No-bet")
    our_play_horses: list[str] | None = None
    our_play_stakes: str | None = Field(None, description="bank-heavy / probe / token")

    # Result
    winner: str | None = None
    places: list[str] | None = None
    pnl_units: float | None = Field(None, description="Profit/loss in units")
    read_race_right: str | None = Field(None, description="Yes / No / Partial")

    # Behavioral analysis
    behaviour_flags: list[str] | None = Field(
        None, description="fake_fav, non_trier_suspected, pace_misread, jockey_star_turn, etc"
    )
    market_story: str | None = Field(None, description="What the market wanted everyone to believe")
    reality_story: str | None = Field(None, description="What actually happened on the track")

    # Learning
    key_learning: str | None = Field(None, description="1-3 sentences in human language")

    # Rule extraction
    rule_trigger: str | None = Field(None, description="When this pattern appears...")
    rule_action: str | None = Field(None, description="...do this")
    rule_confidence: str | None = Field(None, description="Low / Med / High")

    # Emotion
    emotion_tag: str | None = Field(None, description="rage, smug, sickener, lesson, robbery, masterpiece")

    # Raw metadata
    raw_meta: dict[str, Any] | None = None


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
    emotion_tag: str | None
    pnl_units: float | None
    read_race_right: str | None

    class Config:
        from_attributes = True
