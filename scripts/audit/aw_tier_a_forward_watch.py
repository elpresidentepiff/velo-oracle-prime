"""
AW Tier A forward-watch report.

Tracks the doctrine-miner candidate pattern:
    sidecar_tier=A | course_type=AW

This is shadow/operator evidence only. It does not create a router lane, alter
scoring, send Telegram, stake, or write live tables.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
REPORT_DIR = DATA / "sigma_memory"
PATTERN = "sidecar_tier=A|course_type=AW"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def date_token(date_str: str) -> str:
    return date_str.replace("-", "_")


def norm_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\([a-z]{2,3}\)", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def is_aw_course(course: Any) -> bool:
    text = str(course or "").lower()
    return "(aw)" in text or " aw" in text or "all-weather" in text


def parse_position(value: Any) -> int | None:
    match = re.match(r"^(\d+)", str(value or "").strip())
    return int(match.group(1)) if match else None


def index_results(date_str: str) -> dict[tuple[str, str], dict[str, Any]]:
    payload = load_json(DATA / f"results_{date_token(date_str)}.json", {})
    races = payload.get("results", []) if isinstance(payload, dict) else payload
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(races, list):
        return out
    for race in races:
        course = norm_name(race.get("course"))
        off = str(race.get("off") or race.get("off_time") or "").replace(":", ".")
        for runner in race.get("runners", []) or []:
            out[(course, norm_name(runner.get("horse")))] = {
                "off": off,
                "position": parse_position(runner.get("position")),
                "sp_dec": runner.get("sp_dec") or runner.get("sp"),
            }
    return out


def build_watch_report(date_str: str) -> dict[str, Any]:
    verdicts = load_json(DATA / f"velo_prime_verdicts_{date_token(date_str)}.json", [])
    if isinstance(verdicts, dict):
        verdicts = verdicts.get("verdicts", [])
    if not isinstance(verdicts, list):
        verdicts = []

    result_index = index_results(date_str)
    rows: list[dict[str, Any]] = []
    for verdict in verdicts:
        top = verdict.get("top") if isinstance(verdict.get("top"), dict) else {}
        course = verdict.get("course") or top.get("course")
        tier = str(verdict.get("tier") or top.get("decision_tier") or "").upper()
        if tier != "A" or not is_aw_course(course):
            continue

        result = result_index.get((norm_name(course), norm_name(top.get("horse"))))
        pos = result.get("position") if result else None
        outcome = "WIN" if pos == 1 else "FRAME" if pos and pos <= 3 else "MISS" if result else "PENDING_RESULT"
        rows.append(
            {
                "date": date_str,
                "race_id": verdict.get("race_id"),
                "course": course,
                "off_time": verdict.get("off_time"),
                "race_name": verdict.get("race_name"),
                "horse": top.get("horse"),
                "horse_id": top.get("horse_id"),
                "tier": tier,
                "velo_prime_prob": top.get("velo_prime_prob"),
                "place_prob": top.get("place_prob"),
                "market_deception_score": top.get("market_deception_score"),
                "improvement_score": top.get("improvement_score"),
                "pattern": PATTERN,
                "candidate_only": True,
                "live_velo_impact": False,
                "promotion_status": "NOT_PROMOTED",
                "watch_status": "PENDING_FORWARD_RESULT" if outcome == "PENDING_RESULT" else "CLOSED_FORWARD_SAMPLE",
                "result_position": pos,
                "outcome": outcome,
                "sp_dec": result.get("sp_dec") if result else None,
            }
        )

    outcome_counts = Counter(row["outcome"] for row in rows)
    return {
        "schema_version": "aw_tier_a_forward_watch_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_str,
        "pattern": PATTERN,
        "candidate_only": True,
        "shadow_only": True,
        "live_velo_impact": False,
        "rpr_policy": "RPR_NOT_INCLUDED",
        "promotion_status": "NOT_PROMOTED",
        "watch_rows": rows,
        "watch_count": len(rows),
        "outcome_counts": dict(outcome_counts),
        "classification": "AW_TIER_A_FORWARD_WATCH_READY",
    }


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# AW Tier A Forward Watch",
        "",
        f"Date: {report['date']}",
        f"Pattern: `{report['pattern']}`",
        f"Classification: `{report['classification']}`",
        f"Promotion status: `{report['promotion_status']}`",
        f"Candidate only: `{report['candidate_only']}`",
        f"Live VÉLØ impact: `{report['live_velo_impact']}`",
        f"RPR policy: `{report['rpr_policy']}`",
        "",
        f"Qualifying rows: {report['watch_count']}",
        f"Outcome counts: {report['outcome_counts']}",
        "",
        "## Qualifiers",
        "",
    ]
    if not report["watch_rows"]:
        lines.append("No AW Tier A qualifiers for this date.")
    for row in report["watch_rows"]:
        lines.append(
            f"- {row['off_time']} {row['course']} — **{row['horse']}** "
            f"VP={row['velo_prime_prob']} Place={row['place_prob']} "
            f"MDS={row['market_deception_score']} IMP={row['improvement_score']} "
            f"Outcome={row['outcome']}"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Shadow/operator evidence only.",
            "- No router lane created.",
            "- No scoring, staking, Telegram, or live table writes.",
            "- Requires forward validation before any doctrine promotion.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AW Tier A forward-watch report")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    report = build_watch_report(args.date)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tag = date_token(args.date)
    json_path = REPORT_DIR / f"aw_tier_a_forward_watch_{tag}.json"
    md_path = REPORT_DIR / f"aw_tier_a_forward_watch_{tag}.md"
    latest_json = REPORT_DIR / "aw_tier_a_forward_watch_latest.json"
    latest_md = REPORT_DIR / "aw_tier_a_forward_watch_latest.md"
    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    md_text = render_md(report)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    print(f"AW_TIER_A_FORWARD_WATCH_READY {args.date} rows={report['watch_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
