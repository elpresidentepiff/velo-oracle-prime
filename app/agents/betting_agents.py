"""
VÉLØ Oracle - Multi-Agent Betting System
5 specialized agents running simultaneously on Betfair
"""
import os
import sys
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class BettingAgent(ABC):
    """Base class for all betting agents"""
    
    def __init__(self, name: str, bankroll: float = 1000.0):
        self.name = name
        self.bankroll = bankroll
        self.bets_placed = []
        self.profit_loss = 0.0
        self.active = True
        
    @abstractmethod
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Analyze race and return betting opportunities"""
        pass
    
    @abstractmethod
    def calculate_stake(self, opportunity: Dict) -> float:
        """Calculate stake for a betting opportunity"""
        pass
    
    def place_bet(self, bet: Dict):
        """Record a bet placement"""
        bet['timestamp'] = datetime.now().isoformat()
        bet['agent'] = self.name
        self.bets_placed.append(bet)
        
        # Log to Supabase
        try:
            supabase.table("betting_ledger").insert(bet).execute()
            logger.info(f"[{self.name}] Bet placed: {bet}")
        except Exception as e:
            logger.error(f"Error logging bet: {e}")
    
    def update_bankroll(self, amount: float):
        """Update bankroll after bet settlement"""
        self.bankroll += amount
        self.profit_loss += amount
        logger.info(f"[{self.name}] Bankroll: £{self.bankroll:.2f} | P/L: £{self.profit_loss:.2f}")


class Top4FinisherAgent(BettingAgent):
    """
    Agent 1: Top 4 Finisher
    Places bets on horses to finish in the top 4 positions
    Strategy: Each-way betting on value horses with solid place chances
    """
    
    def __init__(self):
        super().__init__(name="TOP4_FINISHER", bankroll=1000.0)
        self.min_place_prob = 0.25  # 25% chance to place
        self.max_place_odds = 10.0
    
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Find horses with good place chances"""
        opportunities = []
        
        runners = race_data.get('runners', [])
        
        for runner in runners:
            # Calculate place probability (top 4)
            win_prob = runner.get('win_probability', 0)
            place_prob = self.estimate_place_probability(win_prob, len(runners))
            
            place_odds = runner.get('place_odds', 0)
            
            # Criteria: Good place chance + reasonable odds
            if place_prob >= self.min_place_prob and 0 < place_odds <= self.max_place_odds:
                edge = (place_prob * place_odds) - 1
                
                if edge > 0.05:  # 5% edge minimum
                    opportunities.append({
                        'type': 'EACH_WAY',
                        'selection': runner['name'],
                        'selection_id': runner['id'],
                        'odds': runner.get('win_odds', 0),
                        'place_odds': place_odds,
                        'place_probability': place_prob,
                        'edge': edge,
                        'confidence': min(place_prob * 100, 95)
                    })
        
        # Sort by edge (best first)
        opportunities.sort(key=lambda x: x['edge'], reverse=True)
        return opportunities[:3]  # Max 3 per race
    
    def estimate_place_probability(self, win_prob: float, field_size: int) -> float:
        """Estimate probability of finishing in top 4"""
        # Simple heuristic: place prob ≈ 3-4x win prob for competitive fields
        if field_size <= 5:
            return min(win_prob * 2.5, 0.95)
        elif field_size <= 10:
            return min(win_prob * 3.5, 0.90)
        else:
            return min(win_prob * 4.0, 0.85)
    
    def calculate_stake(self, opportunity: Dict) -> float:
        """Kelly Criterion for each-way betting"""
        edge = opportunity['edge']
        odds = opportunity['place_odds']
        
        # Conservative Kelly (quarter Kelly)
        kelly_fraction = edge / (odds - 1)
        stake = self.bankroll * kelly_fraction * 0.25
        
        # Limits: 1% to 5% of bankroll
        min_stake = self.bankroll * 0.01
        max_stake = self.bankroll * 0.05
        
        return max(min_stake, min(stake, max_stake))


class LayFavouritesAgent(BettingAgent):
    """
    Agent 2: Lay Vulnerable Favourites
    Lays favourites that are overbet by the public
    Strategy: Contrarian - find false favorites and lay them
    """
    
    def __init__(self):
        super().__init__(name="LAY_FAVOURITES", bankroll=1000.0)
        self.max_lay_odds = 4.0  # Don't lay odds-on favorites
        self.min_vulnerability_score = 0.6
    
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Find vulnerable favourites to lay"""
        opportunities = []
        
        runners = race_data.get('runners', [])
        
        # Find the favourite
        favourite = min(runners, key=lambda x: x.get('win_odds', 999))
        fav_odds = favourite.get('win_odds', 0)
        
        # Only lay if odds are reasonable (not odds-on)
        if fav_odds < 1.5 or fav_odds > self.max_lay_odds:
            return []
        
        # Calculate vulnerability score
        vulnerability = self.calculate_vulnerability(favourite, runners, race_data)
        
        if vulnerability >= self.min_vulnerability_score:
            # Calculate fair odds
            win_prob = favourite.get('win_probability', 0)
            fair_odds = 1 / win_prob if win_prob > 0 else 999
            
            # Edge = market odds are too short
            edge = (fav_odds - fair_odds) / fair_odds
            
            if edge < -0.15:  # Favourite is at least 15% overbet
                opportunities.append({
                    'type': 'LAY',
                    'selection': favourite['name'],
                    'selection_id': favourite['id'],
                    'lay_odds': fav_odds,
                    'fair_odds': fair_odds,
                    'vulnerability_score': vulnerability,
                    'edge': abs(edge),
                    'confidence': min(vulnerability * 100, 90)
                })
        
        return opportunities
    
    def calculate_vulnerability(self, favourite: Dict, runners: List[Dict], race_data: Dict) -> float:
        """Calculate how vulnerable the favourite is"""
        score = 0.0
        
        # 1. Recent form (30% weight)
        recent_form = favourite.get('recent_form', '')
        if recent_form:
            # Count non-wins in last 3 runs
            non_wins = sum(1 for c in recent_form[:3] if c not in ['1', 'W'])
            score += (non_wins / 3) * 0.3
        
        # 2. Class drop/rise (20% weight)
        class_change = favourite.get('class_change', 0)
        if class_change > 0:  # Stepping up in class
            score += 0.2
        
        # 3. Strong challengers (30% weight)
        # Count how many horses have win_prob > 0.15
        strong_challengers = sum(1 for r in runners if r.get('win_probability', 0) > 0.15)
        if strong_challengers >= 3:
            score += 0.3
        elif strong_challengers == 2:
            score += 0.15
        
        # 4. Course/distance record (20% weight)
        cd_wins = favourite.get('course_distance_wins', 0)
        cd_runs = favourite.get('course_distance_runs', 1)
        cd_strike_rate = cd_wins / cd_runs if cd_runs > 0 else 0
        
        if cd_strike_rate < 0.2:  # Less than 20% strike rate
            score += 0.2
        
        return min(score, 1.0)
    
    def calculate_stake(self, opportunity: Dict) -> float:
        """Calculate lay stake (liability-based)"""
        lay_odds = opportunity['lay_odds']
        edge = opportunity['edge']
        
        # Calculate liability
        stake = self.bankroll * 0.02  # 2% of bankroll as base stake
        liability = stake * (lay_odds - 1)
        
        # Limit liability to 10% of bankroll
        max_liability = self.bankroll * 0.10
        if liability > max_liability:
            stake = max_liability / (lay_odds - 1)
        
        return stake


class WinAccumulatorAgent(BettingAgent):
    """
    Agent 3: Win Accumulator
    Places doubles, trebles, accumulators, and Lucky 15s
    Strategy: Combine multiple selections for big returns
    """
    
    def __init__(self):
        super().__init__(name="WIN_ACCUMULATOR", bankroll=1000.0)
        self.min_win_prob = 0.20  # 20% minimum win chance
        self.max_selections = 4
    
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Find strong win candidates for accumulators"""
        opportunities = []
        
        runners = race_data.get('runners', [])
        
        for runner in runners:
            win_prob = runner.get('win_probability', 0)
            win_odds = runner.get('win_odds', 0)
            
            # Criteria: Solid win chance + value
            if win_prob >= self.min_win_prob and win_odds > 0:
                edge = (win_prob * win_odds) - 1
                
                if edge > 0.10:  # 10% edge minimum
                    opportunities.append({
                        'type': 'WIN',
                        'selection': runner['name'],
                        'selection_id': runner['id'],
                        'odds': win_odds,
                        'win_probability': win_prob,
                        'edge': edge,
                        'confidence': min(win_prob * 100, 85),
                        'race_id': race_data.get('race_id')
                    })
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        return opportunities[:2]  # Max 2 per race for accumulators
    
    def build_accumulators(self, all_selections: List[Dict]) -> List[Dict]:
        """Build accumulator bets from multiple races"""
        accumulators = []
        
        if len(all_selections) < 2:
            return []
        
        # Double (2 selections)
        if len(all_selections) >= 2:
            double_odds = all_selections[0]['odds'] * all_selections[1]['odds']
            accumulators.append({
                'type': 'DOUBLE',
                'selections': all_selections[:2],
                'combined_odds': double_odds,
                'num_bets': 1
            })
        
        # Treble (3 selections)
        if len(all_selections) >= 3:
            treble_odds = all_selections[0]['odds'] * all_selections[1]['odds'] * all_selections[2]['odds']
            accumulators.append({
                'type': 'TREBLE',
                'selections': all_selections[:3],
                'combined_odds': treble_odds,
                'num_bets': 1
            })
        
        # Accumulator (4 selections)
        if len(all_selections) >= 4:
            acca_odds = 1.0
            for sel in all_selections[:4]:
                acca_odds *= sel['odds']
            accumulators.append({
                'type': 'ACCUMULATOR',
                'selections': all_selections[:4],
                'combined_odds': acca_odds,
                'num_bets': 1
            })
        
        # Lucky 15 (4 selections, 15 bets)
        if len(all_selections) >= 4:
            accumulators.append({
                'type': 'LUCKY_15',
                'selections': all_selections[:4],
                'num_bets': 15  # 4 singles + 6 doubles + 4 trebles + 1 accumulator
            })
        
        return accumulators
    
    def calculate_stake(self, opportunity: Dict) -> float:
        """Calculate stake per bet in accumulator"""
        bet_type = opportunity['type']
        
        # Base stake depends on bet type
        if bet_type == 'DOUBLE':
            total_stake = self.bankroll * 0.02  # 2%
        elif bet_type == 'TREBLE':
            total_stake = self.bankroll * 0.015  # 1.5%
        elif bet_type == 'ACCUMULATOR':
            total_stake = self.bankroll * 0.01  # 1%
        elif bet_type == 'LUCKY_15':
            total_stake = self.bankroll * 0.03  # 3% total (0.2% per bet)
        else:
            total_stake = self.bankroll * 0.02
        
        # Stake per bet
        num_bets = opportunity.get('num_bets', 1)
        stake_per_bet = total_stake / num_bets
        
        return stake_per_bet


class TacticalReportAgent(BettingAgent):
    """
    Agent 4: Tactical Report Generator
    Generates detailed tactical reports like the Kempton example
    Strategy: Deep analysis with narrative and clear betting commands
    """
    
    def __init__(self):
        super().__init__(name="TACTICAL_REPORT", bankroll=1000.0)
    
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Generate tactical report with betting commands"""
        # This agent doesn't return opportunities directly
        # Instead, it generates a full tactical report
        report = self.generate_tactical_report(race_data)
        
        # Extract betting commands from report
        return report.get('betting_commands', [])
    
    def generate_tactical_report(self, race_data: Dict) -> Dict:
        """Generate full tactical report"""
        race_id = race_data.get('race_id', 'UNKNOWN')
        race_time = race_data.get('race_time', 'UNKNOWN')
        race_class = race_data.get('race_class', 'UNKNOWN')
        
        runners = race_data.get('runners', [])
        
        # Identify key horses
        class_act = self.find_class_act(runners)
        danger_horse = self.find_danger_horse(runners)
        course_specialist = self.find_course_specialist(runners)
        
        # Build report
        report = {
            'title': f"VÉLØ ORACLE TACTICAL REPORT: {race_data.get('course', 'UNKNOWN')} {race_time}",
            'race_id': race_id,
            'race_class': race_class,
            'theme': self.generate_theme(class_act, danger_horse, course_specialist),
            'field_analysis': [],
            'betting_commands': []
        }
        
        # Analyze each key horse
        if class_act:
            report['field_analysis'].append(self.analyze_runner(class_act, "THE CLASS ACT", "Shield"))
            report['betting_commands'].append({
                'type': 'WIN',
                'selection': class_act['name'],
                'selection_id': class_act['id'],
                'odds': class_act.get('win_odds', 0),
                'stake_type': 'ANCHOR',
                'reason': 'Class advantage'
            })
        
        if danger_horse:
            report['field_analysis'].append(self.analyze_runner(danger_horse, "THE DANGER", "Sword"))
            report['betting_commands'].append({
                'type': 'EACH_WAY',
                'selection': danger_horse['name'],
                'selection_id': danger_horse['id'],
                'odds': danger_horse.get('win_odds', 0),
                'stake_type': 'SAVER',
                'reason': 'Value threat'
            })
        
        if course_specialist:
            report['field_analysis'].append(self.analyze_runner(course_specialist, "THE SPECIALIST", "Target"))
            report['betting_commands'].append({
                'type': 'EACH_WAY',
                'selection': course_specialist['name'],
                'selection_id': course_specialist['id'],
                'odds': course_specialist.get('win_odds', 0),
                'stake_type': 'SAFE_EW',
                'reason': 'Course form'
            })
        
        return report
    
    def find_class_act(self, runners: List[Dict]) -> Optional[Dict]:
        """Find the class horse"""
        # Highest rating with recent form
        class_horses = [r for r in runners if r.get('rating', 0) > 85]
        if class_horses:
            return max(class_horses, key=lambda x: x.get('rating', 0))
        return None
    
    def find_danger_horse(self, runners: List[Dict]) -> Optional[Dict]:
        """Find the danger horse (class dropper)"""
        # Look for class drop
        danger_horses = [r for r in runners if r.get('class_change', 0) < 0]
        if danger_horses:
            return max(danger_horses, key=lambda x: x.get('rating', 0))
        return None
    
    def find_course_specialist(self, runners: List[Dict]) -> Optional[Dict]:
        """Find the course specialist"""
        # Best course record
        specialists = [r for r in runners if r.get('course_wins', 0) > 0]
        if specialists:
            return max(specialists, key=lambda x: x.get('course_wins', 0))
        return None
    
    def generate_theme(self, class_act, danger, specialist) -> str:
        """Generate race theme"""
        if class_act and danger:
            return f"The Class Act vs. The {danger.get('name', 'Challenger')}"
        elif class_act:
            return "Class Tells"
        else:
            return "Open Contest"
    
    def analyze_runner(self, runner: Dict, label: str, signal: str) -> Dict:
        """Analyze individual runner"""
        return {
            'name': runner['name'],
            'number': runner.get('number', 0),
            'signal': f"{label} ({signal})",
            'rating': runner.get('rating', 0),
            'form': runner.get('recent_form', ''),
            'odds': runner.get('win_odds', 0),
            'verdict': self.generate_verdict(runner, label)
        }
    
    def generate_verdict(self, runner: Dict, label: str) -> str:
        """Generate verdict for runner"""
        if label == "THE CLASS ACT":
            return "THE WINNER"
        elif label == "THE DANGER":
            return "VALUE THREAT"
        elif label == "THE SPECIALIST":
            return "THE SAFE EACH-WAY"
        else:
            return "CONTENDER"
    
    def calculate_stake(self, opportunity: Dict) -> float:
        """Calculate stake based on stake type"""
        stake_type = opportunity.get('stake_type', 'STANDARD')
        
        if stake_type == 'ANCHOR':
            return self.bankroll * 0.05  # 5% for anchor bet
        elif stake_type == 'SAVER':
            return self.bankroll * 0.03  # 3% for saver
        elif stake_type == 'SAFE_EW':
            return self.bankroll * 0.02  # 2% for safe each-way
        else:
            return self.bankroll * 0.02


class ValueHunterAgent(BettingAgent):
    """
    Agent 5: Value Hunter
    Finds class droppers and course specialists
    Strategy: Identify horses with hidden advantages
    """
    
    def __init__(self):
        super().__init__(name="VALUE_HUNTER", bankroll=1000.0)
    
    def analyze_race(self, race_data: Dict) -> List[Dict]:
        """Find value opportunities"""
        opportunities = []
        
        runners = race_data.get('runners', [])
        
        for runner in runners:
            value_score = self.calculate_value_score(runner, race_data)
            
            if value_score >= 0.6:  # 60% value score minimum
                win_odds = runner.get('win_odds', 0)
                win_prob = runner.get('win_probability', 0)
                
                edge = (win_prob * win_odds) - 1
                
                opportunities.append({
                    'type': 'WIN',
                    'selection': runner['name'],
                    'selection_id': runner['id'],
                    'odds': win_odds,
                    'value_score': value_score,
                    'edge': edge,
                    'confidence': min(value_score * 100, 85),
                    'value_factors': self.get_value_factors(runner)
                })
        
        # Sort by value score
        opportunities.sort(key=lambda x: x['value_score'], reverse=True)
        return opportunities[:2]  # Max 2 per race
    
    def calculate_value_score(self, runner: Dict, race_data: Dict) -> float:
        """Calculate value score (0-1)"""
        score = 0.0
        
        # 1. Class dropper (30% weight)
        class_change = runner.get('class_change', 0)
        if class_change < 0:  # Dropping in class
            score += 0.3
        
        # 2. Course specialist (30% weight)
        course_wins = runner.get('course_wins', 0)
        course_runs = runner.get('course_runs', 1)
        course_sr = course_wins / course_runs if course_runs > 0 else 0
        
        if course_sr >= 0.33:  # 33%+ strike rate
            score += 0.3
        elif course_sr >= 0.20:
            score += 0.15
        
        # 3. Recent form improvement (20% weight)
        recent_form = runner.get('recent_form', '')
        if recent_form:
            # Check if last run was better than average
            last_pos = int(recent_form[0]) if recent_form[0].isdigit() else 10
            if last_pos <= 3:
                score += 0.2
        
        # 4. Trainer/Jockey combo (20% weight)
        tj_combo_sr = runner.get('trainer_jockey_sr', 0)
        if tj_combo_sr >= 0.25:
            score += 0.2
        elif tj_combo_sr >= 0.15:
            score += 0.1
        
        return min(score, 1.0)
    
    def get_value_factors(self, runner: Dict) -> List[str]:
        """Get list of value factors"""
        factors = []
        
        if runner.get('class_change', 0) < 0:
            factors.append("Class Dropper")
        
        course_wins = runner.get('course_wins', 0)
        if course_wins > 0:
            factors.append(f"Course Specialist ({course_wins} wins)")
        
        recent_form = runner.get('recent_form', '')
        if recent_form and recent_form[0] in ['1', '2', '3']:
            factors.append("Recent Form")
        
        tj_combo_sr = runner.get('trainer_jockey_sr', 0)
        if tj_combo_sr >= 0.25:
            factors.append("Strong T/J Combo")
        
        return factors
    
    def calculate_stake(self, opportunity: Dict) -> float:
        """Calculate stake based on value score"""
        value_score = opportunity['value_score']
        
        # Higher value = higher stake (1% to 4% of bankroll)
        stake_pct = 0.01 + (value_score * 0.03)
        stake = self.bankroll * stake_pct
        
        return stake


# Agent Manager
class AgentManager:
    """Manages all betting agents"""
    
    def __init__(self):
        self.agents = [
            Top4FinisherAgent(),
            LayFavouritesAgent(),
            WinAccumulatorAgent(),
            TacticalReportAgent(),
            ValueHunterAgent()
        ]
        
        logger.info(f"✓ Initialized {len(self.agents)} betting agents")
    
    def analyze_race(self, race_data: Dict) -> Dict:
        """Run all agents on a race"""
        results = {}
        
        for agent in self.agents:
            if agent.active:
                try:
                    opportunities = agent.analyze_race(race_data)
                    results[agent.name] = opportunities
                    logger.info(f"[{agent.name}] Found {len(opportunities)} opportunities")
                except Exception as e:
                    logger.error(f"[{agent.name}] Error: {e}")
                    results[agent.name] = []
        
        return results
    
    def get_agent_status(self) -> List[Dict]:
        """Get status of all agents"""
        return [
            {
                'name': agent.name,
                'active': agent.active,
                'bankroll': agent.bankroll,
                'profit_loss': agent.profit_loss,
                'bets_placed': len(agent.bets_placed)
            }
            for agent in self.agents
        ]


if __name__ == "__main__":
    # Test the agents
    manager = AgentManager()
    
    # Sample race data
    test_race = {
        'race_id': 'TEST_1234',
        'course': 'KEMPTON',
        'race_time': '15:57',
        'race_class': '3',
        'runners': [
            {
                'id': 1,
                'name': 'UNITED APPROACH',
                'number': 1,
                'win_odds': 3.5,
                'place_odds': 1.8,
                'win_probability': 0.28,
                'rating': 94,
                'recent_form': '5380',
                'class_change': 0,
                'course_wins': 0,
                'course_runs': 2
            },
            {
                'id': 3,
                'name': 'SILVER SAMURAI',
                'number': 3,
                'win_odds': 5.0,
                'place_odds': 2.2,
                'win_probability': 0.20,
                'rating': 96,
                'recent_form': '275769',
                'class_change': -2,  # Class dropper
                'course_wins': 0,
                'course_runs': 1
            },
            {
                'id': 8,
                'name': 'HOW IMPRESSIVE',
                'number': 8,
                'win_odds': 4.0,
                'place_odds': 1.9,
                'win_probability': 0.25,
                'rating': 88,
                'recent_form': '1',
                'class_change': 0,
                'course_wins': 2,
                'course_runs': 3
            }
        ]
    }
    
    results = manager.analyze_race(test_race)
    
    print("\n" + "="*60)
    print("AGENT ANALYSIS RESULTS")
    print("="*60)
    
    for agent_name, opportunities in results.items():
        print(f"\n[{agent_name}]")
        for opp in opportunities:
            print(f"  - {opp}")
