"""
Daily Metrics Collector for Shadow Racing V13

Generates daily reports with:
- Episodes processed
- Proposals by critic + severity
- Pending queue size
- Top finding types
- CRITICAL leakage events

Author: VÉLØ Team
Date: 2026-01-19
Status: Active
"""

import sqlite3
from datetime import datetime, UTC, timedelta, date
from collections import Counter
from typing import Dict, Any, List


class DailyMetricsCollector:
    """
    Collects and reports daily shadow racing metrics.
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def generate_report(self, target_date: date = None) -> str:
        """
        Generate daily report for shadow racing.
        
        Args:
            target_date: Date to report on (defaults to today)
        
        Returns:
            Formatted report string
        """
        if target_date is None:
            target_date = datetime.now(UTC).date()
        
        # Episodes
        episodes = self._get_episode_stats(target_date)
        
        # Proposals
        proposals = self._get_proposal_stats(target_date)
        
        # Pending queue
        pending = self._get_pending_queue_stats()
        
        # Top finding types
        top_findings = self._get_top_finding_types(target_date)
        
        # CRITICAL leakage events
        critical_leakage = self._get_critical_leakage_events(target_date)
        
        # Format report
        report = f"""
=== SHADOW RACING V13 DAILY REPORT ===
Date: {target_date}

EPISODES:
- Processed: {episodes['processed']}
- Finalized: {episodes['finalized']}
- Pending: {episodes['pending']}

PROPOSALS CREATED:
"""
        
        for critic, counts in proposals.items():
            total = sum(counts.values())
            report += f"- {critic}: {total} ("
            report += ", ".join([f"{sev}: {count}" for sev, count in counts.items()])
            report += ")\n"
        
        report += f"""
PENDING QUEUE:
- Total: {pending['total']} proposals
- By Critic: {', '.join([f"{c} ({n})" for c, n in pending['by_critic'].items()])}
- By Severity: {', '.join([f"{s} ({n})" for s, n in pending['by_severity'].items()])}

TOP 10 FINDING TYPES:
"""
        
        for i, (finding_type, count) in enumerate(top_findings[:10], 1):
            report += f"{i}. {finding_type} ({count} occurrences)\n"
        
        if critical_leakage:
            report += "\nCRITICAL LEAKAGE EVENTS:\n"
            for i, event in enumerate(critical_leakage, 1):
                report += f"{i}. Episode: {event['episode_id']}\n"
                report += f"   Finding: {event['finding_type']}\n"
                report += f"   Description: {event['description']}\n"
                report += f"   Proposed Change: {event['proposed_change']}\n\n"
        else:
            report += "\nCRITICAL LEAKAGE EVENTS: None\n"
        
        return report
    
    def _get_episode_stats(self, target_date: date) -> Dict[str, int]:
        """
        Get episode statistics for date.
        
        Args:
            target_date: Date to query
        
        Returns:
            Dict with episode counts
        """
        # Episodes created on target date
        start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        end_time = start_time + timedelta(days=1)
        
        cursor = self.db.execute(
            """
            SELECT COUNT(*) FROM episodes
            WHERE created_at >= ? AND created_at < ?
            """,
            (start_time.isoformat(), end_time.isoformat())
        )
        processed = cursor.fetchone()[0]
        
        cursor = self.db.execute(
            """
            SELECT COUNT(*) FROM episodes
            WHERE created_at >= ? AND created_at < ? AND finalized = TRUE
            """,
            (start_time.isoformat(), end_time.isoformat())
        )
        finalized = cursor.fetchone()[0]
        
        pending = processed - finalized
        
        return {
            "processed": processed,
            "finalized": finalized,
            "pending": pending,
        }
    
    def _get_proposal_stats(self, target_date: date) -> Dict[str, Dict[str, int]]:
        """
        Get proposal statistics by critic and severity.
        
        Args:
            target_date: Date to query
        
        Returns:
            Dict of critic -> severity -> count
        """
        start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        end_time = start_time + timedelta(days=1)
        
        cursor = self.db.execute(
            """
            SELECT critic_type, severity, COUNT(*) as count
            FROM patch_proposals
            WHERE created_at >= ? AND created_at < ?
            GROUP BY critic_type, severity
            """,
            (start_time.isoformat(), end_time.isoformat())
        )
        
        stats = {}
        for row in cursor.fetchall():
            critic_type, severity, count = row
            if critic_type not in stats:
                stats[critic_type] = {}
            stats[critic_type][severity] = count
        
        # Ensure all critics are present
        for critic in ["LEAKAGE", "BIAS", "FEATURE", "DECISION"]:
            if critic not in stats:
                stats[critic] = {}
        
        return stats
    
    def _get_pending_queue_stats(self) -> Dict[str, Any]:
        """
        Get pending queue statistics.
        
        Returns:
            Dict with pending queue stats
        """
        # Total pending
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM patch_proposals WHERE status = 'PENDING'"
        )
        total = cursor.fetchone()[0]
        
        # By critic
        cursor = self.db.execute(
            """
            SELECT critic_type, COUNT(*) as count
            FROM patch_proposals
            WHERE status = 'PENDING'
            GROUP BY critic_type
            """
        )
        by_critic = {row[0]: row[1] for row in cursor.fetchall()}
        
        # By severity
        cursor = self.db.execute(
            """
            SELECT severity, COUNT(*) as count
            FROM patch_proposals
            WHERE status = 'PENDING'
            GROUP BY severity
            """
        )
        by_severity = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "total": total,
            "by_critic": by_critic,
            "by_severity": by_severity,
        }
    
    def _get_top_finding_types(self, target_date: date) -> List[tuple]:
        """
        Get top finding types for date.
        
        Args:
            target_date: Date to query
        
        Returns:
            List of (finding_type, count) tuples sorted by count descending
        """
        start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        end_time = start_time + timedelta(days=1)
        
        cursor = self.db.execute(
            """
            SELECT finding_type, COUNT(*) as count
            FROM patch_proposals
            WHERE created_at >= ? AND created_at < ?
            GROUP BY finding_type
            ORDER BY count DESC
            """,
            (start_time.isoformat(), end_time.isoformat())
        )
        
        return [(row[0], row[1]) for row in cursor.fetchall()]
    
    def _get_critical_leakage_events(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Get CRITICAL leakage events for date.
        
        Args:
            target_date: Date to query
        
        Returns:
            List of CRITICAL leakage event dicts
        """
        start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        end_time = start_time + timedelta(days=1)
        
        cursor = self.db.execute(
            """
            SELECT pe.episode_id, pp.finding_type, pp.description, pp.proposed_change
            FROM patch_proposals pp
            JOIN proposal_episodes pe ON pp.id = pe.proposal_id
            WHERE pp.critic_type = 'LEAKAGE'
              AND pp.severity = 'CRITICAL'
              AND pp.created_at >= ?
              AND pp.created_at < ?
            """,
            (start_time.isoformat(), end_time.isoformat())
        )
        
        events = []
        for row in cursor.fetchall():
            import json
            events.append({
                "episode_id": row[0],
                "finding_type": row[1],
                "description": row[2],
                "proposed_change": json.loads(row[3]),
            })
        
        return events
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics across all time.
        
        Returns:
            Dict with summary stats
        """
        # Total episodes
        cursor = self.db.execute("SELECT COUNT(*) FROM episodes")
        total_episodes = cursor.fetchone()[0]
        
        # Total proposals
        cursor = self.db.execute("SELECT COUNT(*) FROM patch_proposals")
        total_proposals = cursor.fetchone()[0]
        
        # Pending proposals
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM patch_proposals WHERE status = 'PENDING'"
        )
        pending_proposals = cursor.fetchone()[0]
        
        # Accepted proposals
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM patch_proposals WHERE status = 'ACCEPTED'"
        )
        accepted_proposals = cursor.fetchone()[0]
        
        # Rejected proposals
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM patch_proposals WHERE status = 'REJECTED'"
        )
        rejected_proposals = cursor.fetchone()[0]
        
        # Acceptance rate
        total_reviewed = accepted_proposals + rejected_proposals
        acceptance_rate = (
            accepted_proposals / total_reviewed if total_reviewed > 0 else 0.0
        )
        
        # Active doctrine version
        cursor = self.db.execute(
            "SELECT version FROM doctrine_versions WHERE active = TRUE"
        )
        row = cursor.fetchone()
        doctrine_version = row[0] if row else "13.0.0"
        
        return {
            "total_episodes": total_episodes,
            "total_proposals": total_proposals,
            "pending_proposals": pending_proposals,
            "accepted_proposals": accepted_proposals,
            "rejected_proposals": rejected_proposals,
            "acceptance_rate": acceptance_rate,
            "doctrine_version": doctrine_version,
        }
