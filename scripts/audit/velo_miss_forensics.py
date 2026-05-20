from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_industry_comparison import build_comparison


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def normalize_name(value: str) -> str:
    return " ".join((value or "").lower().replace("(ire)", "").replace("(gb)", "").replace("(fr)", "").split())


def load_verdicts(date_str: str) -> list[dict]:
    path = DATA / f"velo_prime_verdicts_{date_str.replace('-', '_')}.json"
    if not path.exists():
        return []
    payload = load_json(path)
    return payload if isinstance(payload, list) else []


def load_results_map(date_str: str) -> dict[str, dict]:
    path = DATA / f"results_{date_str.replace('-', '_')}.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    return {row.get("race_id"): row for row in rows if isinstance(row, dict) and row.get("race_id")}


def load_industry_rows(date_str: str) -> dict[tuple[str, str], dict]:
    path = DATA / f"industry_selections_{date_str.replace('-', '')}.json"
    if not path.exists():
        return {}
    rows = build_comparison(date_str, path)
    return {(row["course"], row["time"]): row for row in rows}


def classify_primary_cause(*, prob: float, tier: str, winner_sp: float, unmatched: bool) -> str:
    if unmatched:
        return "SOURCE_GAP_UNMATCHED_RESULT"
    if tier == "A" and prob >= 0.40:
        if winner_sp > 10:
            return "A_TIER_LOSS_TO_OUTSIDER"
        if 0 < winner_sp <= 3:
            return "A_TIER_LOSS_TO_SHORT_FAV"
        return "A_TIER_WRONG_HORSE"
    if prob < 0.30 or tier in {"C", "X", "D"}:
        return "LOW_SIGNAL_VOLUME_TRUSTED"
    if winner_sp > 10:
        return "OUTSIDER_CHAOS"
    if 0 < winner_sp <= 3:
        return "SHORT_FAVOURITE_BEAT_US"
    return "MID_PRICE_WINNER_BEAT_US"


def winner_runner(result_row: dict) -> dict:
    for runner in result_row.get("runners", []):
        if str(runner.get("position", "")).strip() == "1":
            return runner
    return {}


def analyse_day(date_str: str) -> dict:
    verdicts = load_verdicts(date_str)
    results = load_results_map(date_str)
    industry_rows = load_industry_rows(date_str)
    if not verdicts or not results:
        return {
            "date": date_str,
            "status": "BLOCKED",
            "missing_verdicts": not bool(verdicts),
            "missing_results": not bool(results),
            "misses": [],
            "summary": {},
        }

    misses: list[dict] = []
    causes = Counter()
    flags = Counter()
    trusted_failures = 0

    for row in verdicts:
        top = row.get("top") or {}
        if not top and any(key in row for key in ("horse_name", "velo_prime_prob", "decision_tier")):
            top = {
                "horse": row.get("horse_name") or row.get("horse") or "",
                "horse_id": row.get("horse_id") or "",
                "velo_prime_prob": row.get("velo_prime_prob"),
            }
        race_id = row.get("race_id") or top.get("race_id") or ""
        result_row = results.get(race_id, {})
        predicted_name = top.get("horse", "")
        predicted_id = top.get("horse_id", "")
        prob = safe_float(top.get("velo_prime_prob"))
        tier = (row.get("tier") or row.get("decision_tier") or "").upper()
        runners = result_row.get("runners", [])

        matched_runner = None
        for runner in runners:
            if predicted_id and runner.get("horse_id") == predicted_id:
                matched_runner = runner
                break
            if not predicted_id and normalize_name(runner.get("horse", "")) == normalize_name(predicted_name):
                matched_runner = runner
                break
        if not matched_runner:
            if result_row:
                winner = winner_runner(result_row)
                cause = classify_primary_cause(prob=prob, tier=tier, winner_sp=safe_float(winner.get("sp_dec")), unmatched=True)
                causes[cause] += 1
                misses.append(
                    {
                        "race_id": race_id,
                        "course": row.get("course", ""),
                        "off_time": row.get("off_time", ""),
                        "horse": predicted_name,
                        "tier": tier,
                        "velo_prime_prob": round(prob, 4),
                        "winner": winner.get("horse", ""),
                        "winner_sp": safe_float(winner.get("sp_dec")),
                        "primary_cause": cause,
                        "flags": ["UNMATCHED_RESULT"],
                    }
                )
            continue

        position = str(matched_runner.get("position", "")).strip()
        if position in {"1", "2", "3"}:
            continue

        winner = winner_runner(result_row)
        winner_sp = safe_float(winner.get("sp_dec"))
        course = row.get("course", "") or row.get("track", "")
        off_time = row.get("off_time", "") or row.get("race_time", "")
        industry = industry_rows.get((course, off_time), {})
        local_flags: list[str] = []
        if prob >= 0.40:
            local_flags.append("HIGH_CONFIDENCE_LOSS")
        if tier == "A":
            local_flags.append("A_TIER_LOSS")
        if prob >= 0.30:
            local_flags.append("VP30_LOSS")
        if prob < 0.30 or tier in {"C", "X", "D"}:
            local_flags.append("LOW_SIGNAL_VOLUME")
        if industry.get("spot_pick") and normalize_name(industry.get("spot_pick", "")) == normalize_name(winner.get("horse", "")):
            local_flags.append("SPOTLIGHT_HAD_WINNER")
        if industry.get("postd_pick") and normalize_name(industry.get("postd_pick", "")) == normalize_name(winner.get("horse", "")):
            local_flags.append("POSTDATA_HAD_WINNER")
        if winner_sp > 10:
            local_flags.append("OUTSIDER_WINNER")
        elif 0 < winner_sp <= 3:
            local_flags.append("SHORT_FAVOURITE_WINNER")
        else:
            local_flags.append("MID_PRICE_WINNER")

        cause = classify_primary_cause(prob=prob, tier=tier, winner_sp=winner_sp, unmatched=False)
        causes[cause] += 1
        for flag in local_flags:
            flags[flag] += 1
        if prob >= 0.30 or tier == "A":
            trusted_failures += 1
        misses.append(
            {
                "race_id": race_id,
                "course": course,
                "off_time": off_time,
                "horse": predicted_name,
                "tier": tier,
                "velo_prime_prob": round(prob, 4),
                "winner": winner.get("horse", ""),
                "winner_sp": winner_sp,
                "primary_cause": cause,
                "flags": local_flags,
            }
        )

    summary = {
        "miss_count": len(misses),
        "primary_causes": dict(causes),
        "flags": dict(flags),
        "trusted_failures": trusted_failures,
        "trusted_failure_rate": round((trusted_failures / len(misses)) * 100, 2) if misses else 0.0,
    }
    return {
        "date": date_str,
        "status": "OK",
        "summary": summary,
        "misses": sorted(misses, key=lambda row: row["velo_prime_prob"], reverse=True),
    }


def render_markdown(report: dict) -> str:
    if report["status"] != "OK":
        return (
            f"# VÉLØ Miss Forensics — {report['date']}\n\n"
            f"- status: `{report['status']}`\n"
            f"- missing_verdicts: `{report.get('missing_verdicts')}`\n"
            f"- missing_results: `{report.get('missing_results')}`\n"
        )

    lines = [
        f"# VÉLØ Miss Forensics — {report['date']}",
        "",
        f"- miss_count: `{report['summary']['miss_count']}`",
        f"- trusted_failures: `{report['summary']['trusted_failures']}`",
        f"- trusted_failure_rate: `{report['summary']['trusted_failure_rate']}%`",
        "",
        "## Primary Causes",
        "",
    ]
    for cause, count in sorted(report["summary"]["primary_causes"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{cause}`: `{count}`")
    lines.extend(
        [
            "",
            "## Misses",
            "",
            "| Course | Time | Horse | Tier | VP | Winner | SP | Cause | Flags |",
            "|---|---:|---|---|---:|---|---:|---|---|",
        ]
    )
    for row in report["misses"][:30]:
        lines.append(
            f"| {row['course']} | {row['off_time']} | {row['horse']} | {row['tier']} | "
            f"{row['velo_prime_prob']:.4f} | {row['winner']} | {row['winner_sp']:.2f} | "
            f"{row['primary_cause']} | {', '.join(row['flags'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(date_str: str) -> dict:
    report = analyse_day(date_str)
    date_tag = date_str.replace("-", "_")
    json_path = DATA / f"velo_miss_forensics_{date_tag}.json"
    md_path = DATA / f"velo_miss_forensics_{date_tag}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["md_path"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    report = write_report(args.date)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
