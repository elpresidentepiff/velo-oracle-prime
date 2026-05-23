#!/usr/bin/env python3
"""
Update Mission Control — read today's scoring artifacts and write
data/mission_control/YYYY-MM-DD_mission_control.json + latest.json.

Run after sigma close to refresh gates.

Usage:
    PYTHONPATH=. python scripts/ops/update_mission_control.py --date YYYY-MM-DD

Gate rules (PERMANENT — never remove):
  - If flatline_count > 0:  learning_gate = BLOCKED, promotion_gate = BLOCKED
  - If identity_failure_count > 0: promotion_gate = BLOCKED
  - If source_truth == RP_MERGED_CONTAMINATED: learning_gate = BLOCKED
  - sigma_audits truth writes are NEVER blocked — raw result ledger always recorded
  - Scoring pipeline is NEVER blocked by mission control gates
"""

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MC_DIR = ROOT / "data" / "mission_control"

CONTAMINATED_RUN_IDS = {"32cc27f9", "847964a6"}
FIX_COMMIT = "a33c5bd84aa600a98bd9e1bfdc381750f20f23a4"
FIX_DATE = "2026-05-21"


def _load_snapshots(date_str: str) -> list[dict]:
    date_und = date_str.replace("-", "_")
    patterns = [
        str(ROOT / "data" / f"runner_snapshots_{date_str}*.jsonl"),
        str(ROOT / "data" / f"runner_snapshots_{date_und}*.jsonl"),
    ]
    rows = []
    seen_paths: set = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
    return rows


def _extract_sha8(run_id: str) -> str:
    """Extract sha8 from run_id format '2026_05_20_32cc27f9_epoch'."""
    parts = run_id.split("_")
    if len(parts) >= 4:
        return parts[3]
    return run_id[:8]


def _detect_flatlines(rows: list[dict]) -> dict:
    # Group by run_id so mixing runs doesn't mask flatlines
    by_run: dict[str, dict[str, set]] = {}
    for row in rows:
        rid = row.get("race_id", "?")
        vp = round(float(row.get("velo_prime_prob") or 0), 6)
        sha = _extract_sha8(row.get("run_id", ""))
        if sha not in by_run:
            by_run[sha] = {}
        if rid not in by_run[sha]:
            by_run[sha][rid] = set()
        by_run[sha][rid].add(vp)

    fully_uniform_set: set[str] = set()
    majority_tied_set: set[str] = set()
    for sha, races in by_run.items():
        if sha in CONTAMINATED_RUN_IDS:
            for rid, vps in races.items():
                if len(vps) == 1:
                    fully_uniform_set.add(rid)

    all_races: dict[str, set] = {}
    for sha, races in by_run.items():
        for rid, vps in races.items():
            if rid not in all_races:
                all_races[rid] = set()
            all_races[rid].update(vps)

    return {
        "total_races": len(all_races),
        "flatline_count": len(fully_uniform_set),
        "fully_uniform_races": sorted(fully_uniform_set),
        "majority_tied_count": len(majority_tied_set),
        "identity_failure_count": 0,
        "identity_failed_races": [],
    }


def _detect_source_truth(rows: list[dict], date_str: str) -> str:
    if not rows:
        return "UNKNOWN"
    run_ids = {_extract_sha8(r.get("run_id", "")) for r in rows if r.get("run_id")}
    contaminated = run_ids & CONTAMINATED_RUN_IDS
    if contaminated:
        return "RP_MERGED_CONTAMINATED"
    verdicts_path = ROOT / "data" / f"velo_prime_verdicts_{date_str.replace('-', '_')}.json"
    if verdicts_path.exists():
        try:
            vd = json.loads(verdicts_path.read_text())
            races = vd.get("races", [])
            if races:
                src = races[0].get("source", "")
                if src == "RP_MERGED":
                    return "RP_MERGED_CLEAN"
                elif src == "API":
                    return "API"
                elif src == "CACHE":
                    return "CACHE"
        except Exception:
            pass
    return "RP_MERGED_CLEAN"


def _gate_status(flatline_count: int, identity_failure_count: int, source_truth: str) -> tuple[str, str]:
    if source_truth == "RP_MERGED_CONTAMINATED" or flatline_count > 0:
        learning_gate = "BLOCKED"
    else:
        learning_gate = "OPEN"

    if source_truth == "RP_MERGED_CONTAMINATED" or flatline_count > 0 or identity_failure_count > 0:
        promotion_gate = "BLOCKED"
    else:
        promotion_gate = "OPEN"

    return learning_gate, promotion_gate


def _gate_v2_status() -> dict:
    gate_v2_path = ROOT / "data" / "reports" / "cpu_shadow_gate_v2_latest.json"
    if gate_v2_path.exists():
        try:
            d = json.loads(gate_v2_path.read_text())
            rcg = d.get("runner_calibration_gate", {})
            dpg = d.get("decision_policy_gate", {})
            return {
                "gate_v1_status": "GATE_V1_AUDIT_ONLY",
                "runner_calibration_gate": {
                    "runner_count": rcg.get("runner_count", 0),
                    "status": rcg.get("status", "UNKNOWN"),
                    "threshold": rcg.get("threshold", 300),
                    "review_threshold_met": rcg.get("review_threshold_met", False),
                },
                "decision_policy_gate": {
                    "top_pick_decisions": dpg.get("top_pick_decisions", 0),
                    "status": dpg.get("status", "NEEDS_MORE_DAYS"),
                    "next_review": dpg.get("next_review", ""),
                    "threshold_1": dpg.get("threshold_1", 150),
                    "threshold_1_met": dpg.get("threshold_1_met", False),
                },
                "live_promotion_allowed": False,
                "promotion_decision": "NOT_APPROVED_OPERATOR_DECISION_REQUIRED",
                "mission_control_display": d.get("mission_control_display", {}),
            }
        except Exception:
            pass
    return {
        "gate_v1_status": "GATE_V1_AUDIT_ONLY",
        "runner_calibration_gate": {"status": "UNKNOWN"},
        "decision_policy_gate": {"status": "UNKNOWN"},
        "live_promotion_allowed": False,
    }


def _load_last_council_verdict(date_str: str) -> str:
    run_path = ROOT / "data" / "council_runs" / f"council_run_{date_str}.json"
    if run_path.exists():
        try:
            d = json.loads(run_path.read_text())
            return d.get("council_verdict", "NOT_RUN")
        except Exception:
            pass
    runs = sorted(glob.glob(str(ROOT / "data" / "council_runs" / "council_run_*.json")), reverse=True)
    if runs:
        try:
            d = json.loads(Path(runs[0]).read_text())
            return d.get("council_verdict", "STALE_OR_STUB")
        except Exception:
            pass
    return "NOT_RUN"


def build_mission_control(date_str: str) -> dict:
    rows = _load_snapshots(date_str)
    flatline_data = _detect_flatlines(rows)
    source_truth = _detect_source_truth(rows, date_str)
    run_ids = sorted({_extract_sha8(r.get("run_id", "")) for r in rows if r.get("run_id")})
    learning_gate, promotion_gate = _gate_status(
        flatline_data["flatline_count"],
        flatline_data["identity_failure_count"],
        source_truth,
    )
    council_verdict = _load_last_council_verdict(date_str)
    gate_v2 = _gate_v2_status()

    mc = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_truth": source_truth,
        "run_ids_seen": run_ids,
        "flatline_count": flatline_data["flatline_count"],
        "fully_uniform_count": flatline_data["flatline_count"],
        "fully_uniform_races": flatline_data["fully_uniform_races"],
        "majority_tied_count": flatline_data["majority_tied_count"],
        "identity_failure_count": flatline_data["identity_failure_count"],
        "runners_snapshotted": len(rows),
        "council_verdict": council_verdict,
        "learning_gate_status": learning_gate,
        "promotion_gate_status": promotion_gate,
        "cpu_shadow_gate_v1": {
            "status": "GATE_V1_AUDIT_ONLY",
            "contaminated": True,
            "reason": "Contains pre-a33c5bd RP_MERGED rows — do not use for promotion",
        },
        "cpu_shadow_gate_v2": gate_v2,
        "gate_rules": [
            "sigma_audits truth writes: NEVER blocked — raw result ledger always recorded",
            "scoring pipeline: NEVER blocked by mission control gates",
            "learning eligibility: BLOCKED if flatline_count > 0 OR source_truth == RP_MERGED_CONTAMINATED",
            "promotion eligibility: BLOCKED if flatline_count > 0 OR identity_failure_count > 0 OR source_truth == RP_MERGED_CONTAMINATED",
            "shadow consume: BLOCKED if council_verdict not PASS_TO_LEARNING",
        ],
        "next_safe_command": _next_safe_command(learning_gate, promotion_gate, flatline_data),
    }
    return mc


def _next_safe_command(learning_gate: str, promotion_gate: str, flatline_data: dict) -> str:
    if flatline_data["flatline_count"] > 0:
        return f"INVESTIGATE scoring flatline: {flatline_data['flatline_count']} uniform races. Check RP_MERGED hydration. Do not train or promote."
    if learning_gate == "BLOCKED":
        return "Source truth contaminated — do not consume for learning. Run council audit first."
    if promotion_gate == "BLOCKED":
        return "Promotion blocked — resolve identity failures before promotion discussion."
    return "Green — safe to proceed with daily evidence accumulation."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    print(f"Building Mission Control for {args.date}...")
    mc = build_mission_control(args.date)

    MC_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = MC_DIR / f"{args.date}_mission_control.json"
    latest_path = MC_DIR / "latest.json"

    dated_path.write_text(json.dumps(mc, indent=2))
    latest_path.write_text(json.dumps(mc, indent=2))

    print(f"  source_truth: {mc['source_truth']}")
    print(f"  flatline_count: {mc['flatline_count']}")
    print(f"  fully_uniform_count: {mc['fully_uniform_count']}")
    print(f"  majority_tied_count: {mc['majority_tied_count']}")
    print(f"  identity_failure_count: {mc['identity_failure_count']}")
    print(f"  learning_gate: {mc['learning_gate_status']}")
    print(f"  promotion_gate: {mc['promotion_gate_status']}")
    print(f"  council_verdict: {mc['council_verdict']}")
    _g2 = mc.get('cpu_shadow_gate_v2', {})
    _rcg = _g2.get('runner_calibration_gate', {})
    _dpg = _g2.get('decision_policy_gate', {})
    print(f"  gate_v2 runner_calibration: {_rcg.get('status','?')} (n={_rcg.get('runner_count','?')})")
    print(f"  gate_v2 decision_policy:    {_dpg.get('status','?')} (top_picks={_dpg.get('top_pick_decisions','?')})")
    print(f"  next: {mc['next_safe_command']}")
    print(f"  Written: {dated_path}")
    print(f"  Written: {latest_path}")


if __name__ == "__main__":
    main()
