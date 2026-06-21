"""
Evaluate Deep Race Agent V1 against local RP result files.

Paper-only. No Racing API. Uses data/results/rp_results_YYYY_MM_DD.json.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"
RESULTS_DIR = DATA_DIR / "results"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _norm_horse(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+\(([A-Z]{2,4})\)\s*$", "", text, flags=re.IGNORECASE)
    return _norm(text)


def _norm_off(value: Any) -> str:
    text = str(value or "").strip()
    if "T" in text:
        m = re.search(r"T(\d{2}):(\d{2})", text)
        if m:
            return f"{int(m.group(1))}.{m.group(2)}"
    text = text.replace(":", ".")
    m = re.match(r"^(\d{1,2})\.(\d{2})", text)
    if not m:
        return text
    hour = int(m.group(1))
    minute = m.group(2)
    if 1 <= hour <= 9:
        hour += 12
    return f"{hour}.{minute}"


def _date_slug(date: str) -> str:
    return date.replace("-", "_")


def _load_results_for_dates(dates: list[str]) -> dict[str, Any]:
    by_race_id: dict[str, dict[str, Any]] = {}
    by_course_off: dict[str, dict[str, Any]] = {}
    files_loaded = 0
    races_loaded = 0
    missing_dates = []

    for date in dates:
        path = RESULTS_DIR / f"rp_results_{_date_slug(date)}.json"
        payload = _load_json(path, {})
        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            missing_dates.append(date)
            continue
        files_loaded += 1
        for race in rows:
            if not isinstance(race, dict):
                continue
            races_loaded += 1
            race_id = str(race.get("race_id") or "")
            if race_id:
                by_race_id[race_id] = race
            key = f"{date}|{_norm(race.get('course'))}|{_norm_off(race.get('off') or race.get('race_time_raw'))}"
            by_course_off[key] = race

    return {
        "files_loaded": files_loaded,
        "races_loaded": races_loaded,
        "missing_dates": missing_dates,
        "by_race_id": by_race_id,
        "by_course_off": by_course_off,
    }


def _find_result(card: dict[str, Any], result_index: dict[str, Any]) -> dict[str, Any] | None:
    race_id = str(card.get("race_id") or "")
    if race_id:
        race = result_index["by_race_id"].get(race_id)
        if race:
            return race
    key = f"{card.get('date')}|{_norm(card.get('course'))}|{_norm_off(card.get('off_time'))}"
    return result_index["by_course_off"].get(key)


def _selected_runner(race: dict[str, Any], horse: str) -> dict[str, Any] | None:
    wanted = _norm_horse(horse)
    for runner in race.get("runners") or []:
        if _norm_horse(runner.get("horse")) == wanted:
            return runner
    return None


def _runner_outcome(race: dict[str, Any], horse: str) -> dict[str, Any]:
    runner = _selected_runner(race, horse)
    if not runner:
        return {
            "outcome": "IDENTITY_MISS",
            "win": False,
            "frame": False,
            "selected_sp_dec": None,
            "position": None,
        }
    if runner.get("non_runner"):
        return {
            "outcome": "NON_RUNNER",
            "win": False,
            "frame": False,
            "selected_sp_dec": None,
            "position": None,
        }
    pos_raw = str(runner.get("position") or "")
    pos = int(pos_raw) if pos_raw.isdigit() else None
    sp_dec = runner.get("sp_dec")
    try:
        sp_dec = float(sp_dec) if sp_dec not in (None, "") else None
    except (TypeError, ValueError):
        sp_dec = None
    win = pos == 1
    if win and (sp_dec is None or sp_dec <= 0):
        try:
            sp_dec = float(race.get("winner_sp")) if race.get("winner_sp") not in (None, "") else None
        except (TypeError, ValueError):
            sp_dec = None
    frame = pos is not None and pos <= 3
    return {
        "outcome": "WIN" if win else "PLACED" if frame else "MISS",
        "win": win,
        "frame": frame,
        "selected_sp_dec": sp_dec,
        "position": pos,
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "n": 0,
        "wins": 0,
        "frames": 0,
        "stakes": 0.0,
        "returns": 0.0,
        "profit": 0.0,
        "missing_results": 0,
        "identity_misses": 0,
        "non_runners": 0,
    }


def _add_bucket(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    if row["outcome"] == "NO_RESULT":
        bucket["missing_results"] += 1
        return
    if row["outcome"] == "IDENTITY_MISS":
        bucket["identity_misses"] += 1
        return
    if row["outcome"] == "NON_RUNNER":
        bucket["non_runners"] += 1
        return
    bucket["n"] += 1
    bucket["wins"] += 1 if row["win"] else 0
    bucket["frames"] += 1 if row["frame"] else 0
    bucket["stakes"] += 10.0
    bucket["returns"] += row["win_return"]
    bucket["profit"] = round(bucket["returns"] - bucket["stakes"], 2)


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    n = bucket["n"]
    bucket["sr"] = round(bucket["wins"] / n, 4) if n else None
    bucket["frame_rate"] = round(bucket["frames"] / n, 4) if n else None
    bucket["roi"] = round(bucket["profit"] / bucket["stakes"], 4) if bucket["stakes"] else None
    bucket["returns"] = round(bucket["returns"], 2)
    bucket["stakes"] = round(bucket["stakes"], 2)
    return bucket


def evaluate(report_path: Path) -> dict[str, Any]:
    report = _load_json(report_path, {})
    cards = list(report.get("agent_cards") or [])
    dates = sorted({str(card.get("date") or "") for card in cards if card.get("date")})
    result_index = _load_results_for_dates(dates)

    rows = []
    by_verdict = defaultdict(_empty_bucket)
    by_identity = defaultdict(_empty_bucket)
    by_course = defaultdict(_empty_bucket)
    by_tri = defaultdict(_empty_bucket)

    for card in cards:
        race = _find_result(card, result_index)
        if not race:
            outcome = {
                "outcome": "NO_RESULT",
                "win": False,
                "frame": False,
                "selected_sp_dec": None,
                "position": None,
            }
        else:
            outcome = _runner_outcome(race, str(card.get("horse") or ""))
        win_return = 0.0
        if outcome["win"] and outcome.get("selected_sp_dec"):
            win_return = round(10.0 * float(outcome["selected_sp_dec"]), 2)
        row = {
            "date": card.get("date"),
            "race_id": card.get("race_id"),
            "off_time": card.get("off_time"),
            "course": card.get("course"),
            "horse": card.get("horse"),
            "agent_verdict": card.get("agent", {}).get("agent_verdict"),
            "tri_action": card.get("tri_action"),
            "identity_confidence": card.get("evidence", {}).get("identity", {}).get("overall_confidence"),
            "support_score": card.get("agent", {}).get("support_score"),
            "risk_score": card.get("agent", {}).get("risk_score"),
            "outcome": outcome["outcome"],
            "position": outcome["position"],
            "frame": outcome["frame"],
            "win": outcome["win"],
            "selected_sp_dec": outcome["selected_sp_dec"],
            "win_return": win_return,
            "winner": race.get("winner_horse") if race else None,
            "winner_sp": race.get("winner_sp") if race else None,
        }
        rows.append(row)
        _add_bucket(by_verdict[row["agent_verdict"]], row)
        _add_bucket(by_identity[row["identity_confidence"]], row)
        _add_bucket(by_course[row["course"]], row)
        _add_bucket(by_tri[row["tri_action"]], row)

    summary = _finalize_bucket(_empty_bucket())
    for row in rows:
        _add_bucket(summary, row)
    summary = _finalize_bucket(summary)

    def finish_group(group: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(key): _finalize_bucket(value) for key, value in sorted(group.items(), key=lambda kv: str(kv[0]))}

    return {
        "generated_at": _utc_now(),
        "status": "DEEP_RACE_AGENT_V1_EVAL_PAPER_ONLY",
        "racing_api_used": False,
        "source_report": str(report_path),
        "result_source": "data/results/rp_results_YYYY_MM_DD.json",
        "dates": dates,
        "result_files_loaded": result_index["files_loaded"],
        "result_races_loaded": result_index["races_loaded"],
        "missing_result_dates": result_index["missing_dates"],
        "summary": summary,
        "by_agent_verdict": finish_group(by_verdict),
        "by_identity_confidence": finish_group(by_identity),
        "by_tri_action": finish_group(by_tri),
        "by_course": finish_group(by_course),
        "rows": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Deep Race Agent V1 Evaluation",
        f"Generated: {report['generated_at']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Racing API used: `{report['racing_api_used']}`",
        f"- Source report: `{report['source_report']}`",
        f"- Result source: `{report['result_source']}`",
        f"- Result files loaded: {report['result_files_loaded']}",
        f"- Result races loaded: {report['result_races_loaded']}",
        f"- Missing result dates: {', '.join(report['missing_result_dates']) or '-'}",
        "",
        "## Overall",
    ]
    s = report["summary"]
    lines.append(
        f"- Evaluated: {s['n']} | Wins: {s['wins']} | Frames: {s['frames']} | "
        f"SR: {s['sr']} | Frame: {s['frame_rate']} | £10 win P/L: {s['profit']} | ROI: {s['roi']}"
    )

    def table(title: str, group: dict[str, dict[str, Any]], min_n: int = 1) -> None:
        lines.extend(["", f"## {title}", "| Key | N | Wins | Frames | SR | Frame | P/L | ROI | ID Miss | No Result |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
        ordered = sorted(group.items(), key=lambda kv: (-(kv[1].get("n") or 0), str(kv[0])))
        for key, b in ordered:
            if (b.get("n") or 0) < min_n and not b.get("missing_results") and not b.get("identity_misses"):
                continue
            lines.append(
                f"| {key} | {b['n']} | {b['wins']} | {b['frames']} | {b['sr']} | "
                f"{b['frame_rate']} | {b['profit']} | {b['roi']} | {b['identity_misses']} | {b['missing_results']} |"
            )

    table("By Agent Verdict", report["by_agent_verdict"])
    table("By Identity Confidence", report["by_identity_confidence"])
    table("By Tri Action", report["by_tri_action"])
    table("By Course", report["by_course"], min_n=8)

    lines.extend(["", "## Best Cash-Run Winners"])
    winners = [
        row for row in report["rows"]
        if row["agent_verdict"] == "CASH_RUN_REVIEW" and row["win"]
    ]
    winners.sort(key=lambda row: float(row.get("selected_sp_dec") or 0), reverse=True)
    for row in winners[:25]:
        lines.append(
            f"- {row['date']} {row['off_time']} {row['course']} - {row['horse']} "
            f"SP {row['selected_sp_dec']} return £{row['win_return']}"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suffix", default=None)
    args = parser.parse_args()

    source = Path(args.report)
    suffix = args.suffix or source.stem.replace("deep_race_agent_v1_", "")
    result = evaluate(source)
    blob = json.dumps(result, indent=2, ensure_ascii=False)
    md = _markdown(result)
    out_json = REPORT_DIR / f"deep_race_agent_v1_eval_{suffix}.json"
    out_md = REPORT_DIR / f"deep_race_agent_v1_eval_{suffix}.md"
    out_json.write_text(blob + "\n", encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    (REPORT_DIR / "deep_race_agent_v1_eval_latest.json").write_text(blob + "\n", encoding="utf-8")
    (REPORT_DIR / "deep_race_agent_v1_eval_latest.md").write_text(md, encoding="utf-8")

    print(f"DEEP_RACE_AGENT_V1_EVAL_COMPLETE n={result['summary']['n']}")
    print(f"wins={result['summary']['wins']} frames={result['summary']['frames']} sr={result['summary']['sr']} frame={result['summary']['frame_rate']}")
    print(f"profit={result['summary']['profit']} roi={result['summary']['roi']}")
    print(f"missing_dates={result['missing_result_dates']}")
    print(f"json={out_json}")
    print(f"md={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
