#!/usr/bin/env python3
"""Review ambiguous identities and RPDC name-only upgrade candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "data" / "racing_post_account_parsed" / "horse_identity_bridge.json"
REPORT_ROOT = ROOT / "data" / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _recommend(row: dict[str, Any]) -> str:
    if row.get("classification") == "MULTI_MATCH_AMBIGUOUS":
        return "MANUAL_REVIEW_REQUIRED"
    if row.get("classification") == "NAME_MATCH_ONLY":
        if row.get("trainer") and row.get("sire") and row.get("country") and row.get("identity_confidence", 0) >= 0.72:
            return "REMAIN_NAME_ONLY"
        return "MANUAL_REVIEW_REQUIRED"
    return "REJECT"


def build(execute: bool) -> dict[str, Any]:
    bridge = _load(BRIDGE_PATH, {}).get("bridge") or []
    ambiguous = [row for row in bridge if row.get("classification") == "MULTI_MATCH_AMBIGUOUS"]
    name_only = [row for row in bridge if row.get("classification") == "NAME_MATCH_ONLY"]
    upgraded = []
    remained = []
    rejected = []
    for row in name_only:
        rec = _recommend(row)
        item = {
            "rp_horse": row.get("rp_horse_name"),
            "rp_horse_id": row.get("rp_horse_id"),
            "rpdc_horse_id": row.get("rpdc_horse_id"),
            "trainer": row.get("trainer"),
            "sire": row.get("sire"),
            "age": row.get("age"),
            "country": row.get("country"),
            "identity_confidence": row.get("identity_confidence"),
            "recommendation": rec,
        }
        if rec == "CONFIRM":
            upgraded.append(item)
        elif rec == "REMAIN_NAME_ONLY":
            remained.append(item)
        else:
            rejected.append(item)
    payload = {
        "generated_at": _utc_now(),
        "ambiguous_count": len(ambiguous),
        "rpdc_name_only_count": len(name_only),
        "upgraded_to_confirmed_count": len(upgraded),
        "remained_name_only_count": len(remained),
        "rejected_or_manual_count": len(rejected),
        "scoring_impact": "NONE",
        "ambiguous": ambiguous,
        "rpdc_name_only_review": {
            "upgraded_to_confirmed": upgraded,
            "remained_name_only": remained,
            "rejected_or_manual": rejected,
        },
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_ROOT / "horse_identity_ambiguous_review_latest.json"
        md_path = REPORT_ROOT / "horse_identity_ambiguous_review_latest.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# Horse Identity Ambiguous Review",
            "",
            f"- Ambiguous: `{len(ambiguous)}`",
            f"- RPDC name-only: `{len(name_only)}`",
            f"- Upgraded to confirmed: `{len(upgraded)}`",
            f"- Remained name-only: `{len(remained)}`",
            f"- Rejected/manual: `{len(rejected)}`",
            "- Scoring impact: `NONE`",
            "",
            "## Ambiguous",
        ]
        for row in ambiguous:
            lines.append(
                f"- **{row.get('rp_horse_name')}**: trainer=`{row.get('trainer')}`, sire=`{row.get('sire')}`, "
                f"age=`{row.get('age')}`, country=`{row.get('country')}` => `MANUAL_REVIEW_REQUIRED`"
            )
        lines += ["", "## RPDC Name-Only Review", ""]
        lines.append("No name-only RPDC rows were upgraded automatically. Trainer/sire/age/country are retained as review evidence, but confirmation requires stronger shared identifiers or dated outcome context.")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["json_path"] = str(json_path)
        payload["md_path"] = str(md_path)
    else:
        payload["status"] = "DRY_RUN"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Review ambiguous identity bridge rows.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
