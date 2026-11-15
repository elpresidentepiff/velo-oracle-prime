#!/usr/bin/env python3
"""Report which daily model lanes have the files they must load.

Reads ``config/model_lane_artifacts.json`` and checks each file on disk. It changes nothing and
scores nothing. Exit code 1 means a lane recorded as SHIPPED cannot find one of its files: the
image is broken and that lane will fail or silently skip. A lane recorded MISSING_FROM_IMAGE is
reported with its impact and repair and does not fail the check, so one known gap is not
re-raised as a new alarm every morning.

Usage:
    PYTHONPATH=. python scripts/ops/check_model_lane_artifacts.py
    PYTHONPATH=. python scripts/ops/check_model_lane_artifacts.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "model_lane_artifacts.json"

SHIPPED = "SHIPPED"
KNOWN_MISSING = "MISSING_FROM_IMAGE"


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["lanes"]


def check_lanes(lanes: list[dict], root: Path = ROOT) -> list[dict]:
    """One finding per lane: OK, KNOWN_MISSING, NOW_PRESENT or BROKEN."""
    findings = []
    for lane in lanes:
        absent = [p for p in lane["artifacts"] if not (root / p).is_file()]
        if lane["status"] == SHIPPED:
            state = "BROKEN" if absent else "OK"
        elif absent:
            state = "KNOWN_MISSING"
        else:
            state = "NOW_PRESENT"  # the file has arrived: flip the manifest entry to SHIPPED
        findings.append(
            {
                "lane": lane["lane"],
                "state": state,
                "loader": lane["loader"],
                "absent": absent,
                "impact": lane.get("impact", ""),
                "repair": lane.get("repair", ""),
            }
        )
    return findings


def format_finding(finding: dict) -> str:
    if finding["state"] == "OK":
        return f"OK             {finding['lane']}"
    if finding["state"] == "NOW_PRESENT":
        return (
            f"NOW_PRESENT    {finding['lane']}: every file is on disk. "
            f"Set its status to SHIPPED in config/model_lane_artifacts.json."
        )
    impact = finding["impact"] or "The lane cannot load its model and will fail or be skipped."
    repair = finding["repair"] or "Restore the file to the image (force-add it; the path is git-ignored)."
    return "\n".join(
        [
            f"{finding['state']:<14} {finding['lane']}",
            f"  WHAT FAILED : model file not in the image: {', '.join(finding['absent'])}",
            f"  WHERE       : {finding['loader']}",
            f"  IMPACT      : {impact}",
            f"  REPAIR      : {repair}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the findings as JSON")
    args = parser.parse_args()
    findings = check_lanes(load_manifest())
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print("MODEL LANE ARTIFACTS")
        for finding in findings:
            print(format_finding(finding))
    return 1 if any(f["state"] == "BROKEN" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
