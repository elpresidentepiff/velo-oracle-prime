"""
VÉLØ Oracle - Automated Alerting System
Sends email/SMS alerts for critical events
"""
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class AlertType(Enum):
    """Alert type classifications"""
    SYSTEM_HEALTH = "System Health"
    PERFORMANCE = "Performance"
    BANKROLL = "Bankroll"
    MODEL = "Model"
    DATA = "Data"
    SECURITY = "Security"


@dataclass
class Alert:
    """Alert data structure"""
    severity: AlertSeverity
    alert_type: AlertType
    title: str
    message: str
    timestamp: datetime
    metadata: Dict


class AlertSystem:
    """
    Automated alerting system for critical events.
    
    Integrates with:
    - Email (SendGrid/SMTP)
    - SMS (Twilio)
    - Slack/Discord webhooks
    """
    
    def __init__(
        self,
        email_enabled: bool = True,
        sms_enabled: bool = False,
        webhook_enabled: bool = False
    ):
        self.email_enabled = email_enabled
        self.sms_enabled = sms_enabled
        self.webhook_enabled = webhook_enabled
        
        # Alert thresholds
        self.thresholds = {
            "daily_loss_pct": 10.0,
            "drawdown_pct": 15.0,
            "api_error_rate": 5.0,
            "model_accuracy_drop": 10.0,
            "database_latency_ms": 1000
        }
        
        # Alert history (in-memory for now, should be in DB)
        self.alert_history: List[Alert] = []
        
    def check_bankroll_health(self, bankroll_state: Dict) -> Optional[Alert]:
        """Check bankroll health and generate alerts"""
        # Daily loss alert
        if bankroll_state.get("daily_pnl", 0) < 0:
            loss_pct = abs(bankroll_state["daily_pnl"] / bankroll_state["starting_balance"]) * 100
            
            if loss_pct >= self.thresholds["daily_loss_pct"]:
                return self._create_alert(
                    severity=AlertSeverity.CRITICAL,
                    alert_type=AlertType.BANKROLL,
                    title=f"Daily Loss Alert: -{loss_pct:.1f}%",
                    message=f"Bankroll down {loss_pct:.1f}% today. Current: £{bankroll_state['current_balance']:.2f}",
                    metadata=bankroll_state
                )
        
        # Drawdown alert
        drawdown_pct = bankroll_state.get("current_drawdown_pct", 0)
        if drawdown_pct >= self.thresholds["drawdown_pct"]:
            return self._create_alert(
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.BANKROLL,
                title=f"Drawdown Alert: -{drawdown_pct:.1f}%",
                message=f"Current drawdown: {drawdown_pct:.1f}% from peak (£{bankroll_state['peak_balance']:.2f})",
                metadata=bankroll_state
            )
        
        # Stop-loss triggered
        if bankroll_state.get("is_stopped", False):
            return self._create_alert(
                severity=AlertSeverity.EMERGENCY,
                alert_type=AlertType.BANKROLL,
                title="STOP-LOSS TRIGGERED",
                message=f"Trading halted. Cooldown until {bankroll_state.get('cooldown_until')}",
                metadata=bankroll_state
            )
        
        return None
    
    def check_model_performance(self, metrics: Dict) -> Optional[Alert]:
        """Check model performance metrics"""
        # Accuracy drop
        current_accuracy = metrics.get("accuracy", 0)
        baseline_accuracy = metrics.get("baseline_accuracy", 0)
        
        if baseline_accuracy > 0:
            accuracy_drop = ((baseline_accuracy - current_accuracy) / baseline_accuracy) * 100
            
            if accuracy_drop >= self.thresholds["model_accuracy_drop"]:
                return self._create_alert(
                    severity=AlertSeverity.WARNING,
                    alert_type=AlertType.MODEL,
                    title=f"Model Accuracy Drop: -{accuracy_drop:.1f}%",
                    message=f"Model accuracy dropped from {baseline_accuracy:.1f}% to {current_accuracy:.1f}%",
                    metadata=metrics
                )
        
        # Model retraining failure
        if metrics.get("retraining_failed", False):
            return self._create_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.MODEL,
                title="Model Retraining Failed",
                message=f"Automated retraining failed: {metrics.get('error_message', 'Unknown error')}",
                metadata=metrics
            )
        
        return None
    
    def check_system_health(self, health_metrics: Dict) -> Optional[Alert]:
        """Check overall system health"""
        # API error rate
        error_rate = health_metrics.get("api_error_rate", 0)
        if error_rate >= self.thresholds["api_error_rate"]:
            return self._create_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.SYSTEM_HEALTH,
                title=f"High API Error Rate: {error_rate:.1f}%",
                message=f"API error rate is {error_rate:.1f}%. Check logs for details.",
                metadata=health_metrics
            )
        
        # Database latency
        db_latency = health_metrics.get("database_latency_ms", 0)
        if db_latency >= self.thresholds["database_latency_ms"]:
            return self._create_alert(
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.SYSTEM_HEALTH,
                title=f"High Database Latency: {db_latency}ms",
                message=f"Database queries taking {db_latency}ms on average. Performance degraded.",
                metadata=health_metrics
            )
        
        # Database connection loss
        if not health_metrics.get("database_connected", True):
            return self._create_alert(
                severity=AlertSeverity.EMERGENCY,
                alert_type=AlertType.SYSTEM_HEALTH,
                title="Database Connection Lost",
                message="Cannot connect to Supabase database. System offline.",
                metadata=health_metrics
            )
        
        return None
    
    def check_data_quality(self, data_metrics: Dict) -> Optional[Alert]:
        """Check data quality metrics"""
        # Missing data
        missing_pct = data_metrics.get("missing_data_pct", 0)
        if missing_pct > 20:
            return self._create_alert(
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.DATA,
                title=f"High Missing Data: {missing_pct:.1f}%",
                message=f"{missing_pct:.1f}% of expected data is missing. Check data pipeline.",
                metadata=data_metrics
            )
        
        # Stale data
        if data_metrics.get("data_stale", False):
            return self._create_alert(
                severity=AlertSeverity.WARNING,
                alert_type=AlertType.DATA,
                title="Stale Data Detected",
                message=f"Data not updated in {data_metrics.get('hours_since_update', 0)} hours",
                metadata=data_metrics
            )
        
        return None
    
    def _create_alert(
        self,
        severity: AlertSeverity,
        alert_type: AlertType,
        title: str,
        message: str,
        metadata: Dict
    ) -> Alert:
        """Create and log an alert"""
        alert = Alert(
            severity=severity,
            alert_type=alert_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        self.alert_history.append(alert)
        
        # Send alert via configured channels
        self._send_alert(alert)
        
        return alert
    
    def _send_alert(self, alert: Alert):
        """Send alert via configured channels"""
        # Format alert message
        formatted_message = self._format_alert(alert)
        
        # Email
        if self.email_enabled:
            self._send_email(alert, formatted_message)
        
        # SMS (for CRITICAL and EMERGENCY only)
        if self.sms_enabled and alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            self._send_sms(alert, formatted_message)
        
        # Webhook
        if self.webhook_enabled:
            self._send_webhook(alert, formatted_message)
        
        # Always log to console
        print(f"\n{'='*60}")
        print(f"🚨 ALERT: {alert.severity.value} - {alert.alert_type.value}")
        print(f"{'='*60}")
        print(formatted_message)
        print(f"{'='*60}\n")
    
    def _format_alert(self, alert: Alert) -> str:
        """Format alert message"""
        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🆘"
        }
        
        return f"""
{emoji.get(alert.severity, '🔔')} {alert.severity.value} ALERT

Type: {alert.alert_type.value}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.title}

{alert.message}

---
VÉLØ Oracle Monitoring System
"""
    
    def _send_email(self, alert: Alert, message: str):
        """Send email alert (placeholder - integrate with SendGrid/SMTP)"""
        # TODO: Integrate with SendGrid or SMTP
        # For now, just log
        print(f"📧 Email alert would be sent: {alert.title}")
    
    def _send_sms(self, alert: Alert, message: str):
        """Send SMS alert (placeholder - integrate with Twilio)"""
        # TODO: Integrate with Twilio
        print(f"📱 SMS alert would be sent: {alert.title}")
    
    def _send_webhook(self, alert: Alert, message: str):
        """Send webhook alert (placeholder - integrate with Slack/Discord)"""
        # TODO: Integrate with webhook service
        print(f"🔗 Webhook alert would be sent: {alert.title}")
    
    def get_recent_alerts(self, limit: int = 10) -> List[Alert]:
        """Get recent alerts"""
        return sorted(
            self.alert_history,
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity"""
        return [a for a in self.alert_history if a.severity == severity]
