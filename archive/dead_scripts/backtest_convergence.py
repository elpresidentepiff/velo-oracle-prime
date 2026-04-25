"""
VÉLØ Oracle - Comprehensive Convergence Backtest Framework

Tests intelligence stack convergence hypothesis:
- 2-module vs 3-module agreement rates
- Signal-by-signal accuracy
- ROI improvement over baseline
- Hit rate and volatility metrics

Designed for memory-efficient processing of large datasets.

Author: VÉLØ Oracle Team
Version: 1.0.0
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass, asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.log import get_logger
from core.settings import get_settings
from models.benter import BenterModel
from models.kelly import KellyCriterion
from models.overlay import OverlaySelector
from intelligence.sqpe import SQPE
from intelligence.tie import TIE
from intelligence.nds import NDS
from intelligence.orchestrator import IntelligenceOrchestrator

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class BacktestResult:
    """Single backtest result"""
    config_name: str
    year: int
    use_intelligence: bool
    min_modules: Optional[int]
    
    total_races: int
    total_bets: int
    total_wins: int
    total_staked: float
    total_returned: float
    
    overlay_rate: float
    win_rate: float
    roi: float
    sharpe: float
    max_drawdown: float
    
    # Intelligence-specific metrics
    sqpe_triggers: int = 0
    tie_triggers: int = 0
    nds_triggers: int = 0
    dual_convergence: int = 0
    triple_convergence: int = 0
    
    # Signal accuracy
    sqpe_accuracy: float = 0.0
    tie_accuracy: float = 0.0
    nds_accuracy: float = 0.0


class ConvergenceBacktester:
    """
    Comprehensive backtesting framework with convergence validation
    """
    
    def __init__(
        self,
        data_path: str,
        chunk_size: int = 50000,
        initial_bankroll: float = 1000.0
    ):
        self.data_path = Path(data_path)
        self.chunk_size = chunk_size
        self.initial_bankroll = initial_bankroll
        
        # Initialize models
        self.benter = BenterModel(alpha=1.0, beta=1.0)
        self.kelly = KellyCriterion(fractional=0.1)
        self.overlay_selector = OverlaySelector(min_edge=0.05, max_odds=40.0)
        
        # Initialize intelligence modules
        self.sqpe = SQPE()
        self.tie = TIE()
        self.nds = NDS()
        
        logger.info(f"Initialized backtester with data: {data_path}")
    
    def load_data_chunked(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        Load data in chunks to avoid memory issues
        
        Args:
            year: Optional year filter
            
        Returns:
            DataFrame with race data
        """
        logger.info(f"Loading data from {self.data_path}")
        
        chunks = []
        total_rows = 0
        
        for chunk in pd.read_csv(self.data_path, chunksize=self.chunk_size):
            # Filter by year if specified
            if year and 'race_date' in chunk.columns:
                chunk['race_date'] = pd.to_datetime(chunk['race_date'], errors='coerce')
                chunk = chunk[chunk['race_date'].dt.year == year]
            
            if len(chunk) > 0:
                chunks.append(chunk)
                total_rows += len(chunk)
                logger.info(f"Loaded {total_rows} rows...")
        
        if not chunks:
            raise ValueError(f"No data found for year {year}")
        
        df = pd.concat(chunks, ignore_index=True)
        logger.info(f"Loaded {len(df)} total rows")
        
        return df
    
    def prepare_race_data(self, race_df: pd.DataFrame) -> Dict:
        """
        Convert race DataFrame to format expected by models
        
        Args:
            race_df: DataFrame with runners in single race
            
        Returns:
            Dict with race data
        """
        runners = []
        
        for _, row in race_df.iterrows():
            runner = {
                'runner_id': str(row.get('runner_id', row.get('horse_name', 'unknown'))),
                'horse_name': str(row.get('horse_name', 'unknown')),
                'or_rating': float(row.get('OR', 0)),
                'rpr_rating': float(row.get('RPR', 0)),
                'ts_rating': float(row.get('TS', 0)),
                'win_odds': float(row.get('win_odds', 999.0)),
                'form': str(row.get('form', '')),
                'trainer': str(row.get('trainer', '')),
                'jockey': str(row.get('jockey', '')),
                'days_since_last': int(row.get('days_since_last', 999)),
                'course_win_pct': float(row.get('course_win_pct', 0.0)),
                'distance_win_pct': float(row.get('distance_win_pct', 0.0)),
                'won': bool(row.get('won', False))
            }
            runners.append(runner)
        
        return {
            'race_id': str(race_df.iloc[0].get('race_id', 'unknown')),
            'runners': runners
        }
    
    def run_baseline_backtest(self, df: pd.DataFrame, year: int) -> BacktestResult:
        """
        Run baseline Benter backtest (no intelligence)
        
        Args:
            df: Race data
            year: Year being tested
            
        Returns:
            BacktestResult
        """
        logger.info(f"Running baseline backtest for {year}")
        
        bankroll = self.initial_bankroll
        total_races = 0
        total_bets = 0
        total_wins = 0
        total_staked = 0.0
        total_returned = 0.0
        
        bankroll_history = [bankroll]
        
        # Group by race
        for race_id, race_df in df.groupby('race_id'):
            total_races += 1
            
            race_data = self.prepare_race_data(race_df)
            
            # Get Benter probabilities
            probs = self.benter.predict_probabilities(race_data)
            
            # Find overlays
            overlays = self.overlay_selector.find_overlays(
                runners=race_data['runners'],
                model_probs=probs,
                market_odds=[r['win_odds'] for r in race_data['runners']]
            )
            
            if not overlays:
                continue
            
            # Bet on top overlay
            best = overlays[0]
            stake = self.kelly.calculate_stake(
                bankroll=bankroll,
                probability=best.model_prob,
                odds=best.market_odds
            )
            
            if stake > 0:
                total_bets += 1
                total_staked += stake
                
                # Check if won
                runner = race_data['runners'][best.runner_index]
                if runner['won']:
                    total_wins += 1
                    winnings = stake * best.market_odds
                    total_returned += winnings
                    bankroll += (winnings - stake)
                else:
                    bankroll -= stake
                
                bankroll_history.append(bankroll)
        
        # Calculate metrics
        roi = (total_returned - total_staked) / total_staked if total_staked > 0 else 0.0
        win_rate = total_wins / total_bets if total_bets > 0 else 0.0
        overlay_rate = total_bets / total_races if total_races > 0 else 0.0
        
        # Sharpe ratio (simplified)
        returns = np.diff(bankroll_history) / bankroll_history[:-1]
        sharpe = np.mean(returns) / np.std(returns) if len(returns) > 0 and np.std(returns) > 0 else 0.0
        
        # Max drawdown
        peak = np.maximum.accumulate(bankroll_history)
        drawdown = (peak - bankroll_history) / peak
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        result = BacktestResult(
            config_name=f"Baseline_{year}",
            year=year,
            use_intelligence=False,
            min_modules=None,
            total_races=total_races,
            total_bets=total_bets,
            total_wins=total_wins,
            total_staked=total_staked,
            total_returned=total_returned,
            overlay_rate=overlay_rate,
            win_rate=win_rate,
            roi=roi,
            sharpe=sharpe,
            max_drawdown=max_drawdown
        )
        
        logger.info(f"Baseline {year}: {total_bets} bets, {win_rate:.1%} win rate, {roi:.1%} ROI")
        
        return result
    
    def run_intelligence_backtest(
        self,
        df: pd.DataFrame,
        year: int,
        min_modules: int = 2,
        sqpe_threshold: float = 0.6,
        tie_threshold: float = 0.7,
        nds_threshold: float = 0.6
    ) -> BacktestResult:
        """
        Run intelligence stack backtest with convergence requirement
        
        Args:
            df: Race data
            year: Year being tested
            min_modules: Minimum modules that must agree (2 or 3)
            sqpe_threshold: SQPE confidence threshold
            tie_threshold: TIE confidence threshold
            nds_threshold: NDS confidence threshold
            
        Returns:
            BacktestResult
        """
        logger.info(f"Running intelligence backtest for {year} (min_modules={min_modules})")
        
        # Initialize orchestrator
        orchestrator = IntelligenceOrchestrator(
            sqpe=self.sqpe,
            tie=self.tie,
            nds=self.nds,
            min_modules=min_modules
        )
        
        bankroll = self.initial_bankroll
        total_races = 0
        total_bets = 0
        total_wins = 0
        total_staked = 0.0
        total_returned = 0.0
        
        sqpe_triggers = 0
        tie_triggers = 0
        nds_triggers = 0
        dual_convergence = 0
        triple_convergence = 0
        
        sqpe_correct = 0
        tie_correct = 0
        nds_correct = 0
        
        bankroll_history = [bankroll]
        
        # Group by race
        for race_id, race_df in df.groupby('race_id'):
            total_races += 1
            
            race_data = self.prepare_race_data(race_df)
            
            # Get Benter probabilities
            probs = self.benter.predict_probabilities(race_data)
            
            # Find overlays
            overlays = self.overlay_selector.find_overlays(
                runners=race_data['runners'],
                model_probs=probs,
                market_odds=[r['win_odds'] for r in race_data['runners']]
            )
            
            if not overlays:
                continue
            
            # Check each overlay with intelligence
            for overlay in overlays:
                runner = race_data['runners'][overlay.runner_index]
                
                # Get intelligence signals
                signals = orchestrator.evaluate_runner(runner, race_data)
                
                # Check convergence
                if not signals['converged']:
                    continue
                
                # Track module triggers
                if signals['sqpe']['triggered']:
                    sqpe_triggers += 1
                    if runner['won']:
                        sqpe_correct += 1
                
                if signals['tie']['triggered']:
                    tie_triggers += 1
                    if runner['won']:
                        tie_correct += 1
                
                if signals['nds']['triggered']:
                    nds_triggers += 1
                    if runner['won']:
                        nds_correct += 1
                
                # Track convergence level
                triggered_count = sum([
                    signals['sqpe']['triggered'],
                    signals['tie']['triggered'],
                    signals['nds']['triggered']
                ])
                
                if triggered_count == 2:
                    dual_convergence += 1
                elif triggered_count == 3:
                    triple_convergence += 1
                
                # Place bet
                stake = self.kelly.calculate_stake(
                    bankroll=bankroll,
                    probability=overlay.model_prob,
                    odds=overlay.market_odds
                )
                
                if stake > 0:
                    total_bets += 1
                    total_staked += stake
                    
                    if runner['won']:
                        total_wins += 1
                        winnings = stake * overlay.market_odds
                        total_returned += winnings
                        bankroll += (winnings - stake)
                    else:
                        bankroll -= stake
                    
                    bankroll_history.append(bankroll)
                    break  # Only bet once per race
        
        # Calculate metrics
        roi = (total_returned - total_staked) / total_staked if total_staked > 0 else 0.0
        win_rate = total_wins / total_bets if total_bets > 0 else 0.0
        overlay_rate = total_bets / total_races if total_races > 0 else 0.0
        
        # Sharpe ratio
        returns = np.diff(bankroll_history) / bankroll_history[:-1]
        sharpe = np.mean(returns) / np.std(returns) if len(returns) > 0 and np.std(returns) > 0 else 0.0
        
        # Max drawdown
        peak = np.maximum.accumulate(bankroll_history)
        drawdown = (peak - bankroll_history) / peak
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        # Signal accuracy
        sqpe_accuracy = sqpe_correct / sqpe_triggers if sqpe_triggers > 0 else 0.0
        tie_accuracy = tie_correct / tie_triggers if tie_triggers > 0 else 0.0
        nds_accuracy = nds_correct / nds_triggers if nds_triggers > 0 else 0.0
        
        result = BacktestResult(
            config_name=f"Intelligence_{year}_Min{min_modules}",
            year=year,
            use_intelligence=True,
            min_modules=min_modules,
            total_races=total_races,
            total_bets=total_bets,
            total_wins=total_wins,
            total_staked=total_staked,
            total_returned=total_returned,
            overlay_rate=overlay_rate,
            win_rate=win_rate,
            roi=roi,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            sqpe_triggers=sqpe_triggers,
            tie_triggers=tie_triggers,
            nds_triggers=nds_triggers,
            dual_convergence=dual_convergence,
            triple_convergence=triple_convergence,
            sqpe_accuracy=sqpe_accuracy,
            tie_accuracy=tie_accuracy,
            nds_accuracy=nds_accuracy
        )
        
        logger.info(
            f"Intelligence {year}: {total_bets} bets, {win_rate:.1%} win rate, "
            f"{roi:.1%} ROI, {dual_convergence} dual + {triple_convergence} triple convergence"
        )
        
        return result
    
    def run_comprehensive_suite(self, years: List[int]) -> List[BacktestResult]:
        """
        Run comprehensive test suite across multiple years
        
        Args:
            years: List of years to test
            
        Returns:
            List of BacktestResults
        """
        results = []
        
        for year in years:
            logger.info(f"\n{'='*60}")
            logger.info(f"TESTING YEAR: {year}")
            logger.info(f"{'='*60}")
            
            # Load data for year
            df = self.load_data_chunked(year=year)
            
            # Run baseline
            baseline = self.run_baseline_backtest(df, year)
            results.append(baseline)
            
            # Run intelligence with different convergence levels
            for min_modules in [2, 3]:
                intel = self.run_intelligence_backtest(
                    df, year, min_modules=min_modules
                )
                results.append(intel)
        
        return results
    
    def save_results(self, results: List[BacktestResult], output_path: str):
        """
        Save results to JSON file
        
        Args:
            results: List of BacktestResults
            output_path: Path to save results
        """
        output = {
            'timestamp': datetime.now().isoformat(),
            'initial_bankroll': self.initial_bankroll,
            'results': [asdict(r) for r in results]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved to {output_path}")
    
    def generate_report(self, results: List[BacktestResult], output_path: str):
        """
        Generate markdown report
        
        Args:
            results: List of BacktestResults
            output_path: Path to save report
        """
        lines = [
            "# VÉLØ Oracle - Convergence Backtest Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Initial Bankroll:** £{self.initial_bankroll:,.2f}",
            "",
            "## Executive Summary",
            "",
            "This report compares baseline Benter model performance against the intelligence stack",
            "with dual-signal and triple-signal convergence requirements.",
            "",
            "## Results by Year",
            ""
        ]
        
        # Group by year
        by_year = {}
        for r in results:
            if r.year not in by_year:
                by_year[r.year] = []
            by_year[r.year].append(r)
        
        for year in sorted(by_year.keys()):
            year_results = by_year[year]
            
            lines.append(f"### {year}")
            lines.append("")
            lines.append("| Configuration | Bets | Win Rate | ROI | Sharpe | Max DD |")
            lines.append("|--------------|------|----------|-----|--------|--------|")
            
            for r in year_results:
                lines.append(
                    f"| {r.config_name} | {r.total_bets} | "
                    f"{r.win_rate:.1%} | {r.roi:.1%} | "
                    f"{r.sharpe:.2f} | {r.max_drawdown:.1%} |"
                )
            
            lines.append("")
            
            # Intelligence metrics
            intel_results = [r for r in year_results if r.use_intelligence]
            if intel_results:
                lines.append("#### Intelligence Module Performance")
                lines.append("")
                lines.append("| Config | SQPE Acc | TIE Acc | NDS Acc | Dual Conv | Triple Conv |")
                lines.append("|--------|----------|---------|---------|-----------|-------------|")
                
                for r in intel_results:
                    lines.append(
                        f"| Min{r.min_modules} | {r.sqpe_accuracy:.1%} | "
                        f"{r.tie_accuracy:.1%} | {r.nds_accuracy:.1%} | "
                        f"{r.dual_convergence} | {r.triple_convergence} |"
                    )
                
                lines.append("")
        
        # Summary comparison
        lines.append("## Baseline vs Intelligence Comparison")
        lines.append("")
        
        baseline_results = [r for r in results if not r.use_intelligence]
        intel_results = [r for r in results if r.use_intelligence]
        
        if baseline_results and intel_results:
            avg_baseline_roi = np.mean([r.roi for r in baseline_results])
            avg_intel_roi = np.mean([r.roi for r in intel_results])
            
            avg_baseline_win = np.mean([r.win_rate for r in baseline_results])
            avg_intel_win = np.mean([r.win_rate for r in intel_results])
            
            lines.append(f"**Average Baseline ROI:** {avg_baseline_roi:.1%}")
            lines.append(f"**Average Intelligence ROI:** {avg_intel_roi:.1%}")
            lines.append(f"**ROI Improvement:** {(avg_intel_roi - avg_baseline_roi):.1%}")
            lines.append("")
            lines.append(f"**Average Baseline Win Rate:** {avg_baseline_win:.1%}")
            lines.append(f"**Average Intelligence Win Rate:** {avg_intel_win:.1%}")
            lines.append(f"**Win Rate Improvement:** {(avg_intel_win - avg_baseline_win):.1%}")
            lines.append("")
        
        lines.append("## Conclusions")
        lines.append("")
        lines.append("*[Analysis to be added after review of results]*")
        lines.append("")
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Report saved to {output_path}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="VÉLØ Convergence Backtest")
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to raceform CSV'
    )
    parser.add_argument(
        '--years',
        type=int,
        nargs='+',
        default=[2023],
        help='Years to test (default: 2023)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='/tmp',
        help='Output directory for results'
    )
    parser.add_argument(
        '--bankroll',
        type=float,
        default=1000.0,
        help='Initial bankroll (default: 1000)'
    )
    
    args = parser.parse_args()
    
    # Create backtester
    backtester = ConvergenceBacktester(
        data_path=args.data,
        initial_bankroll=args.bankroll
    )
    
    # Run comprehensive suite
    results = backtester.run_comprehensive_suite(args.years)
    
    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    backtester.save_results(
        results,
        str(output_dir / f'backtest_results_{timestamp}.json')
    )
    
    backtester.generate_report(
        results,
        str(output_dir / f'BACKTEST_CONVERGENCE_REPORT_{timestamp}.md')
    )
    
    logger.info("Backtest complete!")


if __name__ == '__main__':
    main()

