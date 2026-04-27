from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from global_clean_spine_audit import build_event_key, get_sb_client, load_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify whether a manifest-scoped rollback is clean.")
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def extra_duplicate_count(keys: list[str]) -> int:
    counts: dict[str, int] = {}
    dupes = 0
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > 1:
            dupes += 1
    return dupes


def main() -> None:
    args = parse_args()
    manifest = load_json_file(args.manifest)
    sb = get_sb_client()

    race_events = manifest.get("race_events") or []
    race_ids = [str(rid) for rid in (manifest.get("race_ids") or [])]
    if not race_ids:
        race_ids = [str(event["race_id"]) for event in race_events]

    manifest_runner_count = int(manifest.get("runner_count") or sum(int(event.get("runner_count") or 0) for event in race_events))
    manifest_event_count = len(race_events)

    races_rows = sb.table("races").select("race_id,date,course,raw").in_("race_id", race_ids).execute().data or []
    race_results_rows = sb.table("race_results").select("race_id", count="exact").in_("race_id", race_ids).execute().data or []
    runner_results_rows = sb.table("runner_results").select("race_id,horse_id", count="exact").in_("race_id", race_ids).execute().data or []
    hfs_rows = (
        sb.table("historical_feature_store")
        .select("race_id,horse_id,reconstruction_version", count="exact")
        .in_("race_id", race_ids)
        .execute()
        .data
        or []
    )

    event_keys = []
    for row in races_rows:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        event_keys.append(raw.get("event_key") or build_event_key(str(row["race_id"]), row.get("course"), row.get("date")))

    result = {
        "manifest_path": str(args.manifest),
        "manifest_event_count": manifest_event_count,
        "manifest_runner_count": manifest_runner_count,
        "remaining_rows": {
            "races": len(races_rows),
            "race_results": len(race_results_rows),
            "runner_results": len(runner_results_rows),
            "historical_feature_store": len(hfs_rows),
        },
        "duplicate_event_keys": extra_duplicate_count(event_keys),
    }

    result["rollback_status"] = (
        "clean"
        if result["remaining_rows"]["races"] == 0
        and result["remaining_rows"]["race_results"] == 0
        and result["remaining_rows"]["runner_results"] == 0
        and result["remaining_rows"]["historical_feature_store"] == 0
        and result["duplicate_event_keys"] == 0
        else "dirty"
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
