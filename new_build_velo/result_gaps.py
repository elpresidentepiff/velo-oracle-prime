"""Result gap planner for New Build VELO archive dates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from new_build_velo.database import REPORT_ROOT, _iter_jsonl
from new_build_velo.spine import ROOT, TRUST_POLICY, utc_now, write_json


def plan_result_gaps(*, execute: bool = False) -> dict[str, Any]:
    bridge_dates = sorted(
        {
            str(row.get("race_date") or row.get("source_date"))
            for row in _iter_jsonl(ROOT / "data" / "new_build" / "bridges" / "outcome_bridge_v2.jsonl")
            if row.get("race_date") or row.get("source_date")
        }
    )
    result_dates = sorted(
        {
            str(row.get("source_date"))
            for row in _iter_jsonl(ROOT / "data" / "new_build" / "normalized" / "runner_results.jsonl")
            if row.get("source_date")
        }
    )
    result_set = set(result_dates)
    gaps = []
    for date in bridge_dates:
        local_path = ROOT / "data" / f"results_{date.replace('-', '_')}.json"
        normalized_path = ROOT / "data" / "new_build" / "normalized" / "racing_api_results" / date / "results.json"
        gaps.append(
            {
                "date": date,
                "result_available": date in result_set,
                "raw_result_file": str(local_path),
                "raw_result_file_exists": local_path.exists(),
                "normalized_result_file": str(normalized_path),
                "normalized_result_file_exists": normalized_path.exists(),
                "next_command_after_raw_exists": f"python scripts/ops/new_build_sources.py ingest-results --date {date} --execute",
            }
        )
    missing = [row for row in gaps if not row["result_available"]]
    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_RESULT_GAP_PLAN_READY",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "bridge_dates": bridge_dates,
        "result_date_min": result_dates[0] if result_dates else None,
        "result_date_max": result_dates[-1] if result_dates else None,
        "missing_result_dates": [row["date"] for row in missing],
        "missing_result_count": len(missing),
        "gaps": gaps,
        "recommended_next_step": "CAPTURE_OR_IMPORT_MISSING_RESULT_FILES" if missing else "RERUN_OUTCOME_BRIDGE_V2",
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        write_json(REPORT_ROOT / "result_gap_plan_latest.json", payload)
        lines = [
            "# New Build Result Gap Plan",
            "",
            f"- Bridge dates: {', '.join(bridge_dates) if bridge_dates else 'none'}",
            f"- Result date range: {payload['result_date_min']} to {payload['result_date_max']}",
            f"- Missing result dates: {', '.join(payload['missing_result_dates']) if missing else 'none'}",
            f"- Recommended next step: {payload['recommended_next_step']}",
            "",
            "## Commands After Raw Result Files Exist",
        ]
        for row in missing:
            lines.append(f"- `{row['next_command_after_raw_exists']}`")
        lines.extend(
            [
                "",
                "Then rerun:",
                "- `python scripts/ops/new_build_database.py build-normalized --execute`",
                "- `python scripts/ops/new_build_outcome_bridge.py --execute`",
                "- `python scripts/ops/new_build_database.py sandbox-learn --execute`",
                "- `python scripts/ops/new_build_evaluate.py --execute`",
                "",
                "Live VELO untouched. Shadow VELO untouched.",
            ]
        )
        (REPORT_ROOT / "result_gap_plan_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan missing New Build result files for outcome linking.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(plan_result_gaps(execute=args.execute), indent=2, ensure_ascii=False))
    return 0
