"""
extract_local_draw_stats.py
Extracts stall draw statistics from existing captured Racing Post results HTML.
These are VERIFIED_LOCAL — no guessing, actual race data from our capture archive.

Usage:
    PYTHONPATH=. venv/bin/python scripts/ops/extract_local_draw_stats.py

Outputs:
    data/reports/local_draw_stats_raw.csv       — one row per race with draw data
    data/reports/local_draw_stats_by_course.csv — aggregated by course
    data/reports/local_draw_stats_summary.md    — operator brief

source_status: VERIFIED_LOCAL for all outputs.
REPORT_ONLY. No scoring changes. No Supabase writes.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "data" / "reports"
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"

# ── Patterns ──────────────────────────────────────────────────────────────────

_STALL_RE = re.compile(
    r"L\s*\[(?:Stalls?\s*)?([\d-]+)\]\s*(\d+)\s*\((\d+)%\)\s*"
    r"M\s*\[([\d-]+)\]\s*(\d+)\s*\((\d+)%\)\s*"
    r"H\s*\[([\d-]+)\]\s*(\d+)\s*\((\d+)%\)"
)

_COURSE_FROM_FNAME = re.compile(r"results_(\d+)_([a-z][a-z_]+)_(\d{4}_\d{2}_\d{2})_(\d+)")

_DIST_RE = re.compile(r"(?:class=[\"'][^\"']*distance[^\"']*[\"'][^>]*>|\"distance\"\s*:\s*\")([^<\"]{3,20})")
_GOING_RE = re.compile(r"\b(Firm|Good to Firm|Good|Good to Soft|Soft|Heavy|Standard|Slow|Fast)\b")
_FIELD_SIZE_RE = re.compile(r"(\d+)\s*runners?", re.I)


def _parse_file(path: Path) -> dict | None:
    html = path.read_text(encoding="utf-8", errors="replace")

    m = _STALL_RE.search(html)
    if not m:
        return None

    fn = path.stem
    cm = _COURSE_FROM_FNAME.search(fn)
    if not cm:
        return None

    course_id = cm.group(1)
    course_name = cm.group(2).replace("_", " ").title()
    date = cm.group(3).replace("_", "-")
    race_id = cm.group(4)

    # Distance
    dm = _DIST_RE.search(html)
    distance = dm.group(1).strip() if dm else ""

    # Going
    gm = _GOING_RE.search(html[html.find("Going") : html.find("Going") + 200] if "Going" in html else "")
    going = gm.group(1) if gm else ""

    # Field size
    fsm = _FIELD_SIZE_RE.search(html[:5000])
    field_size = int(fsm.group(1)) if fsm else 0

    low_wins = int(m.group(2))
    low_pct = int(m.group(3))
    mid_wins = int(m.group(5))
    mid_pct = int(m.group(6))
    high_wins = int(m.group(8))
    high_pct = int(m.group(9))

    total = low_wins + mid_wins + high_wins
    dominant = max(
        [("LOW", low_wins, low_pct), ("MID", mid_wins, mid_pct), ("HIGH", high_wins, high_pct)], key=lambda x: x[1]
    )

    return {
        "course_id": course_id,
        "course": course_name,
        "date": date,
        "race_id": race_id,
        "distance": distance,
        "going": going,
        "field_size": field_size,
        "low_range": m.group(1),
        "low_wins": low_wins,
        "low_pct": low_pct,
        "mid_range": m.group(4),
        "mid_wins": mid_wins,
        "mid_pct": mid_pct,
        "high_range": m.group(7),
        "high_wins": high_wins,
        "high_pct": high_pct,
        "dominant_zone": dominant[0],
        "dominant_wins": dominant[1],
        "dominant_pct": dominant[2],
        "total_wins_sample": total,
        "source_status": "VERIFIED_LOCAL",
        "source_file": path.name,
    }


def _aggregate_by_course(rows: list[dict]) -> list[dict]:
    by_course: dict[str, dict] = defaultdict(
        lambda: {
            "course_id": "",
            "course": "",
            "n_races": 0,
            "low_wins_total": 0,
            "mid_wins_total": 0,
            "high_wins_total": 0,
        }
    )

    for r in rows:
        key = r["course_id"]
        agg = by_course[key]
        agg["course_id"] = r["course_id"]
        agg["course"] = r["course"]
        agg["n_races"] += 1
        agg["low_wins_total"] += r["low_wins"]
        agg["mid_wins_total"] += r["mid_wins"]
        agg["high_wins_total"] += r["high_wins"]

    result = []
    for agg in sorted(by_course.values(), key=lambda x: -x["n_races"]):
        total = agg["low_wins_total"] + agg["mid_wins_total"] + agg["high_wins_total"]
        if total == 0:
            continue
        low_share = round(agg["low_wins_total"] / total * 100, 1)
        mid_share = round(agg["mid_wins_total"] / total * 100, 1)
        high_share = round(agg["high_wins_total"] / total * 100, 1)
        dominant = max([("LOW", low_share), ("MID", mid_share), ("HIGH", high_share)], key=lambda x: x[1])
        tier = "MEANINGFUL" if agg["n_races"] >= 20 else "CAUTION" if agg["n_races"] >= 5 else "OBSERVATION_ONLY"
        result.append(
            {
                "course_id": agg["course_id"],
                "course": agg["course"],
                "n_races": agg["n_races"],
                "low_win_pct": low_share,
                "mid_win_pct": mid_share,
                "high_win_pct": high_share,
                "dominant_zone": dominant[0],
                "dominant_zone_pct": dominant[1],
                "draw_bias_verdict": f"{dominant[0]}_FAVOURED" if dominant[1] >= 40 else "MIXED",
                "tier": tier,
                "source_status": "VERIFIED_LOCAL",
            }
        )
    return result


def _write_summary(rows: list[dict], agg: list[dict]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Local Draw Statistics — Extracted from Captured RP Results HTML",
        f"Generated: {now}",
        "source_status: VERIFIED_LOCAL",
        "Status: REPORT_ONLY",
        "",
        f"  Total races with draw data: {len(rows)}",
        f"  Unique courses:             {len(agg)}",
        "",
        "## Draw Bias By Course (aggregated)",
        "",
        f"  {'Course':<30} {'N':<5} {'LOW%':<7} {'MID%':<7} {'HIGH%':<7} {'Dominant':<14} {'Tier'}",
        f"  {'-' * 30} {'-' * 5} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 14} {'-' * 12}",
    ]
    for a in sorted(agg, key=lambda x: -x["n_races"]):
        lines.append(
            f"  {a['course']:<30} "
            f"{a['n_races']:<5} "
            f"{a['low_win_pct']:<7} "
            f"{a['mid_win_pct']:<7} "
            f"{a['high_win_pct']:<7} "
            f"{a['draw_bias_verdict']:<14} "
            f"{a['tier']}"
        )
    lines += [
        "",
        "## Note on Sample Size",
        "",
        "  Courses with n>=20 races: MEANINGFUL (usable for COURSE-01)",
        "  Courses with n=5-19:       CAUTION (directional only)",
        "  Courses with n<5:          OBSERVATION_ONLY (supplement with RP statistics tab)",
        "",
        "  To increase sample size: run collector on more result pages.",
        "  All data from: data/racing_post_account_raw/rp-results-*/",
        "",
        "## Hard Constraints",
        "  REPORT_ONLY | NO_SUPABASE_WRITES | NO_TELEGRAM_SEND | NO_SCORING_CHANGE",
    ]
    return "\n".join(lines)


def main() -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"── extract_local_draw_stats — {now} ──")

    html_files = sorted(RAW_ROOT.glob("rp-results-*/*.html"))
    print(f"  Results HTML files: {len(html_files)}")

    rows: list[dict] = []
    for f in html_files:
        r = _parse_file(f)
        if r:
            rows.append(r)

    print(f"  Races with draw data: {len(rows)}")

    agg = _aggregate_by_course(rows)
    print(f"  Unique courses: {len(agg)}")

    REPORTS.mkdir(parents=True, exist_ok=True)

    # Raw CSV
    raw_path = REPORTS / "local_draw_stats_raw.csv"
    if rows:
        with open(raw_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"  OK   {raw_path.relative_to(ROOT)} ({len(rows)} rows)")

    # Aggregated CSV
    agg_path = REPORTS / "local_draw_stats_by_course.csv"
    if agg:
        with open(agg_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
            writer.writeheader()
            writer.writerows(agg)
    print(f"  OK   {agg_path.relative_to(ROOT)} ({len(agg)} courses)")

    # Summary
    summary = _write_summary(rows, agg)
    sum_path = REPORTS / "local_draw_stats_summary.md"
    sum_path.write_text(summary)
    print(f"  OK   {sum_path.relative_to(ROOT)}")

    print()
    # Show meaningful courses
    meaningful = [a for a in agg if a["tier"] == "MEANINGFUL"]
    caution = [a for a in agg if a["tier"] == "CAUTION"]
    print(f"  MEANINGFUL (n>=20): {len(meaningful)}")
    print(f"  CAUTION (n=5-19):   {len(caution)}")
    for a in agg:
        bias = a["draw_bias_verdict"]
        print(f"    {a['course']:<28} n={a['n_races']:<4} {bias}  ({a['dominant_zone']} {a['dominant_zone_pct']}%)")
    print()
    print("── DONE ──")


if __name__ == "__main__":
    main()
