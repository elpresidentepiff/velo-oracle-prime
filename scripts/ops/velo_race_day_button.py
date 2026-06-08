"""One-button race-day operator layout for VÉLØ.

This script codifies the morning sequence without weakening any safety gates:

1. Parse/write the Racing Post standard cache.
2. Preflight injection gate (blocks if data is bad).
3. Build Old VÉLØ RP files — one file per track, each race has 5 components:
   (1) race info  (2) postdata pick  (3) topspeed pick  (4) spotlight verdict  (5) newspaper selections.
4. Build RPDC release candidate tags (injection JSON → racing_horse_runs → Supabase).
5. Run Old VÉLØ with Telegram suppressed.
6. Refresh New Build current-card feed.
7. Run New Build paper scorer.
8. Write one operator summary.

Old VÉLØ persistence is left to run_prime_today.py. New Build remains paper-only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "reports"
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"


def _best_capture_label(date: str) -> str:
    """Auto-select best capture label: prefers refresh2 > refresh > base.

    Sorted by label length descending so longer (more specific) labels win.
    If live-full-racepages-2026-06-06-refresh2 and -refresh both exist, refresh2 wins.
    """
    if not RAW_ROOT.exists():
        return f"live-full-racepages-{date}"
    base = f"live-full-racepages-{date}"
    candidates = sorted(
        [p.name for p in RAW_ROOT.iterdir() if p.is_dir() and p.name.startswith(base)],
        key=lambda x: (len(x), x),
        reverse=True,
    )
    chosen = candidates[0] if candidates else base
    if chosen != base:
        print(f"[AUTO-LABEL] Detected refresh capture: using '{chosen}' over base '{base}'")
    return chosen


def _preflight_injection_gate(injection_path: Path, date: str) -> list[str]:
    """Validate injection JSON before scoring. Returns list of blocking error messages.

    Hard-blocks on:
    - injection file missing
    - any race with off_time == None
    - fewer than 3 courses (likely partial/stale capture)
    """
    if not injection_path.exists():
        return [f"INJECTION_MISSING: {injection_path} — run parse step first"]
    try:
        data = json.loads(injection_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"INJECTION_PARSE_ERROR: {exc}"]

    races = data.get("races") or []
    if not races:
        return ["INJECTION_EMPTY: 0 races found in injection file"]

    fails: list[str] = []
    null_off = [r.get("course", "?") for r in races if not r.get("off_time")]
    if null_off:
        fails.append(
            f"OFF_TIME_NULL: {len(null_off)} race(s) have no off_time "
            f"(courses: {null_off[:5]}) — re-run parse with correct capture label"
        )

    courses = sorted({r.get("course", "") for r in races if r.get("course")})
    if len(courses) < 3:
        fails.append(
            f"COURSE_COUNT_LOW: only {len(courses)} course(s) in injection: {courses} "
            f"— expected ≥3 on a full race day; check capture label is correct"
        )

    return fails


def _run_step(name: str, command: list[str], extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = "."
    if extra_env:
        env.update(extra_env)
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output_tail = "\n".join((proc.stdout or "").splitlines()[-80:])
    return {
        "name": name,
        "command": command,
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "output_tail": output_tail,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"read_error": str(exc)}


def _summarise(date: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    new_build = _read_json(ROOT / "data" / "new_build" / "reports" / f"two_lane_readiness_{date.replace('-', '_')}.json")
    cache_gate = _read_json(ROOT / "data" / "reports" / "racecard_cache_gate_latest.json")
    old_step = next((s for s in steps if s["name"] == "old_velo_engine"), None)
    new_step = next((s for s in steps if s["name"] == "new_build_score"), None)

    old_blocked = bool(old_step and old_step["exit_code"] != 0)
    old_reason = None
    if old_blocked:
        old_reason = "See old_velo_engine.output_tail"
        failed_checks = [
            c for c in cache_gate.get("checks", [])
            if c.get("blocking") and not c.get("passed")
        ]
        if failed_checks:
            old_reason = "; ".join(f"{c.get('name')}: {c.get('message')}" for c in failed_checks)
        elif cache_gate.get("gate_passed") is False:
            old_reason = "racecard cache gate failed"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_date": date,
        "classification": (
            "RACE_DAY_BUTTON_READY"
            if old_step and old_step["exit_code"] == 0 and new_step and new_step["exit_code"] == 0
            else "RACE_DAY_BUTTON_PARTIAL"
        ),
        "old_velo": {
            "attempted": old_step is not None,
            "status": "PASS" if old_step and old_step["exit_code"] == 0 else "BLOCKED",
            "reason": old_reason,
            "telegram_suppressed": True,
        },
        "new_build": {
            "attempted": new_step is not None,
            "status": new_build.get("overall_status") or ("PASS" if new_step and new_step["exit_code"] == 0 else "UNKNOWN"),
            "races_scored": new_build.get("races_scored"),
            "runners_scored": new_build.get("runners_scored"),
            "operational_lane": new_build.get("operational_lane"),
            "rpr_violations": new_build.get("rpr_violations"),
            "sp_violations": new_build.get("sp_violations"),
            "intent_coverage": new_build.get("intent_coverage"),
            "paper_only": True,
        },
        "steps": steps,
    }


def _write_report(summary: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_slug = summary["target_date"].replace("-", "_")
    json_path = REPORT_DIR / f"race_day_button_{date_slug}_latest.json"
    md_path = REPORT_DIR / f"race_day_button_{date_slug}_latest.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# VÉLØ Race-Day Button: {summary['target_date']}",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"Classification: `{summary['classification']}`",
        "",
        "## Old VÉLØ",
        "",
        f"- Status: `{summary['old_velo']['status']}`",
        f"- Telegram suppressed: `{summary['old_velo']['telegram_suppressed']}`",
        f"- Reason: `{summary['old_velo'].get('reason') or 'none'}`",
        "",
        "## New Build",
        "",
        f"- Status: `{summary['new_build']['status']}`",
        f"- Races scored: `{summary['new_build'].get('races_scored')}`",
        f"- Runners scored: `{summary['new_build'].get('runners_scored')}`",
        f"- Operational lane: `{summary['new_build'].get('operational_lane')}`",
        f"- RPR violations: `{summary['new_build'].get('rpr_violations')}`",
        f"- SP violations: `{summary['new_build'].get('sp_violations')}`",
        f"- Paper only: `{summary['new_build']['paper_only']}`",
        "",
        "## Step Status",
        "",
    ]
    for step in summary["steps"]:
        lines.append(f"- `{step['name']}`: `{step['status']}` exit `{step['exit_code']}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print(
        "RACE_DAY_BUTTON_DISABLED: run the explicit numbered commands in "
        "THE_ONE_TRUTH.md and pass one exact injection path downstream."
    )
    return 2

    # Retained temporarily as migration reference; intentionally unreachable.
    parser = argparse.ArgumentParser(description="Run the VÉLØ race-day button sequence.")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument(
        "--capture-label",
        default=None,
        help="RP raw capture label. Defaults to live-full-racepages-{date}.",
    )
    parser.add_argument("--skip-old", action="store_true", help="Skip Old VÉLØ engine.")
    parser.add_argument("--skip-new-build", action="store_true", help="Skip New Build paper scorer.")
    parser.add_argument("--no-parse", action="store_true", help="Skip RP parse/cache generation.")
    parser.add_argument("--continue-on-old-block", action="store_true", default=True)
    args = parser.parse_args()

    date = args.date
    capture_label = args.capture_label or _best_capture_label(date)
    standard_cache = f"data/racecards_{date.replace('-', '_')}_standard.json"
    label_injection = ROOT / "data" / "racing_post_account_parsed" / capture_label / "racecard_injection.json"
    date_injection = ROOT / "data" / "racing_post_account_parsed" / date / "racecard_injection.json"

    print(f"[BUTTON] date={date}  capture_label={capture_label}")

    steps: list[dict[str, Any]] = []

    if not args.no_parse:
        steps.append(_run_step("parse_rp_card", [
            sys.executable,
            "scripts/ops/parse_racing_post_racecard_capture.py",
            "--date", date,
            "--capture-label", capture_label,
            "--write-standard-cache",
            "--execute",
        ]))

    injection_path = label_injection if label_injection.exists() else date_injection

    # Hard preflight gate — block all scoring if injection is malformed or incomplete
    gate_fails = _preflight_injection_gate(injection_path, date)
    if gate_fails:
        print(f"\n{'='*60}")
        print(f"[PREFLIGHT GATE] ⛔ BLOCKED — {len(gate_fails)} critical issue(s):")
        for fail in gate_fails:
            print(f"  ⛔ {fail}")
        print(f"{'='*60}")
        print("Aborting — fix capture data then re-run button.\n")
        steps.append({
            "name": "preflight_injection_gate",
            "command": [],
            "exit_code": 1,
            "status": "FAIL",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "output_tail": "\n".join(gate_fails),
        })
        summary = _summarise(date, steps)
        _write_report(summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 1
    else:
        try:
            _inj = json.loads(injection_path.read_text(encoding="utf-8"))
            _n = len(_inj.get("races") or [])
            _c = len({r.get("course") for r in (_inj.get("races") or []) if r.get("course")})
        except Exception:
            _n = _c = "?"
        print(f"[PREFLIGHT GATE] ✓ PASS — injection OK: {_n} races, {_c} courses, all off_times present")

    steps.append(_run_step("build_rp_merged", [
        sys.executable,
        "scripts/ops/build_racecard_merged_from_injection.py",
        "--date", date,
        "--injection-path", str(injection_path.relative_to(ROOT)),
    ]))

    # Step 8.5 — RPDC release candidate tags. Must run AFTER rp_merged (needs injection JSON)
    # and BEFORE old_velo_engine (scorer attaches RPDC at scoring time).
    steps.append(_run_step("build_rpdc", [
        sys.executable,
        "scripts/ops/build_rpdc_daily.py",
        "--date", date,
    ]))

    if not args.skip_old:
        steps.append(_run_step("old_velo_engine", [
            sys.executable,
            "scripts/ops/run_prime_today.py",
            "--date", date,
            "--source", "rp",
            "--no-notify",
        ], extra_env={"VELO_FORCE_CARD": "1"}))

    if not args.skip_new_build:
        steps.append(_run_step("new_build_feed", [
            sys.executable,
            "scripts/ops/new_build_current_card_feed.py",
            "--racecard-path", standard_cache,
            "--execute",
        ]))
        steps.append(_run_step("new_build_score", [
            sys.executable,
            "scripts/ops/new_build_two_lane_score.py",
            "--date", date,
            "--execute",
        ]))

    steps.append(_run_step("truth_watchdog", [
        sys.executable,
        "scripts/ops/velo_daily_run_truth_watchdog.py",
        "--date", date,
    ]))

    summary = _summarise(date, steps)
    _write_report(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["classification"] == "RACE_DAY_BUTTON_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
