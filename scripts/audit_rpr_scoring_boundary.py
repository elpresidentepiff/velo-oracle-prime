#!/usr/bin/env python3
"""
Audit that Racing Post RPR stays archive-only and cannot enter Velo scoring.

This is a read-only guard. It scans parsed Racing Post account artifacts and
the known RP merged loader boundary for accidental `rpr` exposure.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> Any:
    return json.loads(_read_text(path))


def _scan_parsed_archives(date_filter: str | None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    violations: list[dict[str, Any]] = []
    stats = {
        "files_checked": 0,
        "races_checked": 0,
        "runners_checked": 0,
        "archive_rpr_fields": 0,
    }
    day_dirs = [PARSED_ROOT / date_filter] if date_filter else sorted(p for p in PARSED_ROOT.glob("20*-*-*") if p.is_dir())
    for day_dir in day_dirs:
        racecard_path = day_dir / "racecard_injection.json"
        if not racecard_path.exists():
            continue
        stats["files_checked"] += 1
        payload = _load_json(racecard_path)
        for race in payload.get("races") or []:
            stats["races_checked"] += 1
            if race.get("velo_scoring_allowed") is not False:
                violations.append({
                    "file": str(racecard_path),
                    "race_id": race.get("race_id"),
                    "issue": "race_velo_scoring_allowed_not_false",
                    "value": race.get("velo_scoring_allowed"),
                })
            if race.get("rpr_policy") != "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO":
                violations.append({
                    "file": str(racecard_path),
                    "race_id": race.get("race_id"),
                    "issue": "race_rpr_policy_missing_or_wrong",
                    "value": race.get("rpr_policy"),
                })
            for runner in race.get("runners") or []:
                stats["runners_checked"] += 1
                if "rp_rpr_archive_only" in runner:
                    stats["archive_rpr_fields"] += 1
                if "rpr" in runner:
                    violations.append({
                        "file": str(racecard_path),
                        "race_id": race.get("race_id"),
                        "horse": runner.get("horse"),
                        "issue": "runner_exposes_generic_rpr",
                    })
                if runner.get("rp_rpr_velo_allowed") is not False:
                    violations.append({
                        "file": str(racecard_path),
                        "race_id": race.get("race_id"),
                        "horse": runner.get("horse"),
                        "issue": "runner_rp_rpr_velo_allowed_not_false",
                        "value": runner.get("rp_rpr_velo_allowed"),
                    })
    return violations, stats


def _scan_source_boundary() -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    loader_path = ROOT / "src" / "velo" / "racecard_loader.py"
    if loader_path.exists():
        text = _read_text(loader_path)
        bad_patterns = [
            (r'"rpr"\s*:\s*h\.get\("rpr_master"\)', "racecard_loader_maps_rpr_master_to_live_rpr"),
            (r"'rpr'\s*:\s*h\.get\('rpr_master'\)", "racecard_loader_maps_rpr_master_to_live_rpr"),
        ]
        for pattern, issue in bad_patterns:
            if re.search(pattern, text):
                violations.append({"file": str(loader_path), "issue": issue})
    parser_path = ROOT / "scripts" / "ops" / "parse_racing_post_racecard_capture.py"
    if parser_path.exists():
        text = _read_text(parser_path)
        if '"rp_rpr_archive_only"' not in text:
            violations.append({"file": str(parser_path), "issue": "parser_missing_archive_rpr_field"})
        if '"rp_rpr_velo_allowed": False' not in text:
            violations.append({"file": str(parser_path), "issue": "parser_missing_rpr_velo_false_guard"})
    return violations


def _write_reports(payload: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "rpr_scoring_boundary_latest.json"
    md_path = REPORT_ROOT / "rpr_scoring_boundary_latest.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# RPR Scoring Boundary Audit",
        "",
        f"- Verdict: `{payload['verdict']}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Files checked: `{payload['stats']['files_checked']}`",
        f"- Races checked: `{payload['stats']['races_checked']}`",
        f"- Runners checked: `{payload['stats']['runners_checked']}`",
        f"- Archive RPR fields found: `{payload['stats']['archive_rpr_fields']}`",
        f"- Violations: `{len(payload['violations'])}`",
        "",
        "## Policy",
        "",
        "- RPR may be collected, parsed, and archived.",
        "- RP-derived RPR must not be exposed as live `runner['rpr']`.",
        "- RP-derived RPR must not enter VP, improvement, model inputs, router, staking, Telegram, or Playbook G.",
        "",
    ]
    if payload["violations"]:
        lines += ["## Violations", ""]
        for item in payload["violations"][:50]:
            lines.append(f"- `{item.get('issue')}` in `{item.get('file')}` horse=`{item.get('horse')}`")
    else:
        lines += ["## Violations", "", "None."]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit RP RPR archive-only scoring boundary.")
    parser.add_argument("--date", help="Optional parsed archive date to inspect, e.g. 2026-05-25")
    args = parser.parse_args()

    archive_violations, stats = _scan_parsed_archives(args.date)
    source_violations = _scan_source_boundary()
    violations = archive_violations + source_violations
    verdict = "PASS_RPR_ARCHIVE_ONLY" if not violations else "FAIL_RPR_SCORING_LEAK"
    payload = {
        "generated_at": _utc_now(),
        "date_filter": args.date,
        "verdict": verdict,
        "stats": stats,
        "violations": violations,
        "scoring_impact": "NONE" if verdict == "PASS_RPR_ARCHIVE_ONLY" else "BLOCKED",
    }
    json_path, md_path = _write_reports(payload)
    payload["json_path"] = str(json_path)
    payload["md_path"] = str(md_path)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if verdict != "PASS_RPR_ARCHIVE_ONLY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
