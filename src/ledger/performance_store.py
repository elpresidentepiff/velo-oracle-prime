"""
VÉLØ v10.1 - Performance Store
===============================

Performance ledger and KPI tracking system.
Stores daily metrics in Parquet/DB tables.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import os
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import json

logger = logging.getLogger(__name__)


class PerformanceStore:
    """
    Performance ledger and KPI tracking.
    
    Tracks:
    - Daily KPIs (A/E, IV, ROI, hit rate, drawdown)
    - Cumulative performance
    - Rolling windows (7d, 30d, 90d)
    - Model performance by version
    """
    
    def __init__(
        self,
        ledger_dir: str = "out/ledger",
        db_path: str = "velo_racing.db"
    ):
        """
        Initialize performance store.
        
        Args:
            ledger_dir: Directory for ledger files
            db_path: Database path
        """
        self.ledger_dir = Path(ledger_dir)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        
        logger.info(f"PerformanceStore initialized at {self.ledger_dir}")
    
    def log_daily_kpis(self, target_date: date, kpis: Dict):
        """
        Log daily KPIs.
        
        Args:
            target_date: Date of KPIs
            kpis: Dictionary of KPI values
        """
        logger.info(f"Logging KPIs for {target_date}...")
        
        # Add metadata
        kpis['date'] = target_date.isoformat()
        kpis['logged_at'] = datetime.now().isoformat()
        
        # Append to daily KPI file
        kpi_file = self.ledger_dir / "daily_kpis.parquet"
        
        if kpi_file.exists():
            existing = pd.read_parquet(kpi_file)
            new_row = pd.DataFrame([kpis])
            combined = pd.concat([existing, new_row], ignore_index=True)
        else:
            combined = pd.DataFrame([kpis])
        
        combined.to_parquet(kpi_file, index=False)
        
        logger.info(f"KPIs logged to {kpi_file}")
        
        # Also log to JSON for easy reading
        json_file = self.ledger_dir / f"kpis_{target_date.isoformat()}.json"
        with open(json_file, 'w') as f:
            json.dump(kpis, f, indent=2)
    
    def compute_daily_kpis(self, target_date: date) -> Dict:
        """
        Compute daily KPIs from predictions and results.
        
        Args:
            target_date: Date to compute
        
        Returns:
            Dictionary of KPIs
        """
        logger.info(f"Computing KPIs for {target_date}...")
        
        # Load predictions and results for date
        outcomes = self._load_outcomes(target_date)
        
        if outcomes.empty:
            logger.warning(f"No outcomes found for {target_date}")
            return self._empty_kpis()
        
        # Compute KPIs
        kpis = {
            'date': target_date.isoformat(),
            'races': outcomes['race_id'].nunique(),
            'picks': len(outcomes),
            'wins': outcomes['won'].sum(),
            'places': outcomes['placed'].sum(),
            'win_rate': outcomes['won'].mean(),
            'place_rate': outcomes['placed'].mean(),
            'ae_ratio': outcomes['ae'].mean(),
            'iv': outcomes['iv'].mean() if 'iv' in outcomes.columns else 0.0,
            'roi': self._compute_roi(outcomes),
            'profit': outcomes['profit'].sum(),
            'max_drawdown': self._compute_max_drawdown(outcomes),
            'sharpe_ratio': self._compute_sharpe(outcomes),
            'hit_rate': outcomes['won'].mean(),
        }
        
        logger.info(f"KPIs computed: ROI={kpis['roi']:.2f}%, A/E={kpis['ae_ratio']:.3f}")
        
        return kpis
    
    def get_rolling_kpis(self, end_date: date, window_days: int = 30) -> Dict:
        """
        Get rolling KPIs over a window.
        
        Args:
            end_date: End date of window
            window_days: Window size in days
        
        Returns:
            Dictionary of rolling KPIs
        """
        logger.info(f"Computing {window_days}-day rolling KPIs ending {end_date}...")
        
        start_date = end_date - timedelta(days=window_days)
        
        # Load all outcomes in window
        all_outcomes = []
        current_date = start_date
        
        while current_date <= end_date:
            outcomes = self._load_outcomes(current_date)
            if not outcomes.empty:
                all_outcomes.append(outcomes)
            current_date += timedelta(days=1)
        
        if not all_outcomes:
            logger.warning(f"No outcomes found in window")
            return self._empty_kpis()
        
        combined = pd.concat(all_outcomes, ignore_index=True)
        
        # Compute KPIs on combined data
        kpis = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'window_days': window_days,
            'races': combined['race_id'].nunique(),
            'picks': len(combined),
            'wins': combined['won'].sum(),
            'win_rate': combined['won'].mean(),
            'ae_ratio': combined['ae'].mean(),
            'roi': self._compute_roi(combined),
            'profit': combined['profit'].sum(),
            'max_drawdown': self._compute_max_drawdown(combined),
            'sharpe_ratio': self._compute_sharpe(combined),
        }
        
        logger.info(f"Rolling KPIs: ROI={kpis['roi']:.2f}%, A/E={kpis['ae_ratio']:.3f}")
        
        return kpis
    
    def get_cumulative_performance(self) -> pd.DataFrame:
        """
        Get cumulative performance over all time.
        
        Returns:
            DataFrame with cumulative metrics
        """
        logger.info("Loading cumulative performance...")
        
        kpi_file = self.ledger_dir / "daily_kpis.parquet"
        
        if not kpi_file.exists():
            logger.warning("No KPI history found")
            return pd.DataFrame()
        
        kpis = pd.read_parquet(kpi_file)
        
        # Compute cumulative metrics
        kpis['cumulative_profit'] = kpis['profit'].cumsum()
        kpis['cumulative_roi'] = (kpis['cumulative_profit'] / kpis['picks'].cumsum()) * 100
        
        return kpis
    
    def export_report(self, output_path: str, start_date: date = None, end_date: date = None):
        """
        Export performance report.
        
        Args:
            output_path: Output file path
            start_date: Start date (None for all)
            end_date: End date (None for all)
        """
        logger.info(f"Exporting performance report to {output_path}...")
        
        # Load KPIs
        kpi_file = self.ledger_dir / "daily_kpis.parquet"
        
        if not kpi_file.exists():
            logger.warning("No KPI history found")
            return
        
        kpis = pd.read_parquet(kpi_file)
        
        # Filter by date range
        if start_date:
            kpis = kpis[kpis['date'] >= start_date.isoformat()]
        if end_date:
            kpis = kpis[kpis['date'] <= end_date.isoformat()]
        
        # Generate report
        report = {
            'generated_at': datetime.now().isoformat(),
            'period': {
                'start': kpis['date'].min(),
                'end': kpis['date'].max(),
                'days': len(kpis)
            },
            'summary': {
                'total_races': kpis['races'].sum(),
                'total_picks': kpis['picks'].sum(),
                'total_wins': kpis['wins'].sum(),
                'total_profit': kpis['profit'].sum(),
                'avg_roi': kpis['roi'].mean(),
                'avg_ae': kpis['ae_ratio'].mean(),
                'best_day_roi': kpis['roi'].max(),
                'worst_day_roi': kpis['roi'].min(),
            },
            'daily_kpis': kpis.to_dict(orient='records')
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report exported to {output_path}")
    
    def _load_outcomes(self, target_date: date) -> pd.DataFrame:
        """
        Load outcomes from database.
        
        Args:
            target_date: Date to load
        
        Returns:
            Outcomes DataFrame
        """
        # Placeholder for database query
        return pd.DataFrame()
    
    def _compute_roi(self, outcomes: pd.DataFrame) -> float:
        """Compute ROI percentage."""
        if len(outcomes) == 0:
            return 0.0
        
        total_staked = len(outcomes)
        total_profit = outcomes['profit'].sum()
        roi = (total_profit / total_staked) * 100
        
        return roi
    
    def _compute_max_drawdown(self, outcomes: pd.DataFrame) -> float:
        """Compute maximum drawdown."""
        if len(outcomes) == 0:
            return 0.0
        
        cumulative = outcomes['profit'].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = running_max - cumulative
        max_drawdown = drawdown.max()
        
        return max_drawdown
    
    def _compute_sharpe(self, outcomes: pd.DataFrame) -> float:
        """Compute Sharpe ratio."""
        if len(outcomes) == 0:
            return 0.0
        
        returns = outcomes['profit']
        mean_return = returns.mean()
        std_return = returns.std()
        
        sharpe = mean_return / std_return if std_return > 0 else 0.0
        
        return sharpe
    
    def _empty_kpis(self) -> Dict:
        """Return empty KPI dictionary."""
        return {
            'races': 0,
            'picks': 0,
            'wins': 0,
            'places': 0,
            'win_rate': 0.0,
            'place_rate': 0.0,
            'ae_ratio': 0.0,
            'iv': 0.0,
            'roi': 0.0,
            'profit': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'hit_rate': 0.0,
        }


if __name__ == "__main__":
    # Test performance store
    logging.basicConfig(level=logging.INFO)
    
    store = PerformanceStore()
    
    # Test logging KPIs
    test_kpis = {
        'races': 10,
        'picks': 30,
        'wins': 5,
        'places': 12,
        'ae_ratio': 1.15,
        'roi': 8.5,
        'profit': 2.55
    }
    
    store.log_daily_kpis(date.today(), test_kpis)
    
    print("\n✅ Performance store test complete")
