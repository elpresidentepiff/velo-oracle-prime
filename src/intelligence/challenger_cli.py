"""Offline Evo² candidate evaluation entry point.

Usage:
  python -m src.intelligence.challenger_cli --input frozen.json --output report.json --baseline-ref SHA

Input JSON: {"observations": [{race_id,runner_id,race_time,prediction_time,outcome,baseline_prob,challenger_prob},...]}
Source must be independently certified by operator; absence of provenance blocks official conclusions.
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from src.intelligence.challenger_lab import Observation
from src.intelligence.challenger_research_cycle import propose_calibration_review, reflect


def run(input_path: Path, output_path: Path, baseline_ref: str, *, min_runners: int = 300) -> dict:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("input and output paths must differ")
    source_bytes = input_path.read_bytes()
    payload = json.loads(source_bytes.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
        raise ValueError("input must contain observations array")
    if payload.get("result_source_complete") is not True:
        raise ValueError("verified result_source_complete=true is mandatory")
    if payload.get("holdout_frozen") is not True:
        raise ValueError("holdout_frozen=true is mandatory")
    if not isinstance(payload.get("source_ref"), str) or not payload["source_ref"].strip():
        raise ValueError("source_ref required")
    if not isinstance(payload.get("run_id"), str) or not payload["run_id"].strip():
        raise ValueError("run_id required")
    observations = [Observation(**item) for item in payload["observations"]]
    proposal = propose_calibration_review(baseline_ref=baseline_ref)
    report = reflect(proposal, observations, min_runners=min_runners)
    report["input_provenance"] = {
        "source_ref": payload["source_ref"],
        "source_file_sha256": sha256(source_bytes).hexdigest(),
        "certification": "SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED",
        "run_id": payload.get("run_id"),
        "result_source_complete": True,
        "holdout_frozen": True,
    }
    if not report["input_provenance"]["source_ref"] or not report["input_provenance"]["run_id"]:
        raise ValueError("source_ref and run_id required")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--min-runners", type=int, default=300)
    args = parser.parse_args()
    report = run(args.input, args.output, args.baseline_ref, min_runners=args.min_runners)
    print(json.dumps({"decision": report["reflector_decision"], "artifact_sha256": report["artifact_sha256"]}))


if __name__ == "__main__":
    main()
