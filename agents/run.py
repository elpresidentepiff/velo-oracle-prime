#!/usr/bin/env python3
"""
CLI for running LangGraph agent orchestration

Usage:
    python -m agents.run --date 2026-01-08
    python -m agents.run --date 2026-01-08 --dry-run

Output: JSON summary to stdout

Version: 1.0.0
"""

import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, Any

from agents.graph import compile_agent_graph
from agents.models import AgentState, AgentRunSummary


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

def run_agent(date: str, dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """
    Run the agent orchestration pipeline
    
    Args:
        date: Race date in YYYY-MM-DD format
        dry_run: If True, use mock data and skip database writes
        verbose: If True, enable debug logging
        
    Returns:
        Summary dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting agent run for date: {date}")
    logger.info(f"Dry run mode: {dry_run}")
    
    # Create initial state
    initial_state = {
        "date": date,
        "dry_run": dry_run,
        "races": [],
        "races_count": 0,
        "valid_races": [],
        "invalid_races": [],
        "validation_errors": [],
        "analyze_results": {},
        "critic_results": {},
        "archive_results": {},
        "races_processed": 0,
        "successes": 0,
        "failures": 0,
        "failure_details": [],
        "run_id": f"run_{int(datetime.utcnow().timestamp())}",
        "start_time": None,
        "end_time": None,
        "total_time_seconds": 0.0
    }
    
    try:
        # Compile and run graph
        logger.info("Compiling agent graph...")
        app = compile_agent_graph()
        
        logger.info("Executing agent pipeline...")
        result = app.invoke(initial_state)
        
        # Build summary
        summary = AgentRunSummary(
            run_id=result["run_id"],
            date=date,
            races_processed=result["races_processed"],
            successes=result["successes"],
            failures=result["failures"],
            total_time_seconds=result["total_time_seconds"],
            failure_details=result["failure_details"]
        )
        
        logger.info("Agent run completed successfully")
        return summary.dict()
        
    except Exception as e:
        logger.error(f"Agent run failed: {e}", exc_info=True)
        
        # Return error summary
        error_summary = {
            "run_id": initial_state["run_id"],
            "date": date,
            "races_processed": 0,
            "successes": 0,
            "failures": 1,
            "total_time_seconds": 0.0,
            "failure_details": [
                {
                    "error": f"Pipeline failure: {str(e)}"
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        return error_summary


def main():
    """Main CLI entrypoint"""
    parser = argparse.ArgumentParser(
        description="Run LangGraph agent orchestration for VÉLØ Oracle Prime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with real data for specific date
  python -m agents.run --date 2026-01-08

  # Run in dry-run mode with mock data
  python -m agents.run --date 2026-01-08 --dry-run

  # Run with verbose logging
  python -m agents.run --date 2026-01-08 --dry-run --verbose
        """
    )
    
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Race date in YYYY-MM-DD format"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock data and skip database writes"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(json.dumps({
            "error": f"Invalid date format: {args.date}. Expected YYYY-MM-DD"
        }), file=sys.stderr)
        sys.exit(1)
    
    # Run agent
    summary = run_agent(date=args.date, dry_run=args.dry_run, verbose=args.verbose)
    
    # Output JSON summary to stdout
    print(json.dumps(summary, indent=2))
    
    # Exit with appropriate code
    if summary["failures"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
