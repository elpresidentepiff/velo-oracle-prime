"""
Canonical pipeline wrapper for daily scoring.
Normalizes env, target date, and calls the underlying script.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def run(target_date: str | None = None, trigger_source: str = "manual", run_id: str | None = None):
    script_path = ROOT / "scripts" / "ops" / "run_prime_today.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Scoring script not found: {script_path}")

    env = os.environ.copy()
    env["TRIGGER_SOURCE"] = trigger_source
    if run_id:
        env["PIPELINE_RUN_ID"] = run_id
        env["PIPELINE_SERVICE_NAME"] = "score_daily"

    cmd = [sys.executable, str(script_path)]
    if target_date:
        cmd.extend(["--date", target_date])

    print(f"Running pipeline: score_daily_runner (Target: {target_date or 'today'})")
    
    # We use run() here to block and stream output if run from CLI, 
    # but FastAPI will wrap this or just call the script directly via subprocess.
    # To keep FastAPI's background running model intact, we can just use this as the target script.
    proc = subprocess.run(cmd, env=env, cwd=str(ROOT), check=False)
    sys.exit(proc.returncode)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD")
    parser.add_argument("--trigger-source", type=str, default="manual")
    parser.add_argument("--run-id", type=str, default=None)
    args = parser.parse_args()
    
    run(target_date=args.date, trigger_source=args.trigger_source, run_id=args.run_id)
