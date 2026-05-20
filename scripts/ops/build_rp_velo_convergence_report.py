from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"

VP30_THRESHOLD = 0.30
MDS_HIGH_THRESHOLD = 0.25
IMPROVEMENT_HIGH_THRESHOLD = 0.20

VENUE_NAME_MAP = {
    "CLO": "Clonmel",
    "FON": "Fontwell",
    "PER": "Perth",
    "SAL": "Salisbury",
    "YOR": "York",
}


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    cleaned = name.upper().replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_course(name: str | None) -> str:
    return normalize_name((name or "").split("(")[0])


def normalize_time(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().replace(".", ":")
    if re.fullmatch(r"\d:\d{2}", text):
        return text
    if re.fullmatch(r"\d{2}:\d{2}", text):
        return text.lstrip("0")
    return text


def rank_map(horses: list[dict[str, Any]], field: str) -> dict[str, int]:
    scored: list[tuple[str, float]] = []
    for horse in horses:
        val = horse.get(field)
        if val in (None, "", "-"):
            continue
        try:
            scored.append((normalize_name(horse.get("horse_name")), float(val)))
        except (TypeError, ValueError):
            continue
    scored.sort(key=lambda item: item[1], reverse=True)
    return {name: idx + 1 for idx, (name, _) in enumerate(scored)}


def parse_cashrun_markdown(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not path.exists():
        return rows

    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            if current:
                key = (
                    normalize_course(current.get("course")),
                    normalize_time(current.get("off_time")),
                    normalize_name(current.get("horse")),
                )
                rows[key] = current
            current = {"horse": None, "course": None, "off_time": None, "cashrun_class": None, "cashrun_score": None}
            title = line[4:]
            match = re.match(r"(.+?) - (.+?) (\d{1,2}\.\d{2})$", title)
            if match:
                current["horse"] = match.group(1).strip()
                current["course"] = match.group(2).strip()
                current["off_time"] = normalize_time(match.group(3))
            continue
        if not current:
            continue
        if line.startswith("- Cashrun class:"):
            current["cashrun_class"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Cashrun score:"):
            try:
                current["cashrun_score"] = float(line.split(":", 1)[1].strip())
            except ValueError:
                current["cashrun_score"] = None
        elif line.startswith("- Spotlight evidence:"):
            current["spotlight_evidence"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Postdata evidence:"):
            current["postdata_evidence"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Negative evidence:"):
            current["negative_evidence"] = line.split(":", 1)[1].strip()
    if current:
        key = (
            normalize_course(current.get("course")),
            normalize_time(current.get("off_time")),
            normalize_name(current.get("horse")),
        )
        rows[key] = current
    return rows


def course_name_from_payload(path: Path, payload: dict[str, Any]) -> str:
    venue = (payload.get("venue") or "").strip().upper()
    if venue:
        return VENUE_NAME_MAP.get(venue, venue)

    stem = path.stem
    match = re.match(r"racecard_(.+)_\d{4}-\d{2}-\d{2}$", stem)
    if match:
        token = match.group(1).replace("_", " ").strip()
        return VENUE_NAME_MAP.get(token.upper(), token)
    return stem.replace("racecard_", "").replace("_", " ")


@dataclass
class RaceContext:
    course: str
    off_time: str
    race_name: str
    postdata_pick: str
    topspeed_pick: str
    spotlight_verdict: str
    horses: list[dict[str, Any]]
    or_ranks: dict[str, int]
    ts_ranks: dict[str, int]
    rpr_ranks: dict[str, int]


def resolve_mapping_status(
    rp_horse: dict[str, Any] | None,
    spotlight_support: bool,
    postdata_support: bool,
    topspeed_support: bool,
) -> str:
    if (rp_horse or {}).get("horse_id"):
        return "MATCHED_ID"
    if rp_horse:
        return "MATCHED_NAME"
    if spotlight_support or postdata_support or topspeed_support:
        return "FUZZY_MATCHED"
    return "UNMAPPED"


def build_rp_map(date_str: str) -> dict[tuple[str, str], RaceContext]:
    mapping: dict[tuple[str, str], RaceContext] = {}
    for path in sorted((DATA_DIR / "racecard_merged").glob(f"racecard_*_{date_str}.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        course = course_name_from_payload(path, payload)
        for race_time, race in (payload.get("races") or {}).items():
            horses = race.get("horses") or []
            mapping[(normalize_course(course), normalize_time(race_time))] = RaceContext(
                course=course,
                off_time=normalize_time(race_time),
                race_name=race.get("race_name") or "",
                postdata_pick=normalize_name(race.get("postdata_pick")),
                topspeed_pick=normalize_name(race.get("topspeed_pick")),
                spotlight_verdict=race.get("spotlight_verdict") or "",
                horses=horses,
                or_ranks=rank_map(horses, "current_or"),
                ts_ranks=rank_map(horses, "ts_master"),
                rpr_ranks=rank_map(horses, "rpr_master"),
            )
    return mapping


def build_row(verdict: dict[str, Any], rp_map: dict[tuple[str, str], RaceContext], cashrun_map: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    top = verdict.get("top") or {}
    course = verdict.get("course") or ""
    off_time = normalize_time(verdict.get("off_time"))
    horse = top.get("horse") or ""
    norm_course = normalize_course(course)
    norm_horse = normalize_name(horse)
    race_ctx = rp_map.get((norm_course, off_time))
    cashrun = cashrun_map.get((norm_course, off_time, norm_horse))

    vp = float(top.get("velo_prime_prob") or 0.0)
    mds = float(top.get("market_deception_score") or 0.0)
    improvement = float(top.get("improvement_score") or 0.0)
    vp30_flag = vp >= VP30_THRESHOLD
    mds_high_flag = mds >= MDS_HIGH_THRESHOLD
    improvement_high_flag = improvement >= IMPROVEMENT_HIGH_THRESHOLD

    row: dict[str, Any] = {
        "course": course,
        "off_time": off_time,
        "race_id": verdict.get("race_id"),
        "race_name": verdict.get("race_name") or "",
        "velo_top_pick": horse,
        "horse_id": top.get("horse_id"),
        "vp_probability": vp,
        "decision_tier": verdict.get("tier"),
        "vp30_flag": vp30_flag,
        "mds_high_flag": mds_high_flag,
        "improvement_high_flag": improvement_high_flag,
        "cashrun_status": cashrun.get("cashrun_class") if cashrun else None,
        "cashrun_score": cashrun.get("cashrun_score") if cashrun else None,
        "mapped_rp_race": bool(race_ctx),
    }

    if not race_ctx:
        row["classification"] = "INSUFFICIENT_RP_DATA"
        row["rp_support_count"] = 0
        row["rp_conflict"] = []
        row["high_convergence_horses"] = []
        row["velo_only_value_horses"] = [horse] if (vp30_flag or mds_high_flag or improvement_high_flag) else []
        row["rp_only_warning_horses"] = []
        return row

    rp_horse = None
    for candidate in race_ctx.horses:
        if normalize_name(candidate.get("horse_name")) == norm_horse:
            rp_horse = candidate
            break

    spotlight_support = norm_horse and norm_horse in normalize_name(race_ctx.spotlight_verdict)
    postdata_support = race_ctx.postdata_pick == norm_horse if race_ctx.postdata_pick else False
    topspeed_support = race_ctx.topspeed_pick == norm_horse if race_ctx.topspeed_pick else False
    or_rank = race_ctx.or_ranks.get(norm_horse)
    ts_rank = race_ctx.ts_ranks.get(norm_horse)
    rpr_rank = race_ctx.rpr_ranks.get(norm_horse)

    top_rank_support = any(rank is not None and rank <= 3 for rank in [or_rank, ts_rank, rpr_rank])
    cashrun_watch = (cashrun or {}).get("cashrun_class") == "CASHRUN_WATCH"

    support_signals = {
        "spotlight_support": spotlight_support,
        "postdata_support": postdata_support,
        "topspeed_support": topspeed_support,
        "top_rank_support": top_rank_support,
        "cashrun_watch": cashrun_watch,
    }
    rp_support_count = sum(1 for value in support_signals.values() if value)

    warning_horses: list[str] = []
    if race_ctx.postdata_pick and race_ctx.postdata_pick != norm_horse:
        warning_horses.append(race_ctx.postdata_pick.title())
    if race_ctx.topspeed_pick and race_ctx.topspeed_pick != norm_horse and race_ctx.topspeed_pick.title() not in warning_horses:
        warning_horses.append(race_ctx.topspeed_pick.title())
    if race_ctx.spotlight_verdict:
        for candidate in race_ctx.horses:
            candidate_name = candidate.get("horse_name") or ""
            norm_candidate = normalize_name(candidate_name)
            if norm_candidate and norm_candidate != norm_horse and norm_candidate in normalize_name(race_ctx.spotlight_verdict):
                if candidate_name not in warning_horses:
                    warning_horses.append(candidate_name)

    mapping_status = resolve_mapping_status(rp_horse, spotlight_support, postdata_support, topspeed_support)

    if rp_support_count >= 2 and (vp30_flag or verdict.get("tier") == "A") and mapping_status != "UNMAPPED":
        classification = "HIGH_CONVERGENCE"
    elif cashrun_watch:
        classification = "CASHRUN_WATCH"
    elif rp_support_count >= 2 and not vp30_flag and verdict.get("tier") not in {"A", "B"} and mapping_status != "UNMAPPED":
        classification = "RP_SUPPORTS_BUT_VELO_WEAK"
    elif (vp30_flag or mds_high_flag or improvement_high_flag) and rp_support_count == 0:
        classification = "VELO_VALUE_RP_SILENT"
    elif warning_horses:
        classification = "CONFLICT"
    else:
        classification = "INSUFFICIENT_RP_DATA"

    high_convergence_horses = []
    if rp_support_count >= 2:
        high_convergence_horses.append(horse)

    velo_only_value = [horse] if classification == "VELO_VALUE_RP_SILENT" else []

    row.update({
        "rp_race_name": race_ctx.race_name,
        "spotlight_support": spotlight_support,
        "postdata_support": postdata_support,
        "topspeed_support": topspeed_support,
        "or_rank": or_rank,
        "ts_rank": ts_rank,
        "rpr_rank": rpr_rank,
        "rp_support_count": rp_support_count,
        "rp_support_signals": support_signals,
        "rp_conflict": warning_horses,
        "high_convergence_horses": high_convergence_horses,
        "velo_only_value_horses": velo_only_value,
        "rp_only_warning_horses": warning_horses,
        "rp_velo_agreement": rp_support_count >= 2,
        "rp_velo_conflict": bool(warning_horses),
        "classification": classification,
        "mapped_runner": bool(rp_horse),
        "mapping_status": mapping_status,
    })
    return row


def build_summary(rows: list[dict[str, Any]], rp_map: dict[tuple[str, str], RaceContext]) -> dict[str, Any]:
    mapped = [row for row in rows if row.get("mapped_rp_race")]
    unmapped = [row for row in rows if not row.get("mapped_rp_race")]
    mapping_status_counts = {
        "MATCHED_ID": sum(1 for row in rows if row.get("mapping_status") == "MATCHED_ID"),
        "MATCHED_NAME": sum(1 for row in rows if row.get("mapping_status") == "MATCHED_NAME"),
        "FUZZY_MATCHED": sum(1 for row in rows if row.get("mapping_status") == "FUZZY_MATCHED"),
        "UNMAPPED": sum(1 for row in rows if row.get("mapping_status") == "UNMAPPED"),
    }
    rp_supported = [row for row in rows if row.get("rp_support_count", 0) > 0]
    cashrun_supported = [row for row in rows if row.get("cashrun_status") in {"CASHRUN_READY", "CASHRUN_WATCH"}]
    conflicts = [row for row in rows if row.get("classification") == "CONFLICT"]
    high_conv = [row for row in rows if row.get("classification") == "HIGH_CONVERGENCE"]

    watchlist = sorted(
        rows,
        key=lambda row: (
            {"HIGH_CONVERGENCE": 5, "CASHRUN_WATCH": 4, "VELO_VALUE_RP_SILENT": 3, "RP_SUPPORTS_BUT_VELO_WEAK": 2, "CONFLICT": 1, "INSUFFICIENT_RP_DATA": 0}.get(row.get("classification"), 0),
            row.get("cashrun_score") or 0,
            row.get("rp_support_count") or 0,
            row.get("vp_probability") or 0,
        ),
        reverse=True,
    )[:10]

    return {
        "total_velo_races": len(rows),
        "total_rp_covered_races": len(rp_map),
        "mapped_races": len(mapped),
        "unmapped_races": len(unmapped),
        "mapped_runners": sum(1 for row in rows if row.get("mapped_runner")),
        "mapping_status_counts": mapping_status_counts,
        "velo_picks_with_rp_support": len(rp_supported),
        "velo_picks_with_cashrun_support": len(cashrun_supported),
        "velo_picks_with_rp_conflict": len(conflicts),
        "high_convergence_picks": len(high_conv),
        "top_operator_watchlist": watchlist,
    }


def write_markdown(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# RP / VELO Convergence Report - 2026-05-14",
        "",
        "## Summary",
        "",
        f"- Total VELO races: `{summary['total_velo_races']}`",
        f"- Total RP-covered races: `{summary['total_rp_covered_races']}`",
        f"- Mapped races: `{summary['mapped_races']}`",
        f"- Unmapped races: `{summary['unmapped_races']}`",
        f"- Mapped runners: `{summary['mapped_runners']}`",
        f"- Mapping status counts: `MATCHED_ID={summary['mapping_status_counts']['MATCHED_ID']}` `MATCHED_NAME={summary['mapping_status_counts']['MATCHED_NAME']}` `FUZZY_MATCHED={summary['mapping_status_counts']['FUZZY_MATCHED']}` `UNMAPPED={summary['mapping_status_counts']['UNMAPPED']}`",
        f"- VELO picks with RP support: `{summary['velo_picks_with_rp_support']}`",
        f"- VELO picks with CASHRUN support: `{summary['velo_picks_with_cashrun_support']}`",
        f"- VELO picks with RP conflict: `{summary['velo_picks_with_rp_conflict']}`",
        f"- High-convergence picks: `{summary['high_convergence_picks']}`",
        "",
        "## Top 10 Operator Watchlist",
        "",
    ]
    for row in summary["top_operator_watchlist"]:
        lines.append(
            f"- {row['course']} {row['off_time']} - {row['velo_top_pick']} - `{row['classification']}` - `{row.get('mapping_status')}` - VP `{row['vp_probability']:.4f}`"
        )

    lines.extend([
        "",
        "## Race Table",
        "",
        "| Course | Time | VELO pick | Map | Tier | VP | VP30 | MDS | IMP | CASHRUN | RP support | Conflict | Class |",
        "|---|---|---|---|---|---:|---|---|---|---|---:|---|---|",
    ])
    for row in rows:
        lines.append(
            f"| {row['course']} | {row['off_time']} | {row['velo_top_pick']} | `{row.get('mapping_status')}` | {row.get('decision_tier') or ''} | {row.get('vp_probability', 0):.4f} | `{row.get('vp30_flag')}` | `{row.get('mds_high_flag')}` | `{row.get('improvement_high_flag')}` | `{row.get('cashrun_status') or ''}` | {row.get('rp_support_count', 0)} | {', '.join(row.get('rp_conflict') or [])} | `{row.get('classification')}` |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RP/VÉLØ convergence report.")
    parser.add_argument("--date", default="2026-05-14")
    args = parser.parse_args()

    date_us = args.date.replace("-", "_")
    verdict_path = DATA_DIR / f"velo_prime_verdicts_{date_us}.json"
    cashrun_path = DATA_DIR / f"cashrun_report_{date_us}.md"

    verdicts = json.loads(verdict_path.read_text(encoding="utf-8"))
    rp_map = build_rp_map(args.date)
    cashrun_map = parse_cashrun_markdown(cashrun_path)

    rows = [build_row(verdict, rp_map, cashrun_map) for verdict in verdicts]
    summary = build_summary(rows, rp_map)

    payload = {"date": args.date, "summary": summary, "races": rows}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"rp_velo_convergence_{args.date}.json"
    md_path = REPORT_DIR / f"rp_velo_convergence_{args.date}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(md_path, rows, summary)

    print(json.dumps({"json": str(json_path), "md": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
