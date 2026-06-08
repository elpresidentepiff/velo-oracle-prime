"""
Run VÉLØ LLM Council — post-Sigma nightly tribunal.

Run after sigma close. Never blocks sigma_audits truth writes.
Blocks: learning admission, shadow consume, promotion evidence.

Usage:
    PYTHONPATH=. python scripts/audit/run_velo_council.py --date YYYY-MM-DD
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.velo.council.council_orchestrator import CouncilOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Run VÉLØ LLM Council tribunal")
    parser.add_argument("--date", type=str, required=True, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    print(f"Repo Root: {repo_root}")

    orchestrator = CouncilOrchestrator(args.date, repo_root)
    results = orchestrator.run_council()

    verdict = results.get("council_verdict", "UNKNOWN")
    print(f"\nCouncil Verdict: {verdict}")

    chair = next(
        (r for r in results.get("agent_responses", []) if r.get("agent") == "PRIME CHAIR"),
        None,
    )
    if chair:
        print(f"Summary: {chair['response']}")

    print("\nGovernance note: sigma_audits truth writes are never blocked by council.")
    print("Blocked when verdict != PASS_TO_LEARNING: learning consume, shadow promote, promotion evidence.")


if __name__ == "__main__":
    main()
