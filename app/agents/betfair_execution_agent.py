"""
Betfair Execution Agent
Translates VÉLØ intelligence (Oracle + Playbooks) into Betfair orders
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

from app.integrations.betfair_client import BetfairClient, BetfairMode
from app.oracle.services.oracle_analyzer import OracleAnalyzer
from app.playbooks.playbook_orchestrator import create_playbook_orchestrator

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Betfair order sides"""
    BACK = "BACK"
    LAY = "LAY"


class BankrollManager:
    """
    Manages bankroll, exposure, and risk limits
    
    Guardrails:
    - Max liability per race
    - Max daily loss
    - Max concurrent races
    - Stress-based throttling
    """
    
    def __init__(
        self,
        starting_bank: float = 1000.0,
        max_liability_per_race_pct: float = 0.05,  # 5%
        max_daily_loss_pct: float = 0.20,  # 20%
        max_concurrent_races: int = 3
    ):
        self.starting_bank = starting_bank
        self.current_bank = starting_bank
        self.max_liability_per_race_pct = max_liability_per_race_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_concurrent_races = max_concurrent_races
        
        self.daily_pnl = 0.0
        self.current_exposure = 0.0
        self.active_races = set()
        
        logger.info(
            f"BankrollManager initialized: £{starting_bank} bank, "
            f"{max_liability_per_race_pct*100}% max per race, "
            f"{max_daily_loss_pct*100}% max daily loss"
        )
    
    def can_risk(self, liability: float) -> bool:
        """Check if we can risk this liability"""
        # Check per-race limit
        max_per_race = self.current_bank * self.max_liability_per_race_pct
        if liability > max_per_race:
            logger.warning(f"Liability £{liability} exceeds max per race £{max_per_race}")
            return False
        
        # Check daily loss limit
        max_daily_loss = self.starting_bank * self.max_daily_loss_pct
        if self.daily_pnl < -max_daily_loss:
            logger.warning(f"Daily loss limit hit: £{self.daily_pnl}")
            return False
        
        # Check concurrent races
        if len(self.active_races) >= self.max_concurrent_races:
            logger.warning(f"Max concurrent races ({self.max_concurrent_races}) reached")
            return False
        
        return True
    
    def register_exposure(self, order: Dict) -> None:
        """Register exposure from an order"""
        if order['side'] == OrderSide.LAY:
            liability = order['size'] * (order['price'] - 1)
        else:  # BACK
            liability = order['size']
        
        self.current_exposure += liability
        self.active_races.add(order['market_id'])
        
        logger.info(
            f"Registered exposure: £{liability:.2f} "
            f"(total: £{self.current_exposure:.2f}, active races: {len(self.active_races)})"
        )
    
    def settle_race(self, market_id: str, pnl: float) -> None:
        """Settle a race and update bankroll"""
        self.current_bank += pnl
        self.daily_pnl += pnl
        self.active_races.discard(market_id)
        
        logger.info(
            f"Race settled: {'+' if pnl >= 0 else ''}{pnl:.2f} "
            f"(bank: £{self.current_bank:.2f}, daily P&L: {'+' if self.daily_pnl >= 0 else ''}{self.daily_pnl:.2f})"
        )
    
    def reset_daily(self) -> None:
        """Reset daily counters"""
        self.daily_pnl = 0.0
        logger.info("Daily counters reset")


class BetfairExecutionAgent:
    """
    Executes VÉLØ intelligence on Betfair
    
    Flow:
    1. Pull Betfair prices
    2. Build Oracle input
    3. Get Playbook directive
    4. Translate directive → orders
    5. Execute orders (with guardrails)
    6. Log to VETP + sentient state
    """
    
    def __init__(
        self,
        betfair_client: BetfairClient,
        bankroll_manager: BankrollManager,
        min_minutes_to_off: int = 10,
        max_minutes_to_off: int = 1
    ):
        self.betfair = betfair_client
        self.bankroll = bankroll_manager
        self.min_minutes_to_off = min_minutes_to_off
        self.max_minutes_to_off = max_minutes_to_off
        
        # Initialize intelligence systems
        self.oracle = OracleAnalyzer()
        self.playbooks = create_playbook_orchestrator()
        
        logger.info("BetfairExecutionAgent initialized")
    
    def run_pre_race_cycle(
        self,
        race_id: str,
        race_data: Dict,
        betfair_mapping: Dict
    ) -> Dict:
        """
        Run complete pre-race analysis and execution cycle
        
        Args:
            race_id: Internal race ID
            race_data: Internal race data
            betfair_mapping: Betfair market/selection mapping
        
        Returns:
            Execution summary dict
        """
        logger.info(f"=== PRE-RACE CYCLE: {race_id} ===")
        
        # 1. Pull Betfair prices
        market_book = self.betfair.get_market_book([betfair_mapping['market_id']])
        
        if not market_book:
            logger.error(f"Failed to get market book for {betfair_mapping['market_id']}")
            return {'status': 'ERROR', 'reason': 'Failed to get market book'}
        
        snapshot = self._build_market_snapshot(race_data, market_book, betfair_mapping)
        
        # 2. Build Oracle input
        race_data_oracle, runners_oracle, market_data_oracle = self._build_oracle_input(race_data, snapshot)
        
        # 3. Run Oracle analysis
        oracle_output = self.oracle.analyze_race(race_data_oracle, runners_oracle, market_data_oracle)
        
        # 4. Convert Oracle output to Playbook input format
        playbook_input = self._convert_oracle_to_playbook_input(oracle_output)
        
        # 5. Run Playbook orchestrator
        playbook_output = self.playbooks.analyze_race(playbook_input)
        
        # 5. Translate directive to orders
        orders = self._translate_directive_to_orders(
            playbook_output,
            betfair_mapping,
            snapshot
        )
        
        # 6. Execute orders (with guardrails)
        executed_orders = self._execute_orders(orders, betfair_mapping['market_id'])
        
        # 7. Build execution summary
        summary = {
            'status': 'SUCCESS',
            'race_id': race_id,
            'market_id': betfair_mapping['market_id'],
            'timestamp': datetime.utcnow().isoformat(),
            'oracle': {
                'narrative_disruption': oracle_output.oracle_view.narrative.disruption_score,
                'mpi': oracle_output.oracle_view.manipulation.manipulation_probability_index,
                'chaos_bloom': oracle_output.oracle_view.chaos.chaos_bloom_score,
                'verdict': oracle_output.oracle_view.verdict.one_sentence_truth
            },
            'playbook': {
                'doctrine': playbook_output['attack']['doctrine'],
                'directive': playbook_output['execution']['positioning_directive'],
                'confidence': playbook_output['execution']['confidence']
            },
            'orders': executed_orders,
            'total_liability': sum(o.get('liability', 0) for o in executed_orders)
        }
        
        logger.info(
            f"✅ Pre-race cycle complete: {len(executed_orders)} orders, "
            f"£{summary['total_liability']:.2f} liability"
        )
        
        return summary
    
    def _build_market_snapshot(
        self,
        race_data: Dict,
        market_book: Dict,
        betfair_mapping: Dict
    ) -> Dict:
        """Build unified market snapshot"""
        market_id = betfair_mapping['market_id']
        book = market_book[market_id]
        
        # Merge internal data with Betfair prices
        runners = []
        for internal_runner in race_data['runners']:
            runner_name = internal_runner['name']
            selection_id = betfair_mapping['runner_mappings'].get(runner_name)
            
            if not selection_id:
                continue
            
            # Find Betfair runner
            betfair_runner = next(
                (r for r in book['runners'] if r['selection_id'] == selection_id),
                None
            )
            
            if not betfair_runner:
                continue
            
            # Get best back/lay prices
            back_prices = betfair_runner['ex']['available_to_back']
            lay_prices = betfair_runner['ex']['available_to_lay']
            
            best_back = back_prices[0]['price'] if back_prices else None
            best_lay = lay_prices[0]['price'] if lay_prices else None
            
            runners.append({
                'name': runner_name,
                'selection_id': selection_id,
                'odds_decimal': best_back or best_lay or internal_runner.get('odds_decimal', 5.0),
                'best_back': best_back,
                'best_lay': best_lay,
                'last_price_traded': betfair_runner.get('last_price_traded'),
                'status': betfair_runner['status'],
                **internal_runner  # Include all internal data
            })
        
        return {
            'market_id': market_id,
            'status': book['status'],
            'inplay': book['inplay'],
            'total_matched': book['total_matched'],
            'runners': runners,
            **race_data  # Include all race data
        }
    
    def _build_oracle_input(self, race_data: Dict, snapshot: Dict) -> tuple:
        """Build Oracle input from race data and market snapshot"""
        # Oracle needs 3 separate args: race_data, runners, market_data
        
        oracle_race_data = {
            'race_id': race_data.get('race_id'),
            'venue': race_data.get('venue'),
            'distance': race_data.get('distance'),
            'class_level': race_data.get('class_level'),
            'meeting': race_data.get('venue'),
            'off_time': race_data.get('off_time')
        }
        
        oracle_runners = snapshot['runners']
        
        oracle_market_data = {
            'total_matched': snapshot.get('total_matched', 0),
            'status': snapshot.get('status', 'OPEN'),
            'inplay': snapshot.get('inplay', False)
        }
        
        return oracle_race_data, oracle_runners, oracle_market_data
    
    def _convert_oracle_to_playbook_input(self, oracle_output) -> Dict:
        """Convert Oracle DualLayerReport to Playbook input dict"""
        oracle_view = oracle_output.oracle_view
        
        return {
            'narrative': {
                'disruption_score': oracle_view.narrative.narrative_disruption_score,
                'weaponized_story': oracle_view.narrative.primary_story,
                'narrative_horse': oracle_view.context.market_snapshot.fav_name
            },
            'manipulation': {
                'mpi': oracle_view.manipulation.mpi_score,
                'integrity_score': 100 - oracle_view.manipulation.mpi_score,
                'trap_indicators': [oracle_view.manipulation.oracle_mpi_note]
            },
            'energy': {
                'profiles': [
                    {
                        'horse_name': p.horse_name,
                        'power_score': p.power_score,
                        'fragility_score': p.fragility_score
                    }
                    for p in oracle_view.energy.profiles
                ]
            },
            'chaos': {
                'chaos_bloom_score': oracle_view.chaos.chaos_bloom_score,
                'chaos_zones': oracle_view.chaos.chaos_zones
            },
            'house': {
                'comfort_zones': oracle_view.house.comfort_zones,
                'discomfort_zones': oracle_view.house.discomfort_zones
            },
            'vetp': {
                'pattern_matches': oracle_view.vetp.pattern_matches if oracle_view.vetp else []
            },
            'verdict': {
                'one_sentence_truth': oracle_view.verdict.one_sentence_truth,
                'primary_threat_cluster': oracle_view.verdict.primary_threat_cluster
            }
        }
    
    def _translate_directive_to_orders(
        self,
        playbook_output: Dict,
        betfair_mapping: Dict,
        snapshot: Dict
    ) -> List[Dict]:
        """
        Translate Playbook directive into concrete Betfair orders
        
        Directive → Order mapping:
        - FAVOURITE_LIABILITY_MODE → Lay favourite
        - POWER_ANCHOR_MODE → Back power horse
        - MULTI_THREAT_ZONE_MODE → Back 2-3 threats
        - CHAOS_CONTAINMENT_MODE → No bet (information only)
        - etc.
        """
        directive = playbook_output['execution']['positioning_directive']
        confidence = playbook_output['execution']['confidence']
        
        logger.info(f"Translating directive: {directive} (confidence: {confidence:.2f})")
        
        orders = []
        
        if directive == "FAVOURITE_LIABILITY_MODE":
            orders = self._build_lay_favourite_orders(playbook_output, snapshot)
        
        elif directive == "POWER_ANCHOR_MODE":
            orders = self._build_back_power_horse_orders(playbook_output, snapshot)
        
        elif directive == "MULTI_THREAT_ZONE_MODE":
            orders = self._build_multi_threat_orders(playbook_output, snapshot)
        
        elif directive == "CHAOS_CONTAINMENT_MODE":
            logger.info("CHAOS_CONTAINMENT: No orders (information only)")
            orders = []
        
        elif directive == "NARRATIVE_FRACTURE_MODE":
            orders = self._build_narrative_fracture_orders(playbook_output, snapshot)
        
        else:
            logger.warning(f"Unknown directive: {directive}")
            orders = []
        
        return orders
    
    def _build_lay_favourite_orders(
        self,
        playbook_output: Dict,
        snapshot: Dict
    ) -> List[Dict]:
        """Build orders to lay the favourite"""
        # Find favourite (lowest odds)
        runners = sorted(snapshot['runners'], key=lambda r: r['odds_decimal'])
        favourite = runners[0]
        
        # Calculate stake (Kelly-style, capped at 5% bank)
        max_liability = self.bankroll.current_bank * 0.05
        best_lay = favourite.get('best_lay')
        
        if not best_lay:
            logger.warning("No lay price available for favourite")
            return []
        
        # Liability = stake * (odds - 1)
        # So stake = liability / (odds - 1)
        stake = max_liability / (best_lay - 1)
        stake = round(stake, 2)
        
        order = {
            'selection_id': favourite['selection_id'],
            'runner_name': favourite['name'],
            'side': OrderSide.LAY,
            'price': best_lay,
            'size': stake,
            'liability': stake * (best_lay - 1),
            'reason': 'LAY_FAVOURITE (VETP trap pattern)'
        }
        
        logger.info(
            f"LAY FAVOURITE: {favourite['name']} @ {best_lay} "
            f"for £{stake} (liability: £{order['liability']:.2f})"
        )
        
        return [order]
    
    def _build_back_power_horse_orders(
        self,
        playbook_output: Dict,
        snapshot: Dict
    ) -> List[Dict]:
        """Build orders to back the power horse"""
        # Find power horse (from Playbook output)
        power_horse_name = playbook_output['attack'].get('power_horse')
        
        if not power_horse_name:
            logger.warning("No power horse identified")
            return []
        
        power_horse = next(
            (r for r in snapshot['runners'] if r['name'] == power_horse_name),
            None
        )
        
        if not power_horse:
            logger.warning(f"Power horse {power_horse_name} not found in snapshot")
            return []
        
        best_back = power_horse.get('best_back')
        
        if not best_back:
            logger.warning("No back price available for power horse")
            return []
        
        # Calculate stake (3% of bank)
        stake = self.bankroll.current_bank * 0.03
        stake = round(stake, 2)
        
        order = {
            'selection_id': power_horse['selection_id'],
            'runner_name': power_horse['name'],
            'side': OrderSide.BACK,
            'price': best_back,
            'size': stake,
            'liability': stake,  # For backs, liability = stake
            'reason': 'BACK_POWER_HORSE (dominant engine)'
        }
        
        logger.info(
            f"BACK POWER HORSE: {power_horse['name']} @ {best_back} "
            f"for £{stake}"
        )
        
        return [order]
    
    def _build_multi_threat_orders(
        self,
        playbook_output: Dict,
        snapshot: Dict
    ) -> List[Dict]:
        """Build orders for multi-threat zone (2-3 horses)"""
        # Get threat cluster from Playbook
        threat_cluster = playbook_output['attack'].get('threat_cluster', [])
        
        if not threat_cluster:
            logger.warning("No threat cluster identified")
            return []
        
        # Limit to top 3
        threat_cluster = threat_cluster[:3]
        
        # Calculate stake per horse (1.5% of bank each)
        stake_per_horse = self.bankroll.current_bank * 0.015
        stake_per_horse = round(stake_per_horse, 2)
        
        orders = []
        for horse_name in threat_cluster:
            horse = next(
                (r for r in snapshot['runners'] if r['name'] == horse_name),
                None
            )
            
            if not horse:
                continue
            
            best_back = horse.get('best_back')
            if not best_back:
                continue
            
            order = {
                'selection_id': horse['selection_id'],
                'runner_name': horse['name'],
                'side': OrderSide.BACK,
                'price': best_back,
                'size': stake_per_horse,
                'liability': stake_per_horse,
                'reason': 'MULTI_THREAT_ZONE (threat cluster)'
            }
            
            orders.append(order)
            logger.info(
                f"BACK THREAT: {horse['name']} @ {best_back} for £{stake_per_horse}"
            )
        
        return orders
    
    def _build_narrative_fracture_orders(
        self,
        playbook_output: Dict,
        snapshot: Dict
    ) -> List[Dict]:
        """Build orders to suppress narrative favourites"""
        # Similar to lay favourite, but targets narrative horse specifically
        narrative_horse_name = playbook_output['oracle'].get('narrative_horse')
        
        if not narrative_horse_name:
            # Fall back to favourite
            return self._build_lay_favourite_orders(playbook_output, snapshot)
        
        narrative_horse = next(
            (r for r in snapshot['runners'] if r['name'] == narrative_horse_name),
            None
        )
        
        if not narrative_horse:
            return []
        
        best_lay = narrative_horse.get('best_lay')
        if not best_lay:
            return []
        
        max_liability = self.bankroll.current_bank * 0.04
        stake = max_liability / (best_lay - 1)
        stake = round(stake, 2)
        
        order = {
            'selection_id': narrative_horse['selection_id'],
            'runner_name': narrative_horse['name'],
            'side': OrderSide.LAY,
            'price': best_lay,
            'size': stake,
            'liability': stake * (best_lay - 1),
            'reason': 'NARRATIVE_FRACTURE (weaponized story)'
        }
        
        logger.info(
            f"LAY NARRATIVE: {narrative_horse['name']} @ {best_lay} "
            f"for £{stake} (liability: £{order['liability']:.2f})"
        )
        
        return [order]
    
    def _execute_orders(
        self,
        orders: List[Dict],
        market_id: str
    ) -> List[Dict]:
        """Execute orders with guardrails"""
        executed = []
        
        for order in orders:
            # Check bankroll can handle liability
            if not self.bankroll.can_risk(order['liability']):
                logger.warning(
                    f"Skipping order: insufficient bankroll for £{order['liability']:.2f} liability"
                )
                continue
            
            # Place order
            result = self.betfair.place_order(
                market_id=market_id,
                selection_id=order['selection_id'],
                side=order['side'],
                size=order['size'],
                price=order['price']
            )
            
            if result['status'] == 'SUCCESS':
                # Register exposure
                order['market_id'] = market_id
                self.bankroll.register_exposure(order)
                
                # Add result to order
                order['bet_id'] = result['bet_id']
                order['placed_date'] = result['placed_date']
                order['status'] = 'PLACED'
                
                executed.append(order)
                
                logger.info(
                    f"✅ Order placed: {order['side']} {order['runner_name']} "
                    f"@ {order['price']} for £{order['size']}"
                )
            else:
                logger.error(
                    f"❌ Order failed: {order['side']} {order['runner_name']} "
                    f"- {result.get('error', 'Unknown error')}"
                )
        
        return executed


def create_execution_agent(
    mode: BetfairMode = BetfairMode.SIM,
    starting_bank: float = 1000.0
) -> BetfairExecutionAgent:
    """
    Factory function to create BetfairExecutionAgent
    
    Args:
        mode: Betfair mode (SIM, DELAYED, LIVE)
        starting_bank: Starting bankroll
    
    Returns:
        Configured BetfairExecutionAgent
    """
    from app.integrations.betfair_client import create_betfair_client
    
    # Create Betfair client
    betfair_client = create_betfair_client(mode=mode)
    betfair_client.login()
    
    # Create bankroll manager
    bankroll_manager = BankrollManager(starting_bank=starting_bank)
    
    # Create execution agent
    agent = BetfairExecutionAgent(
        betfair_client=betfair_client,
        bankroll_manager=bankroll_manager
    )
    
    return agent
