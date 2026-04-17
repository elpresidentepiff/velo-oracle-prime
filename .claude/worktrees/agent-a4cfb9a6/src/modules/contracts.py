"""
VÉLØ v10 - Data Contracts
Pydantic models for type-safe data flow across the system
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class BetType(str, Enum):
    """Types of bets"""
    WIN = "win"
    PLACE = "place"
    EACH_WAY = "each_way"
    EXACTA = "exacta"
    TRIFECTA = "trifecta"


class Going(str, Enum):
    """Track going conditions"""
    FIRM = "firm"
    GOOD_TO_FIRM = "good_to_firm"
    GOOD = "good"
    GOOD_TO_SOFT = "good_to_soft"
    SOFT = "soft"
    HEAVY = "heavy"
    UNKNOWN = "unknown"


class Runner(BaseModel):
    """
    Individual horse/runner in a race
    """
    number: int = Field(..., description="Runner number/draw")
    name: str = Field(..., description="Horse name")
    
    # Form & Ratings
    age: Optional[int] = Field(None, description="Horse age")
    weight: Optional[float] = Field(None, description="Weight carried (kg)")
    or_rating: Optional[int] = Field(None, description="Official Rating")
    ts: Optional[int] = Field(None, description="Timeform Speed Figure")
    rpr: Optional[int] = Field(None, description="Racing Post Rating")
    last6: Optional[List[str]] = Field(None, description="Last 6 form figures")
    
    # Connections
    jockey: Optional[str] = Field(None, description="Jockey name")
    jockey_sr5y: Optional[float] = Field(None, description="Jockey 5-year strike rate")
    trainer: Optional[str] = Field(None, description="Trainer name")
    trainer_sr5y: Optional[float] = Field(None, description="Trainer 5-year strike rate")
    
    # Breeding & Ownership
    breeding: Optional[str] = Field(None, description="Sire x Dam")
    owner: Optional[str] = Field(None, description="Owner name")
    
    # Additional metadata
    days_since_last_run: Optional[int] = None
    career_wins: Optional[int] = None
    career_runs: Optional[int] = None
    
    class Config:
        use_enum_values = True


class Odds(BaseModel):
    """
    Odds for a runner across different markets
    """
    win: Optional[float] = Field(None, description="Win odds (decimal)")
    place: Optional[float] = Field(None, description="Place odds (decimal)")
    
    # Betfair-specific
    bf_win: Optional[float] = Field(None, description="Betfair win price (last traded)")
    bf_place: Optional[float] = Field(None, description="Betfair place price (last traded)")
    bf_back: Optional[float] = Field(None, description="Betfair best back price")
    bf_lay: Optional[float] = Field(None, description="Betfair best lay price")
    bf_volume: Optional[float] = Field(None, description="Betfair matched volume")
    
    # Market depth
    liquidity: Optional[float] = Field(None, description="Total market liquidity")
    
    @validator('win', 'place', 'bf_win', 'bf_place', 'bf_back', 'bf_lay')
    def validate_odds(cls, v):
        """Ensure odds are positive"""
        if v is not None and v <= 0:
            raise ValueError("Odds must be positive")
        return v
    
    def implied_probability_win(self) -> Optional[float]:
        """Calculate implied probability from win odds"""
        if self.win and self.win > 0:
            return 1.0 / self.win
        return None
    
    def implied_probability_bf(self) -> Optional[float]:
        """Calculate implied probability from Betfair odds"""
        if self.bf_win and self.bf_win > 0:
            return 1.0 / self.bf_win
        return None


class Racecard(BaseModel):
    """
    Complete racecard for a single race
    """
    # Race identification
    date: str = Field(..., description="Race date (YYYY-MM-DD)")
    course: str = Field(..., description="Course/track name")
    time: str = Field(..., description="Race time (HH:MM)")
    
    # Race details
    race_id: Optional[str] = Field(None, description="Unique race identifier")
    race_name: Optional[str] = Field(None, description="Race name/title")
    distance: Optional[str] = Field(None, description="Race distance (e.g., '1m 2f')")
    distance_meters: Optional[int] = Field(None, description="Distance in meters")
    going: Optional[Going] = Field(None, description="Track going")
    race_class: Optional[int] = Field(None, description="Race class (1-7)")
    prize_money: Optional[float] = Field(None, description="Total prize money")
    
    # Runners
    runners: List[Runner] = Field(..., description="List of runners in the race")
    
    # Metadata
    num_runners: Optional[int] = Field(None, description="Number of runners")
    non_runners: Optional[List[str]] = Field(None, description="List of non-runners")
    
    @validator('runners')
    def validate_runners(cls, v):
        """Ensure at least one runner"""
        if not v or len(v) == 0:
            raise ValueError("Race must have at least one runner")
        return v
    
    def get_runner_by_number(self, number: int) -> Optional[Runner]:
        """Get runner by number"""
        for runner in self.runners:
            if runner.number == number:
                return runner
        return None
    
    def get_runner_by_name(self, name: str) -> Optional[Runner]:
        """Get runner by name (case-insensitive)"""
        name_lower = name.lower()
        for runner in self.runners:
            if runner.name.lower() == name_lower:
                return runner
        return None


class MarketSnapshot(BaseModel):
    """
    Snapshot of market odds at a specific time
    """
    # Race identification
    date: str = Field(..., description="Race date (YYYY-MM-DD)")
    course: str = Field(..., description="Course/track name")
    time: str = Field(..., description="Race time (HH:MM)")
    
    # Snapshot metadata
    snapshot_time: datetime = Field(..., description="When snapshot was taken")
    market_id: Optional[str] = Field(None, description="Betfair market ID")
    
    # Odds book: runner name/number -> Odds
    book: Dict[str, Odds] = Field(..., description="Odds for each runner")
    
    # Market metadata
    total_matched: Optional[float] = Field(None, description="Total matched on market")
    market_status: Optional[str] = Field(None, description="Market status (open/closed)")
    
    def get_odds(self, runner: str) -> Optional[Odds]:
        """Get odds for a specific runner"""
        return self.book.get(runner)
    
    def overround(self) -> Optional[float]:
        """
        Calculate market overround (sum of implied probabilities)
        >1.0 indicates bookmaker margin
        """
        total_prob = 0.0
        count = 0
        
        for odds in self.book.values():
            if odds.win and odds.win > 0:
                total_prob += 1.0 / odds.win
                count += 1
        
        return total_prob if count > 0 else None


class Overlay(BaseModel):
    """
    Identified overlay opportunity
    """
    runner: str = Field(..., description="Runner name")
    p_model: float = Field(..., description="Model probability")
    p_market: float = Field(..., description="Market-implied probability")
    odds: float = Field(..., description="Decimal odds")
    edge: float = Field(..., description="Expected edge (EV - 1)")
    stake_fraction: float = Field(..., description="Recommended stake as fraction of bankroll")
    
    # Additional context
    confidence: Optional[float] = Field(None, description="Confidence score")
    bet_type: Optional[BetType] = Field(BetType.WIN, description="Recommended bet type")
    
    @validator('edge')
    def validate_edge(cls, v):
        """Ensure edge is positive for overlays"""
        if v <= 0:
            raise ValueError("Overlay must have positive edge")
        return v
    
    def expected_value(self) -> float:
        """Calculate expected value"""
        return self.p_model * self.odds
    
    def roi(self) -> float:
        """Calculate expected ROI"""
        return (self.expected_value() - 1.0) * 100


class BetRecord(BaseModel):
    """
    Record of a placed bet
    """
    # Bet identification
    bet_id: Optional[str] = Field(None, description="Unique bet ID")
    timestamp: datetime = Field(..., description="When bet was placed")
    
    # Race details
    date: str = Field(..., description="Race date")
    course: str = Field(..., description="Course name")
    time: str = Field(..., description="Race time")
    runner: str = Field(..., description="Runner name")
    
    # Bet details
    bet_type: BetType = Field(..., description="Type of bet")
    odds: float = Field(..., description="Odds taken (decimal)")
    stake: float = Field(..., description="Stake amount")
    
    # Model data
    p_model: Optional[float] = Field(None, description="Model probability at bet time")
    p_market: Optional[float] = Field(None, description="Market probability at bet time")
    edge: Optional[float] = Field(None, description="Expected edge")
    
    # Result (filled in after race)
    result_position: Optional[int] = Field(None, description="Finishing position")
    result_won: Optional[bool] = Field(None, description="Whether bet won")
    result_profit: Optional[float] = Field(None, description="Profit/loss")
    result_roi: Optional[float] = Field(None, description="ROI percentage")
    
    def calculate_profit(self, won: bool) -> float:
        """Calculate profit/loss"""
        if won:
            return self.stake * (self.odds - 1.0)
        else:
            return -self.stake
    
    def record_result(self, position: int, won: bool) -> None:
        """Record race result"""
        self.result_position = position
        self.result_won = won
        self.result_profit = self.calculate_profit(won)
        if self.stake > 0:
            self.result_roi = (self.result_profit / self.stake) * 100


class RaceResult(BaseModel):
    """
    Official race result
    """
    # Race identification
    date: str
    course: str
    time: str
    
    # Results
    positions: Dict[int, str] = Field(..., description="Position -> Runner name")
    winning_time: Optional[str] = Field(None, description="Winning time")
    distances: Optional[Dict[int, str]] = Field(None, description="Distances between horses")
    
    # Dividends
    win_dividend: Optional[float] = Field(None, description="Win dividend")
    place_dividends: Optional[Dict[str, float]] = Field(None, description="Place dividends")
    
    def get_winner(self) -> Optional[str]:
        """Get winning horse"""
        return self.positions.get(1)
    
    def get_position(self, runner: str) -> Optional[int]:
        """Get finishing position for a runner"""
        for pos, name in self.positions.items():
            if name.lower() == runner.lower():
                return pos
        return None

