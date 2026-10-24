"""Generate a minimal, offline, non-certified model-cohort evidence report.

Usage: python -m src.intelligence.challenger_export_audit --input scorecards.json --output report.json
Input must be a separately exported JSON array of canonical_model_scorecards.
NEVER upgrades source completeness, official eligibility, or probability status.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from src.intelligence.challenger_scorecard_audit import audit_scorecard_export


def run(input_path: Path, output_path: Path) -> dict:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("input/output must differ")
    source = input_path.read_bytes()
    result = audit_scorecard_export(input_path)
    result["input_sha256"] = sha256(source).hexdigest()
    result["source_certification"] = "NOT_INDEPENDENTLY_VERIFIED"
    result["next_gate"] = "VERIFY_OFFICIAL_RESULTS_AND_PRE_RACE_SNAPSHOTS"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
