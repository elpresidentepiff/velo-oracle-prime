"""
VÉLØ Oracle - Monitoring Dashboard
Real-time system health and performance monitoring
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import time


@dataclass
class SystemMetrics:
    """System-wide metrics"""
    timestamp: datetime
    api_latency_ms: float
    database_latency_ms: float
    prediction_throughput: float  # predictions per minute
    error_rate: float  # percentage
    uptime_pct: float
    active_connections: int


@dataclass
class BankrollMetrics:
    """Bankroll performance metrics"""
    timestamp: datetime
    current_balance: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    roi_pct: float
    drawdown_pct: float
    total_bets: int
    win_rate: float
    avg_stake: float


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    timestamp: datetime
    model_version: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc: float
    predictions_today: int
    last_retrain: datetime


class MonitoringDashboard:
    """
    Centralized monitoring dashboard for VÉLØ Oracle.
    
    Tracks:
    - System health (API, database, errors)
    - Bankroll performance (P&L, ROI, drawdown)
    - Model performance (accuracy, predictions)
    - Live betting activity
    """
    
    def __init__(self):
        self.system_metrics_history: List[SystemMetrics] = []
        self.bankroll_metrics_history: List[BankrollMetrics] = []
        self.model_metrics_history: List[ModelMetrics] = []
        
        self.start_time = datetime.now()
        self.total_requests = 0
        self.total_errors = 0
        
    def record_system_metrics(
        self,
        api_latency_ms: float,
        database_latency_ms: float,
        prediction_throughput: float,
        error_rate: float,
        active_connections: int
    ):
        """Record system metrics"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        uptime_pct = 99.9  # TODO: Calculate from downtime tracking
        
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            api_latency_ms=api_latency_ms,
            database_latency_ms=database_latency_ms,
            prediction_throughput=prediction_throughput,
            error_rate=error_rate,
            uptime_pct=uptime_pct,
            active_connections=active_connections
        )
        
        self.system_metrics_history.append(metrics)
        
        # Keep last 1000 entries
        if len(self.system_metrics_history) > 1000:
            self.system_metrics_history = self.system_metrics_history[-1000:]
    
    def record_bankroll_metrics(
        self,
        current_balance: float,
        daily_pnl: float,
        weekly_pnl: float,
        monthly_pnl: float,
        roi_pct: float,
        drawdown_pct: float,
        total_bets: int,
        win_rate: float,
        avg_stake: float
    ):
        """Record bankroll metrics"""
        metrics = BankrollMetrics(
            timestamp=datetime.now(),
            current_balance=current_balance,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
            roi_pct=roi_pct,
            drawdown_pct=drawdown_pct,
            total_bets=total_bets,
            win_rate=win_rate,
            avg_stake=avg_stake
        )
        
        self.bankroll_metrics_history.append(metrics)
        
        if len(self.bankroll_metrics_history) > 1000:
            self.bankroll_metrics_history = self.bankroll_metrics_history[-1000:]
    
    def record_model_metrics(
        self,
        model_version: str,
        accuracy: float,
        precision: float,
        recall: float,
        f1_score: float,
        auc: float,
        predictions_today: int,
        last_retrain: datetime
    ):
        """Record model metrics"""
        metrics = ModelMetrics(
            timestamp=datetime.now(),
            model_version=model_version,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            auc=auc,
            predictions_today=predictions_today,
            last_retrain=last_retrain
        )
        
        self.model_metrics_history.append(metrics)
        
        if len(self.model_metrics_history) > 1000:
            self.model_metrics_history = self.model_metrics_history[-1000:]
    
    def get_current_status(self) -> Dict:
        """Get current system status"""
        latest_system = self.system_metrics_history[-1] if self.system_metrics_history else None
        latest_bankroll = self.bankroll_metrics_history[-1] if self.bankroll_metrics_history else None
        latest_model = self.model_metrics_history[-1] if self.model_metrics_history else None
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": asdict(latest_system) if latest_system else None,
            "bankroll": asdict(latest_bankroll) if latest_bankroll else None,
            "model": asdict(latest_model) if latest_model else None,
            "status": self._determine_overall_status(latest_system, latest_bankroll, latest_model)
        }
    
    def _determine_overall_status(
        self,
        system: Optional[SystemMetrics],
        bankroll: Optional[BankrollMetrics],
        model: Optional[ModelMetrics]
    ) -> str:
        """Determine overall system status"""
        if not all([system, bankroll, model]):
            return "INITIALIZING"
        
        # Check for critical issues
        if system.error_rate > 10:
            return "DEGRADED"
        if system.uptime_pct < 95:
            return "DEGRADED"
        if bankroll.drawdown_pct > 20:
            return "WARNING"
        if model.accuracy < 0.6:
            return "WARNING"
        
        return "OPERATIONAL"
    
    def get_performance_summary(self, period: str = "day") -> Dict:
        """Get performance summary for a period"""
        if period == "day":
            cutoff = datetime.now() - timedelta(days=1)
        elif period == "week":
            cutoff = datetime.now() - timedelta(weeks=1)
        elif period == "month":
            cutoff = datetime.now() - timedelta(days=30)
        else:
            cutoff = datetime.now() - timedelta(days=1)
        
        # Filter metrics
        bankroll_metrics = [
            m for m in self.bankroll_metrics_history
            if m.timestamp >= cutoff
        ]
        
        if not bankroll_metrics:
            return {"error": "No data for period"}
        
        latest = bankroll_metrics[-1]
        earliest = bankroll_metrics[0]
        
        return {
            "period": period,
            "starting_balance": earliest.current_balance,
            "ending_balance": latest.current_balance,
            "pnl": latest.current_balance - earliest.current_balance,
            "roi_pct": latest.roi_pct,
            "total_bets": latest.total_bets,
            "win_rate": latest.win_rate,
            "max_drawdown": max(m.drawdown_pct for m in bankroll_metrics),
            "avg_daily_pnl": sum(m.daily_pnl for m in bankroll_metrics) / len(bankroll_metrics)
        }
    
    def get_health_check(self) -> Dict:
        """Get detailed health check"""
        latest_system = self.system_metrics_history[-1] if self.system_metrics_history else None
        
        if not latest_system:
            return {
                "healthy": False,
                "message": "No metrics available"
            }
        
        checks = {
            "api_latency": latest_system.api_latency_ms < 500,
            "database_latency": latest_system.database_latency_ms < 1000,
            "error_rate": latest_system.error_rate < 5,
            "uptime": latest_system.uptime_pct > 99
        }
        
        all_healthy = all(checks.values())
        
        return {
            "healthy": all_healthy,
            "checks": checks,
            "metrics": asdict(latest_system),
            "message": "All systems operational" if all_healthy else "Some systems degraded"
        }
    
    def get_live_activity(self, limit: int = 10) -> List[Dict]:
        """Get live betting activity (placeholder)"""
        # TODO: Integrate with betting ledger
        return []
    
    def export_metrics(self, format: str = "json") -> Dict:
        """Export all metrics"""
        return {
            "system_metrics": [asdict(m) for m in self.system_metrics_history[-100:]],
            "bankroll_metrics": [asdict(m) for m in self.bankroll_metrics_history[-100:]],
            "model_metrics": [asdict(m) for m in self.model_metrics_history[-100:]]
        }
