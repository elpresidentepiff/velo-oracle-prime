"""
Build the VÉLØ Course Master.

Daily, paper-only course intelligence:
  - historical Sigma course excellence
  - Deep Race Agent course ROI/frame evidence
  - today's RP merged racecard courses

No Racing API. No scoring mutation. No staking authority.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(date: str) -> str:
    return date.replace("-", "_")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm_course(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


COURSE_ALIASES = {
    "wolverhampton": "wolverhamptonaw",
    "newmarketjuly": "newmarketjuly",
    "newmarket": "newmarket",
    "utt": "uttoxeter",
    "nby": "newbury",
}


def _course_key(value: Any) -> str:
    key = _norm_course(value)
    return COURSE_ALIASES.get(key, key)


def _sample_tier(n: int) -> str:
    if n >= 20:
        return "MEANINGFUL"
    if n >= 10:
        return "CAUTION"
    if n > 0:
        return "OBSERVATION_ONLY"
    return "NONE"


def _flatten_sigma_courses(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path, {})
    out: dict[str, dict[str, Any]] = {}
    for section in ("excelling", "doing_well", "baseline", "caution", "drain"):
        for row in payload.get(section) or []:
            course = row.get("course")
            if not course:
                continue
            out[_course_key(course)] = {
                "course": course,
                "source_section": section,
                "course_tier": row.get("course_tier") or section.upper(),
                "n": int(row.get("n") or 0),
                "wins": int(row.get("wins") or 0),
                "sr": row.get("sr"),
                "avg_vp": row.get("avg_vp"),
                "vp40_n": row.get("vp40_n"),
                "vp40_sr": row.get("vp40_sr"),
                "sample_tier": row.get("sample_tier") or _sample_tier(int(row.get("n") or 0)),
            }
    return out


def _flatten_deep_courses(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path, {})
    out: dict[str, dict[str, Any]] = {}
    for course, row in (payload.get("by_course") or {}).items():
        n = int(row.get("n") or 0)
        out[_course_key(course)] = {
            "course": course,
            "n": n,
            "wins": int(row.get("wins") or 0),
            "frames": int(row.get("frames") or 0),
            "sr": row.get("sr"),
            "frame_rate": row.get("frame_rate"),
            "profit": row.get("profit"),
            "roi": row.get("roi"),
            "identity_misses": int(row.get("identity_misses") or 0),
            "missing_results": int(row.get("missing_results") or 0),
            "sample_tier": _sample_tier(n),
        }
    return out


def _today_courses(date: str) -> dict[str, dict[str, Any]]:
    courses: dict[str, dict[str, Any]] = {}
    for path in (DATA_DIR / "racecard_merged").glob(f"*{date}*.json"):
        payload = _load_json(path, {})
        races = payload.get("races") if isinstance(payload, dict) else None
        if not isinstance(races, dict):
            continue
        venue = payload.get("venue")
        venue_code = payload.get("venue_code")
        race_count = len(races)
        course_name = None
        for race in races.values():
            if isinstance(race, dict) and race.get("course"):
                course_name = race.get("course")
                break
        course_name = course_name or venue
        key = _course_key(course_name)
        courses[key] = {
            "course": course_name,
            "venue": venue,
            "venue_code": venue_code,
            "race_count": race_count,
            "source_file": str(path),
        }
    return courses


def _master_decision(sigma: dict[str, Any] | None, deep: dict[str, Any] | None) -> dict[str, Any]:
    sigma = sigma or {}
    deep = deep or {}
    reasons: list[str] = []
    warnings: list[str] = []

    sigma_tier = str(sigma.get("course_tier") or "").upper()
    sigma_n = int(sigma.get("n") or 0)
    deep_n = int(deep.get("n") or 0)
    deep_roi = deep.get("roi")
    deep_frame = deep.get("frame_rate")
    deep_sr = deep.get("sr")

    score = 0
    if sigma_n >= 20 and sigma_tier in {"EXCELLING", "DOING_WELL"}:
        score += 2
        reasons.append(f"SIGMA_{sigma_tier}_N{sigma_n}")
    elif sigma_n >= 20 and sigma_tier in {"DRAIN", "CAUTION"}:
        score -= 2
        warnings.append(f"SIGMA_{sigma_tier}_N{sigma_n}")
    elif sigma_n >= 10 and sigma_tier in {"EXCELLING", "DOING_WELL"}:
        score += 1
        reasons.append(f"SIGMA_CAUTION_SAMPLE_{sigma_tier}_N{sigma_n}")

    if deep_n >= 8 and deep_roi is not None:
        if deep_roi >= 0.20:
            score += 2
            reasons.append(f"DEEP_POSITIVE_ROI_{deep_roi:.3f}_N{deep_n}")
        elif deep_roi >= 0.05:
            score += 1
            reasons.append(f"DEEP_MODEST_POSITIVE_ROI_{deep_roi:.3f}_N{deep_n}")
        elif deep_roi <= -0.25:
            score -= 2
            warnings.append(f"DEEP_DRAIN_ROI_{deep_roi:.3f}_N{deep_n}")
        elif deep_roi < 0:
            score -= 1
            warnings.append(f"DEEP_NEGATIVE_ROI_{deep_roi:.3f}_N{deep_n}")

    if deep_n >= 8 and deep_frame is not None and deep_frame >= 0.75:
        score += 1
        reasons.append(f"DEEP_FRAME_SUPPORT_{deep_frame:.3f}")
    if deep_n >= 8 and deep_sr is not None and deep_sr <= 0.20:
        score -= 1
        warnings.append(f"DEEP_LOW_STRIKE_{deep_sr:.3f}")

    if deep_n and deep.get("identity_misses", 0) > deep_n:
        warnings.append("IDENTITY_MISS_HEAVY_SAMPLE")

    if score >= 3:
        action = "COURSE_BOOST"
    elif score >= 1:
        action = "COURSE_SUPPORT"
    elif score <= -3:
        action = "COURSE_SUPPRESS"
    elif score <= -1:
        action = "COURSE_WARNING"
    else:
        action = "COURSE_NEUTRAL"

    confidence = "HIGH" if (sigma_n >= 20 or deep_n >= 20) else "MEDIUM" if (sigma_n >= 10 or deep_n >= 8) else "LOW"
    return {
        "action": action,
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "warnings": warnings,
    }


def build_course_master(date: str) -> dict[str, Any]:
    sigma = _flatten_sigma_courses(REPORT_DIR / "current_era_course_excellence_table.json")
    deep = _flatten_deep_courses(REPORT_DIR / "deep_race_agent_v1_eval_2026_06_01_to_2026_06_20_v2.json")
    today = _today_courses(date)
    all_keys = sorted(set(sigma) | set(deep) | set(today))

    courses = {}
    for key in all_keys:
        sigma_row = sigma.get(key)
        deep_row = deep.get(key)
        today_row = today.get(key)
        course_name = (
            (today_row or {}).get("course")
            or (deep_row or {}).get("course")
            or (sigma_row or {}).get("course")
            or key
        )
        decision = _master_decision(sigma_row, deep_row)
        courses[key] = {
            "course": course_name,
            "key": key,
            "master_action": decision["action"],
            "master_score": decision["score"],
            "master_confidence": decision["confidence"],
            "reasons": decision["reasons"],
            "warnings": decision["warnings"],
            "sigma": sigma_row or {"available": False},
            "deep_agent": deep_row or {"available": False},
            "today": today_row or {"available": False, "race_count": 0},
        }

    today_courses = {
        key: row for key, row in courses.items()
        if (row.get("today") or {}).get("race_count", 0) > 0
    }
    counts = Counter(row["master_action"] for row in today_courses.values())
    return {
        "generated_at": _utc_now(),
        "date": date,
        "status": "COURSE_MASTER_PAPER_ONLY",
        "racing_api_used": False,
        "ruleset": "COURSE_MASTER_V1_SIGMA_PLUS_DEEP_AGENT",
        "source_files": {
            "sigma_course_table": "data/reports/current_era_course_excellence_table.json",
            "deep_agent_eval": "data/reports/deep_race_agent_v1_eval_2026_06_01_to_2026_06_20_v2.json",
            "today_racecards": f"data/racecard_merged/*{date}*.json",
        },
        "summary": {
            "course_profiles": len(courses),
            "today_courses": len(today_courses),
            "today_race_count": sum((row.get("today") or {}).get("race_count", 0) for row in today_courses.values()),
            "today_action_counts": dict(counts),
        },
        "today_courses": today_courses,
        "courses": courses,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# VÉLØ Course Master",
        f"Generated: {report['generated_at']}",
        "",
        f"- Date: {report['date']}",
        f"- Status: `{report['status']}`",
        f"- Racing API used: `{report['racing_api_used']}`",
        f"- Ruleset: `{report['ruleset']}`",
        "",
        "## Today",
        f"- Courses: {report['summary']['today_courses']}",
        f"- Races: {report['summary']['today_race_count']}",
        f"- Action counts: {json.dumps(report['summary']['today_action_counts'], sort_keys=True)}",
        "",
        "| Course | Races | Action | Score | Confidence | Sigma | Deep ROI | Deep N | Warnings |",
        "|---|---:|---|---:|---|---|---:|---:|---|",
    ]
    for row in sorted(report["today_courses"].values(), key=lambda r: str(r.get("course"))):
        sigma = row.get("sigma") or {}
        deep = row.get("deep_agent") or {}
        deep_roi = deep.get("roi")
        lines.append(
            f"| {row['course']} | {row['today'].get('race_count', 0)} | {row['master_action']} | "
            f"{row['master_score']} | {row['master_confidence']} | "
            f"{sigma.get('course_tier', 'n/a')} n={sigma.get('n', 0)} | "
            f"{deep_roi if deep_roi is not None else 'n/a'} | {deep.get('n', 0)} | "
            f"{', '.join(row.get('warnings') or []) or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Law",
            "- Course Master is paper-only context.",
            "- It can boost confidence or warn/suppress a review, but it cannot change VP, model score, router, staking, or execution.",
            "- No course becomes a hard ban until sample size and forward evidence justify it.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    report = build_course_master(args.date)
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    md = _markdown(report)
    out_json = REPORT_DIR / f"course_master_{_slug(args.date)}.json"
    out_md = REPORT_DIR / f"course_master_{_slug(args.date)}.md"
    out_json.write_text(blob + "\n", encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    (REPORT_DIR / "course_master_latest.json").write_text(blob + "\n", encoding="utf-8")
    (REPORT_DIR / "course_master_latest.md").write_text(md, encoding="utf-8")

    print(f"COURSE_MASTER_COMPLETE date={args.date}")
    print(f"today_courses={report['summary']['today_courses']} races={report['summary']['today_race_count']}")
    print(f"actions={report['summary']['today_action_counts']}")
    print(f"json={out_json}")
    print(f"md={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
