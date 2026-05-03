import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.velo.council.council_orchestrator import CouncilOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Run VÉLØ LLM Council")
    parser.get_all_evidence = parser.add_argument("--date", type=str, required=True, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    
    # Check if we are in the canonical worktree
    # (In a real run, we'd call scripts/assert_canonical_worktree.py)
    print(f"Repo Root: {repo_root}")
    
    orchestrator = CouncilOrchestrator(args.date, repo_root)
    orchestrator.run_council()

if __name__ == "__main__":
    main()
