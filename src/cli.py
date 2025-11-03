"""
VÉLØ v10.1 - CLI Interface
===========================

Command-line interface for operators.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import argparse
import logging
from datetime import datetime, date
import sys

logger = logging.getLogger(__name__)


def analyze_command(args):
    """Analyze races for a date."""
    print(f"🔮 Analyzing races for {args.date}...")
    print("⚠️  Analysis module not yet implemented")
    # Would call Oracle analysis here
    

def backtest_command(args):
    """Run backtest over date range."""
    print(f"📈 Running backtest from {args.start} to {args.end}...")
    print("⚠️  Backtest module not yet implemented")
    # Would run backtest here


def report_command(args):
    """Generate performance report."""
    from ledger.performance_store import PerformanceStore
    
    print(f"📊 Generating report for {args.date}...")
    
    store = PerformanceStore()
    
    # Parse date
    if args.date == 'TODAY':
        target_date = date.today()
    else:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    # Compute KPIs
    kpis = store.compute_daily_kpis(target_date)
    
    # Log KPIs
    store.log_daily_kpis(target_date, kpis)
    
    # Export report if requested
    if args.export:
        store.export_report(args.export)
    
    print(f"✅ Report generated")


def live_command(args):
    """Run live execution (dry-run or real)."""
    print(f"🎯 Live execution mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print("⚠️  Execution module not yet implemented")
    # Would run live execution here


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='VÉLØ v10.1 - Command Line Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze races')
    analyze_parser.add_argument('--date', type=str, default='TODAY',
                               help='Date to analyze (YYYY-MM-DD or TODAY)')
    analyze_parser.add_argument('--export', type=str, default=None,
                               help='Export predictions to JSON file')
    
    # Backtest command
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
    backtest_parser.add_argument('--start', type=str, required=True,
                                help='Start date (YYYY-MM-DD)')
    backtest_parser.add_argument('--end', type=str, required=True,
                                help='End date (YYYY-MM-DD)')
    backtest_parser.add_argument('--export', type=str, default=None,
                                help='Export results to JSON file')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--date', type=str, default='TODAY',
                              help='Date for report (YYYY-MM-DD or TODAY)')
    report_parser.add_argument('--export', type=str, default=None,
                              help='Export report to JSON file')
    
    # Live command
    live_parser = subparsers.add_parser('live', help='Live execution')
    live_parser.add_argument('--dry-run', action='store_true',
                            help='Dry run mode (no real bets)')
    live_parser.add_argument('--max-liab-per-race', type=str, default='1.5%',
                            help='Max liability per race')
    live_parser.add_argument('--max-liab-day', type=str, default='6%',
                            help='Max liability per day')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command
    if args.command == 'analyze':
        analyze_command(args)
    elif args.command == 'backtest':
        backtest_command(args)
    elif args.command == 'report':
        report_command(args)
    elif args.command == 'live':
        live_command(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
