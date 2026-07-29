#!/usr/bin/env python3
"""
Daily learning enforcer for VELO.

Builds a supported-course RP learning universe, runs Council/Sigma memory/
nightly outcome replay/study/Mission Control, and audits recent days.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)
SUPPORTED_EXCLUDES = {
    "saratoga",
    "happyvalley",
    "sansiro",
    "chantilly",
    "dusseldorf",
    "tokyo",
    "shatin",
    # UK-only learning universe. Irish/foreign cards are quarantined rather
    # than allowed to block or dilute the RP learning replay.
    "ballinrobe",
    "bellewstown",
    "clonmel",
    "cork",
    "curragh",
    "downpatrick",
    "downroyal",
    "dundalk",
    "fairyhouse",
    "galway",
    "gowran",
    "gowranpark",
    "kilbeggan",
    "killarney",
    "leopardstown",
    "limerick",
    "listowel",
    "naas",
    "navan",
    "punchestown",
    "roscommon",
    "sligo",
    "thurles",
    "tipperary",
    "tramore",
    "wexford",
    "bal",
    "clo",
    "cor",
    "cur",
    "dpt",
    "dro",
    "dwr",
    "dun",
    "fai",
    "gal",
    "gow",
    "klb",
    "kil",
    "leo",
    "lim",
    "lit",
    "naa",
    "nav",
    "pat",
    "rho",
    "sli",
    "tip",
    "tra",
    "wex",
}


def _tag(day: str) -> str:
    return day.replace("-", "_")


def _norm_course(value: Any) -> str:
    v = str(value or "").lower().replace("(aw)", "").replace(" aw", "")
    return re.sub(r"[^a-z]", "", v)


def _time24(value: Any) -> str:
    text = str(value or "").replace(":", ".")
    parts = text.split(".")
    if len(parts) < 2:
        return text
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return ""
    if h < 11:
        h += 12
    return f"{h:02d}.{m:02d}"


def _run(cmd: list[str], *, required: bool = True) -> dict[str, Any]:
    print(f"\nRUN: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout[-4000:])
    if proc.stderr:
        print(proc.stderr[-2000:], file=sys.stderr)
    ok = proc.returncode == 0
    if required and not ok:
        raise SystemExit(f"required command failed ({proc.returncode}): {' '.join(cmd)}")
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "ok": ok,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
    }


def build_supported_inputs(day: str) -> dict[str, Any]:
    tag = _tag(day)
    verdicts_path = ROOT / "data" / f"velo_prime_verdicts_{tag}.json"
    results_path = ROOT / "data" / "results" / f"rp_results_{tag}.json"
    if not verdicts_path.exists():
        raise FileNotFoundError(verdicts_path)
    if not results_path.exists():
        raise FileNotFoundError(results_path)

    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    raw_results = json.loads(results_path.read_text(encoding="utf-8"))
    results = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
    results_by_key = {}
    results_by_race_id = {}
    for r in results:
        race_id = str(r.get("race_id") or "")
        if race_id:
            results_by_race_id[race_id] = r
        off = _time24(r.get("off"))
        if off:
            results_by_key[(_norm_course(r.get("course")), off)] = r

    supported_verdicts: list[dict[str, Any]] = []
    supported_results: list[dict[str, Any]] = []
    excluded: list[str] = []
    missing: list[dict[str, Any]] = []

    for verdict in verdicts:
        course = verdict.get("course")
        if _norm_course(course) in SUPPORTED_EXCLUDES:
            excluded.append(verdict.get("race_id", ""))
            continue
        key = (_norm_course(course), _time24(verdict.get("off_time")))
        result = results_by_race_id.get(str(verdict.get("race_id") or "")) or results_by_key.get(key)
        if not result:
            missing.append({
                "race_id": verdict.get("race_id"),
                "course": course,
                "off_time": verdict.get("off_time"),
            })
            continue
        aligned = json.loads(json.dumps(result))
        aligned["rp_numeric_race_id"] = aligned.get("race_id")
        aligned["race_id"] = verdict["race_id"]
        aligned["source"] = "racing_post_supported_learning_compat"
        supported_verdicts.append(verdict)
        supported_results.append(aligned)

    out_dir = ROOT / "data" / "learning_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    verdicts_out = out_dir / f"velo_prime_verdicts_{tag}_supported.json"
    results_out = out_dir / f"results_{tag}_supported.json"
    verdicts_out.write_text(json.dumps(supported_verdicts, indent=2), encoding="utf-8")
    results_out.write_text(json.dumps({
        "source": "racing_post",
        "compatibility": "supported_course_learning_universe",
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_from": str(results_path),
        "excluded_unsupported_courses": {"Saratoga": excluded},
        "missing_after_exclusion": missing,
        "results": supported_results,
    }, indent=2), encoding="utf-8")

    return {
        "date": day,
        "verdicts_file": str(verdicts_out),
        "results_file": str(results_out),
        "supported_predictions": len(supported_verdicts),
        "supported_results": len(supported_results),
        "excluded": len(excluded),
        "missing": missing,
    }


def run_day(day: str, *, allow_partial: bool = False) -> dict[str, Any]:
    prepared = build_supported_inputs(day)
    if prepared["missing"] and not allow_partial:
        raise SystemExit(f"missing supported RP results: {prepared['missing']}")

    cmds = []
    cmds.append(_run([
        str(PYTHON), "scripts/ops/run_supported_rp_sigma.py",
        "--date", day,
        "--verdicts-file", prepared["verdicts_file"],
        "--results-file", prepared["results_file"],
    ]))
    cmds.append(_run([str(PYTHON), "scripts/audit/run_velo_council.py", "--date", day]))
    cmds.append(_run([
        str(PYTHON), "scripts/ops/run_sigma_memory_distillation.py",
        "--date", day,
        "--verdicts-file", prepared["verdicts_file"],
        "--results-file", prepared["results_file"],
    ]))
    cmds.append(_run([
        str(PYTHON), "scripts/ops/nightly_eod_learning_runner.py",
        "--date", day,
        "--state", "data/sentient_state_shadow_daily.json",
        "--fail-on-data-error-rate", "0.001",
        "--pred-file", prepared["verdicts_file"],
        "--result-file", prepared["results_file"],
    ]))
    cmds.append(_run([str(PYTHON), "scripts/audit/eod_result_study_layer.py", "--date", day], required=False))
    cmds.append(_run([str(PYTHON), "scripts/ops/update_mission_control.py", "--date", day]))

    report = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "allow_partial": allow_partial,
        "prepared": prepared,
        "commands": cmds,
        "audit": audit_days(day, days=14, write=False),
    }
    out = ROOT / "data" / "reports" / f"daily_learning_enforcer_{_tag(day)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return report


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def audit_days(anchor: str, *, days: int, write: bool = True) -> list[dict[str, Any]]:
    anchor_date = date.fromisoformat(anchor)
    rows: list[dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        d = anchor_date - timedelta(days=offset)
        iso = d.isoformat()
        tag = _tag(iso)
        sigma = _load_json(ROOT / "data" / "sigma_results" / f"sigma_results_{tag}.json")
        council = _load_json(ROOT / "data" / "council_runs" / f"council_run_{iso}.json")
        mission = _load_json(ROOT / "data" / "mission_control" / f"{iso}_mission_control.json")
        nightly = _load_json(ROOT / "data" / f"nightly_eod_learning_status_{tag}.json")
        memory_path = ROOT / "data" / "sigma_memory" / f"sigma_memory_{tag}.jsonl"
        memory_rows = 0
        if memory_path.exists():
            memory_rows = sum(1 for line in memory_path.read_text(encoding="utf-8").splitlines() if line.strip())
        rows.append({
            "date": iso,
            "sigma_status": sigma.get("sigma_status") or ("PRESENT" if sigma else "MISSING"),
            "sigma_sr": sigma.get("sr"),
            "sigma_evaluated": sigma.get("evaluated_count") or sigma.get("matched"),
            "sigma_no_result": sigma.get("no_result_count"),
            "council_verdict": council.get("council_verdict") or ("PRESENT" if council else "MISSING"),
            "mission_learning_gate": mission.get("learning_gate_status") or "MISSING",
            "nightly_verdict": nightly.get("verdict") or "MISSING",
            "nightly_events": nightly.get("events_created"),
            "nightly_updates": nightly.get("engine_updates_applied_first_run"),
            "duplicate_updates": nightly.get("engine_updates_applied_duplicate_run"),
            "data_error_rate": nightly.get("data_error_rate"),
            "live_touched": nightly.get("live_sentient_state_touched"),
            "hfs_used": nightly.get("hfs_features_used"),
            "memory_rows": memory_rows,
        })

    if write:
        out = ROOT / "data" / "reports" / f"daily_learning_audit_last_{days}_{_tag(anchor)}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote {out}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure and audit daily VELO learning closure.")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--audit-days", type=int, default=14)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Backfill mode only: learn matched supported RP races while reporting missing supported races.",
    )
    args = parser.parse_args()

    if args.audit_only:
        print(json.dumps(audit_days(args.date, days=args.audit_days), indent=2))
    else:
        print(json.dumps(run_day(args.date, allow_partial=args.allow_partial), indent=2))


if __name__ == "__main__":
    main()
