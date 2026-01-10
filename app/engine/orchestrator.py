"""
VÉLØ Orchestrator
Runs all 5 agents and produces final betting verdict with complete audit trail
"""
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from supabase import create_client, Client

from app.engine.agents.form_analyzer import FormAnalyzer
from app.engine.agents.connections_analyzer import ConnectionsAnalyzer
from app.engine.agents.course_distance_analyzer import CourseDistanceAnalyzer
from app.engine.agents.ratings_analyzer import RatingsAnalyzer
from app.engine.agents.market_analyzer import MarketAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class BettingVerdict:
    """Final betting verdict for a horse"""
    horse_name: str
    final_score: float  # 0-100
    action: str  # BACK, LAY, PASS
    stake_pct: float  # Percentage of bankroll
    reason: str
    agent_scores: Dict[str, float]
    evidence: Dict[str, Any]


class Orchestrator:
    """
    Orchestrates all 5 agents and produces betting verdicts
    
    Agent Weights:
    - Connections: 25%
    - Ratings: 20%
    - Form: 20%
    - Course/Distance: 20%
    - Market: 15%
    
    Betting Rules:
    - BACK @ 2%: Score > 70 + hot connections + specialist
    - BACK @ 1%: Score > 60 + value bet
    - LAY @ 0.5%: Score < 40
    - PASS: Everything else or outside 3/1-20/1 range
    """
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """
        Initialize Orchestrator
        
        Args:
            supabase_url: Supabase URL (defaults to env var)
            supabase_key: Supabase service role key (defaults to env var)
        """
        # Initialize Supabase client
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase credentials not available - running without database")
            self.client = None
        else:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✓ Connected to Supabase")
        
        # Initialize agents
        self.agents = {
            'form': FormAnalyzer(self.client),
            'connections': ConnectionsAnalyzer(self.client),
            'course_distance': CourseDistanceAnalyzer(self.client),
            'ratings': RatingsAnalyzer(self.client),
            'market': MarketAnalyzer(self.client)
        }
        
        # Agent weights
        self.weights = {
            'form': 0.20,
            'connections': 0.25,
            'course_distance': 0.20,
            'ratings': 0.20,
            'market': 0.15
        }
        
        logger.info(f"✓ Initialized orchestrator with {len(self.agents)} agents")
    
    def analyze_race(self, race_data: Dict[str, Any]) -> List[BettingVerdict]:
        """
        Analyze a race and produce betting verdicts for all horses
        
        Args:
            race_data: Race data including runners and metadata
            
        Returns:
            List of BettingVerdict for each horse
        """
        race_id = race_data.get('race_id', 'UNKNOWN')
        runners = race_data.get('runners', [])
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Analyzing race: {race_id}")
        logger.info(f"Runners: {len(runners)}")
        logger.info(f"{'='*60}\n")
        
        verdicts = []
        
        for runner in runners:
            verdict = self._analyze_runner(runner, race_data)
            verdicts.append(verdict)
            
            # Log to console
            logger.info(f"{runner.get('horse_name', 'Unknown')}: "
                       f"Score={verdict.final_score:.1f} "
                       f"Action={verdict.action} "
                       f"Stake={verdict.stake_pct:.2f}%")
        
        logger.info(f"\n{'='*60}\n")
        
        return verdicts
    
    def _analyze_runner(self, runner: Dict[str, Any], race_data: Dict[str, Any]) -> BettingVerdict:
        """
        Analyze a single runner using all agents
        
        Args:
            runner: Runner data
            race_data: Full race data
            
        Returns:
            BettingVerdict
        """
        horse_name = runner.get('horse_name', 'Unknown')
        race_id = race_data.get('race_id', 'UNKNOWN')
        
        # Run all agents
        agent_scores = {}
        agent_evidence = {}
        
        race_context = {
            'race_id': race_id,
            'course': race_data.get('course', ''),
            'distance': race_data.get('distance', ''),
            'going': race_data.get('going', ''),
            'runners': race_data.get('runners', [])
        }
        
        # Form Analyzer
        form_result = self.agents['form'].analyze(runner, race_context)
        agent_scores['form'] = form_result.score
        agent_evidence['form'] = form_result.evidence
        
        # Connections Analyzer
        connections_result = self.agents['connections'].analyze(runner, race_context)
        agent_scores['connections'] = connections_result.score
        agent_evidence['connections'] = connections_result.evidence
        
        # Course/Distance Analyzer
        cd_result = self.agents['course_distance'].analyze(runner, race_context)
        agent_scores['course_distance'] = cd_result.score
        agent_evidence['course_distance'] = cd_result.evidence
        
        # Ratings Analyzer
        ratings_result = self.agents['ratings'].analyze(runner, race_context)
        agent_scores['ratings'] = ratings_result.score
        agent_evidence['ratings'] = ratings_result.evidence
        
        # Market Analyzer
        market_result = self.agents['market'].analyze(runner, race_context)
        agent_scores['market'] = market_result.score
        agent_evidence['market'] = market_result.evidence
        
        # Calculate weighted final score
        final_score = sum(
            agent_scores[agent] * self.weights[agent]
            for agent in self.weights
        )
        
        # Save agent executions to audit trail
        if self.client:
            self._save_agent_executions(
                race_id, horse_name, agent_scores, agent_evidence
            )
        
        # Apply betting rules to determine action
        action, stake_pct, reason = self._apply_betting_rules(
            final_score,
            agent_scores,
            agent_evidence,
            runner
        )
        
        # Create verdict
        verdict = BettingVerdict(
            horse_name=horse_name,
            final_score=final_score,
            action=action,
            stake_pct=stake_pct,
            reason=reason,
            agent_scores=agent_scores,
            evidence=agent_evidence
        )
        
        # Save verdict to database
        if self.client:
            self._save_verdict(race_id, verdict)
        
        return verdict
    
    def _apply_betting_rules(
        self,
        final_score: float,
        agent_scores: Dict[str, float],
        agent_evidence: Dict[str, Any],
        runner: Dict[str, Any]
    ) -> tuple:
        """
        Apply betting rules to determine action
        
        Returns:
            (action, stake_pct, reason) tuple
        """
        odds = (
            runner.get('odds') or 
            runner.get('win_odds') or 
            runner.get('sp') or 
            0
        )
        
        # Check odds range (3/1 to 20/1)
        if odds > 0 and (odds < 3.0 or odds > 21.0):
            return ('PASS', 0.0, f'Outside acceptable odds range ({odds:.1f})')
        
        # Check for hot connections
        hot_connections = False
        connections_evidence = agent_evidence.get('connections', {})
        for factor in connections_evidence.get('factors', []):
            if '🔥 HOT COMBO' in factor:
                hot_connections = True
                break
        
        # Check for specialist
        is_specialist = False
        cd_evidence = agent_evidence.get('course_distance', {})
        for factor in cd_evidence.get('factors', []):
            if 'SPECIALIST' in factor:
                is_specialist = True
                break
        
        # Check for value
        has_value = False
        market_evidence = agent_evidence.get('market', {})
        for factor in market_evidence.get('factors', []):
            if 'VALUE' in factor or 'value' in factor:
                has_value = True
                break
        
        # BACK @ 2%: Score > 70 + hot connections + specialist
        if (final_score > 70 and hot_connections and is_specialist):
            return (
                'BACK',
                2.0,
                f'Strong play: Score={final_score:.1f}, Hot combo + Specialist'
            )
        
        # BACK @ 1%: Score > 60 + value bet
        elif (final_score > 60 and has_value):
            return (
                'BACK',
                1.0,
                f'Value play: Score={final_score:.1f}, Market value identified'
            )
        
        # LAY @ 0.5%: Score < 40
        elif final_score < 40:
            return (
                'LAY',
                0.5,
                f'Lay opportunity: Score={final_score:.1f}, Multiple weaknesses'
            )
        
        # PASS: Everything else
        else:
            return (
                'PASS',
                0.0,
                f'No clear edge: Score={final_score:.1f}'
            )
    
    def _save_agent_executions(
        self,
        race_id: str,
        horse_name: str,
        agent_scores: Dict[str, float],
        agent_evidence: Dict[str, Any]
    ) -> None:
        """Save agent executions to audit trail"""
        try:
            records = []
            for agent_name, score in agent_scores.items():
                evidence = agent_evidence.get(agent_name, {})
                confidence = evidence.get('confidence', 0.5)
                
                records.append({
                    'race_id': race_id,
                    'horse_name': horse_name,
                    'agent_name': agent_name,
                    'score': score,
                    'confidence': confidence,
                    'evidence': evidence
                })
            
            if records:
                self.client.table('agent_executions').insert(records).execute()
                logger.debug(f"Saved {len(records)} agent executions for {horse_name}")
        
        except Exception as e:
            logger.error(f"Failed to save agent executions: {e}")
    
    def _save_verdict(self, race_id: str, verdict: BettingVerdict) -> None:
        """Save verdict to database"""
        try:
            record = {
                'race_id': race_id,
                'horse_name': verdict.horse_name,
                'final_score': verdict.final_score,
                'action': verdict.action,
                'stake_pct': verdict.stake_pct,
                'reason': verdict.reason
            }
            
            self.client.table('race_verdicts').insert(record).execute()
            logger.debug(f"Saved verdict for {verdict.horse_name}")
        
        except Exception as e:
            logger.error(f"Failed to save verdict: {e}")
