#!/usr/bin/env python3
"""Verify that every daily artifact is describing the same race universe.

This is a hardening guard for the RP-only workflow. It does not scrape, score,
or mutate live tables. It compares local artifacts and fails if race IDs drift.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _race_id(value: Any) -> str:
    return str(value or "").strip()


def _race_ids_from_races(payload: Any) -> set[str]:
    if payload is None:
        return set()
    races = payload if isinstance(payload, list) else payload.get("races") or payload.get("racecards") or []
    return {_race_id(r.get("race_id")) for r in races if _race_id(r.get("race_id"))}


def _race_ids_from_old_velo(date: str) -> set[str]:
    ids: set[str] = set()
    for path in sorted((DATA / "racecard_merged").glob(f"racecard_*_{date}.json")):
        payload = _load_json(path) or {}
        races = payload.get("races", [])
        if isinstance(races, dict):
            races = races.values()
        for race in races:
            if not isinstance(race, dict):
                continue
            rid = _race_id(race.get("race_id"))
            if rid:
                ids.add(rid)
    return ids


def _race_ids_from_new_build(date_slug: str) -> set[str]:
    path = DATA / "new_build" / "reports" / f"two_lane_readiness_{date_slug}.json"
    payload = _load_json(path) or {}
    return {_race_id(r.get("race_id")) for r in payload.get("race_day_scorecards", []) if _race_id(r.get("race_id"))}


def _race_ids_from_results(date_slug: str) -> set[str]:
    payload = _load_json(DATA / "results" / f"rp_results_{date_slug}.json")
    if payload is None:
        return set()
    return {_race_id(r.get("race_id")) for r in payload.get("results", []) if _race_id(r.get("race_id"))}


def _compare(name: str, expected: set[str], actual: set[str]) -> dict[str, Any]:
    return {
        "name": name,
        "count": len(actual),
        "missing_from_actual": sorted(expected - actual),
        "extra_in_actual": sorted(actual - expected),
        "matches_expected": actual == expected,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify race-day artifact universe consistency")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--execute", action="store_true", help="Write report JSON/MD")
    args = ap.parse_args()

    date = args.date
    date_slug = date.replace("-", "_")

    injection_path = DATA / "racing_post_account_parsed" / f"live-full-racepages-{date}" / "racecard_injection.json"
    standard_path = DATA / f"racecards_{date_slug}_standard.json"

    sources = {
        "rp_injection": _race_ids_from_races(_load_json(injection_path)),
        "standard_cache": _race_ids_from_races(_load_json(standard_path)),
        "old_velo_rp_merged": _race_ids_from_old_velo(date),
        "new_build_readiness": _race_ids_from_new_build(date_slug),
        "rp_results": _race_ids_from_results(date_slug),
    }

    expected = sources["rp_injection"] or sources["standard_cache"]
    comparisons = [_compare(name, expected, ids) for name, ids in sources.items()]
    status = "PASS" if expected and all(c["matches_expected"] for c in comparisons if c["count"] > 0) else "FAIL"

    payload = {
        "date": date,
        "status": status,
        "expected_source": "rp_injection" if sources["rp_injection"] else "standard_cache",
        "expected_count": len(expected),
        "sources": {k: sorted(v) for k, v in sources.items()},
        "comparisons": comparisons,
        "rule": "All scoring/learning artifacts must match the RP injection race_id universe before use.",
    }

    if args.execute:
        out_json = DATA / "reports" / f"raceday_universe_check_{date_slug}.json"
        out_md = DATA / "reports" / f"raceday_universe_check_{date_slug}.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        lines = [
            f"# Raceday Universe Check — {date}",
            "",
            f"- Status: {status}",
            f"- Expected source: {payload['expected_source']}",
            f"- Expected races: {len(expected)}",
            "",
            "| Artifact | Count | Match | Missing | Extra |",
            "|---|---:|---|---:|---:|",
        ]
        for c in comparisons:
            lines.append(
                f"| {c['name']} | {c['count']} | {c['matches_expected']} | "
                f"{len(c['missing_from_actual'])} | {len(c['extra_in_actual'])} |"
            )
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Written: {out_json}")
        print(f"Written: {out_md}")

    print(json.dumps(payload, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
