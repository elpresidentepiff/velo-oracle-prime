#!/usr/bin/env python
"""Build league tables from stored Racing Post industry selections.

Reads data/industry_selections_YYYYMMDD.json, reconciles against stored
data/results_YYYY_MM_DD.json, and writes week/month/all-time tipster tables.
This is read-only with respect to Velo scoring: no live writes, no Telegram.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"

DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}

COURSE_ALIASES = {
    "Ain": "Aintree",
    "AIN": "Aintree",
    "CLO": "Clonmel",
    "HAM": "Hamilton",
    "NBY": "Newbury",
    "RIP": "Ripon",
    "THI": "Thirsk",
    "YOR": "York",
    "Chelmsford City (AW)": "Chelmsford (AW)",
    "Chelmsford (AW)": "Chelmsford (AW)",
    "Kempton (AW)": "Kempton (AW)",
    "Lingfield (AW)": "Lingfield",
    "Lingfield": "Lingfield",
    "Southwell (AW)": "Southwell (AW)",
    "Wolverhampton (AW)": "Wolverhampton",
    "Wolverhampton": "Wolverhampton",
}


def normalize_name(name: Any) -> str:
    text = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", str(name or ""))
    text = text.strip().upper()
    text = text.replace("'", "")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_time(value: Any) -> str:
    text = str(value or "").strip().replace(".", ":")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text[:5])
    if not match:
        return text[:5]
    hour = int(match.group(1))
    minutes = match.group(2)
    if hour > 12:
        hour -= 12
    return f"{hour}:{minutes}"


def normalize_course(name: Any) -> str:
    course = str(name or "").strip()
    course = re.sub(r"\s*\((IRE|GB|FR)\)\s*$", "", course, flags=re.I)
    if course in COURSE_ALIASES:
        return COURSE_ALIASES[course]
    lower_alias = {k.lower(): v for k, v in COURSE_ALIASES.items()}
    if course.lower() in lower_alias:
        return lower_alias[course.lower()]
    return course.title()


def canonical_tipster(name: Any) -> str:
    text = re.sub(r"\s+", " ", str(name or "").strip())
    upper = text.upper()
    if upper.startswith("RP RATINGS"):
        return "RP RATINGS"
    if upper == "PEARSON)":
        return "UNKNOWN (PEARSON)"
    return upper


def date_from_selection_path(path: Path) -> date:
    match = re.search(r"industry_selections_(\d{8})\.json$", path.name)
    if not match:
        raise ValueError(f"Cannot parse date from {path}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def result_code(position: Any, *, is_nr: bool = False) -> str:
    if is_nr:
        return "NR"
    if position is None:
        return "M"
    text = str(position).strip().upper()
    if text in DNF_POSITIONS:
        return "NR"
    try:
        parsed = int(text)
    except ValueError:
        return "NR"
    if parsed == 1:
        return "W"
    if parsed <= 3:
        return "P"
    return "M"


def load_results_index(day: date) -> tuple[dict[tuple[str, str], dict[str, Any]], str | None]:
    candidates = [
        DATA_DIR / f"results_{day:%Y_%m_%d}.json",
        DATA_DIR / f"results_{day:%Y-%m-%d}.json",
        DATA_DIR / "results" / f"rp_results_{day:%Y_%m_%d}.json",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return {}, None

    raw = json.loads(path.read_text(encoding="utf-8"))
    races = raw.get("results", raw) if isinstance(raw, dict) else raw
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for race in races:
        course = normalize_course(race.get("course"))
        off_time = normalize_time(race.get("off") or race.get("off_time"))
        if course and off_time:
            index[(course, off_time)] = race
    return index, str(path.relative_to(ROOT))


def pick_result(horse: str, race: dict[str, Any] | None) -> tuple[str, str | None, str | None]:
    if race is None:
        return "UNMATCHED", None, None

    norm = normalize_name(horse)
    for runner in race.get("runners", []):
        runner_horse = runner.get("horse") if isinstance(runner, dict) else runner
        if normalize_name(runner_horse) == norm:
            position = str(runner.get("position", "")).strip().upper() if isinstance(runner, dict) else ""
            return result_code(position), position, str(runner_horse)

    for runner in race.get("non_runners", []) or []:
        runner_horse = runner.get("horse") if isinstance(runner, dict) else runner
        if normalize_name(runner_horse) == norm:
            return "NR", "NR", str(runner_horse)

    return "M", None, None


@dataclass(frozen=True)
class PickRow:
    date: str
    course: str
    off_time: str
    tipster: str
    tipster_raw: str
    horse: str
    is_nap: bool
    result: str
    position: str | None
    matched_horse: str | None
    matched_race: bool
    result_source: str | None
    selection_source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "course": self.course,
            "off_time": self.off_time,
            "tipster": self.tipster,
            "tipster_raw": self.tipster_raw,
            "horse": self.horse,
            "is_nap": self.is_nap,
            "result": self.result,
            "position": self.position,
            "matched_horse": self.matched_horse,
            "matched_race": self.matched_race,
            "result_source": self.result_source,
            "selection_source": self.selection_source,
        }


def iter_selection_rows(path: Path) -> tuple[list[PickRow], dict[str, Any]]:
    day = date_from_selection_path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    results, result_source = load_results_index(day)
    rows: list[PickRow] = []
    unmatched_races = 0

    for venue in payload.get("venues", []):
        course = normalize_course(venue.get("course"))
        tipsters = venue.get("tipsters") or {}
        for tipster_raw, time_map in tipsters.items():
            if not isinstance(time_map, dict):
                continue
            tipster = canonical_tipster(tipster_raw)
            for raw_time, pick in time_map.items():
                if not isinstance(pick, dict):
                    continue
                horse = str(pick.get("horse") or "").strip()
                if not horse:
                    continue
                off_time = normalize_time(raw_time)
                race = results.get((course, off_time))
                if race is None:
                    unmatched_races += 1
                code, position, matched_horse = pick_result(horse, race)
                rows.append(
                    PickRow(
                        date=f"{day:%Y-%m-%d}",
                        course=course,
                        off_time=off_time,
                        tipster=tipster,
                        tipster_raw=str(tipster_raw),
                        horse=horse,
                        is_nap=bool(pick.get("is_nap")),
                        result=code,
                        position=position,
                        matched_horse=matched_horse,
                        matched_race=race is not None,
                        result_source=result_source,
                        selection_source="industry_selections_file",
                    )
                )

    meta = {
        "date": f"{day:%Y-%m-%d}",
        "selection_file": str(path.relative_to(ROOT)),
        "result_source": result_source,
        "picks": len(rows),
        "result_races": len(results),
        "unmatched_pick_races": unmatched_races,
        "source": "industry_selections_file",
    }
    return rows, meta


def date_from_injection_path(path: Path) -> date | None:
    parts = list(path.parts)
    candidates = [part for part in parts if re.fullmatch(r"\d{4}-\d{2}-\d{2}", part)]
    if candidates:
        return datetime.strptime(candidates[-1], "%Y-%m-%d").date()
    match = re.search(r"(\d{4}[_-]\d{2}[_-]\d{2})", str(path))
    if match:
        return datetime.strptime(match.group(1).replace("_", "-"), "%Y-%m-%d").date()
    return None


def injection_score(path: Path) -> tuple[int, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (0, 0)
    races = payload.get("races") or []
    tips = sum(len(race.get("top_newspaper_tips") or []) for race in races)
    return (len(races), tips)


def injection_files_by_date() -> dict[date, list[Path]]:
    candidates: dict[date, list[Path]] = defaultdict(list)
    for path in (DATA_DIR / "racing_post_account_parsed").rglob("racecard_injection.json"):
        day = date_from_injection_path(path)
        if day is None:
            continue
        score = injection_score(path)
        if score == (0, 0):
            continue
        candidates[day].append(path)
    return dict(candidates)


def iter_injection_rows(path: Path, day: date) -> tuple[list[PickRow], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results, result_source = load_results_index(day)
    rows: list[PickRow] = []
    unmatched_races = 0
    races = payload.get("races") or []

    for race in races:
        course = normalize_course(race.get("course"))
        race_time = race.get("race_time") or race.get("off_time") or ""
        if "T" in str(race_time):
            race_time = str(race_time).split("T", 1)[1][:5]
        off_time = normalize_time(race_time)
        result_race = results.get((course, off_time))
        if result_race is None:
            unmatched_races += 1

        tips = [
            tip for tip in (race.get("top_newspaper_tips") or [])
            if isinstance(tip, dict) and str(tip.get("horse") or "").strip()
        ]
        for rank, tip in enumerate(tips[:3], start=1):
            tip_count = int(tip.get("tips") or 0)
            if rank > 1 and tip_count <= 0:
                continue
            horse = str(tip.get("horse") or "").strip()
            code, position, matched_horse = pick_result(horse, result_race)
            rows.append(
                PickRow(
                    date=f"{day:%Y-%m-%d}",
                    course=course,
                    off_time=off_time,
                    tipster=f"NEWSPAPER CONSENSUS #{rank}",
                    tipster_raw=f"top_newspaper_tips_rank_{rank}",
                    horse=horse,
                    is_nap=False,
                    result=code,
                    position=position,
                    matched_horse=matched_horse,
                    matched_race=result_race is not None,
                    result_source=result_source,
                    selection_source="racecard_injection_top_newspaper_tips",
                )
            )

        for threshold in (5, 10):
            qualifying = [tip for tip in tips if int(tip.get("tips") or 0) >= threshold]
            if not qualifying:
                continue
            tip = qualifying[0]
            horse = str(tip.get("horse") or "").strip()
            code, position, matched_horse = pick_result(horse, result_race)
            rows.append(
                PickRow(
                    date=f"{day:%Y-%m-%d}",
                    course=course,
                    off_time=off_time,
                    tipster=f"NEWSPAPER TIPS >={threshold}",
                    tipster_raw=f"newspaper_tips_ge_{threshold}",
                    horse=horse,
                    is_nap=False,
                    result=code,
                    position=position,
                    matched_horse=matched_horse,
                    matched_race=result_race is not None,
                    result_source=result_source,
                    selection_source="racecard_injection_top_newspaper_tips",
                )
            )

    meta = {
        "date": f"{day:%Y-%m-%d}",
        "selection_file": str(path.relative_to(ROOT)),
        "result_source": result_source,
        "picks": len(rows),
        "result_races": len(results),
        "unmatched_pick_races": unmatched_races,
        "source": "racecard_injection_top_newspaper_tips",
    }
    return rows, meta


def iter_velo_rows(day: date) -> tuple[list[PickRow], dict[str, Any]]:
    verdict_path = DATA_DIR / f"velo_prime_verdicts_{day:%Y_%m_%d}.json"
    results, result_source = load_results_index(day)
    if not verdict_path.exists():
        return [], {
            "date": f"{day:%Y-%m-%d}",
            "selection_file": str(verdict_path.relative_to(ROOT)),
            "result_source": result_source,
            "picks": 0,
            "result_races": len(results),
            "unmatched_pick_races": 0,
            "source": "velo_top_pick",
            "included": False,
        }

    verdicts = json.loads(verdict_path.read_text(encoding="utf-8"))
    rows: list[PickRow] = []
    unmatched_races = 0
    for verdict in verdicts:
        top = verdict.get("top") or {}
        horse = str(top.get("horse") or "").strip()
        if not horse:
            continue
        course = normalize_course(verdict.get("course"))
        off_time = normalize_time(verdict.get("off_time"))
        race = results.get((course, off_time))
        if race is None:
            unmatched_races += 1
        code, position, matched_horse = pick_result(horse, race)
        tier = str(verdict.get("tier") or "").strip().upper()
        rows.append(
            PickRow(
                date=f"{day:%Y-%m-%d}",
                course=course,
                off_time=off_time,
                tipster="VÉLØ TOP PICK",
                tipster_raw=f"velo_top_pick_tier_{tier or 'UNKNOWN'}",
                horse=horse,
                is_nap=tier == "A",
                result=code,
                position=position,
                matched_horse=matched_horse,
                matched_race=race is not None,
                result_source=result_source,
                selection_source="velo_prime_verdicts",
            )
        )
        if tier:
            rows.append(
                PickRow(
                    date=f"{day:%Y-%m-%d}",
                    course=course,
                    off_time=off_time,
                    tipster=f"VÉLØ TIER {tier}",
                    tipster_raw=f"velo_tier_{tier}",
                    horse=horse,
                    is_nap=tier == "A",
                    result=code,
                    position=position,
                    matched_horse=matched_horse,
                    matched_race=race is not None,
                    result_source=result_source,
                    selection_source="velo_prime_verdicts",
                )
            )

    return rows, {
        "date": f"{day:%Y-%m-%d}",
        "selection_file": str(verdict_path.relative_to(ROOT)),
        "result_source": result_source,
        "picks": len(rows),
        "result_races": len(results),
        "unmatched_pick_races": unmatched_races,
        "source": "velo_top_pick",
        "included": bool(result_source) and len(results) > 0,
    }


def summarize(rows: list[PickRow], *, min_decisions: int = 1) -> list[dict[str, Any]]:
    grouped: dict[str, list[PickRow]] = defaultdict(list)
    for row in rows:
        grouped[row.tipster].append(row)

    table = []
    for tipster, picks in grouped.items():
        wins = sum(row.result == "W" for row in picks)
        places = sum(row.result == "P" for row in picks)
        misses = sum(row.result == "M" for row in picks)
        nrs = sum(row.result == "NR" for row in picks)
        unmatched = sum(row.result == "UNMATCHED" for row in picks)
        decisions = wins + places + misses
        matched = len(picks) - unmatched
        if decisions < min_decisions and not tipster.startswith("SHADOW:"):
            continue
        nap_picks = [row for row in picks if row.is_nap]
        nap_decisions = sum(row.result in {"W", "P", "M"} for row in nap_picks)
        nap_wins = sum(row.result == "W" for row in nap_picks)
        nap_frames = sum(row.result in {"W", "P"} for row in nap_picks)
        strike = wins / decisions if decisions else 0.0
        frame = (wins + places) / decisions if decisions else 0.0
        table.append(
            {
                "tipster": tipster,
                "selections": len(picks),
                "matched": matched,
                "decisions": decisions,
                "wins": wins,
                "places": places,
                "misses": misses,
                "non_runners": nrs,
                "unmatched": unmatched,
                "strike_rate": round(strike, 4),
                "frame_rate": round(frame, 4),
                "nap_decisions": nap_decisions,
                "nap_wins": nap_wins,
                "nap_frame": nap_frames,
                "nap_strike_rate": round(nap_wins / nap_decisions, 4) if nap_decisions else None,
                "coverage_rate": round(matched / len(picks), 4) if picks else 0.0,
            }
        )

    return sorted(
        table,
        key=lambda item: (
            item["strike_rate"],
            item["frame_rate"],
            item["decisions"],
            item["wins"],
        ),
        reverse=True,
    )


def add_shadow_confluence_rows(rows: list[PickRow]) -> list[PickRow]:
    keyed: dict[tuple[str, str, str], dict[str, PickRow]] = defaultdict(dict)
    for row in rows:
        key = (row.date, row.course, row.off_time)
        keyed[key][row.tipster] = row

    confluence: list[PickRow] = []
    for _key, rails in keyed.items():
        velo = rails.get("VÉLØ TOP PICK")
        strong_np = rails.get("NEWSPAPER TIPS >=10")
        if not velo or not strong_np:
            continue
        if normalize_name(velo.horse) != normalize_name(strong_np.horse):
            continue
        confluence.append(
            PickRow(
                date=velo.date,
                course=velo.course,
                off_time=velo.off_time,
                tipster="SHADOW: VÉLØ + NEWSPAPER >=10",
                tipster_raw="shadow_confluence_velo_newspaper_ge_10",
                horse=velo.horse,
                is_nap=True,
                result=velo.result,
                position=velo.position,
                matched_horse=velo.matched_horse,
                matched_race=velo.matched_race,
                result_source=velo.result_source,
                selection_source="shadow_confluence",
            )
        )
    return confluence


def render_table(title: str, rows: list[dict[str, Any]], *, limit: int = 15) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| # | Tipster | Dec | W | P | M | SR | Frame | NR | Unmatched |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(rows[:limit], start=1):
        lines.append(
            "| {idx} | {tipster} | {decisions} | {wins} | {places} | {misses} | "
            "{sr:.1f}% | {frame:.1f}% | {nr} | {unmatched} |".format(
                idx=idx,
                tipster=row["tipster"],
                decisions=row["decisions"],
                wins=row["wins"],
                places=row["places"],
                misses=row["misses"],
                sr=row["strike_rate"] * 100,
                frame=row["frame_rate"] * 100,
                nr=row["non_runners"],
                unmatched=row["unmatched"],
            )
        )
    lines.append("")
    return lines


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    selection_files = sorted(DATA_DIR.glob("industry_selections_*.json"))
    all_rows: list[PickRow] = []
    daily_meta = []

    for path in selection_files:
        rows, meta = iter_selection_rows(path)
        all_rows.extend(rows)
        daily_meta.append(meta)

    injection_candidates = injection_files_by_date()
    selected_injection_files: dict[date, Path] = {}
    for day, paths in sorted(injection_candidates.items()):
        scored = []
        for path in paths:
            rows, meta = iter_injection_rows(path, day)
            matched_rows = sum(row.matched_race for row in rows)
            has_results = bool(meta["result_source"]) and meta["result_races"] > 0
            canonical_bonus = 1 if path.parent.name == f"{day:%Y-%m-%d}" else 0
            scored.append((
                (1 if has_results else 0, matched_rows, -meta["unmatched_pick_races"], canonical_bonus, meta["picks"]),
                rows,
                meta,
                path,
            ))

        _score, rows, meta, path = sorted(scored, key=lambda item: item[0], reverse=True)[0]
        selected_injection_files[day] = path
        # Only include days with a non-empty stored result file; future/empty cards stay out of the league.
        if not meta["result_source"] or meta["result_races"] == 0:
            meta["included"] = False
            daily_meta.append(meta)
            continue
        meta["included"] = True
        all_rows.extend(rows)
        daily_meta.append(meta)

    source_dates = set(injection_candidates)
    source_dates.update(date_from_selection_path(path) for path in selection_files)
    for day in sorted(source_dates):
        rows, meta = iter_velo_rows(day)
        if meta.get("included"):
            all_rows.extend(rows)
        daily_meta.append(meta)

    if not all_rows:
        raise SystemExit("No industry selection rows found")

    all_rows.extend(add_shadow_confluence_rows(all_rows))

    deduped: dict[tuple[str, str, str, str, str, str], PickRow] = {}
    for row in all_rows:
        key = (
            row.date,
            row.course,
            row.off_time,
            row.tipster,
            normalize_name(row.horse),
            row.selection_source,
        )
        deduped[key] = row
    duplicate_rows_removed = len(all_rows) - len(deduped)
    all_rows = list(deduped.values())

    dates = sorted({datetime.strptime(row.date, "%Y-%m-%d").date() for row in all_rows})
    latest_day = dates[-1]
    week_start = latest_day - timedelta(days=6)
    latest_month = latest_day.strftime("%Y-%m")

    week_rows = [row for row in all_rows if week_start <= datetime.strptime(row.date, "%Y-%m-%d").date() <= latest_day]
    month_rows = [row for row in all_rows if row.date.startswith(latest_month)]

    periods = {
        "latest_week": {
            "label": f"Latest 7 Days ({week_start:%Y-%m-%d} to {latest_day:%Y-%m-%d})",
            "rows": week_rows,
            "min_decisions": 20,
        },
        "latest_month": {
            "label": f"Latest Month ({latest_month})",
            "rows": month_rows,
            "min_decisions": 50,
        },
        "all_time": {
            "label": f"All Stored Selections ({dates[0]:%Y-%m-%d} to {latest_day:%Y-%m-%d})",
            "rows": all_rows,
            "min_decisions": 50,
        },
    }

    league = {
        key: summarize(value["rows"], min_decisions=value["min_decisions"])
        for key, value in periods.items()
    }

    pick_csv = REPORT_DIR / "industry_selection_league_picks_latest.csv"
    with pick_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].as_dict().keys()))
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row.as_dict())

    report = {
        "schema_version": "industry_selection_league_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "selection_files": len(selection_files),
        "racecard_injection_dates_discovered": len(injection_candidates),
        "racecard_injection_files_discovered": sum(len(paths) for paths in injection_candidates.values()),
        "racecard_injection_files_selected": len(selected_injection_files),
        "duplicate_rows_removed": duplicate_rows_removed,
        "date_range": {"start": f"{dates[0]:%Y-%m-%d}", "end": f"{latest_day:%Y-%m-%d}"},
        "total_picks": len(all_rows),
        "periods": {
            key: {
                "label": periods[key]["label"],
                "picks": len(periods[key]["rows"]),
                "min_decisions": periods[key]["min_decisions"],
                "league": league[key],
            }
            for key in periods
        },
        "daily_coverage": daily_meta,
        "outputs": {
            "pick_csv": str(pick_csv.relative_to(ROOT)),
            "json": "data/reports/industry_selection_league_latest.json",
            "markdown": "data/reports/industry_selection_league_latest.md",
        },
    }

    json_path = REPORT_DIR / "industry_selection_league_latest.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Industry Selection League",
        "",
        f"Generated: {report['generated_at']}",
        f"Selection files: {len(selection_files)}",
        f"Racecard injection dates discovered: {len(injection_candidates)}",
        f"Racecard injection files selected: {len(selected_injection_files)}",
        f"Duplicate rows removed: {duplicate_rows_removed}",
        f"Date range: {dates[0]:%Y-%m-%d} to {latest_day:%Y-%m-%d}",
        f"Total pick rows: {len(all_rows):,}",
        "",
        "Result codes: W=winner, P=placed 2nd/3rd, M=miss, NR=non-runner/non-completion, Unmatched=no stored result race matched.",
        "",
    ]
    for key in ("latest_week", "latest_month", "all_time"):
        lines.extend(render_table(periods[key]["label"], league[key]))

    lines.extend(
        [
            "## Coverage Notes",
            "",
            "| Date | Source | Picks | Result races | Unmatched pick races | Included | Result source |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for meta in daily_meta:
        lines.append(
            f"| {meta['date']} | {meta.get('source', 'unknown')} | {meta['picks']} | {meta['result_races']} | "
            f"{meta['unmatched_pick_races']} | {meta.get('included', True)} | {meta['result_source'] or 'MISSING'} |"
        )
    lines.append("")
    lines.append("Boundary: read-only industry-selection audit. No VÉLØ scoring, Telegram, staking, or live table writes.")

    md_path = REPORT_DIR / "industry_selection_league_latest.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Selection files: {len(selection_files)}")
    print(f"Racecard injection dates: {len(injection_candidates)}")
    print(f"Racecard injection files discovered: {sum(len(paths) for paths in injection_candidates.values())}")
    print(f"Racecard injection files selected: {len(selected_injection_files)}")
    print(f"Duplicate rows removed: {duplicate_rows_removed}")
    print(f"Pick rows: {len(all_rows):,}")
    print(f"Written: {json_path}")
    print(f"Written: {md_path}")
    print(f"Written: {pick_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
