from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from build_industry_comparison import (
    TIPSTER_SHORT,
    build_comparison,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DNF_POSITIONS = {"PU", "UR", "F", "R", "BD", "SU", "DSQ", "RR", "RO", "VOID"}


@dataclass
class PickRecord:
    date: str
    race_id: str
    course: str
    off_time: str
    race_name: str
    horse: str
    tier: str
    prob: float
    mds: float
    improve: float
    place_prob: float
    verdict_flags: list[str]
    active_components: list[str]
    outcome: str
    position: str
    winner: str
    stack_roles: list[str]


def daterange(start: date, end: date) -> list[str]:
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep-dive recent VÉLØ result quality.")
    parser.add_argument("--start", default="2026-04-29")
    parser.add_argument("--end", default="2026-05-10")
    parser.add_argument(
        "--output-prefix",
        default="velo_results_deep_dive_latest",
        help="Writes data/<prefix>.md and data/<prefix>.json",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_name(value: str) -> str:
    return " ".join((value or "").lower().replace("(ire)", "").replace("(gb)", "").replace("(fr)", "").split())


def position_code(position: str) -> str:
    pos = (position or "").strip().upper()
    if not pos:
        return "?"
    if pos == "1":
        return "W"
    if pos in {"2", "3"}:
        return "P"
    if pos in DNF_POSITIONS:
        return "NR"
    return "M"


def probability_band(prob: float) -> str:
    if prob >= 0.50:
        return "0.50+"
    if prob >= 0.40:
        return "0.40-0.49"
    if prob >= 0.30:
        return "0.30-0.39"
    if prob >= 0.20:
        return "0.20-0.29"
    return "<0.20"


def sidecar_roles_from_thresholds(prob: float, mds: float, improve: float) -> list[str]:
    roles: list[str] = []
    if prob >= 0.30:
        roles.append("VP30")
    if mds >= 0.50:
        roles.append("MDS_HIGH")
    if improve >= 0.40:
        roles.append("IMP_HIGH")
    if prob >= 0.30 and mds < 0.50 and improve < 0.40:
        roles.append("VP30_BASE")
    if prob >= 0.30 and improve >= 0.40 and mds < 0.50:
        roles.append("VP30_IMPROVE")
    return roles


def load_sidecar_map(date_str: str) -> dict[str, list[str]]:
    path = DATA_DIR / f"sidecar_stack_operator_card_{date_str.replace('-', '_')}.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    race_to_roles: dict[str, list[str]] = {}
    for stack_name, rows in payload.get("stacks", {}).items():
        for row in rows:
            race_id = row.get("race_id")
            if not race_id:
                continue
            race_to_roles.setdefault(race_id, []).append(stack_name)
    return race_to_roles


def load_results_map(date_str: str) -> dict[str, dict[str, Any]]:
    path = DATA_DIR / f"results_{date_str.replace('-', '_')}.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    return {row.get("race_id"): row for row in rows if isinstance(row, dict) and row.get("race_id")}


def find_runner(result_row: dict[str, Any], horse: str) -> dict[str, Any] | None:
    target = normalize_name(horse)
    for runner in result_row.get("runners", []):
        if normalize_name(runner.get("horse", "")) == target:
            return runner
    return None


def load_pick_records(date_str: str) -> tuple[list[PickRecord], dict[str, Any]]:
    verdict_path = DATA_DIR / f"velo_prime_verdicts_{date_str.replace('-', '_')}.json"
    results_path = DATA_DIR / f"results_{date_str.replace('-', '_')}.json"
    if not verdict_path.exists() or not results_path.exists():
        return [], {"missing_verdict": not verdict_path.exists(), "missing_results": not results_path.exists()}

    verdicts = load_json(verdict_path)
    results = load_results_map(date_str)
    sidecar_map = load_sidecar_map(date_str)

    records: list[PickRecord] = []
    unmatched_results = 0
    unresolved_predictions = 0

    for race in verdicts:
        top = race.get("top") or {}
        if not top and any(key in race for key in ("horse_name", "velo_prime_prob", "decision_tier")):
            top = {
                "horse": race.get("horse_name") or race.get("horse") or "",
                "velo_prime_prob": race.get("velo_prime_prob"),
                "market_deception_score": race.get("market_deception_score"),
                "improvement_score": race.get("improvement_score"),
                "place_prob": race.get("place_prob"),
                "verdict_flags": race.get("verdict_flags") or [],
                "active_components": race.get("active_components") or [],
            }
        race_id = race.get("race_id") or top.get("race_id") or ""
        result_row = results.get(race_id, {})
        predicted_name = top.get("horse", "")
        if not predicted_name:
            unresolved_predictions += 1
            continue
        if not result_row:
            unresolved_predictions += 1
            continue
        runner = find_runner(result_row, predicted_name)
        if result_row and runner is None:
            unmatched_results += 1
            unresolved_predictions += 1
            continue
        position = (runner or {}).get("position", "")
        outcome = position_code(position)
        winner = next(
            (
                r.get("horse", "")
                for r in result_row.get("runners", [])
                if str(r.get("position", "")).strip() == "1"
            ),
            "",
        )
        stack_roles = sidecar_map.get(race_id) or sidecar_roles_from_thresholds(
            safe_float(top.get("velo_prime_prob")),
            safe_float(top.get("market_deception_score")),
            safe_float(top.get("improvement_score")),
        )
        records.append(
            PickRecord(
                date=date_str,
                race_id=race_id,
                course=race.get("course", "") or race.get("track", ""),
                off_time=race.get("off_time", "") or race.get("race_time", ""),
                race_name=race.get("race_name", "") or top.get("race_name", ""),
                horse=top.get("horse", ""),
                tier=race.get("tier", "") or race.get("decision_tier", ""),
                prob=safe_float(top.get("velo_prime_prob")),
                mds=safe_float(top.get("market_deception_score")),
                improve=safe_float(top.get("improvement_score")),
                place_prob=safe_float(top.get("place_prob")),
                verdict_flags=list(top.get("verdict_flags", [])),
                active_components=list(top.get("active_components", [])),
                outcome=outcome,
                position=str(position or ""),
                winner=winner,
                stack_roles=stack_roles,
            )
        )

    sigma_path = DATA_DIR / f"eod_sigma_study_{date_str.replace('-', '')}.json"
    sigma_summary = load_json(sigma_path) if sigma_path.exists() else {}
    return records, {
        "unmatched_results": unmatched_results,
        "unresolved_predictions": unresolved_predictions,
        "sigma_summary": sigma_summary,
        "raw_verdict_count": len(verdicts),
    }


def metric_block(records: list[PickRecord]) -> dict[str, Any]:
    total = len(records)
    wins = sum(1 for r in records if r.outcome == "W")
    frames = sum(1 for r in records if r.outcome in {"W", "P"})
    misses = sum(1 for r in records if r.outcome == "M")
    nrs = sum(1 for r in records if r.outcome == "NR")
    avg_prob = round(sum(r.prob for r in records) / total, 4) if total else 0.0
    avg_mds = round(sum(r.mds for r in records) / total, 4) if total else 0.0
    avg_improve = round(sum(r.improve for r in records) / total, 4) if total else 0.0
    return {
        "count": total,
        "wins": wins,
        "frames": frames,
        "misses": misses,
        "non_runners": nrs,
        "strike_rate": round((wins / total) * 100, 2) if total else 0.0,
        "frame_rate": round((frames / total) * 100, 2) if total else 0.0,
        "avg_prob": avg_prob,
        "avg_mds": avg_mds,
        "avg_improve": avg_improve,
    }


def group_metrics(records: list[PickRecord], key_fn) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[PickRecord]] = defaultdict(list)
    for record in records:
        buckets[key_fn(record)].append(record)
    return {name: metric_block(rows) for name, rows in sorted(buckets.items())}


def analyze_industry(dates: list[str]) -> dict[str, Any]:
    summary: dict[str, dict[str, Counter]] = {}
    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    for date_str in dates:
        selections_path = DATA_DIR / f"industry_selections_{date_str.replace('-', '')}.json"
        if not selections_path.exists():
            continue
        rows = build_comparison(date_str, selections_path)
        rows_by_date[date_str] = rows
        for row in rows:
            for label, result_key in [("VELO", "velo_result")] + [
                (tipster, f"{short}_result") for tipster, short in TIPSTER_SHORT.items()
            ]:
                code = row.get(result_key, "")
                if label not in summary:
                    summary[label] = {"counts": Counter(), "dates": Counter()}
                if code in {"W", "P", "M", "NR"}:
                    summary[label]["counts"][code] += 1
                    summary[label]["counts"]["total"] += 1
                    summary[label]["dates"][date_str] += 1
    rolled_up: dict[str, Any] = {}
    for label, payload in summary.items():
        counts = payload["counts"]
        total = counts["total"]
        rolled_up[label] = {
            "count": total,
            "wins": counts["W"],
            "frames": counts["W"] + counts["P"],
            "strike_rate": round((counts["W"] / total) * 100, 2) if total else 0.0,
            "frame_rate": round(((counts["W"] + counts["P"]) / total) * 100, 2) if total else 0.0,
            "dates_covered": sorted(payload["dates"].keys()),
        }
    return {"dates": sorted(rows_by_date.keys()), "summary": rolled_up}


def build_summary(start: str, end: str) -> dict[str, Any]:
    days = daterange(date.fromisoformat(start), date.fromisoformat(end))
    all_records: list[PickRecord] = []
    by_day: dict[str, Any] = {}
    available_verdict_days: list[str] = []
    results_without_verdicts: list[str] = []
    verdict_without_results: list[str] = []

    sigma_wrong_horse = 0
    sigma_calibration = 0

    for date_str in days:
        verdict_path = DATA_DIR / f"velo_prime_verdicts_{date_str.replace('-', '_')}.json"
        results_path = DATA_DIR / f"results_{date_str.replace('-', '_')}.json"
        if results_path.exists() and not verdict_path.exists():
            results_without_verdicts.append(date_str)
        if verdict_path.exists() and not results_path.exists():
            verdict_without_results.append(date_str)

        records, extra = load_pick_records(date_str)
        if not records:
            continue
        available_verdict_days.append(date_str)
        all_records.extend(records)
        sigma_summary = extra.get("sigma_summary", {})
        sigma_wrong_horse += int(sigma_summary.get("wrong_horse_count", 0) or 0)
        sigma_calibration += int(sigma_summary.get("calibration_error_count", 0) or 0)
        by_day[date_str] = {
            **metric_block(records),
            "unmatched_results": extra.get("unmatched_results", 0),
            "unresolved_predictions": extra.get("unresolved_predictions", 0),
            "raw_verdict_count": extra.get("raw_verdict_count", len(records)),
            "sigma_verdict": sigma_summary.get("sigma_verdict", "UNAVAILABLE"),
            "wrong_horse_count": sigma_summary.get("wrong_horse_count", 0),
            "calibration_error_count": sigma_summary.get("calibration_error_count", 0),
            "sigma_predictions_matched": sigma_summary.get("predictions_matched"),
            "local_vs_sigma_pick_delta": (
                len(records) - int(sigma_summary.get("predictions_matched", len(records)) or len(records))
            ),
            "top_misses": [
                {
                    "horse": r.horse,
                    "course": r.course,
                    "off_time": r.off_time,
                    "prob": round(r.prob, 4),
                    "winner": r.winner,
                    "tier": r.tier,
                }
                for r in sorted(
                    [x for x in records if x.outcome == "M"],
                    key=lambda item: item.prob,
                    reverse=True,
                )[:5]
            ],
        }

    all_records_sorted = sorted(all_records, key=lambda r: (r.date, r.off_time, r.course))
    high_conf_misses = [
        {
            "date": r.date,
            "course": r.course,
            "off_time": r.off_time,
            "horse": r.horse,
            "tier": r.tier,
            "prob": round(r.prob, 4),
            "winner": r.winner,
            "stack_roles": r.stack_roles,
        }
        for r in sorted([x for x in all_records if x.outcome == "M"], key=lambda item: item.prob, reverse=True)[:12]
    ]

    stack_metrics = group_metrics(
        [r for r in all_records if r.stack_roles],
        key_fn=lambda r: ",".join(sorted(r.stack_roles)),
    )
    single_stack_metrics = group_metrics(
        [
            PickRecord(**{**r.__dict__, "stack_roles": [role]})
            for r in all_records
            for role in r.stack_roles
        ],
        key_fn=lambda r: r.stack_roles[0],
    )

    industry = analyze_industry(available_verdict_days)

    return {
        "window": {"start": start, "end": end},
        "dates_analyzed": available_verdict_days,
        "results_without_verdicts": results_without_verdicts,
        "verdict_without_results": verdict_without_results,
        "overall": metric_block(all_records_sorted),
        "by_day": by_day,
        "by_tier": group_metrics(all_records_sorted, key_fn=lambda r: r.tier or "UNKNOWN"),
        "by_probability_band": group_metrics(all_records_sorted, key_fn=lambda r: probability_band(r.prob)),
        "by_single_stack_role": single_stack_metrics,
        "by_stack_combo": stack_metrics,
        "high_confidence_misses": high_conf_misses,
        "sigma_loss_labels": {
            "wrong_horse_count": sigma_wrong_horse,
            "calibration_error_count": sigma_calibration,
        },
        "archive_integrity_warnings": [
            {
                "date": date_str,
                "local_count": row["count"],
                "sigma_predictions_matched": row["sigma_predictions_matched"],
                "delta": row["local_vs_sigma_pick_delta"],
            }
            for date_str, row in by_day.items()
            if row["sigma_predictions_matched"] is not None and row["local_vs_sigma_pick_delta"] != 0
        ],
        "industry_benchmark": industry,
    }


def md_table_from_metrics(title: str, metrics: dict[str, dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", "", "| Bucket | Count | Wins | Frames | SR | FR | Avg VP | Avg MDS | Avg Improve |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for bucket, values in metrics.items():
        lines.append(
            f"| {bucket} | {values['count']} | {values['wins']} | {values['frames']} | "
            f"{values['strike_rate']}% | {values['frame_rate']}% | {values['avg_prob']:.4f} | "
            f"{values['avg_mds']:.4f} | {values['avg_improve']:.4f} |"
        )
    lines.append("")
    return lines


def render_markdown(summary: dict[str, Any]) -> str:
    overall = summary["overall"]
    lines = [
        f"# VÉLØ Results Deep Dive — {summary['window']['start']} to {summary['window']['end']}",
        "",
        "## Executive Read",
        "",
        f"- Days analyzed: `{len(summary['dates_analyzed'])}`",
        f"- Total settled top picks: `{overall['count']}`",
        f"- Overall strike rate: `{overall['strike_rate']}%`",
        f"- Overall frame rate: `{overall['frame_rate']}%`",
        f"- Average top-pick VP: `{overall['avg_prob']:.4f}`",
        f"- Sigma wrong-horse labels: `{summary['sigma_loss_labels']['wrong_horse_count']}`",
        f"- Sigma calibration-error labels: `{summary['sigma_loss_labels']['calibration_error_count']}`",
        "",
        "## Where VÉLØ Is Going Wrong",
        "",
        "1. The main failure class is still picking the wrong horse rather than total confidence collapse.",
        "2. Mid-strength and weak days are dragging the window harder than the strong days can rescue it.",
        "3. VP30 base is cleaner than freedom-sidecar thinking; improve-heavy and mixed stacks are less trustworthy.",
        "4. Industry rails are beating us on the dates where external comparison exists, especially Spotlight.",
        "5. Operational truth is incomplete: some result days exist without local verdict truth, and only one day has a formal run-truth packet.",
        "",
        "## Missing / Broken Inputs",
        "",
        f"- Results present but no local verdict file: `{', '.join(summary['results_without_verdicts']) or 'none'}`",
        f"- Local verdict file present but no results file: `{', '.join(summary['verdict_without_results']) or 'none'}`",
        f"- Local verdict archive mismatch days: `{', '.join(w['date'] for w in summary['archive_integrity_warnings']) or 'none'}`",
        "- Telegram delivery is not yet first-class system-of-record truth.",
        "- Commit SHA lineage is still not attached to every scoring run in a provable way.",
        "",
        "## Day Breakdown",
        "",
        "| Date | Picks | Wins | Frames | SR | FR | Sigma Verdict | Wrong Horse | Calibration | Unmatched | Local-Sigma Delta |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for date_str, row in summary["by_day"].items():
        lines.append(
            f"| {date_str} | {row['count']} | {row['wins']} | {row['frames']} | {row['strike_rate']}% | "
            f"{row['frame_rate']}% | {row['sigma_verdict']} | {row['wrong_horse_count']} | "
            f"{row['calibration_error_count']} | {row['unmatched_results']} | {row['local_vs_sigma_pick_delta']} |"
        )
    lines.append("")
    lines.extend(md_table_from_metrics("By Tier", summary["by_tier"]))
    lines.extend(md_table_from_metrics("By Probability Band", summary["by_probability_band"]))
    lines.extend(md_table_from_metrics("By Sidecar Role", summary["by_single_stack_role"]))

    lines.extend(
        [
            "## Highest-Confidence Misses",
            "",
            "| Date | Course | Time | Horse | Tier | VP | Winner | Stack Roles |",
            "|---|---|---:|---|---|---:|---|---|",
        ]
    )
    for row in summary["high_confidence_misses"]:
        lines.append(
            f"| {row['date']} | {row['course']} | {row['off_time']} | {row['horse']} | {row['tier']} | "
            f"{row['prob']:.4f} | {row['winner']} | {', '.join(row['stack_roles']) or '-'} |"
        )
    lines.append("")

    industry = summary["industry_benchmark"]
    lines.extend(
        [
            "## Industry Benchmark",
            "",
            f"- Dates covered: `{', '.join(industry['dates']) or 'none'}`",
            "",
            "| Rail | Count | Wins | Frames | SR | FR |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in sorted(industry["summary"].items()):
        lines.append(
            f"| {label} | {row['count']} | {row['wins']} | {row['frames']} | {row['strike_rate']}% | {row['frame_rate']}% |"
        )
    lines.append("")

    lines.extend(
        [
            "## What Looks Missing",
            "",
            "1. A stable morning truth packet for every scored day, not just failure days.",
            "2. A consistent local verdict archive for every result day so replay windows are complete.",
            "3. A cleaner sidecar promotion discipline: VP30 base looks useful, but improve-heavy and mixed stacks need stricter proof.",
            "4. A formal benchmark rail in daily close so Spotlight/Postdata/Topspeed comparisons are not ad hoc.",
            "5. A miss-class drilldown that tells us whether weak days are caused by tier drift, market shape misses, or source-quality gaps.",
            "",
            "## Recommended Next Fixes",
            "",
            "1. Make daily run-truth packets automatic and mandatory for every scoring day.",
            "2. Add commit SHA + trigger source into persisted scoring truth.",
            "3. Keep VP30 base as the clean reference lane; hold improve/MDS claims to replay and close truth.",
            "4. Run the industry benchmark automatically on every closed day where RP selection files exist.",
            "5. Add a miss-forensics layer that tags high-confidence losses by likely cause using results + source completeness.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    summary = build_summary(args.start, args.end)
    md = render_markdown(summary)
    output_prefix = DATA_DIR / args.output_prefix
    (output_prefix.with_suffix(".json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_prefix.with_suffix(".md")).write_text(md, encoding="utf-8")
    print(f"WROTE {output_prefix.with_suffix('.json')}")
    print(f"WROTE {output_prefix.with_suffix('.md')}")
    print(
        f"DEEP_DIVE_OK days={len(summary['dates_analyzed'])} picks={summary['overall']['count']} "
        f"sr={summary['overall']['strike_rate']} fr={summary['overall']['frame_rate']}"
    )


if __name__ == "__main__":
    main()
