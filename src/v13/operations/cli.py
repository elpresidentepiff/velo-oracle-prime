"""
Shadow Racing CLI Tool

Command-line interface for running shadow racing and generating reports.

Usage:
    python -m v13.operations.cli run-race --race-file race_data.json
    python -m v13.operations.cli finalize --episode-id race_2026-01-19_R3 --result-file result.json
    python -m v13.operations.cli report --date 2026-01-19
    python -m v13.operations.cli stats

Author: VÉLØ Team
Date: 2026-01-19
Status: Active
"""

import argparse
import sqlite3
import json
import sys
from datetime import datetime, date
from pathlib import Path

from .shadow_racing_runner import ShadowRacingRunner
from .daily_metrics import DailyMetricsCollector


def get_db_connection() -> sqlite3.Connection:
    """Get database connection."""
    # Default database path
    db_path = Path(__file__).parent.parent.parent.parent / "governance.db"
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        print("Creating new database...", file=sys.stderr)
        
        # Create database with schema
        conn = sqlite3.connect(str(db_path))
        schema_path = Path(__file__).parent.parent.parent.parent / "database" / "schema_v13_governance.sql"
        
        if schema_path.exists():
            with open(schema_path, "r") as f:
                conn.executescript(f.read())
            print(f"✅ Database created at {db_path}", file=sys.stderr)
        else:
            print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
            sys.exit(1)
    else:
        conn = sqlite3.connect(str(db_path))
    
    return conn


def cmd_run_race(args):
    """Run shadow racing for a race."""
    # Load race data
    with open(args.race_file, "r") as f:
        race_data = json.load(f)
    
    # Run shadow racing
    conn = get_db_connection()
    runner = ShadowRacingRunner(conn)
    
    episode_id = runner.run_race(race_data)
    
    print(f"✅ Shadow racing complete")
    print(f"Episode ID: {episode_id}")
    print(f"Decision Time: {race_data.get('off_time', 'N/A')}")
    print(f"Venue: {race_data.get('venue', 'N/A')}")
    
    # Show episode stats
    stats = runner.get_episode_stats()
    print(f"\nEpisode Stats:")
    print(f"- Processed: {stats['processed']}")
    print(f"- Finalized: {stats['finalized']}")
    print(f"- Pending: {stats['pending']}")
    
    conn.close()


def cmd_finalize(args):
    """Finalize episode with race result."""
    # Load result data
    with open(args.result_file, "r") as f:
        result = json.load(f)
    
    # Finalize episode
    conn = get_db_connection()
    runner = ShadowRacingRunner(conn)
    
    runner.finalize_race(args.episode_id, result)
    
    print(f"✅ Episode finalized: {args.episode_id}")
    print(f"Winner: {result.get('winner', 'N/A')}")
    print(f"Placed: {', '.join(result.get('placed', []))}")
    
    conn.close()


def cmd_report(args):
    """Generate daily report."""
    # Parse date
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()
    
    # Generate report
    conn = get_db_connection()
    collector = DailyMetricsCollector(conn)
    
    report = collector.generate_report(target_date)
    
    print(report)
    
    # Optionally save to file
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\n✅ Report saved to {args.output}")
    
    conn.close()


def cmd_stats(args):
    """Show summary statistics."""
    conn = get_db_connection()
    collector = DailyMetricsCollector(conn)
    
    stats = collector.get_summary_stats()
    
    print("=== SHADOW RACING V13 SUMMARY STATS ===\n")
    print(f"Total Episodes: {stats['total_episodes']}")
    print(f"Total Proposals: {stats['total_proposals']}")
    print(f"Pending Proposals: {stats['pending_proposals']}")
    print(f"Accepted Proposals: {stats['accepted_proposals']}")
    print(f"Rejected Proposals: {stats['rejected_proposals']}")
    print(f"Acceptance Rate: {stats['acceptance_rate']:.1%}")
    print(f"Doctrine Version: {stats['doctrine_version']}")
    
    conn.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Shadow Racing V13 CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run shadow racing for a race
  python -m v13.operations.cli run-race --race-file race_data.json
  
  # Finalize episode with result
  python -m v13.operations.cli finalize --episode-id race_2026-01-19_R3 --result-file result.json
  
  # Generate daily report
  python -m v13.operations.cli report --date 2026-01-19
  
  # Show summary stats
  python -m v13.operations.cli stats
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # run-race command
    parser_run = subparsers.add_parser("run-race", help="Run shadow racing for a race")
    parser_run.add_argument("--race-file", required=True, help="Path to race data JSON file")
    parser_run.set_defaults(func=cmd_run_race)
    
    # finalize command
    parser_finalize = subparsers.add_parser("finalize", help="Finalize episode with race result")
    parser_finalize.add_argument("--episode-id", required=True, help="Episode ID")
    parser_finalize.add_argument("--result-file", required=True, help="Path to result JSON file")
    parser_finalize.set_defaults(func=cmd_finalize)
    
    # report command
    parser_report = subparsers.add_parser("report", help="Generate daily report")
    parser_report.add_argument("--date", help="Date to report on (YYYY-MM-DD, defaults to today)")
    parser_report.add_argument("--output", help="Output file path (optional)")
    parser_report.set_defaults(func=cmd_report)
    
    # stats command
    parser_stats = subparsers.add_parser("stats", help="Show summary statistics")
    parser_stats.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
