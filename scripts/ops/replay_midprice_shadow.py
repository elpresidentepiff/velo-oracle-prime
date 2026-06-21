"""
Replay VÉLØ midprice/shadow rules against completed Sigma days.

Purpose:
  - Evidence the midprice problem across many days, not one angry afternoon.
  - Use RP-supported Sigma outcomes and Old VÉLØ verdict files only.
  - Keep the layer paper-only: no scoring changes, no staking, no promotion.

Usage:
  python scripts/ops/replay_midprice_shadow.py --start-date 2026-06-01 --end-date 2026-06-20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.midprice_hunter import evaluate_race  # noqa: E402

DATA_DIR = ROOT / "data"
SIGMA_DIR = DATA_DIR / "sigma_results"
REPORT_DIR = DATA_DIR / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _date_from_sigma_path(path: Path) -> str | None:
    m = re.search(r"sigma_results_(\d{4})_(\d{2})_(\d{2})\.json$", path.name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _date_tag(date_str: str) -> str:
    return date_str.replace("-", "_")


def _sigma_rows(path: Path) -> list[dict]:
    data = _load_json(path, {})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("rows") or data.get("results") or data.get("verdicts") or []
        return rows if isinstance(rows, list) else []
    return []


def _verdicts_by_race(date_str: str) -> dict[str, dict]:
    rows = _load_json(DATA_DIR / f"velo_prime_verdicts_{_date_tag(date_str)}.json", [])
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            result[rid] = row
    return result


def _float_from(*items: Any, default: float | None = None) -> float | None:
    for item in items:
        if item is None or item == "":
            continue
        try:
            return float(item)
        except (TypeError, ValueError):
            continue
    return default


def _int_from(*items: Any, default: int | None = None) -> int | None:
    val = _float_from(*items, default=None)
    return int(val) if val is not None else default


def _norm(s: Any) -> str:
    return str(s or "").strip().upper()


def _odds_band(sp_dec: float | None) -> str:
    if not sp_dec or sp_dec <= 1:
        return "ODDS_UNKNOWN"
    if sp_dec < 1.5:
        return "ODDS_ON_LT_1_5"
    if sp_dec < 2:
        return "EVS_TO_6_4"
    if sp_dec < 3:
        return "TWO_TO_THREE"
    if sp_dec < 5:
        return "THREE_TO_FIVE"
    if sp_dec < 8:
        return "FIVE_TO_EIGHT"
    if sp_dec < 14:
        return "EIGHT_TO_FOURTEEN"
    return "LONGSHOT_14_PLUS"


def _win_profit(sp_dec: float | None, won: bool) -> float | None:
    if not sp_dec or sp_dec <= 1:
        return None
    return round(sp_dec - 1, 4) if won else -1.0


def _summarise(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "UNKNOWN")].append(row)

    summary = []
    for name, items in buckets.items():
        n = len(items)
        wins = sum(1 for r in items if r["won"])
        frames = sum(1 for r in items if r["framed"])
        mid_misses = sum(1 for r in items if r.get("miss_class") == "mid_priced_won")
        profits = [r["win_profit"] for r in items if r.get("win_profit") is not None]
        pl = round(sum(profits), 4) if profits else None
        summary.append({
            key: name,
            "n": n,
            "wins": wins,
            "strike_rate": round(wins / n * 100, 2) if n else 0.0,
            "frames": frames,
            "frame_rate": round(frames / n * 100, 2) if n else 0.0,
            "mid_priced_won_misses": mid_misses,
            "mid_miss_rate": round(mid_misses / n * 100, 2) if n else 0.0,
            "win_pl_units": pl,
            "win_roi_pct": round(pl / len(profits) * 100, 2) if profits else None,
        })
    return sorted(summary, key=lambda r: (-r["n"], str(r.get(key))))


def _top(summary: list[dict], key: str, minimum_n: int) -> list[dict]:
    return [r for r in summary if r["n"] >= minimum_n][:40]


def replay(start_date: str | None, end_date: str | None, minimum_n: int) -> dict:
    sigma_files = sorted(SIGMA_DIR.glob("sigma_results_*.json"))
    rows: list[dict] = []
    missing_verdicts: list[dict] = []

    for sigma_path in sigma_files:
        date_str = _date_from_sigma_path(sigma_path)
        if not date_str:
            continue
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue

        verdict_by_race = _verdicts_by_race(date_str)
        for sigma in _sigma_rows(sigma_path):
            rid = str(sigma.get("race_id") or "")
            verdict_row = verdict_by_race.get(rid)
            if not verdict_row:
                missing_verdicts.append({
                    "date": date_str,
                    "race_id": rid,
                    "course": sigma.get("course") or "",
                    "reason": "VERDICT_MISSING_FOR_SIGMA_ROW",
                })
                continue

            top = verdict_row.get("top") or {}
            pick = top.get("horse") or sigma.get("predicted") or ""
            actual = sigma.get("actual_name") or sigma.get("winner") or ""
            outcome = str(sigma.get("outcome") or "").upper()
            won = outcome == "WIN" or _norm(pick) == _norm(actual)
            framed = outcome in {"WIN", "PLACE", "PLACED", "FRAME"} or won
            sp_dec = _float_from(
                top.get("sp_dec"),
                top.get("best_odds_decimal"),
                top.get("forecast_decimal"),
                top.get("_resolved_sp_dec"),
                default=None,
            )

            shadow = evaluate_race(
                race_id=rid,
                race_date=date_str,
                course=verdict_row.get("course") or sigma.get("course") or "",
                off_time=str(verdict_row.get("off_time") or sigma.get("off") or ""),
                tier=str(verdict_row.get("tier") or ""),
                top_pick=str(pick),
                top_vp=_float_from(top.get("velo_prime_prob"), sigma.get("velo_prime_prob"), default=0.0),
                top_mds=_float_from(top.get("market_deception_score"), default=0.0),
                top_improvement=_float_from(top.get("improvement_score"), default=0.0),
                top_place_prob=_float_from(top.get("place_prob"), default=0.0),
                field_size=_int_from(verdict_row.get("scored"), verdict_row.get("runner_count"), default=None),
                class_num=_int_from(top.get("class_num"), verdict_row.get("class_num"), default=None),
                sp_dec=sp_dec,
            )

            field_band = shadow.get("field_band") or top.get("midprice_shadow_field_band") or ""
            action = shadow.get("shadow_action") or top.get("midprice_shadow_action") or "UNKNOWN"
            row = {
                "date": date_str,
                "race_id": rid,
                "course": verdict_row.get("course") or sigma.get("course") or "",
                "off_time": verdict_row.get("off_time") or sigma.get("off") or "",
                "tier": verdict_row.get("tier") or "",
                "top_pick": pick,
                "actual_winner": actual,
                "outcome": outcome,
                "won": won,
                "framed": framed,
                "miss_class": sigma.get("miss_class") or "",
                "winner_sp": _float_from(sigma.get("winner_sp"), default=None),
                "pick_sp_dec": sp_dec,
                "pick_odds_band": _odds_band(sp_dec),
                "winner_odds_band": _odds_band(_float_from(sigma.get("winner_sp"), default=None)),
                "field_size": _int_from(verdict_row.get("scored"), verdict_row.get("runner_count"), default=None),
                "field_band": field_band,
                "class_num": _int_from(top.get("class_num"), verdict_row.get("class_num"), default=None),
                "velo_prime_prob": _float_from(top.get("velo_prime_prob"), sigma.get("velo_prime_prob"), default=0.0),
                "market_deception_score": _float_from(top.get("market_deception_score"), default=0.0),
                "improvement_score": _float_from(top.get("improvement_score"), default=0.0),
                "place_prob": _float_from(top.get("place_prob"), default=0.0),
                "shadow_action": action,
                "shadow_evidence": shadow.get("evidence") or top.get("midprice_shadow_evidence") or "",
                "action_field_band": f"{action}|{field_band or 'UNKNOWN'}",
                "action_pick_odds_band": f"{action}|{_odds_band(sp_dec)}",
                "win_profit": _win_profit(sp_dec, won),
            }
            rows.append(row)

    overall_n = len(rows)
    overall_wins = sum(1 for r in rows if r["won"])
    overall_frames = sum(1 for r in rows if r["framed"])
    overall_mid_misses = sum(1 for r in rows if r.get("miss_class") == "mid_priced_won")

    summaries = {
        "by_shadow_action": _summarise(rows, "shadow_action"),
        "by_pick_odds_band": _summarise(rows, "pick_odds_band"),
        "by_winner_odds_band": _summarise(rows, "winner_odds_band"),
        "by_field_band": _summarise(rows, "field_band"),
        "by_tier": _summarise(rows, "tier"),
        "by_course": _summarise(rows, "course"),
        "by_action_field_band": _summarise(rows, "action_field_band"),
        "by_action_pick_odds_band": _summarise(rows, "action_pick_odds_band"),
    }

    payload = {
        "generated_at": _utc_now(),
        "start_date": start_date,
        "end_date": end_date,
        "source": "RP_SUPPORTED_SIGMA_PLUS_OLD_VELO_VERDICTS",
        "promotion_status": "PAPER_ONLY_NOT_FOR_PROMOTION",
        "live_scoring_changed": False,
        "racing_api_used": False,
        "minimum_n_for_markdown": minimum_n,
        "summary": {
            "rows_total": overall_n,
            "wins": overall_wins,
            "strike_rate": round(overall_wins / overall_n * 100, 2) if overall_n else 0.0,
            "frames": overall_frames,
            "frame_rate": round(overall_frames / overall_n * 100, 2) if overall_n else 0.0,
            "mid_priced_won_misses": overall_mid_misses,
            "mid_miss_rate": round(overall_mid_misses / overall_n * 100, 2) if overall_n else 0.0,
            "missing_verdicts": len(missing_verdicts),
        },
        "summaries": summaries,
        "missing_verdicts": missing_verdicts[:200],
        "rows": rows,
    }
    return payload


def _markdown(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        f"# Midprice Shadow Replay: {payload.get('start_date') or 'START'} to {payload.get('end_date') or 'END'}",
        f"Generated: {payload['generated_at']}",
        "",
        f"**Source:** `{payload['source']}`",
        f"**Promotion:** `{payload['promotion_status']}`",
        f"**Racing API used:** `{payload['racing_api_used']}`",
        "",
        "## Overall",
        "| Metric | Value |",
        "|---|---:|",
        f"| Rows matched | {s['rows_total']} |",
        f"| Wins | {s['wins']} |",
        f"| Strike rate | {s['strike_rate']}% |",
        f"| Frames | {s['frames']} |",
        f"| Frame rate | {s['frame_rate']}% |",
        f"| Mid-priced-winner misses | {s['mid_priced_won_misses']} |",
        f"| Mid miss rate | {s['mid_miss_rate']}% |",
        f"| Missing verdicts | {s['missing_verdicts']} |",
        "",
    ]

    for title, key, label in [
        ("By Shadow Action", "by_shadow_action", "shadow_action"),
        ("By Pick Odds Band", "by_pick_odds_band", "pick_odds_band"),
        ("By Winner Odds Band", "by_winner_odds_band", "winner_odds_band"),
        ("By Field Band", "by_field_band", "field_band"),
        ("By Tier", "by_tier", "tier"),
        ("By Action + Field Band", "by_action_field_band", "action_field_band"),
        ("By Action + Pick Odds Band", "by_action_pick_odds_band", "action_pick_odds_band"),
    ]:
        lines.extend([
            f"## {title}",
            "| Group | N | Wins | SR | Frames | Frame | Mid Misses | Mid Miss | Win P/L | ROI |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in _top(payload["summaries"].get(key, []), label, payload["minimum_n_for_markdown"]):
            lines.append(
                f"| {row[label]} | {row['n']} | {row['wins']} | {row['strike_rate']}% | "
                f"{row['frames']} | {row['frame_rate']}% | {row['mid_priced_won_misses']} | "
                f"{row['mid_miss_rate']}% | {row['win_pl_units']} | {row['win_roi_pct']}% |"
            )
        lines.append("")

    lines.extend([
        "## Boundary",
        "- Replay only. No scoring changes, no staking, no promotion.",
        "- Inputs are RP-supported Sigma outcomes and Old VÉLØ verdict artifacts.",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--minimum-n", type=int, default=10)
    args = parser.parse_args()

    payload = replay(args.start_date, args.end_date, args.minimum_n)
    start = args.start_date or "start"
    end = args.end_date or "end"
    slug = f"{start.replace('-', '_')}_to_{end.replace('-', '_')}"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"midprice_shadow_replay_{slug}.json"
    md_path = REPORT_DIR / f"midprice_shadow_replay_{slug}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    (REPORT_DIR / "midprice_shadow_replay_latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (REPORT_DIR / "midprice_shadow_replay_latest.md").write_text(
        _markdown(payload),
        encoding="utf-8",
    )

    s = payload["summary"]
    print(f"Written: {json_path}")
    print(f"Written: {md_path}")
    print(f"Rows: {s['rows_total']}  SR: {s['strike_rate']}%  Frame: {s['frame_rate']}%")
    print(f"Mid-priced-winner misses: {s['mid_priced_won_misses']} ({s['mid_miss_rate']}%)")
    print("Promotion: PAPER_ONLY_NOT_FOR_PROMOTION")


if __name__ == "__main__":
    main()
