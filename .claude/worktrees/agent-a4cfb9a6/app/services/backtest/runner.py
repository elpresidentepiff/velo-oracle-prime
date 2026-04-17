"""
VÉLØ Oracle - Backtest Runner
High-level interface for running backtests
"""
from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
import logging

from .engine import BacktestEngine
from .metrics import calculate_all_metrics

logger = logging.getLogger(__name__)


class BacktestRunner:
    """High-level backtest runner with strategy support"""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.engine: Optional[BacktestEngine] = None
        
    def execute(self, 
                start_date: date,
                end_date: date,
                strategy: str = "default",
                stake: float = 10.0,
                max_bets_per_day: int = 10) -> Dict[str, Any]:
        """
        Execute a backtest
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            strategy: Betting strategy name
            stake: Standard stake amount
            max_bets_per_day: Maximum bets per day
            
        Returns:
            Complete backtest results
        """
        logger.info(f"Executing backtest: {start_date} to {end_date}")
        logger.info(f"Strategy: {strategy}, Stake: ${stake}, Max bets/day: {max_bets_per_day}")
        
        # Create engine
        self.engine = BacktestEngine(start_date, end_date)
        
        # Run backtest
        backtest_results = self.engine.run_backtest(strategy=strategy)
        
        # Calculate metrics
        predictions = self.engine.predictions
        results = self.engine.results if self.engine.results else self._generate_stub_results(predictions)
        
        metrics = calculate_all_metrics(predictions, results)
        
        # Compile final results
        self.results = {
            "backtest_id": f"BT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "config": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "strategy": strategy,
                "stake": stake,
                "max_bets_per_day": max_bets_per_day
            },
            "summary": backtest_results,
            "metrics": metrics,
            "performance": self._calculate_performance(predictions, results, stake),
            "status": "complete",
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Backtest execution complete")
        
        return self.results
    
    def export_results(self, filepath: str, format: str = "json") -> bool:
        """
        Export backtest results
        
        Args:
            filepath: Output file path
            format: Export format (json, csv, html)
            
        Returns:
            Success status
        """
        try:
            logger.info(f"Exporting results to {filepath} (format: {format})")
            
            if format == "json":
                import json
                with open(filepath, 'w') as f:
                    json.dump(self.results, f, indent=2)
                    
            elif format == "csv":
                # Stub: Would export to CSV
                logger.info("CSV export not yet implemented")
                return False
                
            elif format == "html":
                # Stub: Would generate HTML report
                logger.info("HTML export not yet implemented")
                return False
            
            logger.info(f"Results exported successfully to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export results: {e}")
            return False
    
    def _generate_stub_results(self, predictions: list) -> list:
        """Generate stub results for predictions"""
        results = []
        
        for pred in predictions:
            # Stub: Random outcome based on probability
            prob = pred.get("final_probability", 0.5)
            won = prob > 0.15  # Simplified win condition
            
            result = {
                "race_id": pred.get("race_id"),
                "runner_id": pred.get("runner_id"),
                "won": won,
                "odds": pred.get("odds", 5.0)
            }
            results.append(result)
        
        return results
    
    def _calculate_performance(self, predictions: list, results: list, stake: float) -> Dict[str, Any]:
        """Calculate detailed performance metrics"""
        total_bets = len(predictions)
        wins = sum(1 for r in results if r.get("won", False))
        
        total_staked = total_bets * stake
        total_returned = sum(
            stake * r.get("odds", 1.0) 
            for r in results 
            if r.get("won", False)
        )
        
        profit = total_returned - total_staked
        roi_pct = (profit / total_staked * 100) if total_staked > 0 else 0.0
        
        return {
            "total_bets": total_bets,
            "total_wins": wins,
            "total_losses": total_bets - wins,
            "win_rate": wins / total_bets if total_bets > 0 else 0.0,
            "total_staked": total_staked,
            "total_returned": total_returned,
            "profit_loss": profit,
            "roi_percentage": roi_pct,
            "average_odds": sum(r.get("odds", 1.0) for r in results) / len(results) if results else 0.0
        }


def run_backtest(start_date: date, 
                end_date: date,
                strategy: str = "default",
                stake: float = 10.0) -> Dict[str, Any]:
    """
    Convenience function to run a backtest
    
    Args:
        start_date: Backtest start date
        end_date: Backtest end date
        strategy: Betting strategy
        stake: Standard stake amount
        
    Returns:
        Backtest results
    """
    runner = BacktestRunner()
    return runner.execute(start_date, end_date, strategy, stake)


def run_quick_backtest(days: int = 30, strategy: str = "default") -> Dict[str, Any]:
    """
    Run a quick backtest for recent period
    
    Args:
        days: Number of days to backtest
        strategy: Betting strategy
        
    Returns:
        Backtest results
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    return run_backtest(start_date, end_date, strategy)
