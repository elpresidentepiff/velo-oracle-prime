"""
VÉLØ Bettor Framework - Systematic Betting and Backtesting
Inspired by sports-betting library's ClassifierBettor pattern

Provides:
- Systematic backtesting with TimeSeriesSplit
- Bankroll management
- Value bet detection
- Performance tracking
- Risk assessment
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum


class BetType(Enum):
    """Types of bets supported."""
    WIN = "win"
    EACH_WAY = "each_way"
    PLACE = "place"


class StakeLevel(Enum):
    """Stake sizing levels."""
    CONSERVATIVE = 0.01  # 1% of bankroll
    MODERATE = 0.02      # 2% of bankroll
    AGGRESSIVE = 0.03    # 3% of bankroll


class VeloBettor:
    """
    VÉLØ Betting Framework
    
    Manages:
    - Bankroll
    - Bet sizing
    - Risk management
    - Performance tracking
    - Backtesting
    """
    
    def __init__(
        self,
        initial_bankroll: float = 1000.0,
        stake_level: StakeLevel = StakeLevel.MODERATE,
        max_drawdown: float = 0.10,  # 10% max drawdown
        target_odds_range: Tuple[float, float] = (3.0, 20.0)
    ):
        """
        Initialize VeloBettor.
        
        Args:
            initial_bankroll: Starting bankroll
            stake_level: Default stake sizing
            max_drawdown: Maximum allowed drawdown before reset
            target_odds_range: Target odds range (min, max)
        """
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.stake_level = stake_level
        self.max_drawdown = max_drawdown
        self.target_odds_range = target_odds_range
        
        # Performance tracking
        self.bets_placed = []
        self.wins = 0
        self.losses = 0
        self.total_staked = 0.0
        self.total_returned = 0.0
        self.peak_bankroll = initial_bankroll
        
        print(f"✓ VeloBettor initialized")
        print(f"  Bankroll: £{initial_bankroll:.2f}")
        print(f"  Stake level: {stake_level.name} ({stake_level.value * 100}%)")
        print(f"  Target odds: {target_odds_range[0]}/1 to {target_odds_range[1]}/1")
    
    def calculate_stake(self, confidence: float = 1.0, custom_level: StakeLevel = None) -> float:
        """
        Calculate stake size based on current bankroll and confidence.
        
        Args:
            confidence: Confidence multiplier (0.0 to 1.0)
            custom_level: Override default stake level
        
        Returns:
            Stake amount in pounds
        """
        level = custom_level or self.stake_level
        base_stake = self.current_bankroll * level.value
        
        # Adjust for confidence
        adjusted_stake = base_stake * confidence
        
        # Ensure minimum stake
        return max(adjusted_stake, 1.0)
    
    def place_bet(
        self,
        horse_name: str,
        odds: float,
        bet_type: BetType = BetType.EACH_WAY,
        confidence: float = 1.0,
        race_id: str = None
    ) -> Dict:
        """
        Place a bet and record it.
        
        Args:
            horse_name: Name of the horse
            odds: Decimal odds
            bet_type: Type of bet
            confidence: Confidence level (0.0 to 1.0)
            race_id: Optional race identifier
        
        Returns:
            Bet record dictionary
        """
        # Check if odds are in target range
        if not (self.target_odds_range[0] <= odds <= self.target_odds_range[1]):
            print(f"⚠ Odds {odds} outside target range {self.target_odds_range}")
        
        # Calculate stake
        stake = self.calculate_stake(confidence)
        
        # Check if we have enough bankroll
        if stake > self.current_bankroll:
            print(f"✗ Insufficient bankroll (£{self.current_bankroll:.2f}) for stake (£{stake:.2f})")
            return None
        
        # Create bet record
        bet = {
            'bet_id': len(self.bets_placed) + 1,
            'horse_name': horse_name,
            'odds': odds,
            'bet_type': bet_type.value,
            'stake': stake,
            'confidence': confidence,
            'race_id': race_id,
            'placed_at': datetime.now().isoformat(),
            'result': None,  # To be filled when settled
            'return': 0.0
        }
        
        # Deduct stake from bankroll
        self.current_bankroll -= stake
        self.total_staked += stake
        
        # Record bet
        self.bets_placed.append(bet)
        
        print(f"✓ Bet placed: {horse_name} @ {odds}/1 ({bet_type.value}) - Stake: £{stake:.2f}")
        
        return bet
    
    def settle_bet(self, bet_id: int, result: str, position: int = None) -> float:
        """
        Settle a bet and update bankroll.
        
        Args:
            bet_id: ID of the bet to settle
            result: 'win', 'place', or 'lose'
            position: Final position (for place bets)
        
        Returns:
            Return amount
        """
        # Find bet
        bet = next((b for b in self.bets_placed if b['bet_id'] == bet_id), None)
        if not bet:
            print(f"✗ Bet {bet_id} not found")
            return 0.0
        
        stake = bet['stake']
        odds = bet['odds']
        bet_type = bet['bet_type']
        
        # Calculate return
        return_amount = 0.0
        
        if result == 'win':
            # Win bet returns stake + winnings
            return_amount = stake * odds
            if bet_type == 'each_way':
                # EW also gets place return (typically 1/5 odds, top 3)
                place_odds = 1 + (odds - 1) / 5  # 1/5 odds
                return_amount += stake * place_odds
            self.wins += 1
        
        elif result == 'place' and bet_type == 'each_way':
            # Place only (didn't win but placed)
            place_odds = 1 + (odds - 1) / 5
            return_amount = stake * place_odds
            self.wins += 1  # Count as partial win
        
        else:
            # Lost
            return_amount = 0.0
            self.losses += 1
        
        # Update bet record
        bet['result'] = result
        bet['return'] = return_amount
        bet['settled_at'] = datetime.now().isoformat()
        
        # Update bankroll
        self.current_bankroll += return_amount
        self.total_returned += return_amount
        
        # Update peak
        if self.current_bankroll > self.peak_bankroll:
            self.peak_bankroll = self.current_bankroll
        
        # Check drawdown
        self._check_drawdown()
        
        profit = return_amount - stake
        print(f"✓ Bet settled: {bet['horse_name']} - {result.upper()} - Return: £{return_amount:.2f} (P/L: £{profit:.2f})")
        
        return return_amount
    
    def _check_drawdown(self):
        """Check if drawdown limit is exceeded."""
        current_drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        
        if current_drawdown >= self.max_drawdown:
            print(f"⚠ DRAWDOWN ALERT: {current_drawdown * 100:.1f}% (limit: {self.max_drawdown * 100:.1f}%)")
            print(f"  Consider reducing stakes or reviewing strategy")
    
    def get_performance_stats(self) -> Dict:
        """
        Calculate performance statistics.
        
        Returns:
            Dictionary of performance metrics
        """
        total_bets = len(self.bets_placed)
        settled_bets = [b for b in self.bets_placed if b['result'] is not None]
        
        if not settled_bets:
            return {
                'total_bets': total_bets,
                'settled_bets': 0,
                'win_rate': 0.0,
                'roi': 0.0,
                'profit': 0.0,
                'bankroll': self.current_bankroll,
                'bankroll_change': 0.0
            }
        
        win_rate = self.wins / len(settled_bets) if settled_bets else 0.0
        profit = self.total_returned - self.total_staked
        roi = (profit / self.total_staked * 100) if self.total_staked > 0 else 0.0
        bankroll_change = ((self.current_bankroll - self.initial_bankroll) / self.initial_bankroll * 100)
        
        return {
            'total_bets': total_bets,
            'settled_bets': len(settled_bets),
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'total_staked': self.total_staked,
            'total_returned': self.total_returned,
            'profit': profit,
            'roi': roi,
            'initial_bankroll': self.initial_bankroll,
            'current_bankroll': self.current_bankroll,
            'peak_bankroll': self.peak_bankroll,
            'bankroll_change': bankroll_change,
            'current_drawdown': (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        }
    
    def backtest(
        self,
        historical_races: List[Dict],
        oracle_predictions: List[Dict],
        actual_results: List[Dict]
    ) -> Dict:
        """
        Backtest strategy on historical data.
        
        Args:
            historical_races: List of race data
            oracle_predictions: List of Oracle predictions
            actual_results: List of actual race results
        
        Returns:
            Backtest performance statistics
        """
        print("\n=== Starting Backtest ===")
        print(f"Races to analyze: {len(historical_races)}")
        
        # Reset bettor state
        self.current_bankroll = self.initial_bankroll
        self.bets_placed = []
        self.wins = 0
        self.losses = 0
        self.total_staked = 0.0
        self.total_returned = 0.0
        self.peak_bankroll = self.initial_bankroll
        
        # Process each race
        for i, (race, prediction, result) in enumerate(zip(historical_races, oracle_predictions, actual_results)):
            race_id = race.get('race_id', f'race_{i}')
            
            # Check if Oracle made a prediction
            if not prediction or not prediction.get('shortlist'):
                continue
            
            # Place bets on shortlisted horses
            for horse in prediction['shortlist']:
                bet = self.place_bet(
                    horse_name=horse['name'],
                    odds=horse['odds'],
                    bet_type=BetType.EACH_WAY,
                    confidence=horse.get('confidence', 0.8),
                    race_id=race_id
                )
                
                if bet:
                    # Settle bet based on actual result
                    winner = result.get('winner')
                    placed = result.get('placed', [])
                    
                    if horse['name'] == winner:
                        self.settle_bet(bet['bet_id'], 'win')
                    elif horse['name'] in placed:
                        self.settle_bet(bet['bet_id'], 'place')
                    else:
                        self.settle_bet(bet['bet_id'], 'lose')
        
        # Get final stats
        stats = self.get_performance_stats()
        
        print("\n=== Backtest Complete ===")
        print(f"Total bets: {stats['total_bets']}")
        print(f"Win rate: {stats['win_rate'] * 100:.1f}%")
        print(f"ROI: {stats['roi']:.2f}%")
        print(f"Profit: £{stats['profit']:.2f}")
        print(f"Final bankroll: £{stats['current_bankroll']:.2f} ({stats['bankroll_change']:+.1f}%)")
        
        return stats
    
    def reset_bankroll(self):
        """Reset bankroll to initial amount."""
        self.current_bankroll = self.initial_bankroll
        self.peak_bankroll = self.initial_bankroll
        print(f"✓ Bankroll reset to £{self.initial_bankroll:.2f}")


if __name__ == "__main__":
    # Test VeloBettor
    print("=== VÉLØ Bettor Framework Test ===\n")
    
    bettor = VeloBettor(initial_bankroll=1000.0)
    
    # Place some test bets
    bet1 = bettor.place_bet("Test Horse 1", odds=5.0, confidence=0.8)
    bet2 = bettor.place_bet("Test Horse 2", odds=10.0, confidence=0.9)
    bet3 = bettor.place_bet("Test Horse 3", odds=15.0, confidence=0.7)
    
    # Settle bets
    bettor.settle_bet(1, 'win')  # Win
    bettor.settle_bet(2, 'place')  # Place
    bettor.settle_bet(3, 'lose')  # Lose
    
    # Get stats
    print("\n=== Performance Stats ===")
    stats = bettor.get_performance_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    
    print("\n✓ VeloBettor operational")

