from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")


@dataclass
class ResearchRecord:
    date: str
    race_id: str
    horse: str
    tier: str
    prob: float
    outcome: str
    stack_roles: list[str]
    sp: float


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


def predicted_sp(record: Any) -> float:
    if isinstance(record, ResearchRecord):
        return record.sp
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


def collect_local_records(start: str, end: str) -> list[Any]:
    # Legacy import remains lazy so canonical research does not inherit the
    # local-file loader's script-path assumptions.
    from scripts.audit.deep_dive_recent_results import load_pick_records

    records: list[Any] = []
    for day in daterange(start, end):
        day_records, _meta = load_pick_records(day)
        records.extend([row for row in day_records if row.outcome in {"W", "P", "M"}])
    return records


def _canonical_rows(start: str, end: str) -> list[dict]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("Canonical source requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        query = {
            "select": "run_date,race_id,horse,score,settled_sp_dec,sp_dec,result_position,win,frame,official_evaluation_eligible",
            "model_name": "eq.MAIN_VELO_PRIME",
            "rank": "eq.1",
            "and": f"(run_date.gte.{start},run_date.lte.{end})",
            "order": "run_date.asc,race_id.asc",
            "limit": str(page_size),
            "offset": str(offset),
        }
        request = urllib.request.Request(
            f"{url}/rest/v1/canonical_model_scorecards?{urllib.parse.urlencode(query)}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            page = json.loads(response.read().decode("utf-8"))
        if not isinstance(page, list):
            raise RuntimeError("Canonical scorecard query returned a non-list payload")
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def collect_canonical_records(start: str, end: str) -> list[ResearchRecord]:
    records: list[ResearchRecord] = []
    for row in _canonical_rows(start, end):
        if row.get("official_evaluation_eligible") is False:
            continue
        position = row.get("result_position")
        if position is None and not row.get("win") and not row.get("frame"):
            continue
        outcome = "W" if row.get("win") else "P" if row.get("frame") else "M"
        prob = float(row.get("score") or 0.0)
        sp = float(row.get("settled_sp_dec") or row.get("sp_dec") or 0.0)
        roles = ["VP30", "VP30_BASE"] if prob >= 0.30 else []
        records.append(
            ResearchRecord(
                date=str(row.get("run_date") or ""),
                race_id=str(row.get("race_id") or ""),
                horse=str(row.get("horse") or ""),
                tier="",
                prob=prob,
                outcome=outcome,
                stack_roles=roles,
                sp=sp,
            )
        )
    return records


def metric_block(records: list[Any]) -> dict:
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


def run_modes(records: list[Any]) -> dict:
    modes: dict[str, Callable[[Any], bool]] = {
        "BASELINE": lambda row: True,
        "A_ONLY": lambda row: row.tier == "A",
        "VP30_BASE_ONLY": lambda row: ("VP30_BASE" in row.stack_roles) or ("VP30" in row.stack_roles),
        "NO_SUB_020": lambda row: row.prob >= 0.20,
        "A_AND_030_PLUS": lambda row: row.tier == "A" and row.prob >= 0.30,
        "NO_ODDS_ON": lambda row: (predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0),
        "A_AND_030_PLUS_NO_ODDS_ON": lambda row: (
            row.tier == "A" and row.prob >= 0.30 and ((predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0))
        ),
        "VP30_BASE_NO_ODDS_ON": lambda row: (
            (("VP30_BASE" in row.stack_roles) or ("VP30" in row.stack_roles))
            and ((predicted_sp(row) == 0.0) or (predicted_sp(row) >= 2.0))
        ),
    }
    baseline_metrics = metric_block(records)
    output = {}
    for name, fn in modes.items():
        if name.startswith("A_") and not any(row.tier for row in records):
            output[name] = {
                "available": False,
                "unavailable_reason": "decision tier is not persisted in the canonical scorecard",
                "count": 0,
                "wins": 0,
                "frames": 0,
                "strike_rate": 0.0,
                "frame_rate": 0.0,
                "roi": 0.0,
                "odds_on_count": 0,
                "delta_vs_baseline_sr": 0.0,
                "delta_vs_baseline_roi": 0.0,
            }
            continue
        selected = [row for row in records if fn(row)]
        metrics = metric_block(selected)
        metrics["available"] = True
        metrics["delta_vs_baseline_sr"] = round(metrics["strike_rate"] - baseline_metrics["strike_rate"], 2)
        metrics["delta_vs_baseline_roi"] = round(metrics["roi"] - baseline_metrics["roi"], 2)
        output[name] = metrics
    return output


def render_markdown(report: dict) -> str:
    lines = [
        "# VÉLØ AutoResearch Shadow Board",
        "",
        f"- window: `{report['window']['start']} -> {report['window']['end']}`",
        f"- evidence source: `{report['source']}`",
        f"- records: `{report['records']}`",
        "",
        "## Modes",
        "",
        "| Mode | Count | SR | FR | ROI | Odds-on Count | Delta SR | Delta ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in report["modes"].items():
        if not metrics.get("available", True):
            lines.append(f"| {name} | unavailable | — | — | — | — | — | — |")
            continue
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
    parser.add_argument(
        "--source",
        choices=("canonical", "local"),
        default="canonical",
        help="canonical reads the settled Supabase scorecard; local is legacy compatibility only",
    )
    parser.add_argument("--output-prefix", default="velo_autoresearch_shadow_latest")
    args = parser.parse_args()

    records = (
        collect_canonical_records(args.start, args.end)
        if args.source == "canonical"
        else collect_local_records(args.start, args.end)
    )
    report = {
        "window": {"start": args.start, "end": args.end},
        "source": args.source,
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
