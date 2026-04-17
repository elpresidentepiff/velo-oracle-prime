"""
ORACLE INTERNAL DOSSIER MODEL

This is the spine. The truth layer.

What the system REALLY thinks about:
- The race structure
- The humans involved
- The trap mechanics
- The narrative vs reality gap

This is not for civilians. This is for you + VÉLØ only.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# ========== HEADER & CONTEXT ==========

class MarketSnapshot(BaseModel):
    """Market state at analysis time"""
    fav_name: str
    fav_odds: float
    fav_implied_prob: float
    overround_pct: float
    place_terms: str  # e.g. "1/5 1-3"


class RaceContext(BaseModel):
    """Core race metadata"""
    race_id: str = Field(..., description="Internal ID (e.g. 2025-12-04_CHE_17:00)")
    meeting: str
    off_time_utc: datetime
    surface: str  # "AW (polytrack)", "Turf (good)", etc
    distance_furlongs: float
    class_band: str  # "Class 4 Handicaps", "G1", etc
    field_size: int
    market_snapshot: MarketSnapshot


# ========== NARRATIVE DISRUPTION LAYER ==========

class NarrativeAnalysis(BaseModel):
    """
    Detects weaponized narratives.
    
    The stories the market wants you to believe vs structural reality.
    """
    primary_story: str
    secondary_stories: List[str]
    
    # Public sentiment metrics (0-1)
    hype_on_fav: float = Field(..., ge=0, le=1)
    media_sync: float = Field(..., ge=0, le=1)
    tipster_convergence: float = Field(..., ge=0, le=1)
    
    # Insider discord signals
    drift_against_tips: bool
    early_blue_later_red: bool  # Early support then fade
    yard_mixed_messages: str  # "low", "medium", "high"
    
    # 0-100: how weaponized is the narrative?
    narrative_disruption_score: int = Field(..., ge=0, le=100, description="0-30: aligned; 30-60: mild distortion; 60-100: weaponised")


# ========== MANIPULATION PROBABILITY INDEX ==========

class ManipulationLayer(BaseModel):
    """
    Manipulation Probability Index (MPI).
    
    How likely is this race designed to extract money from pattern-readers?
    """
    mpi_score: int = Field(..., ge=0, le=100)
    
    # Driver factors
    class_switch_gaming: str  # "low", "medium", "high"
    schooling_possibility: str
    handicap_plot_risk: str
    pace_sacrifice_risk: str
    
    # Market behavior flags
    sudden_early_steam_then_flat: bool
    late_fade_despite_good_news: bool
    liquidity_cluster_around_non_fav: bool
    
    oracle_mpi_note: str


# ========== ENERGY & STRESS BEHAVIOUR MAP ==========

class HorseEnergyProfile(BaseModel):
    """
    Per-runner energy and stress behavior.
    
    Not just "form" - how the engine actually works under pressure.
    """
    horse_name: str
    engine_profile: str  # "Long-stride, late-torque, momentum killer"
    effort_curve: str  # "Builds gradually, lethal last 2f if unboxed"
    stress_response: str  # "Responds to pressure, thrives in traffic"
    collapse_threshold_furlongs: Optional[float]
    trip_resistance_index: int = Field(..., ge=0, le=100)
    lane_preference: str  # "Outside-mid", "Rail-hugging", etc
    prior_energy_events: str  # Recent race behavior summary


class EnergyBehaviourLayer(BaseModel):
    """
    Global energy map for the race.
    
    Who has the real engine? Who's fragile? Who collapses under stress?
    """
    horse_profiles: List[HorseEnergyProfile]
    dominant_engine_candidates: List[str]
    fragile_favourites: List[str]
    stress_sensitive_runners: List[str]
    oracle_energy_comment: str


# ========== CHAOS BLOOM MODEL ==========

class ChaosLayer(BaseModel):
    """
    Chaos Bloom Probability.
    
    When does the race become a lottery? Where are the hot zones?
    """
    chaos_bloom_probability: int = Field(..., ge=0, le=100)
    
    # Driver factors
    large_field: str  # "low", "medium", "high"
    draw_clustering: str
    raw_pace_conflict: str
    inexperienced_riders: str
    
    chaos_hot_zones: List[str]  # "2f-1f from home: high interference risk"
    
    # Who benefits from chaos?
    shock_winner_range_odds: str  # "14-33"
    best_chaos_surfboard: List[str]  # Types that thrive in mess


# ========== HOUSE BEHAVIOUR & MARKET WARFARE ==========

class HouseLayer(BaseModel):
    """
    Bookmaker posture and market warfare analysis.
    
    Where is the house comfortable? Where are they hedging?
    """
    # Bookmaker posture
    comfortable_with_fav: bool
    liability_hedging_visible: str  # "low", "medium", "high"
    each_way_trap_set: str  # "Yes - places 1-4 / 1/5"
    
    # Herd behavior
    public_herd_on_short_price: str  # "weak", "medium", "strong"
    sharp_money_cluster: str  # "around 7-10.0"
    late_dumb_flow_expected: str  # "low", "medium", "high"
    
    oracle_house_verdict: str


# ========== VETP MEMORY HOOKS ==========

class VETPLinks(BaseModel):
    """
    Links to VETP Layer 1 memory.
    
    Which historical patterns does this race match?
    """
    matched_patterns: Dict[str, float]  # {"mesaafi_trap": 0.71, "castanea_dominance": 0.29}
    historical_events_triggered: List[str]  # Event IDs from VETP
    learning_directives: Dict[str, bool]  # {"tighten_fake_fav_filter": true}


# ========== ORACLE VERDICT ==========

class OracleVerdict(BaseModel):
    """
    The final Oracle judgment.
    
    One sentence that compresses the entire dossier.
    """
    integrity_score: int = Field(..., ge=0, le=100, description="Perceived race cleanliness")
    
    attack_doctrine: Dict[str, Any]  # {"doctrine_tag": "OPPOSE_FAV_TOP4_SYNDROME", "suitable_modes": [...]}
    
    primary_threat_cluster: List[str]  # The real dangers
    
    oracle_sentence: str  # The compressed truth


# ========== COMPLETE ORACLE DOSSIER ==========

class OracleRaceDossier(BaseModel):
    """
    Complete Oracle Internal Dossier.
    
    This is what VÉLØ really thinks.
    Private. Never for civilians.
    """
    # Header
    context: RaceContext
    
    # Analysis layers
    narrative: NarrativeAnalysis
    manipulation: ManipulationLayer
    energy: EnergyBehaviourLayer
    chaos: ChaosLayer
    house: HouseLayer
    vetp: VETPLinks
    verdict: OracleVerdict
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    oracle_version: str = "1.0"


# ========== CLIENT-FACING VIEW ==========

class ClientRaceSummary(BaseModel):
    """
    Clean, professional, digestible.
    
    This is what paying users see.
    The Oracle layer stays hidden.
    """
    race_id: str
    meeting: str
    off_time: datetime
    
    # Clean summary
    race_summary: str
    
    # Key factors (sanitized)
    key_factors: Dict[str, Any]  # {"pace_complexion": "Likely to collapse early", ...}
    
    # Primary contender (value zone)
    primary_contender: Dict[str, Any]  # {"name": "Castanea Breeze", "indicators": [...]}
    
    # Risk notes
    risk_notes: List[str]
    
    # Client verdict
    client_verdict: str


# ========== DUAL-LAYER REPORT ==========

class DualLayerReport(BaseModel):
    """
    The complete output: Client view + Oracle inner view.
    
    Two faces. One truth.
    """
    client_view: ClientRaceSummary
    oracle_view: OracleRaceDossier
    
    # Metadata
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
