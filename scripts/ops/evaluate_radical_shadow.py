#!/usr/bin/env python3
"""Evaluate Radical Shadow packets against settled Sigma results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.radical.regime_router import safe_float

DATA = ROOT / "data"
REPORT_DIR = DATA / "reports"
SIGMA_DIR = DATA / "sigma_results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Radical Shadow against Sigma results.")
    parser.add_argument("--date", required=True, help="Race date in YYYY-MM-DD format.")
    return parser.parse_args()


def _slug(date: str) -> str:
    return date.replace("-", "_")


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _pl(outcome: str, sp_decimal: Any) -> float:
    if outcome == "WIN":
        return max(0.0, safe_float(sp_decimal, 0.0) - 1.0)
    return -1.0


def _summarise(rows: list[dict[str, Any]], group_key: str) -> list[dict[str, Any]]:
    out = []
    groups = sorted({str(row.get(group_key) or "UNKNOWN") for row in rows})
    for group in groups:
        sub = [row for row in rows if str(row.get(group_key) or "UNKNOWN") == group]
        n = len(sub)
        if not n:
            continue
        wins = sum(1 for row in sub if row["outcome"] == "WIN")
        frames = sum(1 for row in sub if row["outcome"] in {"WIN", "PLACED"})
        pl = sum(row["pl"] for row in sub)
        out.append(
            {
                "group": group,
                "n": n,
                "wins": wins,
                "strike_rate": round(wins / n, 4),
                "frames": frames,
                "frame_rate": round(frames / n, 4),
                "pl": round(pl, 2),
                "roi": round(pl / n, 4),
                "avg_sp_decimal": round(sum(safe_float(row.get("sp_decimal"), 0.0) for row in sub) / n, 3),
            }
        )
    return sorted(out, key=lambda row: (row["roi"], row["strike_rate"], row["n"]), reverse=True)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Radical Shadow Evaluation - {report['date']}",
        "",
        f"- Evaluated: {report['evaluated_count']}",
        f"- Unmatched: {report['unmatched_count']}",
        "",
        "## By Action",
        "| Action | n | Wins | SR | Frames | Frame | P&L | ROI | Avg SP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["by_action"]:
        lines.append(
            f"| {row['group']} | {row['n']} | {row['wins']} | {row['strike_rate']:.2%} | "
            f"{row['frames']} | {row['frame_rate']:.2%} | {row['pl']:.2f} | "
            f"{row['roi']:.2%} | {row['avg_sp_decimal']:.2f} |"
        )
    lines.extend(["", "## By Field Band"])
    lines.append("| Field band | n | Wins | SR | Frames | Frame | P&L | ROI |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in report["by_field_band"]:
        lines.append(
            f"| {row['group']} | {row['n']} | {row['wins']} | {row['strike_rate']:.2%} | "
            f"{row['frames']} | {row['frame_rate']:.2%} | {row['pl']:.2f} | {row['roi']:.2%} |"
        )
    if report["unmatched"]:
        lines.extend(["", "## Unmatched"])
        for row in report["unmatched"][:20]:
            lines.append(f"- {row.get('off_time')} {row.get('course')} {row.get('horse')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    slug = _slug(args.date)
    shadow = _load_json(REPORT_DIR / f"radical_shadow_{slug}.json")
    sigma = _load_json(SIGMA_DIR / f"sigma_results_{slug}.json")
    sigma_rows = sigma.get("rows", []) if isinstance(sigma, dict) else sigma
    sigma_by_race = {str(row.get("race_id")): row for row in sigma_rows}

    evaluated = []
    unmatched = []
    for decision in shadow.get("decisions", []):
        result = sigma_by_race.get(str(decision.get("race_id")))
        if not result:
            unmatched.append(decision)
            continue
        outcome = str(result.get("outcome") or "").upper()
        predicted_match = _norm(result.get("predicted")) == _norm(decision.get("horse"))
        if not predicted_match:
            unmatched.append(decision | {"sigma_predicted": result.get("predicted")})
            continue
        row = {
            "race_id": decision.get("race_id"),
            "course": decision.get("course"),
            "off_time": decision.get("off_time"),
            "horse": decision.get("horse"),
            "action": decision.get("radical", {}).get("action"),
            "field_band": decision.get("radical", {}).get("field_band"),
            "odds_band": decision.get("radical", {}).get("odds_band"),
            "class_band": decision.get("radical", {}).get("class_band"),
            "sp_decimal": decision.get("sp_decimal"),
            "outcome": outcome,
            "pl": _pl(outcome, decision.get("sp_decimal")),
            "winner": result.get("actual_name"),
            "winner_sp": result.get("winner_sp"),
            "passport_available": decision.get("passport", {}).get("passport_available"),
        }
        evaluated.append(row)

    report = {
        "date": args.date,
        "shadow_packet": str(REPORT_DIR / f"radical_shadow_{slug}.json"),
        "sigma_results": str(SIGMA_DIR / f"sigma_results_{slug}.json"),
        "evaluated_count": len(evaluated),
        "unmatched_count": len(unmatched),
        "by_action": _summarise(evaluated, "action"),
        "by_field_band": _summarise(evaluated, "field_band"),
        "by_odds_band": _summarise(evaluated, "odds_band"),
        "evaluated": evaluated,
        "unmatched": unmatched,
    }

    json_path = REPORT_DIR / f"radical_shadow_eval_{slug}.json"
    md_path = REPORT_DIR / f"radical_shadow_eval_{slug}.md"
    latest_json = REPORT_DIR / "radical_shadow_eval_latest.json"
    latest_md = REPORT_DIR / "radical_shadow_eval_latest.md"
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    markdown = render_markdown(report)
    json_path.write_text(blob + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    latest_json.write_text(blob + "\n", encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    print(f"RADICAL_SHADOW_EVAL_COMPLETE date={args.date} evaluated={len(evaluated)} unmatched={len(unmatched)}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
