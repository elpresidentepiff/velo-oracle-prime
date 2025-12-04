"""
VETP LAYER 1 – EVENT MEMORY / LEDGER OF PAIN & VICTORY

Every meaningful race we live through becomes permanent memory.
Every time they shaft us or we nail them, it becomes code.

This is the spine. This is how VÉLØ learns.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    Time,
    Float,
    Boolean,
    JSON,
    Text,
    DateTime,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VETPEvent(Base):
    """
    The Event Memory Table.
    
    Every race we analyze, every bet we place, every result we witness
    gets logged here with:
    - What happened (facts)
    - What we thought would happen (prediction)
    - What the market thought (narrative)
    - What actually happened (reality)
    - What we learned (rules)
    - How it felt (emotion)
    
    This is not just data. This is lived experience turned into architecture.
    """
    __tablename__ = "vetp_events"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique event identifier (e.g. "2025-12-03_KEM_19:40_MESAAFI")
    event_id = Column(String(80), unique=True, nullable=False, index=True)

    # Race metadata
    date = Column(Date, nullable=False, index=True)
    course = Column(String(50), nullable=False, index=True)
    off_time = Column(Time, nullable=True)
    code = Column(String(20), nullable=False, index=True)  # Flat-AW / Hurdle / Chase / NHF
    race_class = Column(String(20), nullable=True)  # "C4", "C5", "G1", "G2", etc
    field_size = Column(Integer, nullable=True)

    # Track conditions
    going = Column(String(40), nullable=True)
    pace_shape_pre = Column(String(40), nullable=True)  # Expected: Even / Strong / Crawl
    pace_shape_actual = Column(String(40), nullable=True)  # Observed: Even / Burn-Up / Crawl

    # Favorite analysis
    fav_name = Column(String(80), nullable=True)
    fav_sp = Column(Float, nullable=True)
    fav_profile = Column(Text, nullable=True)  # Human description of the favorite

    # Key rivals (JSON array of {name, sp, profile})
    key_rivals = Column(JSON, nullable=True)

    # Our play
    our_play_type = Column(String(40), nullable=True)  # "Back-win", "Lay-fav", "Dutch", etc
    our_play_horses = Column(JSON, nullable=True)  # List of horse names
    our_play_stakes = Column(String(80), nullable=True)  # "bank-heavy", "probe", "token"

    # Result
    winner = Column(String(80), nullable=True)
    places = Column(JSON, nullable=True)  # List of placed horses
    pnl_units = Column(Float, nullable=True)  # Profit/loss in units
    read_race_right = Column(String(20), nullable=True)  # "Yes" / "No" / "Partial"

    # Behavioral analysis
    behaviour_flags = Column(JSON, nullable=True)  # [fake_fav, non_trier, pace_misread, etc]
    market_story = Column(Text, nullable=True)  # What the market wanted everyone to believe
    reality_story = Column(Text, nullable=True)  # What actually happened

    # Learning extraction
    key_learning = Column(Text, nullable=True)  # 1-3 sentences in human language
    
    # Rule extraction (for future pattern matching)
    rule_trigger = Column(Text, nullable=True)  # When this pattern appears...
    rule_action = Column(Text, nullable=True)  # ...do this
    rule_confidence = Column(String(20), nullable=True)  # Low / Med / High

    # Emotion (because this is personal)
    emotion_tag = Column(String(20), nullable=True, index=True)  # rage, smug, sickener, lesson, robbery, masterpiece

    # Raw metadata (anything extra)
    raw_meta = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<VETPEvent {self.event_id} | {self.emotion_tag} | PnL: {self.pnl_units}>"
