from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.global_clean_spine_audit import build_report, get_sb_client
except ModuleNotFoundError:
    from global_clean_spine_audit import build_report, get_sb_client

DATA_DIR = ROOT / "data"
STATE_OUT = DATA_DIR / "velo_current_state.json"
ARTIFACT_INDEX_OUT = DATA_DIR / "velo_artifact_index.json"


def latest_existing(prefix: str, suffix: str) -> str | None:
    matches = sorted(DATA_DIR.glob(f"{prefix}_*.{suffix}"))
    return matches[-1].name if matches else None


def table_count(sb, table: str) -> int:
    result = sb.table(table).select("race_id", count="exact", head=True).execute()
    return int(result.count or 0)


def main() -> None:
    sb = get_sb_client()
    report = build_report(sb)
    race_results_total = table_count(sb, "race_results")
    runner_results_total = table_count(sb, "runner_results")
    hfs_total = table_count(sb, "historical_feature_store")

    state = {
        "project": "VELO",
        "phase": "historical_doctrine_full_reapply_v1_post_audit",
        "training_status": "paused",
        "playbook_e_status": "paused",
        "current_accepted_spine": {
            "race_results": race_results_total,
            "runner_results": runner_results_total,
            "historical_feature_store": hfs_total,
            "clean_historical_races_integrated_approx": 1939,
            "accepted_oasis_historical_events": report["A_accepted_clean_race_event_count"],
            "accepted_oasis_historical_hfs_rows": report["C_accepted_hfs_row_count"],
        },
        "latest_passed_audit": latest_existing("global_clean_spine_audit", "json"),
        "latest_passed_block": "OASIS_BLOCK_025",
        "latest_failed_block": None,
        "failed_block_reason": None,
        "archive_exhausted": True,
        "next_required_mission": "Playbook G V2 ablation dry-run",
        "accepted_training_authority_model": {
            "authority": [
                "race_results distinct accepted events",
                "races.runners_count",
                "accepted historical_feature_store rows",
            ],
            "known_caveat": "direct runner_results join has legacy horse-id drift and is not the authority for Playbook G V2 training cohort.",
        },
        "do_not_do": [
            "do not train live",
            "do not run Playbook E",
            "do not change training_eligible without approval",
            "do not mutate race_results or runner_results in doctrine reapply work",
        ],
    }

    artifact_index = {
        "state": str(STATE_OUT),
        "latest_global_audit_json": latest_existing("global_clean_spine_audit", "json"),
        "latest_global_audit_md": latest_existing("global_clean_spine_audit", "md"),
        "latest_doctrine_audit_json": latest_existing("historical_doctrine_feature_audit", "json"),
        "latest_doctrine_audit_md": latest_existing("historical_doctrine_feature_audit", "md"),
        "latest_doctrine_reapply_json": latest_existing("historical_doctrine_full_reapply", "json"),
        "latest_doctrine_reapply_md": latest_existing("historical_doctrine_full_reapply", "md"),
    }

    STATE_OUT.write_text(json.dumps(state, indent=2), encoding="utf-8")
    ARTIFACT_INDEX_OUT.write_text(json.dumps(artifact_index, indent=2), encoding="utf-8")
    print(f"Wrote {STATE_OUT}")
    print(f"Wrote {ARTIFACT_INDEX_OUT}")


if __name__ == "__main__":
    main()
