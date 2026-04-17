"""
VÉLØ Oracle - Bankroll Management System
Implements Fractional Kelly Criterion with risk controls
"""
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math


class BetType(Enum):
    """Bet type classifications"""
    WIN = "WIN"
    EACH_WAY = "EW"
    PLACE = "PLACE"
    PASS = "PASS"


@dataclass
class StakeRecommendation:
    """Stake recommendation with reasoning"""
    bet_type: BetType
    stake: float
    kelly_fraction: float
    confidence: float
    max_stake: float
    reasons: List[str]
    risk_level: str


@dataclass
class BankrollState:
    """Current bankroll state"""
    current_balance: float
    starting_balance: float
    peak_balance: float
    daily_pnl: float
    weekly_pnl: float
    current_drawdown_pct: float
    bets_today: int
    losses_in_row: int
    last_bet_time: Optional[datetime]


class RiskLevel(Enum):
    """Risk level classifications"""
    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


class BankrollManager:
    """
    Manages bankroll, stake sizing, and risk controls.
    
    Philosophy:
    - Preserve capital first, grow second
    - Kelly Criterion for optimal stake sizing
    - Fractional Kelly to reduce variance
    - Hard stop-losses to prevent catastrophic losses
    - Dynamic stake adjustment based on performance
    """
    
    def __init__(
        self,
        starting_balance: float = 1000.0,
        kelly_fraction: float = 0.25,  # Quarter Kelly (conservative)
        max_stake_pct: float = 5.0,    # Max 5% of bankroll per bet
        daily_stop_loss_pct: float = 15.0,  # Stop if down 15% in a day
        max_drawdown_pct: float = 25.0,     # Stop if down 25% from peak
        cooldown_hours: int = 24,           # Cooldown after stop-loss
        max_bets_per_day: int = 10          # Max bets per day
    ):
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.peak_balance = starting_balance
        
        # Kelly settings
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct / 100.0
        
        # Risk controls
        self.daily_stop_loss_pct = daily_stop_loss_pct / 100.0
        self.max_drawdown_pct = max_drawdown_pct / 100.0
        self.cooldown_hours = cooldown_hours
        self.max_bets_per_day = max_bets_per_day
        
        # State tracking
        self.daily_start_balance = starting_balance
        self.bets_today = 0
        self.losses_in_row = 0
        self.last_bet_time = None
        self.cooldown_until = None
        self.is_stopped = False
        
    def get_state(self) -> BankrollState:
        """Get current bankroll state"""
        daily_pnl = self.current_balance - self.daily_start_balance
        weekly_pnl = 0.0  # TODO: Track weekly
        
        current_drawdown_pct = (
            (self.peak_balance - self.current_balance) / self.peak_balance * 100
            if self.peak_balance > 0 else 0.0
        )
        
        return BankrollState(
            current_balance=self.current_balance,
            starting_balance=self.starting_balance,
            peak_balance=self.peak_balance,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            current_drawdown_pct=current_drawdown_pct,
            bets_today=self.bets_today,
            losses_in_row=self.losses_in_row,
            last_bet_time=self.last_bet_time
        )
    
    def calculate_stake(
        self,
        win_probability: float,
        odds: float,
        confidence: float,
        bet_type: str = "WIN"
    ) -> StakeRecommendation:
        """
        Calculate optimal stake using Fractional Kelly Criterion.
        
        Kelly Formula: f = (bp - q) / b
        where:
        - f = fraction of bankroll to bet
        - b = decimal odds - 1
        - p = probability of winning
        - q = probability of losing (1 - p)
        
        Args:
            win_probability: Model's predicted win probability (0-1)
            odds: Decimal odds (e.g., 5.0 for 4/1)
            confidence: Model confidence score (0-100)
            bet_type: WIN, EW, or PLACE
        
        Returns:
            StakeRecommendation with stake amount and reasoning
        """
        reasons = []
        
        # Check if betting is allowed
        if self.is_stopped:
            return self._no_bet_recommendation(
                "System is stopped due to stop-loss trigger"
            )
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return self._no_bet_recommendation(
                f"In cooldown period until {self.cooldown_until}"
            )
        
        if self.bets_today >= self.max_bets_per_day:
            return self._no_bet_recommendation(
                f"Daily bet limit reached ({self.max_bets_per_day})"
            )
        
        # Check risk controls
        state = self.get_state()
        
        # Daily stop-loss
        daily_loss_pct = abs(state.daily_pnl / self.daily_start_balance)
        if state.daily_pnl < 0 and daily_loss_pct >= self.daily_stop_loss_pct:
            self._trigger_stop_loss("Daily stop-loss triggered")
            return self._no_bet_recommendation(
                f"Daily stop-loss triggered (-{daily_loss_pct*100:.1f}%)"
            )
        
        # Maximum drawdown
        if state.current_drawdown_pct >= self.max_drawdown_pct:
            self._trigger_stop_loss("Maximum drawdown exceeded")
            return self._no_bet_recommendation(
                f"Maximum drawdown exceeded (-{state.current_drawdown_pct:.1f}%)"
            )
        
        # Calculate Kelly stake
        b = odds - 1.0  # Decimal odds to fractional
        p = win_probability
        q = 1.0 - p
        
        # Kelly fraction
        kelly_f = (b * p - q) / b
        
        # Apply fractional Kelly
        fractional_kelly_f = kelly_f * self.kelly_fraction
        
        # Adjust for confidence
        confidence_multiplier = confidence / 100.0
        adjusted_f = fractional_kelly_f * confidence_multiplier
        
        # Calculate stake
        raw_stake = self.current_balance * adjusted_f
        
        # Apply maximum stake limit
        max_stake = self.current_balance * self.max_stake_pct
        final_stake = min(raw_stake, max_stake)
        
        # Round to 2 decimal places
        final_stake = round(max(final_stake, 0), 2)
        
        # Determine bet type and risk level
        if final_stake < 1.0:
            return self._no_bet_recommendation(
                "Calculated stake too small (< £1)"
            )
        
        # Build reasons
        reasons.append(f"Kelly fraction: {kelly_f*100:.1f}%")
        reasons.append(f"Fractional Kelly ({self.kelly_fraction*100:.0f}%): {fractional_kelly_f*100:.1f}%")
        reasons.append(f"Confidence adjusted: {adjusted_f*100:.1f}%")
        
        if final_stake < raw_stake:
            reasons.append(f"Capped at max stake ({self.max_stake_pct*100:.0f}% of bankroll)")
        
        # Risk level
        stake_pct = final_stake / self.current_balance
        if stake_pct < 0.02:
            risk_level = "Low"
        elif stake_pct < 0.04:
            risk_level = "Medium"
        else:
            risk_level = "High"
        
        return StakeRecommendation(
            bet_type=BetType(bet_type),
            stake=final_stake,
            kelly_fraction=fractional_kelly_f,
            confidence=confidence,
            max_stake=max_stake,
            reasons=reasons,
            risk_level=risk_level
        )
    
    def record_bet_result(
        self,
        stake: float,
        result: str,  # "WON", "PLACED", "LOST"
        returns: float = 0.0
    ):
        """Record a bet result and update bankroll"""
        profit_loss = returns - stake
        self.current_balance += profit_loss
        self.bets_today += 1
        self.last_bet_time = datetime.now()
        
        # Update peak
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Track losing streak
        if result == "LOST":
            self.losses_in_row += 1
        else:
            self.losses_in_row = 0
        
        # Check if we need to trigger stop-loss
        state = self.get_state()
        daily_loss_pct = abs(state.daily_pnl / self.daily_start_balance)
        
        if state.daily_pnl < 0 and daily_loss_pct >= self.daily_stop_loss_pct:
            self._trigger_stop_loss("Daily stop-loss triggered after bet")
        
        if state.current_drawdown_pct >= self.max_drawdown_pct:
            self._trigger_stop_loss("Maximum drawdown exceeded after bet")
    
    def reset_daily(self):
        """Reset daily counters (call at start of each day)"""
        self.daily_start_balance = self.current_balance
        self.bets_today = 0
        
        # Clear cooldown if expired
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            self.cooldown_until = None
            self.is_stopped = False
    
    def _trigger_stop_loss(self, reason: str):
        """Trigger stop-loss and enter cooldown"""
        self.is_stopped = True
        self.cooldown_until = datetime.now() + timedelta(hours=self.cooldown_hours)
        print(f"🚨 STOP-LOSS TRIGGERED: {reason}")
        print(f"   Cooldown until: {self.cooldown_until}")
    
    def _no_bet_recommendation(self, reason: str) -> StakeRecommendation:
        """Return a PASS recommendation"""
        return StakeRecommendation(
            bet_type=BetType.PASS,
            stake=0.0,
            kelly_fraction=0.0,
            confidence=0.0,
            max_stake=0.0,
            reasons=[reason],
            risk_level="None"
        )
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        roi = ((self.current_balance - self.starting_balance) / self.starting_balance) * 100
        
        return {
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "total_pnl": self.current_balance - self.starting_balance,
            "roi_pct": round(roi, 2),
            "current_drawdown_pct": round(
                (self.peak_balance - self.current_balance) / self.peak_balance * 100, 2
            ),
            "bets_today": self.bets_today,
            "losses_in_row": self.losses_in_row,
            "is_stopped": self.is_stopped,
            "cooldown_until": self.cooldown_until
        }
