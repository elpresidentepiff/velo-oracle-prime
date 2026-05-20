"""
run_velo_closed_loop_daily.py
==============================
Daily closure orchestrator for VÉLØ Oracle Prime.

Runs all closure scripts in order, captures output, detects errors,
writes a daily closure report.

Order of execution:
  1. backfill_shadow_ledger_outcomes.py
  2. learning_loop_closure_audit.py
  3. router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
  4. racing_api_shadow_forward_audit.py
  5. run_execution_bridge_shadow.py --date {date} --mode SIM --audit-results
  6. signal_promotion_board.py
  7. live_sidecar_ablation_audit.py
  8. sqpe_alone_control_audit.py

NO promotion. NO live change. NO model change.

Usage:
  python scripts/run_velo_closed_loop_daily.py
  python scripts/run_velo_closed_loop_daily.py --date 2026-05-08
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "data"
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = ROOT / "venv" / "bin" / "python"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)


# ── Step definitions ───────────────────────────────────────────────────────────

def _build_steps(date_str: str) -> list[dict]:
    return [
        {
            "name": "backfill_shadow_ledger_outcomes",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "backfill_shadow_ledger_outcomes.py")],
            "desc": "Backfill outcomes from results JSON into shadow/paper ledgers",
            "required": False,  # non-fatal if ledgers already backfilled
        },
        {
            "name": "learning_loop_closure_audit",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "learning_loop_closure_audit.py")],
            "desc": "Audit closure status of all verdicts, sigma, paper ledgers",
            "required": True,
        },
        {
            "name": "router_shadow_audit",
            "cmd": [
                str(VENV_PYTHON), str(ROOT / "scripts" / "router_shadow_audit.py"),
                "--prev-csv", str(ROOT / "data" / "router_shadow_audit_latest.csv"),
            ],
            "desc": "Router shadow lane evidence accumulation",
            "required": False,
        },
        {
            "name": "racing_api_shadow_forward_audit",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "racing_api_shadow_forward_audit.py")],
            "desc": "Racing API shadow forward enrichment audit",
            "required": False,
        },
        {
            "name": "run_execution_bridge_shadow",
            "cmd": [
                str(VENV_PYTHON), str(ROOT / "scripts" / "run_execution_bridge_shadow.py"),
                "--date", date_str,
                "--mode", "SIM",
                "--audit-results",
            ],
            "desc": "Execution bridge paper ledger close for date",
            "required": False,
        },
        {
            "name": "signal_promotion_board",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "signal_promotion_board.py")],
            "desc": "Signal promotion board — threshold tracker",
            "required": False,
        },
        {
            "name": "live_sidecar_ablation_audit",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "live_sidecar_ablation_audit.py")],
            "desc": "Live sidecar ablation audit",
            "required": True,
        },
        {
            "name": "sqpe_alone_control_audit",
            "cmd": [str(VENV_PYTHON), str(ROOT / "scripts" / "sqpe_alone_control_audit.py")],
            "desc": "SQPE-alone vs ensemble control audit",
            "required": True,
        },
    ]


# ── Runner ─────────────────────────────────────────────────────────────────────

def _run_step(step: dict, env: dict) -> dict:
    name = step["name"]
    cmd = step["cmd"]
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"DESC: {step['desc']}")
    print(f"CMD:  {' '.join(cmd)}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(ROOT),
        )
        elapsed = time.time() - start
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        returncode = result.returncode
        success = returncode == 0

        # Print output live
        if stdout:
            print(stdout[-3000:] if len(stdout) > 3000 else stdout)
        if stderr and not success:
            print(f"STDERR:\n{stderr[-2000:] if len(stderr) > 2000 else stderr}", file=sys.stderr)

        # Detect common error patterns even on returncode=0
        error_patterns = ["Traceback", "ModuleNotFoundError", "ImportError", "RuntimeError", "CRITICAL"]
        has_error_pattern = any(p in (stdout + stderr) for p in error_patterns)
        if has_error_pattern and success:
            success = False
            returncode = -1

        return {
            "name": name,
            "desc": step["desc"],
            "required": step["required"],
            "success": success,
            "returncode": returncode,
            "elapsed_s": round(elapsed, 1),
            "stdout_tail": stdout[-1500:],
            "stderr_tail": stderr[-500:] if stderr else "",
            "error": None,
        }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"  TIMEOUT after {elapsed:.0f}s")
        return {
            "name": name,
            "desc": step["desc"],
            "required": step["required"],
            "success": False,
            "returncode": -99,
            "elapsed_s": round(elapsed, 1),
            "stdout_tail": "",
            "stderr_tail": "",
            "error": f"TIMEOUT after {elapsed:.0f}s",
        }
    except Exception as exc:
        elapsed = time.time() - start
        print(f"  EXCEPTION: {exc}")
        return {
            "name": name,
            "desc": step["desc"],
            "required": step["required"],
            "success": False,
            "returncode": -1,
            "elapsed_s": round(elapsed, 1),
            "stdout_tail": "",
            "stderr_tail": "",
            "error": str(exc),
        }


# ── Report builder ─────────────────────────────────────────────────────────────

def _build_report(date_str: str, step_results: list[dict], run_ts: str) -> str:
    succeeded = [r for r in step_results if r["success"]]
    failed = [r for r in step_results if not r["success"]]
    required_failed = [r for r in failed if r["required"]]

    if required_failed:
        status = "BROKEN"
    elif failed:
        status = "PARTIAL"
    else:
        status = "CLOSED"

    lines = [
        f"# VÉLØ Closed Loop Daily Report — {date_str}",
        "",
        f"- Run timestamp: `{run_ts}`",
        f"- Date: `{date_str}`",
        f"- **FINAL STATUS: {status}**",
        "",
        "## Step Summary",
        "",
        "| Step | Status | Elapsed | Required |",
        "|---|---|---:|---|",
    ]
    for r in step_results:
        icon = "PASS" if r["success"] else "FAIL"
        req = "YES" if r["required"] else "no"
        lines.append(f"| {r['name']} | {icon} | {r['elapsed_s']}s | {req} |")
    lines.append("")

    if failed:
        lines += [
            "## Failed Steps",
            "",
        ]
        for r in failed:
            lines += [
                f"### {r['name']}",
                f"- Required: {r['required']}",
                f"- Return code: {r['returncode']}",
                f"- Error: {r['error'] or 'See stderr/stdout'}",
                "```",
                (r["stderr_tail"] or r["stdout_tail"] or "no output captured")[-800:],
                "```",
                "",
            ]

    lines += [
        "## What Advanced",
        "",
    ]
    for r in succeeded:
        lines.append(f"- {r['name']}: PASS ({r['elapsed_s']}s)")
    lines.append("")

    lines += [
        "## What Did Not Advance",
        "",
    ]
    if failed:
        for r in failed:
            req_note = " (REQUIRED — blocks CLOSED status)" if r["required"] else ""
            lines.append(f"- {r['name']}: FAIL{req_note}")
    else:
        lines.append("- None — all steps succeeded")
    lines.append("")

    lines += [
        "## Thresholds and Freeze Recommendations",
        "",
        "These are determined by the individual audit scripts. See:",
        "- `data/learning_loop_closure_audit_latest.md` for closure status",
        "- `data/router_shadow_audit_latest.md` for router gate thresholds",
        "- `data/sidecar_role_decision_board_latest.md` for freeze recommendations",
        "- `data/sqpe_alone_control_audit_latest.md` for SQPE control comparison",
        "",
        "## Governance Confirmation",
        "",
        "```",
        "NO live scoring change",
        "NO SQPE/model change",
        "NO router promotion",
        "NO weight change",
        "NO live staking",
        "NO Betfair execution",
        "AUDIT / RECONCILIATION / OPERATOR VISIBILITY ONLY",
        "```",
        "",
        f"---",
        f"*Generated by run_velo_closed_loop_daily.py at {run_ts}*",
    ]

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="VÉLØ closed loop daily orchestrator")
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y-%m-%d"),
        help="Race date YYYY-MM-DD (defaults to today UTC)",
    )
    args = parser.parse_args()
    date_str = args.date

    run_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    print(f"\nVELO CLOSED LOOP DAILY — {date_str}")
    print(f"Run timestamp: {run_ts}")
    print(f"AUDIT ONLY — no live changes, no promotion, no staking")

    # Set up env with PYTHONPATH
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("PYTHONUTF8", "1")

    steps = _build_steps(date_str)
    step_results: list[dict] = []
    for step in steps:
        result = _run_step(step, env)
        step_results.append(result)

        # If a required step failed, continue anyway (don't abort — still run all steps)
        if not result["success"] and result["required"]:
            print(f"\n  WARNING: Required step {step['name']} FAILED (continuing to run remaining steps)")

    # Build report
    report_md = _build_report(date_str, step_results, run_ts)
    report_date = date_str.replace("-", "_")
    report_path = OUTPUT_DIR / f"velo_closed_loop_daily_{report_date}.md"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")

    # Final status
    succeeded = [r for r in step_results if r["success"]]
    failed = [r for r in step_results if not r["success"]]
    required_failed = [r for r in failed if r["required"]]

    if required_failed:
        final_status = "BROKEN"
    elif failed:
        final_status = "PARTIAL"
    else:
        final_status = "CLOSED"

    print()
    print("=" * 70)
    print(f"VELO CLOSED LOOP DAILY — FINAL STATUS: {final_status}")
    print("=" * 70)
    print(f"  Date: {date_str}")
    print(f"  Steps passed: {len(succeeded)}/{len(steps)}")
    print(f"  Steps failed: {len(failed)}/{len(steps)}")
    if required_failed:
        print(f"  Required failures: {[r['name'] for r in required_failed]}")
    print(f"  Report written: {report_path.name}")
    print(f"\n  GOVERNANCE: No live scoring, model, router, or staking changes made.")
    print("=" * 70)

    return 0 if final_status == "CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
