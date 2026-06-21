#!/usr/bin/env python3
"""Deep dive the Radical Shadow CASH_RUN lane."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORT_DIR = DATA / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cash-run deep dive over Radical Shadow evals.")
    parser.add_argument("--min-date", default=None, help="Optional YYYY-MM-DD lower bound.")
    parser.add_argument("--max-date", default=None, help="Optional YYYY-MM-DD upper bound.")
    return parser.parse_args()


def _date_from_path(path: Path) -> str:
    return path.stem.replace("radical_shadow_eval_", "").replace("_", "-")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if out != out:
            return default
        return out
    except Exception:
        return default


def _valid_sp(value: Any) -> bool:
    return _safe_float(value, 0.0) >= 1.01


def _valid_win_pl(row: dict[str, Any]) -> float | None:
    if not _valid_sp(row.get("sp_decimal")):
        return None
    if row.get("outcome") == "WIN":
        return _safe_float(row.get("sp_decimal")) - 1.0
    return -1.0


def _load_rows(min_date: str | None, max_date: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("radical_shadow_eval_2026_*.json")):
        date = _date_from_path(path)
        if min_date and date < min_date:
            continue
        if max_date and date > max_date:
            continue
        obj = json.loads(path.read_text(encoding="utf-8"))
        evaluated = obj.get("evaluated") or []
        coverage.append(
            {
                "date": date,
                "evaluated": int(obj.get("evaluated_count") or len(evaluated)),
                "unmatched": int(obj.get("unmatched_count") or 0),
                "cash_run": sum(1 for row in evaluated if row.get("action") == "CASH_RUN"),
            }
        )
        for row in evaluated:
            row = dict(row)
            row["date"] = date
            rows.append(row)
    return rows, coverage


def _summarise(rows: list[dict[str, Any]], key: str, min_n: int = 1) -> list[dict[str, Any]]:
    groups = sorted({str(row.get(key) or "UNKNOWN") for row in rows})
    out = []
    for group in groups:
        sub = [row for row in rows if str(row.get(key) or "UNKNOWN") == group]
        n = len(sub)
        if n < min_n:
            continue
        wins = sum(1 for row in sub if row.get("outcome") == "WIN")
        frames = sum(1 for row in sub if row.get("outcome") in {"WIN", "PLACED"})
        valid_pls = [_valid_win_pl(row) for row in sub]
        valid_pls = [pl for pl in valid_pls if pl is not None]
        valid_n = len(valid_pls)
        pl = sum(valid_pls)
        out.append(
            {
                "group": group,
                "n": n,
                "valid_odds_n": valid_n,
                "invalid_odds_n": n - valid_n,
                "wins": wins,
                "strike_rate": round(wins / n, 4),
                "frames": frames,
                "frame_rate": round(frames / n, 4),
                "valid_win_pl": round(pl, 2),
                "valid_win_roi": round(pl / valid_n, 4) if valid_n else None,
                "avg_sp_decimal": round(
                    sum(_safe_float(row.get("sp_decimal")) for row in sub if _valid_sp(row.get("sp_decimal")))
                    / valid_n,
                    3,
                )
                if valid_n
                else None,
            }
        )
    return sorted(
        out,
        key=lambda item: (item["frame_rate"], item["n"], item["valid_win_roi"] or -999),
        reverse=True,
    )


def _combo(rows: list[dict[str, Any]], keys: list[str], name: str, min_n: int = 1) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        copy = dict(row)
        copy[name] = "|".join(str(row.get(key) or "UNKNOWN") for key in keys)
        enriched.append(copy)
    return _summarise(enriched, name, min_n=min_n)


def _passport_key(row: dict[str, Any]) -> str:
    return "PASSPORT_AVAILABLE" if row.get("passport_available") else "NO_PASSPORT"


def _quality_verdict(cash_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cash_rows)
    if not n:
        return {"status": "NO_SAMPLE", "reason": "No cash-run rows found."}
    frames = sum(1 for row in cash_rows if row.get("outcome") in {"WIN", "PLACED"})
    wins = sum(1 for row in cash_rows if row.get("outcome") == "WIN")
    frame_rate = frames / n
    strike_rate = wins / n
    if n >= 100 and frame_rate >= 0.70:
        status = "CASH_RUN_RESEARCH_GREEN"
    elif n >= 50 and frame_rate >= 0.65:
        status = "CASH_RUN_WATCH_GREEN"
    else:
        status = "PAPER_ONLY_NOT_READY"
    return {
        "status": status,
        "n": n,
        "strike_rate": round(strike_rate, 4),
        "frame_rate": round(frame_rate, 4),
        "reason": "Frame signal only; place ROI is not computed because place odds are not present.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Cash Run Deep Dive",
        f"Generated: {report['generated_at']}",
        "",
        f"- Dates covered: {report['date_count']}",
        f"- Evaluated rows: {report['evaluated_rows']}",
        f"- Cash-run rows: {report['cash_run_rows']}",
        f"- Verdict: {report['quality_verdict']['status']}",
        f"- Reason: {report['quality_verdict']['reason']}",
        "",
        "## Cash-Run Summary",
        f"- Wins: {report['cash_summary']['wins']}",
        f"- Strike rate: {report['cash_summary']['strike_rate']:.2%}",
        f"- Frames: {report['cash_summary']['frames']}",
        f"- Frame rate: {report['cash_summary']['frame_rate']:.2%}",
        f"- Valid odds rows: {report['cash_summary']['valid_odds_n']}",
        f"- Invalid/missing odds rows: {report['cash_summary']['invalid_odds_n']}",
        f"- Valid-odds win-only P&L: {report['cash_summary']['valid_win_pl']:.2f}",
        f"- Valid-odds win-only ROI: {report['cash_summary']['valid_win_roi']:.2%}"
        if report["cash_summary"]["valid_win_roi"] is not None
        else "- Valid-odds win-only ROI: n/a",
        f"- Avg SP decimal: {report['cash_summary']['avg_sp_decimal']:.2f}",
        "",
    ]

    def table(title: str, rows: list[dict[str, Any]]) -> None:
        lines.extend(
            [
                f"## {title}",
                "| Group | n | Valid odds | Wins | SR | Frames | Frame | Valid win P&L | Valid ROI | Avg SP |",
            ]
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows[:20]:
            roi = f"{row['valid_win_roi']:.2%}" if row["valid_win_roi"] is not None else "n/a"
            avg_sp = f"{row['avg_sp_decimal']:.2f}" if row["avg_sp_decimal"] is not None else "n/a"
            lines.append(
                f"| {row['group']} | {row['n']} | {row['valid_odds_n']} | {row['wins']} | "
                f"{row['strike_rate']:.2%} | {row['frames']} | {row['frame_rate']:.2%} | "
                f"{row['valid_win_pl']:.2f} | {roi} | {avg_sp} |"
            )
        lines.append("")

    table("By Field Band", report["by_field_band"])
    table("By Odds Band", report["by_odds_band"])
    table("By Class Band", report["by_class_band"])
    table("By Course", report["by_course"])
    table("By Passport", report["by_passport"])
    table("Best Combos", report["best_combos"])

    lines.extend(["## Coverage Warnings"])
    for item in report["coverage_warnings"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    rows, coverage = _load_rows(args.min_date, args.max_date)
    cash_rows = [row for row in rows if row.get("action") == "CASH_RUN"]
    for row in cash_rows:
        row["passport_group"] = _passport_key(row)

    wins = sum(1 for row in cash_rows if row.get("outcome") == "WIN")
    frames = sum(1 for row in cash_rows if row.get("outcome") in {"WIN", "PLACED"})
    valid_pls = [_valid_win_pl(row) for row in cash_rows]
    valid_pls = [pl for pl in valid_pls if pl is not None]
    valid_n = len(valid_pls)
    pl = sum(valid_pls)
    n = len(cash_rows)
    coverage_warnings = [
        f"{row['date']}: evaluated={row['evaluated']} unmatched={row['unmatched']} cash_run={row['cash_run']}"
        for row in coverage
        if row["evaluated"] == 0 or row["unmatched"] > 0
    ]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date_count": len(coverage),
        "evaluated_rows": len(rows),
        "cash_run_rows": n,
        "quality_verdict": _quality_verdict(cash_rows),
        "cash_summary": {
            "wins": wins,
            "strike_rate": round(wins / n, 4) if n else 0.0,
            "frames": frames,
            "frame_rate": round(frames / n, 4) if n else 0.0,
            "valid_odds_n": valid_n,
            "invalid_odds_n": n - valid_n,
            "valid_win_pl": round(pl, 2),
            "valid_win_roi": round(pl / valid_n, 4) if valid_n else None,
            "avg_sp_decimal": round(
                sum(_safe_float(row.get("sp_decimal")) for row in cash_rows if _valid_sp(row.get("sp_decimal")))
                / valid_n,
                3,
            )
            if valid_n
            else 0.0,
        },
        "by_field_band": _summarise(cash_rows, "field_band"),
        "by_odds_band": _summarise(cash_rows, "odds_band"),
        "by_class_band": _summarise(cash_rows, "class_band"),
        "by_course": _summarise(cash_rows, "course", min_n=2),
        "by_passport": _summarise(cash_rows, "passport_group"),
        "best_combos": _combo(cash_rows, ["field_band", "odds_band", "class_band"], "combo", min_n=3),
        "action_counts": dict(Counter(row.get("action") for row in rows)),
        "coverage": coverage,
        "coverage_warnings": coverage_warnings,
        "cash_rows": cash_rows,
    }
    json_path = REPORT_DIR / "cash_run_deep_dive_latest.json"
    md_path = REPORT_DIR / "cash_run_deep_dive_latest.md"
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    json_path.write_text(blob + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"CASH_RUN_DEEP_DIVE_COMPLETE cash_rows={n} evaluated_rows={len(rows)}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
