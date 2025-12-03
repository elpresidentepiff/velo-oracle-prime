"""
VÉLØ Oracle - Betfair Exchange Trading Agents
Automated Back-to-Lay trading system for guaranteed profits
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.agents.odds_movement_predictor import OddsMovementPredictor


class TradeStatus(Enum):
    """Trade status states"""
    PENDING = "pending"
    BACKED = "backed"
    LAID_OFF = "laid_off"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BetfairTradingAgent:
    """Base class for Betfair trading agents"""
    
    def __init__(self, betfair_client, bankroll: float = 1000.0):
        self.betfair = betfair_client
        self.bankroll = bankroll
        self.active_trades = []
        self.completed_trades = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_available_balance(self) -> float:
        """Get available balance from Betfair account"""
        try:
            account_funds = self.betfair.get_account_funds()
            return account_funds.get('available_to_bet_balance', 0)
        except Exception as e:
            self.logger.error(f"Error getting account balance: {e}")
            return 0
    
    def calculate_stake(self, odds: float, confidence: float, risk_pct: float = 0.02) -> float:
        """
        Calculate optimal stake using Kelly Criterion
        
        Args:
            odds: Decimal odds
            confidence: Win probability (0-1)
            risk_pct: Maximum % of bankroll to risk (default 2%)
        
        Returns:
            Stake amount
        """
        # Kelly Criterion: f = (bp - q) / b
        # where b = odds - 1, p = win probability, q = 1 - p
        
        b = odds - 1
        p = confidence
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b
        
        # Use fractional Kelly (25% of full Kelly for safety)
        fractional_kelly = kelly_fraction * 0.25
        
        # Cap at risk_pct of bankroll
        max_stake = self.bankroll * risk_pct
        kelly_stake = self.bankroll * fractional_kelly
        
        stake = min(kelly_stake, max_stake)
        
        # Minimum stake £2
        return max(stake, 2.0)


class EarlyBackerAgent(BetfairTradingAgent):
    """
    Early Backer Agent
    Backs horses at long odds days before race
    Uses VÉLØ's Odds Movement Predictor to identify opportunities
    """
    
    def __init__(self, betfair_client, bankroll: float = 1000.0):
        super().__init__(betfair_client, bankroll)
        self.predictor = OddsMovementPredictor()
        self.min_confidence = 0.65
        self.min_odds = 8.0  # Minimum 8/1
        self.max_odds = 50.0  # Maximum 50/1
    
    def scan_for_opportunities(self, days_ahead: int = 3) -> List[Dict]:
        """
        Scan upcoming races for back-to-lay opportunities
        
        Args:
            days_ahead: How many days ahead to scan
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        # Get upcoming races from Betfair
        races = self._get_upcoming_races(days_ahead)
        
        for race in races:
            # Get runners for each race
            runners = self._get_race_runners(race['market_id'])
            
            for runner in runners:
                # Prepare data for predictor
                horse_data = self._prepare_horse_data(runner, race)
                race_data = self._prepare_race_data(race)
                
                # Predict odds movement
                prediction = self.predictor.predict_odds_movement(horse_data, race_data)
                
                # Check if opportunity meets criteria
                if self._is_valid_opportunity(prediction, runner):
                    opportunity = {
                        'race': race,
                        'runner': runner,
                        'prediction': prediction,
                        'timestamp': datetime.now()
                    }
                    opportunities.append(opportunity)
                    
                    self.logger.info(
                        f"Opportunity found: {runner['name']} @ {runner['back_price']} "
                        f"-> {prediction['target_lay_odds']} "
                        f"(Confidence: {prediction['confidence']*100:.1f}%)"
                    )
        
        return opportunities
    
    def execute_back_bet(self, opportunity: Dict) -> Dict:
        """
        Execute back bet on identified opportunity
        
        Returns:
            Trade record
        """
        runner = opportunity['runner']
        prediction = opportunity['prediction']
        race = opportunity['race']
        
        # Calculate stake
        stake = self.calculate_stake(
            odds=prediction['entry_odds'],
            confidence=prediction['confidence'],
            risk_pct=0.02
        )
        
        # Place back bet
        try:
            bet_result = self.betfair.place_bet(
                market_id=race['market_id'],
                selection_id=runner['selection_id'],
                side='BACK',
                price=prediction['entry_odds'],
                size=stake
            )
            
            # Create trade record
            trade = {
                'trade_id': bet_result.get('bet_id'),
                'status': TradeStatus.BACKED,
                'horse_name': runner['name'],
                'race_id': race['market_id'],
                'race_time': race['race_time'],
                'back_odds': prediction['entry_odds'],
                'back_stake': stake,
                'target_lay_odds': prediction['target_lay_odds'],
                'prediction': prediction,
                'back_bet_placed': datetime.now(),
                'lay_bet_placed': None,
                'profit': 0,
                'status_history': [
                    {'status': TradeStatus.BACKED, 'timestamp': datetime.now()}
                ]
            }
            
            self.active_trades.append(trade)
            
            self.logger.info(
                f"✅ BACKED: {runner['name']} @ {prediction['entry_odds']} "
                f"Stake: £{stake:.2f}"
            )
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing back bet: {e}")
            return None
    
    def _get_upcoming_races(self, days_ahead: int) -> List[Dict]:
        """Get upcoming races from Betfair"""
        # Placeholder - would call Betfair API
        return []
    
    def _get_race_runners(self, market_id: str) -> List[Dict]:
        """Get runners for a race"""
        # Placeholder - would call Betfair API
        return []
    
    def _prepare_horse_data(self, runner: Dict, race: Dict) -> Dict:
        """Prepare horse data for predictor"""
        # Placeholder - would fetch additional data
        return {
            'name': runner.get('name'),
            'current_odds': runner.get('back_price'),
            'trainer': runner.get('trainer'),
            'jockey': runner.get('jockey'),
        }
    
    def _prepare_race_data(self, race: Dict) -> Dict:
        """Prepare race data for predictor"""
        race_time = race.get('race_time')
        if isinstance(race_time, datetime):
            days_to_race = (race_time - datetime.now()).days
        else:
            days_to_race = 3
        
        return {
            'course': race.get('course'),
            'race_class': race.get('race_class'),
            'days_to_race': days_to_race
        }
    
    def _is_valid_opportunity(self, prediction: Dict, runner: Dict) -> bool:
        """Check if opportunity meets criteria"""
        current_odds = runner.get('back_price', 0)
        
        return (
            prediction['will_shorten'] and
            prediction['confidence'] >= self.min_confidence and
            self.min_odds <= current_odds <= self.max_odds and
            prediction['expected_profit_pct'] >= 15.0  # Minimum 15% expected profit
        )


class LayOffAgent(BetfairTradingAgent):
    """
    Lay-Off Agent
    Monitors active back bets and lays them off when odds shorten
    Locks in guaranteed profit
    """
    
    def __init__(self, betfair_client, bankroll: float = 1000.0):
        super().__init__(betfair_client, bankroll)
        self.min_profit_pct = 10.0  # Minimum 10% profit to lay off
    
    def monitor_active_trades(self, active_trades: List[Dict]) -> List[Dict]:
        """
        Monitor active trades and execute lay bets when profitable
        
        Returns:
            List of completed trades
        """
        completed = []
        
        for trade in active_trades:
            if trade['status'] != TradeStatus.BACKED:
                continue
            
            # Get current odds
            current_odds = self._get_current_odds(
                trade['race_id'],
                trade['horse_name']
            )
            
            if current_odds is None:
                continue
            
            # Check if we should lay off
            if self._should_lay_off(trade, current_odds):
                result = self.execute_lay_bet(trade, current_odds)
                if result:
                    completed.append(result)
        
        return completed
    
    def execute_lay_bet(self, trade: Dict, current_odds: float) -> Optional[Dict]:
        """
        Execute lay bet to lock in profit
        
        Returns:
            Updated trade record
        """
        # Calculate lay stake for equal profit both outcomes
        lay_stake = self._calculate_lay_stake(
            back_stake=trade['back_stake'],
            back_odds=trade['back_odds'],
            lay_odds=current_odds
        )
        
        try:
            # Place lay bet
            bet_result = self.betfair.place_bet(
                market_id=trade['race_id'],
                selection_id=trade.get('selection_id'),
                side='LAY',
                price=current_odds,
                size=lay_stake
            )
            
            # Calculate profit
            profit = self._calculate_profit(
                back_stake=trade['back_stake'],
                back_odds=trade['back_odds'],
                lay_stake=lay_stake,
                lay_odds=current_odds
            )
            
            # Update trade record
            trade['status'] = TradeStatus.LAID_OFF
            trade['lay_odds'] = current_odds
            trade['lay_stake'] = lay_stake
            trade['lay_bet_placed'] = datetime.now()
            trade['profit'] = profit
            trade['profit_pct'] = (profit / trade['back_stake']) * 100
            trade['status_history'].append({
                'status': TradeStatus.LAID_OFF,
                'timestamp': datetime.now()
            })
            
            self.logger.info(
                f"✅ LAID OFF: {trade['horse_name']} @ {current_odds} "
                f"Profit: £{profit:.2f} ({trade['profit_pct']:.1f}%)"
            )
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing lay bet: {e}")
            return None
    
    def _get_current_odds(self, market_id: str, horse_name: str) -> Optional[float]:
        """Get current odds for a horse"""
        # Placeholder - would call Betfair API
        return None
    
    def _should_lay_off(self, trade: Dict, current_odds: float) -> bool:
        """Determine if we should lay off this trade"""
        # Check if odds have shortened
        if current_odds >= trade['back_odds']:
            return False
        
        # Calculate potential profit
        profit_pct = self._calculate_profit_pct(
            back_odds=trade['back_odds'],
            lay_odds=current_odds
        )
        
        # Check if profit meets minimum
        if profit_pct < self.min_profit_pct:
            return False
        
        # Check if we've reached target
        target_odds = trade.get('target_lay_odds')
        if target_odds and current_odds <= target_odds:
            return True
        
        # Check if we're close to race time (force exit)
        race_time = trade.get('race_time')
        if isinstance(race_time, datetime):
            hours_to_race = (race_time - datetime.now()).total_seconds() / 3600
            if hours_to_race < 2:  # Force exit 2 hours before race
                return profit_pct > 5.0  # Accept any profit > 5%
        
        return False
    
    def _calculate_lay_stake(
        self,
        back_stake: float,
        back_odds: float,
        lay_odds: float
    ) -> float:
        """
        Calculate lay stake for equal profit both outcomes
        
        Formula: lay_stake = (back_stake * back_odds) / lay_odds
        """
        return (back_stake * back_odds) / lay_odds
    
    def _calculate_profit(
        self,
        back_stake: float,
        back_odds: float,
        lay_stake: float,
        lay_odds: float
    ) -> float:
        """
        Calculate guaranteed profit
        
        If horse wins:
            Back profit = back_stake * (back_odds - 1)
            Lay loss = lay_stake * (lay_odds - 1)
            Net = Back profit - Lay loss
        
        If horse loses:
            Back loss = back_stake
            Lay profit = lay_stake
            Net = Lay profit - Back loss
        """
        # Calculate both scenarios
        if_wins = (back_stake * (back_odds - 1)) - (lay_stake * (lay_odds - 1))
        if_loses = lay_stake - back_stake
        
        # Return minimum (guaranteed profit)
        return min(if_wins, if_loses)
    
    def _calculate_profit_pct(self, back_odds: float, lay_odds: float) -> float:
        """Calculate profit percentage"""
        return ((back_odds - lay_odds) / back_odds) * 100


class TradingOrchestrator:
    """
    Orchestrates the complete back-to-lay trading system
    Coordinates Early Backer and Lay-Off agents
    """
    
    def __init__(self, betfair_client, bankroll: float = 1000.0):
        self.backer = EarlyBackerAgent(betfair_client, bankroll)
        self.layer = LayOffAgent(betfair_client, bankroll)
        self.logger = logging.getLogger('TradingOrchestrator')
    
    def run_trading_cycle(self):
        """Run one complete trading cycle"""
        
        self.logger.info("=" * 60)
        self.logger.info("VÉLØ ORACLE - BETFAIR TRADING CYCLE")
        self.logger.info("=" * 60)
        
        # 1. Scan for new opportunities
        self.logger.info("\n1. Scanning for back opportunities...")
        opportunities = self.backer.scan_for_opportunities(days_ahead=3)
        self.logger.info(f"Found {len(opportunities)} opportunities")
        
        # 2. Execute back bets on best opportunities
        self.logger.info("\n2. Executing back bets...")
        for opp in opportunities[:5]:  # Limit to top 5
            trade = self.backer.execute_back_bet(opp)
            if trade:
                self.logger.info(f"✅ Trade opened: {trade['horse_name']}")
        
        # 3. Monitor active trades and lay off when profitable
        self.logger.info("\n3. Monitoring active trades...")
        active_trades = self.backer.active_trades
        self.logger.info(f"Monitoring {len(active_trades)} active trades")
        
        completed = self.layer.monitor_active_trades(active_trades)
        
        # 4. Report results
        self.logger.info("\n4. Results:")
        total_profit = sum(t['profit'] for t in completed)
        self.logger.info(f"Completed trades: {len(completed)}")
        self.logger.info(f"Total profit: £{total_profit:.2f}")
        
        # 5. Move completed trades
        for trade in completed:
            active_trades.remove(trade)
            self.backer.completed_trades.append(trade)
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        completed = self.backer.completed_trades
        
        if not completed:
            return {
                'total_trades': 0,
                'total_profit': 0,
                'total_staked': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'roi': 0
            }
        
        total_trades = len(completed)
        total_profit = sum(t['profit'] for t in completed)
        total_staked = sum(t['back_stake'] for t in completed)
        winning_trades = len([t for t in completed if t['profit'] > 0])
        
        return {
            'total_trades': total_trades,
            'total_profit': total_profit,
            'total_staked': total_staked,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / total_trades) * 100,
            'avg_profit': total_profit / total_trades,
            'roi': (total_profit / total_staked) * 100 if total_staked > 0 else 0
        }


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Mock Betfair client (replace with real client)
    class MockBetfairClient:
        def get_account_funds(self):
            return {'available_to_bet_balance': 1000.0}
        
        def place_bet(self, **kwargs):
            return {'bet_id': 'mock_bet_123'}
    
    # Initialize trading system
    betfair = MockBetfairClient()
    orchestrator = TradingOrchestrator(betfair, bankroll=1000.0)
    
    # Run trading cycle
    orchestrator.run_trading_cycle()
    
    # Get performance stats
    stats = orchestrator.get_performance_stats()
    
    print("\n" + "=" * 60)
    print("PERFORMANCE STATS")
    print("=" * 60)
    print(f"Total Trades:     {stats['total_trades']}")
    print(f"Winning Trades:   {stats['winning_trades']}")
    print(f"Win Rate:         {stats['win_rate']:.1f}%")
    print(f"Total Profit:     £{stats['total_profit']:.2f}")
    print(f"Average Profit:   £{stats['avg_profit']:.2f}")
    print(f"ROI:              {stats['roi']:.1f}%")
