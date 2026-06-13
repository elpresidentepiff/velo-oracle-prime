"""
Canonical pipeline wrapper for Sigma reconciliation.
Normalizes env, target date, and calls the underlying script.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def run(target_date: str | None = None, trigger_source: str = "manual", run_id: str | None = None, source: str = "auto", min_coverage: str | None = None):
    script_path = ROOT / "scripts" / "ops" / "run_results_sigma.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Sigma script not found: {script_path}")

    env = os.environ.copy()
    env["TRIGGER_SOURCE"] = trigger_source
    if run_id:
        env["PIPELINE_RUN_ID"] = run_id
        env["PIPELINE_SERVICE_NAME"] = "sigma"

    cmd = [sys.executable, str(script_path)]
    if target_date:
        cmd.extend(["--date", target_date])
    if source:
        cmd.extend(["--source", source])
    if min_coverage is not None:
        cmd.extend(["--min-coverage", str(min_coverage)])

    print(f"Running pipeline: sigma_runner (Target: {target_date or 'today'}, Source: {source}, Min Coverage: {min_coverage or 'default'})")

    proc = subprocess.run(cmd, env=env, cwd=str(ROOT), check=False)

    # ── NEW: Decision Policy Lane Ledger ─────────────────────────────────────
    ledger_status = "NOT_RUN"
    ledger_skip_reason = None

    if proc.returncode == 0:
        print("\nUpdating Decision Policy Lane Ledger...")
        ledger_script = ROOT / "scripts" / "audit" / "build_policy_lane_ledger.py"
        if ledger_script.exists():
            ledger_cmd = [sys.executable, str(ledger_script)]
            if target_date:
                ledger_cmd.extend(["--date", target_date])

            # Capture output to find skip reason if it exits with 2
            res = subprocess.run(ledger_cmd, env=env, cwd=str(ROOT), capture_output=True, text=True)

            if res.returncode == 0:
                ledger_status = "PASS"
            elif res.returncode == 2:
                ledger_status = "SKIPPED"
                # Extract reason from stdout (look for [SKIPPED] line)
                import re
                m = re.search(r"\[SKIPPED\] (.*)", res.stdout)
                ledger_skip_reason = m.group(1) if m else "Completeness check or duplicate"
            else:
                ledger_status = "FAIL"

            # Print ledger output for transparency
            print(res.stdout)
            if res.stderr:
                print(res.stderr, file=sys.stderr)
        else:
            print(f"  [WARN] Ledger script not found: {ledger_script}")
            ledger_status = "SCRIPT_MISSING"

    # ── Write Summary Artifact ───────────────────────────────────────────────
    from app.pipelines.pipeline_support import write_summary
    artifact_dir = ROOT / "data" / "new_build" / "summaries"
    safe_date = (target_date or "today").replace("-", "_")

    counts = {
        "lane_ledger_status": ledger_status
    }
    if ledger_skip_reason:
        counts["lane_ledger_skip_reason"] = ledger_skip_reason

    write_summary(
        pipeline_type="sigma",
        target_date=target_date or "today",
        status="PASS" if proc.returncode == 0 else "FAIL",
        counts=counts,
        artifact_path=artifact_dir / f"sigma_{safe_date}.json"
    )

    sys.exit(proc.returncode)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD")
    parser.add_argument("--trigger-source", type=str, default="manual")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--source", type=str, default="auto")
    parser.add_argument("--min-coverage", type=str, default=None)
    args = parser.parse_args()

    run(
        target_date=args.date,
        trigger_source=args.trigger_source,
        run_id=args.run_id,
        source=args.source,
        min_coverage=args.min_coverage
    )
