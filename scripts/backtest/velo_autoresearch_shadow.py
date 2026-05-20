from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from deep_dive_recent_results import PickRecord, load_pick_records


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def normalize_name(value: str) -> str:
    return " ".join((value or "").lower().replace("(ire)", "").replace("(gb)", "").replace("(fr)", "").split())


def daterange(start: str, end: str) -> list[str]:
    cursor = date.fromisoformat(start)
    limit = date.fromisoformat(end)
    out: list[str] = []
    while cursor <= limit:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def predicted_sp(record: PickRecord) -> float:
    result_path = DATA / f"results_{record.date.replace('-', '_')}.json"
    if not result_path.exists():
        return 0.0
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    race = next((row for row in rows if row.get("race_id") == record.race_id), {})
    for runner in race.get("runners", []):
        if normalize_name(runner.get("horse", "")) == normalize_name(record.horse):
            try:
                return float(runner.get("sp_dec") or 0.0)
            except Exception:
                return 0.0
    return 0.0


def collect_records(start: str, end: str) -> list[PickRecord]:
    records: list[PickRecord] = []
    for day in daterange(start, end):
        day_records, _meta = load_pick_records(day)
        records.extend([row for row in day_records if row.outcome in {"W", "P", "M"}])
    return records


def metric_block(records: list[PickRecord]) -> dict:
    count = len(records)
    wins = sum(1 for row in records if row.outcome == "W")
    frames = sum(1 for row in records if row.outcome in {"W", "P"})
    returns = 0.0
    odds_on_count = 0
    short_count = 0
    for row in records:
        sp = predicted_sp(row)
        if 0 < sp < 2.0:
            odds_on_count += 1
        if 0 < sp <= 3.0:
            short_count += 1
        if row.outcome == "W" and sp > 0:
            returns += sp
    stake = float(count)
    return {
        "count": count,
        "wins": wins,
        "frames": frames,
        "strike_rate": round((wins / count) * 100, 2) if count else 0.0,
        "frame_rate": round((frames / count) * 100, 2) if count else 0.0,
        "roi": round(((returns - stake) / stake) * 100, 2) if stake else 0.0,
        "avg_prob": round(sum(row.prob for row in records) / count, 4) if count else 0.0,
        "odds_on_count": odds_on_count,
        "short_price_count": short_count,
    }


def run_modes(records: list[PickRecord]) -> dict:
    modes: dict[str, Callable[[PickRecord], bool]] = {
        "BASELINE": lambda row: True,
        "A_ONLY": lambda row: row.tier == "A",
        "VP30_BASE_ONLY": lambda row: ("VP30_BASE" in row.stack_roles) or ("VP30" in row.stack_roles),
        "NO_SUB_020": lambda row: row.prob >= 0.20,
        "A_AND_030_PLUS": lambda row: row.tier == "A" and row.prob >= 0.30,
        "NO_ODDS_ON": lambda row: (predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0),
        "A_AND_030_PLUS_NO_ODDS_ON": lambda row: row.tier == "A"
        and row.prob >= 0.30
        and ((predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0)),
        "VP30_BASE_NO_ODDS_ON": lambda row: (("VP30_BASE" in row.stack_roles) or ("VP30" in row.stack_roles))
        and ((predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0)),
    }
    baseline_metrics = metric_block(records)
    output = {}
    for name, fn in modes.items():
        selected = [row for row in records if fn(row)]
        metrics = metric_block(selected)
        metrics["delta_vs_baseline_sr"] = round(metrics["strike_rate"] - baseline_metrics["strike_rate"], 2)
        metrics["delta_vs_baseline_roi"] = round(metrics["roi"] - baseline_metrics["roi"], 2)
        output[name] = metrics
    return output


def render_markdown(report: dict) -> str:
    lines = [
        "# VÉLØ AutoResearch Shadow Board",
        "",
        f"- window: `{report['window']['start']} -> {report['window']['end']}`",
        f"- records: `{report['records']}`",
        "",
        "## Modes",
        "",
        "| Mode | Count | SR | FR | ROI | Odds-on Count | Delta SR | Delta ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in report["modes"].items():
        lines.append(
            f"| {name} | {metrics['count']} | {metrics['strike_rate']:.2f}% | {metrics['frame_rate']:.2f}% | "
            f"{metrics['roi']:.2f}% | {metrics['odds_on_count']} | {metrics['delta_vs_baseline_sr']:.2f} | "
            f"{metrics['delta_vs_baseline_roi']:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrained autoresearch-style shadow board for VÉLØ.")
    parser.add_argument("--start", default="2026-04-29")
    parser.add_argument("--end", default="2026-05-10")
    parser.add_argument("--output-prefix", default="velo_autoresearch_shadow_latest")
    args = parser.parse_args()

    records = collect_records(args.start, args.end)
    report = {
        "window": {"start": args.start, "end": args.end},
        "records": len(records),
        "modes": run_modes(records),
    }
    json_path = DATA / f"{args.output_prefix}.json"
    md_path = DATA / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "md_path": str(md_path), "records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
