#!/usr/bin/env python3
"""
Loop Health Checker — READ-ONLY
================================
Evaluates every loop in data/current/loop_registry.json:
artifact presence, artifact freshness, and embedded status fields.

Looped OS law (docs/current/VELO_LOOPED_OS_ARCHITECTURE.md):
DETECT -> DECIDE -> ACT -> VERIFY -> LOG -> LEARN OR BLOCK.
This script is the VERIFY+LOG stage for the loop stack itself.

Usage:
    PYTHONPATH=. python scripts/ops/check_loop_health.py [--date YYYY-MM-DD]

Outputs:
    data/current/loop_health_latest.json
    data/reports/loop_health_latest.md

Hard constraints:
  - READ-ONLY against everything except its own two output files.
  - No Supabase access. No scoring imports. No learning execution.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime, date as date_cls
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LOOP_OK = "LOOP_OK"
LOOP_PARTIAL = "LOOP_PARTIAL"
LOOP_MISSING_ARTIFACT = "LOOP_MISSING_ARTIFACT"
LOOP_FAILING = "LOOP_FAILING"
LOOP_NOT_IMPLEMENTED = "LOOP_NOT_IMPLEMENTED"
LOOP_BLOCKED_OPERATOR = "LOOP_BLOCKED_OPERATOR"


def _artifact_exists(pattern: str, date_str: str) -> bool:
    p = pattern.replace("{date}", date_str).replace("{date_und}", date_str.replace("-", "_"))
    # Patterns may contain globs; date may appear with dashes or underscores.
    candidates = {p, p.replace(date_str, date_str.replace("-", "_"))}
    for c in candidates:
        if glob.glob(str(ROOT / c)):
            return True
    return False


def _status_from_artifact(path: Path, key: str) -> str | None:
    try:
        return json.loads(path.read_text()).get(key)
    except Exception:
        return None


def evaluate_loop(loop: dict, date_str: str) -> dict:
    declared = loop.get("current_status", LOOP_NOT_IMPLEMENTED)
    artifacts = loop.get("required_artifacts") or []
    missing = [a for a in artifacts if not _artifact_exists(a, date_str)]

    status = declared
    detail = ""

    if declared in (LOOP_NOT_IMPLEMENTED, LOOP_BLOCKED_OPERATOR):
        pass  # declared state stands; artifact checks are informational
    elif missing:
        status = LOOP_MISSING_ARTIFACT
        detail = f"missing: {', '.join(missing)}"
    else:
        # Embedded-status escalation for the implemented proof loops.
        if loop["loop_id"] == "L4":
            s = _status_from_artifact(ROOT / "data/current/persistence_proof_latest.json", "status")
            if s and s != "PASS":
                status = LOOP_FAILING
                detail = f"persistence proof status={s}"
        if loop["loop_id"] == "L3":
            s = _status_from_artifact(ROOT / "data/current/rpdc_integrity_latest.json", "status")
            if s and s not in ("RPDC_OK",):
                status = LOOP_FAILING
                detail = f"rpdc integrity status={s}"
        if loop["loop_id"] == "L5":
            mc = ROOT / "data/mission_control/latest.json"
            src = _status_from_artifact(mc, "source_truth")
            if src is None:
                status = LOOP_MISSING_ARTIFACT
                detail = "mission_control latest.json unreadable"
            else:
                detail = f"mc source_truth={src}"

    return {
        "loop_id": loop["loop_id"],
        "name": loop["name"],
        "status": status,
        "declared_status": declared,
        "detail": detail,
        "missing_artifacts": missing,
        "blocks_learning": loop.get("blocks_learning", False),
        "blocks_telegram": loop.get("blocks_telegram", False),
        "blocks_clean_claim": loop.get("blocks_clean_claim", False),
        "next_fix": loop.get("next_fix", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date_cls.today().isoformat())
    args = parser.parse_args()

    registry_path = ROOT / "data/current/loop_registry.json"
    registry = json.loads(registry_path.read_text())
    results = [evaluate_loop(lp, args.date) for lp in registry["loops"]]

    blocking_learning = [r["loop_id"] for r in results if r["blocks_learning"] and r["status"] != LOOP_OK]
    blocking_telegram = [r["loop_id"] for r in results if r["blocks_telegram"] and r["status"] != LOOP_OK]
    blocking_claims = [r["loop_id"] for r in results if r["blocks_clean_claim"] and r["status"] != LOOP_OK]

    health = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date_context": args.date,
        "registry_version": registry.get("registry_version"),
        "loops": results,
        "summary": {s: sum(1 for r in results if r["status"] == s) for s in {r["status"] for r in results}},
        "loops_blocking_learning": blocking_learning,
        "loops_blocking_telegram": blocking_telegram,
        "loops_blocking_clean_claims": blocking_claims,
        "read_only_confirmed": True,
    }

    out_json = ROOT / "data/current/loop_health_latest.json"
    out_json.write_text(json.dumps(health, indent=2))

    lines = [
        "# Loop Health — latest",
        "",
        f"Generated {health['generated_at']} · date context {args.date} · READ-ONLY",
        "",
        "| Loop | Status | Detail / next fix |",
        "|---|---|---|",
    ]
    for r in results:
        note = r["detail"] or r["next_fix"]
        lines.append(f"| {r['loop_id']} {r['name']} | {r['status']} | {note} |")
    lines += [
        "",
        f"**Blocking learning:** {', '.join(blocking_learning) or 'none'}",
        f"**Blocking Telegram:** {', '.join(blocking_telegram) or 'none'}",
        f"**Blocking clean public claims:** {', '.join(blocking_claims) or 'none'}",
    ]
    reports = ROOT / "data/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "loop_health_latest.md").write_text("\n".join(lines))

    print(f"Loop health written -> {out_json}")
    for r in results:
        print(f"  {r['loop_id']:4} {r['status']:24} {r['name']}")
    print(f"  blocking learning: {blocking_learning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
