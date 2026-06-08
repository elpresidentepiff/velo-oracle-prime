#!/usr/bin/env python3
"""Analyze archive-only RP context for early profile candidates and warnings."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _iter_dossiers(from_date: str, to_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in sorted(PARSED_ROOT.glob("20*-*-*")):
        if not (from_date <= day.name <= to_date):
            continue
        payload = _load(day / "horse_dossiers.json", {})
        for row in payload.get("dossiers") or []:
            item = dict(row)
            item["source_date"] = day.name
            rows.append(item)
    return rows


def _classify(row: dict[str, Any], linked: bool, rpdc: bool) -> list[str]:
    flags: list[str] = []
    tips = int(row.get("tip_count") or 0)
    if tips >= 7:
        flags.append("HYPE_TRAP_CANDIDATE")
    if tips == 0 and linked:
        flags.append("QUIET_PROFILE_CANDIDATE")
    if row.get("trainer"):
        flags.append("TRAINER_CLUSTER_SIGNAL")
    if row.get("sire") or row.get("dam_sire"):
        flags.append("PEDIGREE_CLUSTER_SIGNAL")
    if row.get("headgear_first_time") or row.get("wind_surgery"):
        flags.append("EARLY_PROFILE_EDGE_CANDIDATE")
    if not linked:
        flags.append("LOW_DATA_WARNING")
    if rpdc:
        flags.append("EARLY_PROFILE_EDGE_CANDIDATE")
    flags.append("OUTCOME_REQUIRED_BEFORE_PROMOTION")
    return sorted(set(flags))


def run(from_date: str, to_date: str) -> dict[str, Any]:
    dossiers = _iter_dossiers(from_date, to_date)
    bridge = _load(PARSED_ROOT / "horse_identity_bridge.json", {}).get("bridge") or []
    bridge_by_key = {(row.get("source_date"), row.get("normalized_name")): row for row in bridge}
    trainer = Counter(row.get("trainer") for row in dossiers if row.get("trainer"))
    owner = Counter(row.get("owner") for row in dossiers if row.get("owner"))
    sire = Counter(row.get("sire") for row in dossiers if row.get("sire"))
    dam_sire = Counter(row.get("dam_sire") for row in dossiers if row.get("dam_sire"))
    tip_heat = [row for row in dossiers if int(row.get("tip_count") or 0) >= 7]
    headgear = [row for row in dossiers if row.get("headgear_first_time") or row.get("headgear")]
    wind = [row for row in dossiers if row.get("wind_surgery")]
    candidates: list[dict[str, Any]] = []
    for row in dossiers:
        key = "".join(ch for ch in str(row.get("horse") or "").lower() if ch.isalnum())
        b = bridge_by_key.get((row.get("source_date"), key), {})
        linked = b.get("classification") == "IDENTITY_CONFIRMED"
        rpdc = "RPDC" in (b.get("matched_sources") or [])
        classes = _classify(row, linked, rpdc)
        if any(c in classes for c in ["HYPE_TRAP_CANDIDATE", "QUIET_PROFILE_CANDIDATE", "EARLY_PROFILE_EDGE_CANDIDATE", "LOW_DATA_WARNING"]):
            candidates.append({
                "date": row.get("source_date"),
                "course": row.get("course"),
                "time": row.get("race_time"),
                "horse": row.get("horse"),
                "trainer": row.get("trainer"),
                "sire": row.get("sire"),
                "tip_count": row.get("tip_count"),
                "identity_classification": b.get("classification", "BRIDGE_MISSING"),
                "classifications": classes,
            })
    payload = {
        "generated_at": _utc_now(),
        "from_date": from_date,
        "to_date": to_date,
        "horse_count": len(dossiers),
        "trainer_concentration": trainer.most_common(15),
        "owner_clusters": owner.most_common(15),
        "sire_clusters": sire.most_common(15),
        "dam_sire_clusters": dam_sire.most_common(15),
        "tip_heat_count": len(tip_heat),
        "headgear_count": len(headgear),
        "wind_surgery_count": len(wind),
        "candidate_count": len(candidates),
        "candidates": candidates[:250],
        "scoring_impact": "NONE",
        "promotion_status": "OUTCOME_REQUIRED_BEFORE_PROMOTION",
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "rp_archive_deeper_analysis_latest.json"
    md_path = REPORT_ROOT / "rp_archive_deeper_analysis_latest.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# RP Archive Deeper Analysis",
        "",
        f"- Horses: `{len(dossiers)}`",
        f"- Tip heat candidates: `{len(tip_heat)}`",
        f"- Headgear/wind candidates: `{len(headgear) + len(wind)}`",
        f"- Candidate rows: `{len(candidates)}`",
        "- Promotion status: `OUTCOME_REQUIRED_BEFORE_PROMOTION`",
        "- Scoring impact: `NONE`",
        "",
        "## Top Trainer Clusters",
    ]
    for name, count in trainer.most_common(10):
        lines.append(f"- {name}: `{count}`")
    lines += ["", "## Top Sire Clusters"]
    for name, count in sire.most_common(10):
        lines.append(f"- {name}: `{count}`")
    lines += ["", "## Candidate Sample"]
    for row in candidates[:50]:
        lines.append(f"- {row['date']} {row['time']} {row['course']} - **{row['horse']}**: {', '.join(row['classifications'])}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze RP archive advantage layer.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    args = parser.parse_args()
    run(args.from_date, args.to_date)


if __name__ == "__main__":
    main()
