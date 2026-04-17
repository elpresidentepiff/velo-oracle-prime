"""
VÉLØ Oracle - Self-Learning Loop

Orchestrates the complete learning cycle:
1. Ingest race results
2. Evaluate predictions
3. Update ROI archive
4. Trigger retraining if needed
5. Generate performance reports

Designed to run as a nightly cron job.

Author: VÉLØ Oracle Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.log import get_logger
from core.settings import get_settings
from learning.post_race_evaluator import PostRaceEvaluator
from learning.auto_retrain import AutoRetrainer, ROIArchive

logger = get_logger(__name__)
settings = get_settings()


class SelfLearningLoop:
    """
    Orchestrates the complete self-learning cycle
    """
    
    def __init__(
        self,
        memory_dir: str = "/var/velo/memory",
        archive_path: str = "/var/velo/roi_archive.json"
    ):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.evaluator = PostRaceEvaluator(memory_dir=str(self.memory_dir))
        self.roi_archive = ROIArchive(archive_path=archive_path)
        self.retrainer = AutoRetrainer(
            evaluator=self.evaluator,
            roi_archive=self.roi_archive
        )
        
        logger.info("Initialized self-learning loop")
    
    def ingest_results(self, results_file: str) -> int:
        """
        Ingest race results from file
        
        Args:
            results_file: Path to results JSON file
            
        Returns:
            Number of results ingested
        """
        logger.info(f"Ingesting results from {results_file}")
        
        with open(results_file, 'r') as f:
            results_data = json.load(f)
        
        count = 0
        
        for result in results_data.get('results', []):
            # Process each race result
            # (Implementation depends on result format)
            count += 1
        
        logger.info(f"Ingested {count} race results")
        return count
    
    def evaluate_recent_bets(self, days: int = 1) -> Dict:
        """
        Evaluate recent bets against results
        
        Args:
            days: Number of days to look back
            
        Returns:
            Evaluation summary
        """
        logger.info(f"Evaluating bets from last {days} days")
        
        evaluations = self.evaluator.get_recent_evaluations(days)
        
        if not evaluations:
            logger.info("No recent bets to evaluate")
            return {
                'total_bets': 0,
                'wins': 0,
                'losses': 0,
                'roi': 0.0
            }
        
        wins = sum(1 for e in evaluations if e.get('won'))
        losses = len(evaluations) - wins
        
        total_profit = sum(e.get('profit', 0.0) for e in evaluations)
        total_stake = sum(e.get('stake', 0.0) for e in evaluations)
        
        roi = total_profit / total_stake if total_stake > 0 else 0.0
        
        summary = {
            'total_bets': len(evaluations),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(evaluations) if evaluations else 0.0,
            'total_stake': total_stake,
            'total_profit': total_profit,
            'roi': roi
        }
        
        logger.info(
            f"Evaluated {len(evaluations)} bets: "
            f"{wins}W-{losses}L, ROI: {roi:.1%}"
        )
        
        return summary
    
    def update_roi_archive(self, days: int = 1):
        """
        Update ROI archive with recent results
        
        Args:
            days: Number of days to process
        """
        logger.info(f"Updating ROI archive with last {days} days")
        
        evaluations = self.evaluator.get_recent_evaluations(days)
        
        for ev in evaluations:
            # Determine pattern
            signals = ev.get('signals', {})
            pattern_parts = []
            
            if signals.get('sqpe', {}).get('triggered'):
                pattern_parts.append('sqpe')
            if signals.get('tie', {}).get('triggered'):
                pattern_parts.append('tie')
            if signals.get('nds', {}).get('triggered'):
                pattern_parts.append('nds')
            
            if pattern_parts:
                pattern = '_'.join(pattern_parts) + '_convergence'
            else:
                pattern = 'baseline'
            
            # Record in archive
            self.roi_archive.record_bet(
                pattern=pattern,
                stake=ev.get('stake', 0.0),
                profit=ev.get('profit', 0.0),
                metadata={
                    'race_id': ev.get('race_id'),
                    'horse_name': ev.get('horse_name'),
                    'odds': ev.get('odds'),
                    'won': ev.get('won')
                }
            )
        
        logger.info(f"Updated ROI archive with {len(evaluations)} bets")
    
    def generate_performance_report(self, output_path: str, days: int = 7):
        """
        Generate performance report
        
        Args:
            output_path: Path to save report
            days: Number of days to analyze
        """
        logger.info(f"Generating performance report for last {days} days")
        
        # Get metrics
        recent_perf = self.roi_archive.get_recent_performance(days)
        module_acc = self.evaluator.calculate_module_accuracy(days)
        top_patterns = self.roi_archive.get_top_patterns(10)
        
        # Generate report
        lines = [
            "# VÉLØ Oracle - Performance Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Period:** Last {days} days",
            "",
            "## Overall Performance",
            "",
            f"**Total Bets:** {recent_perf['total_bets']}",
            f"**Total Staked:** £{recent_perf['total_staked']:.2f}",
            f"**Total Returned:** £{recent_perf['total_returned']:.2f}",
            f"**ROI:** {recent_perf['roi']:.1%}",
            "",
            "## Module Accuracy",
            "",
            "| Module | Accuracy | Total Predictions | Correct |",
            "|--------|----------|-------------------|---------|"
        ]
        
        for module, metrics in module_acc.items():
            lines.append(
                f"| {module.upper()} | {metrics['accuracy']:.1%} | "
                f"{metrics['total']} | {metrics['correct']} |"
            )
        
        lines.extend([
            "",
            "## Top Performing Patterns",
            "",
            "| Pattern | ROI |",
            "|---------|-----|"
        ])
        
        for pattern, roi in top_patterns:
            lines.append(f"| {pattern} | {roi:.1%} |")
        
        lines.extend([
            "",
            "## Recommendations",
            "",
            "*[To be added based on analysis]*",
            ""
        ])
        
        # Save report
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Performance report saved to {output_path}")
    
    def run_daily_cycle(self, results_file: Optional[str] = None) -> Dict:
        """
        Run complete daily learning cycle
        
        Args:
            results_file: Optional path to results file
            
        Returns:
            Cycle summary dict
        """
        logger.info("="*60)
        logger.info("VÉLØ Self-Learning Loop - Daily Cycle")
        logger.info("="*60)
        
        cycle_summary = {
            'timestamp': datetime.now().isoformat(),
            'steps': []
        }
        
        # Step 1: Ingest results (if provided)
        if results_file:
            count = self.ingest_results(results_file)
            cycle_summary['steps'].append({
                'step': 'ingest_results',
                'count': count
            })
        
        # Step 2: Evaluate recent bets
        eval_summary = self.evaluate_recent_bets(days=1)
        cycle_summary['steps'].append({
            'step': 'evaluate_bets',
            'summary': eval_summary
        })
        
        # Step 3: Update ROI archive
        self.update_roi_archive(days=1)
        cycle_summary['steps'].append({
            'step': 'update_roi_archive',
            'completed': True
        })
        
        # Step 4: Check for retraining
        retrain_result = self.retrainer.run_nightly_update()
        cycle_summary['steps'].append({
            'step': 'retrain_check',
            'result': retrain_result
        })
        
        # Step 5: Generate performance report
        report_path = self.memory_dir / f"performance_report_{datetime.now().strftime('%Y%m%d')}.md"
        self.generate_performance_report(str(report_path), days=7)
        cycle_summary['steps'].append({
            'step': 'generate_report',
            'path': str(report_path)
        })
        
        logger.info("="*60)
        logger.info("Daily cycle complete")
        logger.info("="*60)
        
        return cycle_summary


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="VÉLØ Self-Learning Loop")
    parser.add_argument(
        '--results',
        type=str,
        help='Path to race results JSON file'
    )
    parser.add_argument(
        '--memory-dir',
        type=str,
        default='/var/velo/memory',
        help='Memory directory path'
    )
    parser.add_argument(
        '--archive-path',
        type=str,
        default='/var/velo/roi_archive.json',
        help='ROI archive path'
    )
    
    args = parser.parse_args()
    
    # Create learning loop
    loop = SelfLearningLoop(
        memory_dir=args.memory_dir,
        archive_path=args.archive_path
    )
    
    # Run daily cycle
    summary = loop.run_daily_cycle(results_file=args.results)
    
    # Save summary
    summary_path = Path(args.memory_dir) / f"cycle_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Cycle summary saved to {summary_path}")


if __name__ == '__main__':
    main()

