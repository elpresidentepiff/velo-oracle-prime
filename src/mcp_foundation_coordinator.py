"""
MCP Foundation Layer Coordinator

Orchestrates the foundation layer agents according to VÉLØ MCP architecture:
1. RaceIndexAgent (mandatory first)
2. RunnerParserAgent
3. RatingsParserAgent
4. SanityCheckAgent (hard gate)

If SanityCheckAgent passes, outputs consolidated data for intelligence layer.
If fails, halts with error (no fallback).
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any

class MCPFoundationCoordinator:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.race_index = None
        self.runners = []
        self.ratings = []

    def run_race_index_agent(self) -> Dict:
        """Run RaceIndexAgent to define the universe."""
        print("🔍 Running RaceIndexAgent...")
        # In production, this would call the agent module directly
        # For now, use mock data
        from agents.race_index_agent import extract_race_index
        self.race_index = extract_race_index(self.pdf_path)
        print(f"   Extracted {len(self.race_index.get('races', []))} races for {self.race_index.get('venue')} on {self.race_index.get('date')}")
        return self.race_index

    def run_runner_parser_agent(self) -> List[Dict]:
        """Run RunnerParserAgent to extract horse identity data."""
        print("🏇 Running RunnerParserAgent...")
        from agents.runner_parser_agent import extract_runners
        self.runners = extract_runners(self.pdf_path)
        print(f"   Extracted {len(self.runners)} runners")
        return self.runners

    def run_ratings_parser_agent(self) -> List[Dict]:
        """Run RatingsParserAgent to extract performance metrics."""
        print("📊 Running RatingsParserAgent...")
        from agents.ratings_parser_agent import extract_ratings
        self.ratings = extract_ratings(self.pdf_path)
        print(f"   Extracted ratings for {len(self.ratings)} runners")
        return self.ratings

    def run_sanity_check_agent(self) -> bool:
        """Run SanityCheckAgent - hard gate with veto power."""
        print("🔒 Running SanityCheckAgent...")
        from agents.sanity_check_agent import sanity_check

        # Prepare data for sanity check
        data = {
            'race_index': self.race_index,
            'runners': self.runners,
            'ratings': self.ratings
        }

        # Run sanity check
        if sanity_check(self.race_index, self.runners, self.ratings):
            print("✅ SanityCheckAgent PASSED")
            return True
        else:
            print("❌ SanityCheckAgent FAILED - System halted")
            return False

    def run(self) -> Dict:
        """Execute the full foundation layer pipeline."""
        print("🚀 Starting MCP Foundation Layer Pipeline")
        print(f"   Processing PDF: {self.pdf_path.name}")

        # Step 1: RaceIndexAgent (mandatory first)
        self.run_race_index_agent()

        # Step 2 & 3: Parsing agents (could run in parallel in production)
        self.run_runner_parser_agent()
        self.run_ratings_parser_agent()

        # Step 4: SanityCheckAgent (hard gate)
        if not self.run_sanity_check_agent():
            sys.exit(1)  # Halt system

        # Consolidate results
        result = {
            'race_index': self.race_index,
            'runners': self.runners,
            'ratings': self.ratings,
            'status': 'PASSED',
            'metadata': {
                'venue': self.race_index.get('venue'),
                'date': self.race_index.get('date'),
                'race_count': len(self.race_index.get('races', [])),
                'runner_count': len(self.runners)
            }
        }

        print(f"
🎯 Foundation layer completed successfully")
        print(f"   Venue: {result['metadata']['venue']}")
        print(f"   Date: {result['metadata']['date']}")
        print(f"   Races: {result['metadata']['race_count']}")
        print(f"   Runners: {result['metadata']['runner_count']}")

        return result

def main(pdf_path_str: str):
    """Entry point."""
    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    coordinator = MCPFoundationCoordinator(pdf_path)
    result = coordinator.run()

    # Output result as JSON
    print("
📋 Foundation Layer Output:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python mcp_foundation_coordinator.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
