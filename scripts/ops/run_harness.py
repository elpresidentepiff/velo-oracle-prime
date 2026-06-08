#!/usr/bin/env python3
"""
Secure Agent Runtime / Harness Hub
A central read-only router for VÉLØ observability and operational scripts.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COMMANDS = {
    "harness-audit": {
        "script": "scripts/ops/run_leakage_audit.py",
        "desc": "Scans morning models for feature leakage violations."
    },
    "run-readiness": {
        "script": "scripts/ops/new_build_two_lane_score.py",
        "desc": "Checks data completeness and readiness for today's run. Requires --date."
    },
    "passport-coverage": {
        "script": "scripts/ops/verify_ts_coverage.py",
        "desc": "Counts passport coverage and TS presence in current feed."
    },
    "sidecar-league": {
        "script": "data/sidecar_elo/sidecar_elo_latest.md",
        "desc": "Prints sidecar Elo leaderboard.",
        "type": "read_md"
    },
    "sigma-close": {
        "script": "app/pipelines/sigma_runner.py",
        "desc": "Runs 3-step sigma sequence for a date. Requires --date."
    },
    "dashboard-check": {
        "script": "",
        "desc": "Checks dashboard truth endpoint (GET only).",
        "type": "http_get",
        "url": "http://127.0.0.1:8000/api/dashboard/truth-summary"
    },
    "context-budget": {
        "script": "",
        "desc": "Counts lines in active scripts, flags any >500 lines.",
        "type": "budget_check"
    },
    "markov-state": {
        "script": "data/markov/markov_state_summary_",
        "desc": "Prints today's markov state summary. Requires --date.",
        "type": "read_json_date"
    },
    "rag-brief": {
        "script": "data/rag/rag_dossier_",
        "desc": "Prints today's rag dossier. Requires --date.",
        "type": "read_md_date"
    },
    "graph-brief": {
        "script": "data/graph/graph_summary_",
        "desc": "Prints today's graph summary. Requires --date.",
        "type": "read_md_date"
    }
}

def print_help():
    print("VÉLØ Secure Agent Runtime / Harness Hub")
    print("Available Commands:\n")
    for cmd, info in COMMANDS.items():
        print(f"  --cmd {cmd:<18} | {info['desc']}")
    print("\nUsage: python scripts/ops/run_harness.py --cmd <command> [--date YYYY-MM-DD]")

def run_harness(cmd, target_date=None):
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print_help()
        return

    info = COMMANDS[cmd]
    cmd_type = info.get("type", "run_script")

    if cmd_type == "run_script":
        script_path = ROOT / info["script"]
        if not script_path.exists():
            print(f"Script not found: {script_path}")
            return
        
        args = [sys.executable, str(script_path)]
        if info["script"] == "scripts/ops/new_build_two_lane_score.py":
            if not target_date:
                print("Error: --date required for run-readiness")
                return
            args.extend(["--date", target_date])
        elif info["script"] == "app/pipelines/sigma_runner.py":
             if not target_date:
                print("Error: --date required for sigma-close")
                return
             args.extend(["--date", target_date])

        subprocess.run(args, cwd=str(ROOT))

    elif cmd_type == "read_md":
        path = ROOT / info["script"]
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        else:
            print(f"File not found: {path}")

    elif cmd_type == "read_json_date":
        if not target_date:
            print("Error: --date required")
            return
        date_und = target_date.replace("-", "_")
        path = ROOT / f"{info['script']}{date_und}.json"
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        else:
            print(f"File not found: {path}")

    elif cmd_type == "read_md_date":
        if not target_date:
            print("Error: --date required")
            return
        date_und = target_date.replace("-", "_")
        path = ROOT / f"{info['script']}{date_und}.md"
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        else:
            print(f"File not found: {path}")

    elif cmd_type == "http_get":
        import urllib.request
        try:
            req = urllib.request.Request(info["url"])
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Dashboard check failed: {e}")

    elif cmd_type == "budget_check":
        print("Checking context budget (>500 lines)...")
        ops_dir = ROOT / "scripts" / "ops"
        for py_file in ops_dir.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) > 500:
                    print(f"  [WARN] {py_file.name}: {len(lines)} lines")
        
        main_app = ROOT / "app" / "main.py"
        if main_app.exists():
            lines = main_app.read_text(encoding="utf-8").splitlines()
            if len(lines) > 500:
                print(f"  [WARN] app/main.py: {len(lines)} lines")
        print("Context budget check complete.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", help="Harness command to run")
    parser.add_argument("--date", help="YYYY-MM-DD for date-dependent commands")
    args = parser.parse_args()

    if not args.cmd:
        print_help()
    else:
        run_harness(args.cmd, args.date)

if __name__ == "__main__":
    main()
