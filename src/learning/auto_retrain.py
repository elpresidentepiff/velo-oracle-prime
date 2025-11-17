"""
VÉLØ Oracle - Auto-Retraining System

Nightly weight updates based on recent performance.
Maintains ROI archive per pattern for adaptive learning.

Author: VÉLØ Oracle Team
Version: 1.0.0
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import numpy as np

from core.log import get_logger
from core.settings import get_settings
from models.benter import BenterModel
from learning.post_race_evaluator import PostRaceEvaluator

logger = get_logger(__name__)
settings = get_settings()


class ROIArchive:
    """
    Maintains ROI history per pattern/configuration
    """
    
    def __init__(self, archive_path: str = "/var/velo/roi_archive.json"):
        self.archive_path = Path(archive_path)
        self.archive = self._load_archive()
    
    def _load_archive(self) -> Dict:
        """Load archive from disk"""
        if self.archive_path.exists():
            with open(self.archive_path, 'r') as f:
                return json.load(f)
        return {
            'patterns': {},
            'global': {
                'total_bets': 0,
                'total_staked': 0.0,
                'total_returned': 0.0,
                'roi': 0.0
            }
        }
    
    def _save_archive(self):
        """Save archive to disk"""
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.archive_path, 'w') as f:
            json.dump(self.archive, f, indent=2)
    
    def record_bet(
        self,
        pattern: str,
        stake: float,
        profit: float,
        metadata: Optional[Dict] = None
    ):
        """
        Record a bet outcome
        
        Args:
            pattern: Pattern identifier (e.g., 'sqpe_tie_convergence')
            stake: Stake amount
            profit: Profit/loss
            metadata: Optional metadata
        """
        if pattern not in self.archive['patterns']:
            self.archive['patterns'][pattern] = {
                'total_bets': 0,
                'total_staked': 0.0,
                'total_returned': 0.0,
                'roi': 0.0,
                'history': []
            }
        
        p = self.archive['patterns'][pattern]
        p['total_bets'] += 1
        p['total_staked'] += stake
        p['total_returned'] += (stake + profit)
        p['roi'] = (p['total_returned'] - p['total_staked']) / p['total_staked'] if p['total_staked'] > 0 else 0.0
        
        p['history'].append({
            'timestamp': datetime.now().isoformat(),
            'stake': stake,
            'profit': profit,
            'roi': profit / stake if stake > 0 else 0.0,
            'metadata': metadata or {}
        })
        
        # Update global
        g = self.archive['global']
        g['total_bets'] += 1
        g['total_staked'] += stake
        g['total_returned'] += (stake + profit)
        g['roi'] = (g['total_returned'] - g['total_staked']) / g['total_staked'] if g['total_staked'] > 0 else 0.0
        
        self._save_archive()
    
    def get_pattern_roi(self, pattern: str) -> float:
        """Get ROI for a pattern"""
        if pattern in self.archive['patterns']:
            return self.archive['patterns'][pattern]['roi']
        return 0.0
    
    def get_top_patterns(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N patterns by ROI
        
        Args:
            n: Number of patterns to return
            
        Returns:
            List of (pattern, roi) tuples
        """
        patterns = []
        for pattern, data in self.archive['patterns'].items():
            if data['total_bets'] >= 5:  # Minimum sample size
                patterns.append((pattern, data['roi']))
        
        return sorted(patterns, key=lambda x: x[1], reverse=True)[:n]
    
    def get_recent_performance(self, days: int = 7) -> Dict:
        """
        Get performance over recent period
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Performance dict
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        total_bets = 0
        total_staked = 0.0
        total_returned = 0.0
        
        for pattern_data in self.archive['patterns'].values():
            for bet in pattern_data['history']:
                bet_time = datetime.fromisoformat(bet['timestamp'])
                if bet_time >= cutoff:
                    total_bets += 1
                    total_staked += bet['stake']
                    total_returned += (bet['stake'] + bet['profit'])
        
        roi = (total_returned - total_staked) / total_staked if total_staked > 0 else 0.0
        
        return {
            'days': days,
            'total_bets': total_bets,
            'total_staked': total_staked,
            'total_returned': total_returned,
            'roi': roi
        }


class AutoRetrainer:
    """
    Automatic model retraining based on recent performance
    """
    
    def __init__(
        self,
        evaluator: PostRaceEvaluator,
        roi_archive: ROIArchive,
        min_sample_size: int = 20
    ):
        self.evaluator = evaluator
        self.roi_archive = roi_archive
        self.min_sample_size = min_sample_size
        
        logger.info("Initialized auto-retrainer")
    
    def should_retrain(self, lookback_days: int = 7) -> Tuple[bool, str]:
        """
        Determine if retraining is needed
        
        Args:
            lookback_days: Days to analyze
            
        Returns:
            (should_retrain, reason)
        """
        # Get recent performance
        recent_perf = self.roi_archive.get_recent_performance(lookback_days)
        
        if recent_perf['total_bets'] < self.min_sample_size:
            return False, f"Insufficient data ({recent_perf['total_bets']} bets)"
        
        # Check if ROI is declining
        if recent_perf['roi'] < -0.05:  # -5% threshold
            return True, f"ROI declining ({recent_perf['roi']:.1%})"
        
        # Check module accuracy
        module_acc = self.evaluator.calculate_module_accuracy(lookback_days)
        
        for module, metrics in module_acc.items():
            if metrics['total'] >= 10 and metrics['accuracy'] < 0.15:  # 15% threshold
                return True, f"{module.upper()} accuracy low ({metrics['accuracy']:.1%})"
        
        return False, "Performance stable"
    
    def calculate_optimal_weights(
        self,
        lookback_days: int = 30
    ) -> Dict[str, float]:
        """
        Calculate optimal module weights based on recent performance
        
        Args:
            lookback_days: Days to analyze
            
        Returns:
            Dict of module weights
        """
        module_acc = self.evaluator.calculate_module_accuracy(lookback_days)
        
        # Calculate weights based on accuracy
        weights = {}
        total_weight = 0.0
        
        for module, metrics in module_acc.items():
            if metrics['total'] >= 5:
                # Weight = accuracy * sqrt(sample_size)
                weight = metrics['accuracy'] * np.sqrt(metrics['total'])
                weights[module] = weight
                total_weight += weight
            else:
                weights[module] = 0.0
        
        # Normalize
        if total_weight > 0:
            for module in weights:
                weights[module] /= total_weight
        else:
            # Equal weights if no data
            weights = {m: 1.0/3.0 for m in ['sqpe', 'tie', 'nds']}
        
        return weights
    
    def retrain(self, lookback_days: int = 30) -> Dict:
        """
        Perform retraining
        
        Args:
            lookback_days: Days of data to use
            
        Returns:
            Retraining results dict
        """
        logger.info(f"Starting retraining with {lookback_days} days of data")
        
        # Calculate optimal weights
        new_weights = self.calculate_optimal_weights(lookback_days)
        
        # Get performance metrics
        module_acc = self.evaluator.calculate_module_accuracy(lookback_days)
        recent_perf = self.roi_archive.get_recent_performance(lookback_days)
        
        # Create retraining record
        record = {
            'timestamp': datetime.now().isoformat(),
            'lookback_days': lookback_days,
            'new_weights': new_weights,
            'module_accuracy': module_acc,
            'recent_performance': recent_perf,
            'reason': 'scheduled_retrain'
        }
        
        # Save record
        self._save_retrain_record(record)
        
        logger.info(
            f"Retraining complete. New weights: "
            f"SQPE={new_weights['sqpe']:.2f}, "
            f"TIE={new_weights['tie']:.2f}, "
            f"NDS={new_weights['nds']:.2f}"
        )
        
        return record
    
    def _save_retrain_record(self, record: Dict):
        """Save retraining record"""
        record_dir = Path("/var/velo/retrain_records")
        record_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        record_file = record_dir / f'retrain_{timestamp}.json'
        
        with open(record_file, 'w') as f:
            json.dump(record, f, indent=2)
    
    def run_nightly_update(self) -> Dict:
        """
        Run nightly update check and retrain if needed
        
        Returns:
            Update results dict
        """
        logger.info("Running nightly update check")
        
        should_retrain, reason = self.should_retrain()
        
        if should_retrain:
            logger.info(f"Retraining triggered: {reason}")
            return self.retrain()
        else:
            logger.info(f"No retraining needed: {reason}")
            return {
                'timestamp': datetime.now().isoformat(),
                'retrained': False,
                'reason': reason
            }


def main():
    """Main entry point for nightly cron job"""
    logger.info("="*60)
    logger.info("VÉLØ Auto-Retrain - Nightly Update")
    logger.info("="*60)
    
    # Initialize components
    evaluator = PostRaceEvaluator()
    roi_archive = ROIArchive()
    retrainer = AutoRetrainer(evaluator, roi_archive)
    
    # Run update
    result = retrainer.run_nightly_update()
    
    # Log result
    if result.get('retrained'):
        logger.info("✓ Retraining completed successfully")
        logger.info(f"  New weights: {result.get('new_weights')}")
    else:
        logger.info(f"✓ No retraining needed: {result.get('reason')}")
    
    logger.info("="*60)


if __name__ == '__main__':
    main()

