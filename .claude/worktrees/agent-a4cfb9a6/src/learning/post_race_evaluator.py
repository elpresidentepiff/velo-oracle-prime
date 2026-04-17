"""
VÉLØ Oracle - Post-Race Evaluation System

Automatically ingests race results and compares predictions to outcomes.
Feeds error data to learning loop for continuous improvement.

Author: VÉLØ Oracle Team
Version: 1.0.0
"""

from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path

from core.log import get_logger
from core.settings import get_settings
from modules.contracts import Runner, BetRecord, RaceResult
from intelligence.sqpe import SQPE
from intelligence.tie import TIE
from intelligence.nds import NDS
from intelligence.orchestrator import IntelligenceOrchestrator

logger = get_logger(__name__)
settings = get_settings()


class PostRaceEvaluator:
    """
    Evaluates predictions against actual race results
    """
    
    def __init__(
        self,
        memory_dir: str = "/var/velo/memory",
        sqpe: Optional[SQPE] = None,
        tie: Optional[TIE] = None,
        nds: Optional[NDS] = None
    ):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize intelligence modules
        self.sqpe = sqpe or SQPE()
        self.tie = tie or TIE()
        self.nds = nds or NDS()
        
        self.orchestrator = IntelligenceOrchestrator(
            sqpe=self.sqpe,
            tie=self.tie,
            nds=self.nds
        )
        
        logger.info(f"Initialized post-race evaluator, memory: {memory_dir}")
    
    def evaluate_bet(self, bet: BetRecord, result: RaceResult) -> Dict:
        """
        Evaluate a single bet against race result
        
        Args:
            bet: BetRecord with prediction details
            result: RaceResult with actual outcome
            
        Returns:
            Evaluation dict with outcome and learning data
        """
        # Find the runner we bet on
        bet_runner = None
        for runner in result.runners:
            if runner.runner_id == bet.runner_id:
                bet_runner = runner
                break
        
        if not bet_runner:
            logger.warning(f"Runner {bet.runner_id} not found in results")
            return {
                'success': False,
                'error': 'runner_not_found'
            }
        
        # Determine outcome
        won = bet_runner.position == 1
        
        # Calculate profit/loss
        if won:
            profit = bet.stake * bet.odds - bet.stake
        else:
            profit = -bet.stake
        
        # Get intelligence signals that triggered the bet
        race_data = {
            'race_id': result.race_id,
            'runners': [self._runner_to_dict(r) for r in result.runners]
        }
        
        runner_data = self._runner_to_dict(bet_runner)
        signals = self.orchestrator.evaluate_runner(runner_data, race_data)
        
        # Create evaluation record
        evaluation = {
            'bet_id': bet.bet_id,
            'race_id': result.race_id,
            'runner_id': bet.runner_id,
            'horse_name': bet_runner.horse_name,
            'timestamp': datetime.now().isoformat(),
            
            # Bet details
            'stake': bet.stake,
            'odds': bet.odds,
            'model_prob': bet.model_prob,
            'edge': bet.edge,
            
            # Outcome
            'won': won,
            'position': bet_runner.position,
            'profit': profit,
            'roi': profit / bet.stake if bet.stake > 0 else 0.0,
            
            # Intelligence signals
            'signals': {
                'sqpe': {
                    'triggered': signals['sqpe']['triggered'],
                    'confidence': signals['sqpe']['confidence'],
                    'correct': won if signals['sqpe']['triggered'] else None
                },
                'tie': {
                    'triggered': signals['tie']['triggered'],
                    'confidence': signals['tie']['confidence'],
                    'correct': won if signals['tie']['triggered'] else None
                },
                'nds': {
                    'triggered': signals['nds']['triggered'],
                    'confidence': signals['nds']['confidence'],
                    'correct': won if signals['nds']['triggered'] else None
                },
                'convergence': signals['converged'],
                'module_count': signals['module_count']
            },
            
            # Learning data
            'error_type': self._classify_error(won, signals),
            'narrative_tags': self._tag_narrative(bet_runner, result) if not won else []
        }
        
        # Save to memory
        self._save_evaluation(evaluation)
        
        logger.info(
            f"Evaluated bet {bet.bet_id}: "
            f"{'WON' if won else 'LOST'} {profit:+.2f} "
            f"({evaluation['error_type']})"
        )
        
        return evaluation
    
    def _runner_to_dict(self, runner: Runner) -> Dict:
        """Convert Runner to dict for intelligence modules"""
        return {
            'runner_id': runner.runner_id,
            'horse_name': runner.horse_name,
            'or_rating': getattr(runner, 'or_rating', 0),
            'rpr_rating': getattr(runner, 'rpr_rating', 0),
            'ts_rating': getattr(runner, 'ts_rating', 0),
            'win_odds': getattr(runner, 'win_odds', 999.0),
            'form': getattr(runner, 'form', ''),
            'trainer': getattr(runner, 'trainer', ''),
            'jockey': getattr(runner, 'jockey', ''),
            'days_since_last': getattr(runner, 'days_since_last', 999),
            'course_win_pct': getattr(runner, 'course_win_pct', 0.0),
            'distance_win_pct': getattr(runner, 'distance_win_pct', 0.0),
            'won': runner.position == 1 if hasattr(runner, 'position') else False
        }
    
    def _classify_error(self, won: bool, signals: Dict) -> str:
        """
        Classify prediction error type
        
        Args:
            won: Whether bet won
            signals: Intelligence signals
            
        Returns:
            Error type string
        """
        if won:
            return 'true_positive'
        else:
            # False positive - we predicted win but lost
            if signals['convergence']:
                if signals['module_count'] == 3:
                    return 'false_positive_triple_convergence'
                else:
                    return 'false_positive_dual_convergence'
            else:
                return 'false_positive_no_convergence'
    
    def _tag_narrative(self, runner: Runner, result: RaceResult) -> List[str]:
        """
        Tag narrative patterns for losing bets
        
        Args:
            runner: Runner that lost
            result: Race result
            
        Returns:
            List of narrative tags
        """
        tags = []
        
        # Hype favorite
        if hasattr(runner, 'win_odds') and runner.win_odds < 3.0:
            tags.append('hype_favorite')
        
        # False form
        if hasattr(runner, 'form'):
            form = runner.form
            if form and len(form) >= 3:
                recent = form[:3]
                if recent.count('1') >= 2:
                    tags.append('false_form')
        
        # Class drop
        if hasattr(runner, 'or_rating') and runner.or_rating > 100:
            tags.append('class_drop')
        
        # Long layoff
        if hasattr(runner, 'days_since_last') and runner.days_since_last > 60:
            tags.append('long_layoff')
        
        return tags
    
    def _save_evaluation(self, evaluation: Dict):
        """
        Save evaluation to memory
        
        Args:
            evaluation: Evaluation dict
        """
        # Save to daily file
        date = datetime.now().strftime('%Y%m%d')
        daily_file = self.memory_dir / f'evaluations_{date}.jsonl'
        
        with open(daily_file, 'a') as f:
            f.write(json.dumps(evaluation) + '\n')
    
    def get_recent_evaluations(self, days: int = 7) -> List[Dict]:
        """
        Get recent evaluations
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of evaluation dicts
        """
        evaluations = []
        
        # Read from daily files
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y%m%d')
            daily_file = self.memory_dir / f'evaluations_{date_str}.jsonl'
            
            if daily_file.exists():
                with open(daily_file, 'r') as f:
                    for line in f:
                        evaluations.append(json.loads(line))
        
        return evaluations
    
    def calculate_module_accuracy(self, days: int = 30) -> Dict:
        """
        Calculate per-module accuracy over recent period
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with module accuracy metrics
        """
        evaluations = self.get_recent_evaluations(days)
        
        if not evaluations:
            return {
                'sqpe': {'accuracy': 0.0, 'total': 0},
                'tie': {'accuracy': 0.0, 'total': 0},
                'nds': {'accuracy': 0.0, 'total': 0}
            }
        
        # Count correct predictions per module
        sqpe_correct = 0
        sqpe_total = 0
        tie_correct = 0
        tie_total = 0
        nds_correct = 0
        nds_total = 0
        
        for ev in evaluations:
            signals = ev.get('signals', {})
            
            if signals.get('sqpe', {}).get('triggered'):
                sqpe_total += 1
                if signals['sqpe'].get('correct'):
                    sqpe_correct += 1
            
            if signals.get('tie', {}).get('triggered'):
                tie_total += 1
                if signals['tie'].get('correct'):
                    tie_correct += 1
            
            if signals.get('nds', {}).get('triggered'):
                nds_total += 1
                if signals['nds'].get('correct'):
                    nds_correct += 1
        
        return {
            'sqpe': {
                'accuracy': sqpe_correct / sqpe_total if sqpe_total > 0 else 0.0,
                'total': sqpe_total,
                'correct': sqpe_correct
            },
            'tie': {
                'accuracy': tie_correct / tie_total if tie_total > 0 else 0.0,
                'total': tie_total,
                'correct': tie_correct
            },
            'nds': {
                'accuracy': nds_correct / nds_total if nds_total > 0 else 0.0,
                'total': nds_total,
                'correct': nds_correct
            }
        }

