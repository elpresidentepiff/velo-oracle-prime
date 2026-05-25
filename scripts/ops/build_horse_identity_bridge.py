#!/usr/bin/env python3
"""Build a conservative RP/Velo/Racing API/RPDC horse identity bridge."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"
OUT_PATH = PARSED_ROOT / "horse_identity_bridge.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _all_rp_dossiers(start_date: str | None, end_date: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in sorted(p for p in PARSED_ROOT.glob("20*-*-*") if p.is_dir()):
        date = day.name
        if start_date and date < start_date:
            continue
        if end_date and date > end_date:
            continue
        payload = _load(day / "horse_dossiers.json", {})
        for dossier in payload.get("dossiers") or []:
            row = dict(dossier)
            row["_source_date"] = date
            rows.append(row)
    # Include Bow Echo pilot profile.
    profiles = _load(PARSED_ROOT / "2026-05-24" / "horse_profiles.json", {}).get("horse_profiles") or []
    for profile in profiles:
        if _norm(profile.get("horse_name")) == "bowecho":
            rows.append({
                "_source_date": "2026-05-24",
                "horse": profile.get("horse_name"),
                "rp_horse_id": profile.get("horse_uid"),
                "trainer": profile.get("trainer_name"),
                "sire": profile.get("sire_name"),
                "age": profile.get("age"),
                "country": profile.get("country"),
                "owner": profile.get("owner_name"),
                "dam": profile.get("dam_name"),
                "dam_sire": profile.get("dam_sire_name"),
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            })
    return rows


def _runner_snapshot_rows(start_date: str | None, end_date: str | None) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in ROOT.glob("data/runner_snapshots_*.jsonl"):
        for row in _iter_jsonl(path):
            date = row.get("race_date")
            if start_date and date and date < start_date:
                continue
            if end_date and date and date > end_date:
                continue
            if row.get("horse"):
                index[_norm(row["horse"])].append(row)
    return index


def _verdict_rows(start_date: str | None, end_date: str | None) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in ROOT.glob("data/velo_prime_verdicts_20*.json"):
        date = path.stem.replace("velo_prime_verdicts_", "").replace("_", "-")
        if start_date and date < start_date:
            continue
        if end_date and date > end_date:
            continue
        payload = _load(path, [])
        if not isinstance(payload, list):
            continue
        for race in payload:
            top = race.get("top") or {}
            if top.get("horse"):
                row = dict(top)
                row["race_date"] = date
                row["race_id"] = race.get("race_id") or row.get("race_id")
                row["course"] = race.get("course")
                row["off_time"] = race.get("off_time")
                index[_norm(top["horse"])].append(row)
    return index


def _rpdc_rows() -> dict[str, list[dict[str, Any]]]:
    rows = _iter_jsonl(ROOT / "data" / "rpdc_backfill" / "rpdc_tags_historical.jsonl")
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("horse"):
            index[_norm(row["horse"])].append(row)
    return index


def _sigma_rows() -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in ROOT.glob("data/sigma_results/sigma_results_20*.json"):
        payload = _load(path, {})
        rows = payload.get("learning_candidate_rows") or payload.get("raw_sigma_audits_preserved") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            horse = row.get("horse") or row.get("selection") or row.get("top_horse")
            if horse:
                index[_norm(horse)].append(row)
    return index


def _pick_candidate(
    dossier: dict[str, Any],
    candidates: list[dict[str, Any]],
    source: str,
) -> tuple[dict[str, Any] | None, str, float, str | None]:
    if not candidates:
        return None, "no_match", 0.0, None
    date = dossier.get("_source_date")
    course = str(dossier.get("course") or "").lower()
    same_date = [c for c in candidates if not date or c.get("race_date") == date]
    pool = same_date or candidates
    if len(pool) == 1:
        method = "normalized_name_date" if same_date else "normalized_name"
        confidence = 0.86 if same_date else 0.72
        return pool[0], method, confidence, None
    same_course = [c for c in pool if course and str(c.get("course") or "").lower() in {course, course[:3]}]
    if len(same_course) == 1:
        return same_course[0], "normalized_name_date_course", 0.92, None
    return None, "ambiguous", 0.0, f"{source}_MULTI_MATCH_{len(pool)}"


def _classification(matched_sources: list[str], ambiguous: bool) -> str:
    if ambiguous:
        return "MULTI_MATCH_AMBIGUOUS"
    if "VELO" in matched_sources or "RUNNER_SNAPSHOT" in matched_sources:
        return "IDENTITY_CONFIRMED"
    if "RPDC" in matched_sources or "SIGMA" in matched_sources:
        return "NAME_MATCH_ONLY"
    if matched_sources == ["RP"]:
        return "RP_ONLY"
    return "NEEDS_MANUAL_REVIEW"


def build(start_date: str | None, end_date: str | None, execute: bool) -> dict[str, Any]:
    dossiers = _all_rp_dossiers(start_date, end_date)
    snapshots = _runner_snapshot_rows(start_date, end_date)
    verdicts = _verdict_rows(start_date, end_date)
    rpdc = _rpdc_rows()
    sigmas = _sigma_rows()
    bridge: list[dict[str, Any]] = []

    for dossier in dossiers:
        horse = dossier.get("horse")
        key = _norm(horse)
        snap, snap_method, snap_conf, snap_blocker = _pick_candidate(dossier, snapshots.get(key) or [], "RUNNER_SNAPSHOT")
        verdict, verdict_method, verdict_conf, verdict_blocker = _pick_candidate(dossier, verdicts.get(key) or [], "VELO")
        rpdc_match, rpdc_method, rpdc_conf, rpdc_blocker = _pick_candidate(dossier, rpdc.get(key) or [], "RPDC")
        sigma_match, sigma_method, sigma_conf, sigma_blocker = _pick_candidate(dossier, sigmas.get(key) or [], "SIGMA")
        matched_sources = ["RP"]
        if snap:
            matched_sources.append("RUNNER_SNAPSHOT")
        if verdict:
            matched_sources.append("VELO")
        if rpdc_match:
            matched_sources.append("RPDC")
        if sigma_match:
            matched_sources.append("SIGMA")
        blockers = [b for b in [snap_blocker, verdict_blocker, rpdc_blocker, sigma_blocker] if b]
        ambiguous = any("MULTI_MATCH" in b for b in blockers)
        confidence = max([snap_conf, verdict_conf, rpdc_conf, sigma_conf, 0.0])
        if matched_sources == ["RP"]:
            blocker_reason = "NO_LOCAL_VELO_RACING_API_RPDC_SIGMA_MATCH"
        elif blockers:
            blocker_reason = ";".join(blockers)
        else:
            blocker_reason = None
        bridge.append({
            "rp_horse_id": dossier.get("rp_horse_id"),
            "rp_horse_name": horse,
            "normalized_name": key,
            "source_date": dossier.get("_source_date"),
            "racing_api_horse_id": (snap or verdict or {}).get("horse_id"),
            "velo_horse_id": (snap or verdict or {}).get("horse_id"),
            "rpdc_horse_id": (rpdc_match or {}).get("horse_id"),
            "sigma_horse_id": (sigma_match or {}).get("horse_id"),
            "trainer": dossier.get("trainer"),
            "sire": dossier.get("sire"),
            "age": dossier.get("age"),
            "country": dossier.get("country"),
            "matched_sources": matched_sources,
            "match_method": {
                "runner_snapshot": snap_method,
                "velo": verdict_method,
                "rpdc": rpdc_method,
                "sigma": sigma_method,
            },
            "identity_confidence": round(confidence, 4),
            "classification": _classification(matched_sources, ambiguous),
            "blocker_reason": blocker_reason,
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "velo_scoring_allowed": False,
            "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
        })

    counts = Counter(row["classification"] for row in bridge)
    source_counts = Counter(src for row in bridge for src in row["matched_sources"])
    payload = {
        "generated_at": _utc_now(),
        "start_date": start_date,
        "end_date": end_date,
        "horse_count": len(bridge),
        "classification_counts": dict(counts),
        "source_counts": dict(source_counts),
        "scoring_impact": "NONE",
        "bridge": bridge,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_ROOT / "horse_identity_bridge_latest.json"
        md_path = REPORT_ROOT / "horse_identity_bridge_latest.md"
        OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# Horse Identity Bridge",
            "",
            f"- Horses bridged: `{len(bridge)}`",
            "- Scoring impact: `NONE`",
            "",
            "## Classification Counts",
        ]
        for name, count in counts.most_common():
            lines.append(f"- {name}: `{count}`")
        lines += ["", "## Source Counts"]
        for name, count in source_counts.most_common():
            lines.append(f"- {name}: `{count}`")
        lines += ["", "## Manual Review / RP Only Sample"]
        for row in bridge:
            if row["classification"] in {"RP_ONLY", "MULTI_MATCH_AMBIGUOUS", "NEEDS_MANUAL_REVIEW"}:
                lines.append(f"- **{row['rp_horse_name']}** ({row['source_date']}): {row['classification']} - {row.get('blocker_reason')}")
                if len(lines) > 80:
                    break
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["output_path"] = str(OUT_PATH)
        payload["json_path"] = str(json_path)
        payload["md_path"] = str(md_path)
    else:
        payload["status"] = "DRY_RUN"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RP/Velo horse identity bridge.")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.start_date, args.end_date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
