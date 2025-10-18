"""
VÉLØ Oracle 2.0 - Database ORM Models
======================================

SQLAlchemy models for all database tables.
This provides a Pythonic interface to the database.

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric, Boolean, 
    Text, ARRAY, JSON, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================================================
# CORE RACING DATA
# ============================================================================

class RacingData(Base):
    """Historical race results from Kaggle datasets."""
    __tablename__ = 'racing_data'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    course = Column(String(100), index=True)
    race_id = Column(String(50), index=True)
    off_time = Column(String(10))
    race_name = Column(Text)
    type = Column(String(20), index=True)
    class_ = Column('class', String(20))
    pattern = Column(String(50))
    rating_band = Column(String(30))
    age_band = Column(String(30))
    sex_rest = Column(String(30))
    dist = Column(String(20))
    going = Column(String(50))
    ran = Column(Integer)
    num = Column(Numeric(5, 1))
    pos = Column(String(10))
    draw = Column(Integer)
    ovr_btn = Column(Numeric(10, 2))
    btn = Column(Numeric(10, 2))
    horse = Column(String(150), index=True)
    age = Column(Integer)
    sex = Column(String(1))
    wgt = Column(String(20))
    hg = Column(String(10))
    time = Column(String(20))
    sp = Column(String(30))
    jockey = Column(String(150), index=True)
    trainer = Column(String(150), index=True)
    prize = Column(String(50))
    official_rating = Column(String(10))
    rpr = Column(String(10))
    ts = Column(String(10))
    sire = Column(String(150))
    dam = Column(String(150))
    damsire = Column(String(150))
    owner = Column(Text)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = (
        Index('idx_date_course', 'date', 'course'),
    )


class SectionalData(Base):
    """Sectional timing data from ATR."""
    __tablename__ = 'sectional_data'
    
    id = Column(Integer, primary_key=True)
    race_id = Column(String(50), index=True)
    horse = Column(String(150), index=True)
    date = Column(Date, index=True)
    course = Column(String(100))
    
    # Furlong times
    f1 = Column(Numeric(5, 2))
    f2 = Column(Numeric(5, 2))
    f3 = Column(Numeric(5, 2))
    f4 = Column(Numeric(5, 2))
    f5 = Column(Numeric(5, 2))
    f6 = Column(Numeric(5, 2))
    f7 = Column(Numeric(5, 2))
    f8 = Column(Numeric(5, 2))
    f9 = Column(Numeric(5, 2))
    f10 = Column(Numeric(5, 2))
    f11 = Column(Numeric(5, 2))
    f12 = Column(Numeric(5, 2))
    f13 = Column(Numeric(5, 2))
    f14 = Column(Numeric(5, 2))
    f15 = Column(Numeric(5, 2))
    f16 = Column(Numeric(5, 2))
    
    # Calculated metrics
    finishing_speed_pct = Column(Numeric(5, 2))
    efficiency_grade = Column(String(1))
    early_speed_mph = Column(Numeric(5, 2))
    mid_speed_mph = Column(Numeric(5, 2))
    late_speed_mph = Column(Numeric(5, 2))
    
    # Race context
    total_time = Column(Numeric(6, 2))
    race_finishing_speed_pct = Column(Numeric(5, 2))
    pace_scenario = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.now)


class Racecard(Base):
    """Daily racecards from rpscrape."""
    __tablename__ = 'racecards'
    
    id = Column(Integer, primary_key=True)
    race_id = Column(String(50))
    date = Column(Date, nullable=False, index=True)
    course = Column(String(100), index=True)
    off_time = Column(String(10))
    race_name = Column(Text)
    distance = Column(String(20))
    going = Column(String(50))
    horse = Column(String(150), index=True)
    jockey = Column(String(150))
    trainer = Column(String(150))
    weight = Column(String(20))
    draw = Column(Integer)
    age = Column(Integer)
    official_rating = Column(Integer)
    last_run_date = Column(Date)
    form = Column(String(50))
    odds = Column(Numeric(10, 2))
    scraped_at = Column(DateTime, default=datetime.now)


# ============================================================================
# BETFAIR MARKET DATA
# ============================================================================

class BetfairMarket(Base):
    """Betfair market information."""
    __tablename__ = 'betfair_markets'
    
    id = Column(Integer, primary_key=True)
    market_id = Column(String(50), unique=True, nullable=False, index=True)
    event_name = Column(String(200))
    course = Column(String(100), index=True)
    race_time = Column(DateTime, index=True)
    country_code = Column(String(5))
    market_type = Column(String(20))
    total_matched = Column(Numeric(15, 2))
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    odds = relationship("BetfairOdds", back_populates="market")
    alerts = relationship("ManipulationAlert", back_populates="market")


class BetfairOdds(Base):
    """Betfair odds snapshots over time."""
    __tablename__ = 'betfair_odds'
    
    id = Column(Integer, primary_key=True)
    market_id = Column(String(50), nullable=False, index=True)
    selection_id = Column(Integer, nullable=False, index=True)
    runner_name = Column(String(150))
    back_price = Column(Numeric(10, 2))
    back_size = Column(Numeric(15, 2))
    lay_price = Column(Numeric(10, 2))
    lay_size = Column(Numeric(15, 2))
    total_matched = Column(Numeric(15, 2))
    last_price_traded = Column(Numeric(10, 2))
    snapshot_time = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    market = relationship("BetfairMarket", back_populates="odds")
    
    __table_args__ = (
        Index('idx_bf_odds_market_time', 'market_id', 'snapshot_time'),
    )


class ManipulationAlert(Base):
    """Market manipulation detection alerts."""
    __tablename__ = 'manipulation_alerts'
    
    id = Column(Integer, primary_key=True)
    market_id = Column(String(50), nullable=False, index=True)
    selection_id = Column(Integer, nullable=False)
    runner_name = Column(String(150))
    manipulation_score = Column(Integer, index=True)
    odds_drift = Column(Numeric(10, 2))
    volume_surge = Column(Boolean)
    smart_money = Column(Boolean)
    alert_type = Column(String(50))
    message = Column(Text)
    detected_at = Column(DateTime, default=datetime.now, index=True)
    
    # Relationships
    market = relationship("BetfairMarket", back_populates="alerts")


# ============================================================================
# PREDICTIONS & ML
# ============================================================================

class Prediction(Base):
    """ML model predictions."""
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True)
    race_id = Column(String(50), index=True)
    market_id = Column(String(50), index=True)
    date = Column(Date, nullable=False, index=True)
    course = Column(String(100))
    race_time = Column(DateTime)
    horse = Column(String(150), index=True)
    
    # Model predictions
    model_version = Column(String(20))
    win_probability = Column(Numeric(5, 4))
    place_probability = Column(Numeric(5, 4))
    expected_position = Column(Numeric(5, 2))
    confidence_score = Column(Numeric(5, 2))
    
    # VÉLØ analysis scores
    sqpe_score = Column(Numeric(5, 2))
    v9pm_score = Column(Numeric(5, 2))
    tie_score = Column(Numeric(5, 2))
    ssm_score = Column(Numeric(5, 2))
    bop_score = Column(Numeric(5, 2))
    manipulation_risk = Column(Numeric(5, 2))
    value_score = Column(Numeric(5, 2))
    
    # Recommendation
    recommended_bet = Column(String(20))  # WIN, EW, PLACE, PASS
    recommended_stake = Column(Numeric(10, 2))
    odds_at_prediction = Column(Numeric(10, 2))
    
    # Actual outcome
    actual_position = Column(Integer)
    actual_sp = Column(Numeric(10, 2))
    result = Column(String(20), index=True)  # WON, PLACED, LOST
    profit_loss = Column(Numeric(10, 2))
    
    predicted_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ModelVersion(Base):
    """ML model version tracking."""
    __tablename__ = 'model_versions'
    
    id = Column(Integer, primary_key=True)
    version = Column(String(20), unique=True, nullable=False, index=True)
    model_type = Column(String(50))
    features_used = Column(ARRAY(Text))
    training_data_size = Column(Integer)
    validation_accuracy = Column(Numeric(5, 4))
    test_accuracy = Column(Numeric(5, 4))
    
    # Performance metrics
    win_strike_rate = Column(Numeric(5, 2))
    place_strike_rate = Column(Numeric(5, 2))
    roi = Column(Numeric(10, 2))
    profit_loss = Column(Numeric(15, 2))
    total_bets = Column(Integer)
    
    # Model parameters
    hyperparameters = Column(JSON)
    feature_importance = Column(JSON)
    
    trained_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=False, index=True)


# ============================================================================
# GENESIS PROTOCOL (LEARNING)
# ============================================================================

class RaceAnalysis(Base):
    """Post-race analysis and learning."""
    __tablename__ = 'race_analysis'
    
    id = Column(Integer, primary_key=True)
    race_id = Column(String(50), index=True)
    market_id = Column(String(50))
    date = Column(Date, nullable=False, index=True)
    course = Column(String(100), index=True)
    
    # Pre-race vs reality
    favorite_expected = Column(String(150))
    favorite_actual = Column(String(150))
    favorite_trap = Column(Boolean)
    
    # Pattern analysis
    pace_scenario = Column(String(50))
    pace_advantage = Column(String(50))
    draw_bias_detected = Column(Boolean)
    going_impact = Column(String(50))
    
    # Lessons learned
    key_insights = Column(ARRAY(Text))
    mistakes_made = Column(ARRAY(Text))
    patterns_confirmed = Column(ARRAY(Text))
    patterns_rejected = Column(ARRAY(Text))
    
    # Performance
    predictions_correct = Column(Integer)
    predictions_total = Column(Integer)
    accuracy = Column(Numeric(5, 2))
    profit_loss = Column(Numeric(10, 2))
    
    analyzed_at = Column(DateTime, default=datetime.now)


class LearnedPattern(Base):
    """Pattern library - learned patterns over time."""
    __tablename__ = 'learned_patterns'
    
    id = Column(Integer, primary_key=True)
    pattern_name = Column(String(100), unique=True, nullable=False, index=True)
    pattern_type = Column(String(50), index=True)
    description = Column(Text)
    
    # Pattern conditions (JSON)
    conditions = Column(JSON)
    
    # Pattern performance
    occurrences = Column(Integer, default=0)
    successful_predictions = Column(Integer, default=0)
    success_rate = Column(Numeric(5, 2))
    avg_roi = Column(Numeric(10, 2))
    confidence_level = Column(Numeric(5, 2))
    
    # Pattern evolution
    first_observed = Column(DateTime)
    last_observed = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============================================================================
# BETTING LEDGER
# ============================================================================

class BettingLedger(Base):
    """Complete betting history and bankroll tracking."""
    __tablename__ = 'betting_ledger'
    
    id = Column(Integer, primary_key=True)
    race_id = Column(String(50))
    market_id = Column(String(50))
    date = Column(Date, nullable=False, index=True)
    course = Column(String(100))
    race_time = Column(DateTime)
    
    # Bet details
    horse = Column(String(150), index=True)
    bet_type = Column(String(20))  # WIN, EW, PLACE
    stake = Column(Numeric(10, 2))
    odds = Column(Numeric(10, 2))
    
    # Outcome
    result = Column(String(20), index=True)  # WON, PLACED, LOST, VOID
    returns = Column(Numeric(10, 2))
    profit_loss = Column(Numeric(10, 2))
    
    # Context
    bankroll_before = Column(Numeric(15, 2))
    bankroll_after = Column(Numeric(15, 2))
    confidence_level = Column(Numeric(5, 2))
    reasoning = Column(Text)
    
    placed_at = Column(DateTime, default=datetime.now, index=True)
    settled_at = Column(DateTime)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def init_database(engine):
    """
    Initialize database - create all tables.
    
    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)


def get_or_create(session, model, **kwargs):
    """
    Get existing record or create new one.
    
    Args:
        session: SQLAlchemy session
        model: Model class
        **kwargs: Field values
        
    Returns:
        Tuple of (instance, created)
    """
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance, True

