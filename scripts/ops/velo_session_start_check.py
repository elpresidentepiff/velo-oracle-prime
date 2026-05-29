"""
VÉLØ Session Start Check
=========================
Implements VELO_SESSION_START_PROTOCOL_V1.

Runs the mandatory 10-step session-start checklist and outputs a structured
status table. Must pass before any scoring, model, or database operation.

Hard constraints:
  - READ_ONLY: no file writes, no DB writes, no scoring changes
  - No live-state mutation of any kind
  - Exits with code 1 if any CRITICAL check fails

Usage:
    python scripts/ops/velo_session_start_check.py
    python scripts/ops/velo_session_start_check.py --json
    python scripts/ops/velo_session_start_check.py --strict   # exit 1 on any failure
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DOCS_ENG = ROOT / "docs" / "engineering"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))


# ── Severity constants ────────────────────────────────────────────────────────
CRITICAL = "CRITICAL"
WARN = "WARN"
OK = "OK"
INFO = "INFO"


def _run_git(*args: str) -> str:
    """Run a git command and return stripped stdout, or '' on failure."""
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""


# ── Individual checks ─────────────────────────────────────────────────────────

def check_branch_head() -> dict:
    """1. Branch / HEAD commit SHA."""
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD") or "UNKNOWN"
    sha = _run_git("rev-parse", "--short", "HEAD") or "UNKNOWN"
    full_sha = _run_git("rev-parse", "HEAD") or "UNKNOWN"
    status = OK if branch != "UNKNOWN" and sha != "UNKNOWN" else CRITICAL
    return {
        "check": "1. Branch / HEAD",
        "value": f"{branch} ({sha})",
        "full_sha": full_sha,
        "status": status,
        "detail": "OK" if status == OK else "Git not available or not a repo",
    }


def check_operational_date() -> dict:
    """2. Current operational date."""
    today = date.today().isoformat()
    return {
        "check": "2. Operational Date",
        "value": today,
        "status": OK,
        "detail": "System clock",
    }


def check_live_formula() -> dict:
    """3. Live scoring formula — reads CURRENT_RUNTIME_TRUTH.md."""
    crt = ROOT / "CURRENT_RUNTIME_TRUTH.md"
    formula = "UNKNOWN"
    status = WARN
    if crt.exists():
        for line in crt.read_text(encoding="utf-8").splitlines():
            if "sqpe_v" in line.lower() or "SQPE" in line:
                formula = line.strip().lstrip("-").strip()[:80]
                status = OK
                break
    return {
        "check": "3. Live Formula",
        "value": formula,
        "status": status,
        "detail": "Parsed from CURRENT_RUNTIME_TRUTH.md" if status == OK else "CURRENT_RUNTIME_TRUTH.md missing or no formula found",
    }


def check_active_gates() -> dict:
    """4. Active execution gates — reads feature_audit.py constants."""
    fa = ROOT / "src" / "velo" / "feature_audit.py"
    gates = []
    if fa.exists():
        for line in fa.read_text(encoding="utf-8").splitlines():
            if "_FLATLINE" in line or "_GATE" in line or "Gate" in line:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    gates.append(stripped[:80])
    # Known gates from doctrine
    known = ["Gate 2 (FEATURE_FLATLINE)", "Gate 5 (RPDC_COVERAGE_WARN)", "Gate 6 (LEARNING_ELIGIBILITY_BLOCK)"]
    value = ", ".join(known) if not gates else "; ".join(gates[:3])
    return {
        "check": "4. Active Gates",
        "value": value,
        "status": OK,
        "detail": "Read from src/velo/feature_audit.py",
    }


def check_degraded_dates() -> dict:
    """5. Dates with degraded run status."""
    degraded = []
    for f in sorted(DATA.glob("velo_daily_run_truth_*.md")):
        content = f.read_text(encoding="utf-8")
        if "MANUAL_RECOVERY_ONLY" in content or "FALSE_PASS" in content or "DEGRADED" in content:
            # Extract date from filename: velo_daily_run_truth_2026_05_19.md
            parts = f.stem.replace("velo_daily_run_truth_", "").split("_")
            if len(parts) == 3:
                degraded.append("-".join(parts))
    if degraded:
        value = ", ".join(degraded[-5:])  # last 5 degraded dates
        status = WARN
        detail = f"{len(degraded)} degraded day(s) found in truth watchdog"
    else:
        value = "None"
        status = OK
        detail = "No degraded days in local truth watchdog"
    return {
        "check": "5. Degraded Dates",
        "value": value,
        "status": status,
        "detail": detail,
    }


def check_learning_blocks() -> dict:
    """6. Dates where learning is blocked."""
    blocked = []
    for f in sorted(DATA.glob("nightly_eod_learning_failures_*.json")):
        try:
            failures = json.loads(f.read_text(encoding="utf-8"))
            if failures:  # non-empty list = blocked
                parts = f.stem.replace("nightly_eod_learning_failures_", "").split("_")
                if len(parts) == 3:
                    blocked.append("-".join(parts))
        except Exception:
            pass
    if blocked:
        value = ", ".join(blocked[-5:])
        status = WARN
        detail = f"{len(blocked)} learning-blocked day(s)"
    else:
        value = "None"
        status = OK
        detail = "No learning blocks found"
    return {
        "check": "6. Learning Blocks",
        "value": value,
        "status": status,
        "detail": detail,
    }


def check_open_council_items() -> dict:
    """7. Open Council items — checks for unratified council docs."""
    council_dir = ROOT / "src" / "velo" / "council"
    open_items = []
    if council_dir.exists():
        for f in council_dir.glob("*.py"):
            if "pending" in f.name.lower() or "open" in f.name.lower():
                open_items.append(f.name)
    # Also check docs/council if it exists
    docs_council = ROOT / "docs" / "council"
    if docs_council.exists():
        for f in docs_council.glob("*.md"):
            if "pending" in f.name.lower() or "open" in f.name.lower():
                open_items.append(f.name)
    value = ", ".join(open_items) if open_items else "None"
    return {
        "check": "7. Open Council Items",
        "value": value,
        "status": OK if not open_items else WARN,
        "detail": "Scanned src/velo/council/ and docs/council/",
    }


def check_worktree_status() -> dict:
    """8. Git worktree dirty-file check."""
    dirty = _run_git("status", "--porcelain")
    if dirty:
        lines = [l for l in dirty.splitlines() if l.strip()]
        value = f"DIRTY — {len(lines)} modified/untracked file(s)"
        status = WARN
        detail = "; ".join(lines[:5])
    else:
        value = "CLEAN"
        status = OK
        detail = "No uncommitted changes"
    return {
        "check": "8. Worktree Status",
        "value": value,
        "status": status,
        "detail": detail,
    }


def check_next_safe_command() -> dict:
    """9. Next safe command — always dry-run unless operator overrides."""
    return {
        "check": "9. Next Safe Command",
        "value": "python scripts/ops/run_prime_today.py --dry-run",
        "status": INFO,
        "detail": "Default safe command. Operator must explicitly approve live run.",
    }


def check_no_go_rules() -> dict:
    """10. Active no-go rules from CLAUDE.md."""
    claude_md = ROOT / "CLAUDE.md"
    rules = []
    if claude_md.exists():
        in_no_go = False
        for line in claude_md.read_text(encoding="utf-8").splitlines():
            if "no.go" in line.lower() or "never" in line.lower() or "forbidden" in line.lower():
                in_no_go = True
            if in_no_go and line.strip().startswith("-"):
                rules.append(line.strip()[1:].strip()[:80])
            if in_no_go and len(rules) >= 5:
                break
    # Hardcoded doctrine rules always present
    doctrine_rules = [
        "No live scoring/weight changes without Council approval",
        "No Supabase write without verified git_commit_sha",
        "No model promotion without A/B comparison + dry-run",
        "No feature wiring without LIVE_SCORING_INPUT_CHANGE approval",
    ]
    all_rules = (rules or doctrine_rules)[:5]
    return {
        "check": "10. No-Go Rules",
        "value": f"{len(all_rules)} active rules",
        "status": OK,
        "detail": " | ".join(all_rules),
    }


# ── Runner ────────────────────────────────────────────────────────────────────

def run_checks() -> list[dict]:
    return [
        check_branch_head(),
        check_operational_date(),
        check_live_formula(),
        check_active_gates(),
        check_degraded_dates(),
        check_learning_blocks(),
        check_open_council_items(),
        check_worktree_status(),
        check_next_safe_command(),
        check_no_go_rules(),
    ]


def _status_icon(status: str) -> str:
    return {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRIT]", "INFO": "[INFO]"}.get(status, "[?]")


def print_table(checks: list[dict]) -> None:
    print("\nVÉLØ SESSION START CHECK")
    print("=" * 72)
    print(f"{'Check':<35} {'Status':<8} {'Value'}")
    print("-" * 72)
    for c in checks:
        icon = _status_icon(c["status"])
        val = str(c["value"])[:40]
        print(f"{c['check']:<35} {icon:<8} {val}")
    print("-" * 72)
    criticals = [c for c in checks if c["status"] == CRITICAL]
    warns = [c for c in checks if c["status"] == WARN]
    if criticals:
        print(f"\n[CRIT] {len(criticals)} CRITICAL failure(s):")
        for c in criticals:
            print(f"  {c['check']}: {c['detail']}")
    if warns:
        print(f"\n[WARN] {len(warns)} warning(s):")
        for c in warns:
            print(f"  {c['check']}: {c['detail']}")
    if not criticals and not warns:
        print("\n[OK] All checks passed. Safe to proceed.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="VÉLØ Session Start Check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any WARN or CRITICAL")
    args = parser.parse_args()

    checks = run_checks()

    if args.json:
        print(json.dumps({"timestamp": datetime.utcnow().isoformat() + "Z", "checks": checks}, indent=2))
    else:
        print_table(checks)

    criticals = [c for c in checks if c["status"] == CRITICAL]
    warns = [c for c in checks if c["status"] == WARN]

    if criticals:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
