#!/usr/bin/env python3
"""Prime vs FormFav vs their blend vs the starting price, on identical UK/Irish races.

Read-only. Reads Supabase over REST, writes one JSON report under data/reports and prints a
table. It scores nothing live, changes no weight and feeds no model. Runs anywhere the Supabase
service key is set (Railway, GitHub Actions); nothing is read from a local archive.

    PYTHONPATH=. python scripts/research/formfav_head_to_head.py --from 2026-10-12 --to 2026-11-14

The rules (pre-off predictions only, identical fields, Racing Post results) are in
src/velo/formfav_head_to_head.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo import formfav_head_to_head as h2h  # noqa: E402

PAGE = 1000


def _get(table: str, params: dict[str, str]) -> list[dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
    rows: list[dict] = []
    offset = 0
    while True:
        response = requests.get(
            f"{url}/rest/v1/{table}",
            params={**params, "limit": str(PAGE), "offset": str(offset)},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=120,
        )
        response.raise_for_status()
        chunk = response.json()
        rows.extend(chunk)
        if len(chunk) < PAGE:
            return rows
        offset += PAGE


def _chunks(values: list[str], size: int = 40) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch(date_from: str, date_to: str) -> dict[str, list[dict]]:
    window = f"(date.gte.{date_from},date.lte.{date_to})"
    velo_races = _get("races", {"select": "race_id,course,date,time", "and": window, "order": "race_id.asc"})
    formfav_races = _get(
        "formfav_races",
        {
            "select": "provider_race_key,race_date,country,track,start_time",
            "and": f"(race_date.gte.{date_from},race_date.lte.{date_to})",
            "country": "in.(gb,ie,GB,IE)",
            "order": "provider_race_key.asc",
        },
    )
    race_ids = sorted({str(r["race_id"]) for r in velo_races})
    verdicts: list[dict] = []
    for chunk in _chunks(race_ids, 25):  # full_analysis is large
        verdicts.extend(
            _get(
                "velo_verdicts",
                {"select": "race_id,generated_at,full_analysis", "race_id": f"in.({','.join(chunk)})", "order": "id.asc"},
            )
        )
    predictions: list[dict] = []
    for chunk in _chunks(sorted(r["provider_race_key"] for r in formfav_races)):
        quoted = ",".join(f'"{key}"' for key in chunk)
        predictions.extend(
            _get(
                "formfav_predictions",
                {"select": "provider_race_key,predictions_payload", "provider_race_key": f"in.({quoted})",
                 "order": "provider_race_key.asc"},
            )
        )
    results = _get(
        "racing_horse_runs",
        {
            "select": "race_id,horse,position_int,sp_dec",
            "and": f"(run_date.gte.{date_from},run_date.lte.{date_to})",
            "order": "id.asc",
        },
    )
    # Market snapshots are facts (prices), not provider opinions. Only the columns needed are read.
    snapshots: list[dict] = []
    for chunk in _chunks(sorted(r["provider_race_key"] for r in formfav_races), 10):
        quoted = ",".join(f'"{key}"' for key in chunk)
        snapshots.extend(
            _get(
                "formfav_market_snapshots",
                {"select": "provider_race_key,captured_at,horse_name,best_win", "provider_race_key": f"in.({quoted})",
                 "order": "id.asc"},
            )
        )
    return {"velo_races": velo_races, "formfav_races": formfav_races, "verdicts": verdicts,
            "predictions": predictions, "results": results, "snapshots": snapshots}


def render(report: dict) -> str:
    lines = [f"{'model':<18}{'races':>6}{'top pick %':>12}{'in top 3 %':>12}{'ROI at SP %':>13}{'log loss':>10}"]
    for model, row in report["metrics"].items():
        lines.append(
            f"{model:<18}{row['races']:>6}{row['top1_pct']!s:>12}{row['winner_in_top3_pct']!s:>12}"
            f"{row['roi_at_sp_pct']!s:>13}{row['winner_log_loss']!s:>10}"
        )
    lines += ["", f"coverage: {json.dumps(report['coverage'])}", f"Prime vs blend: {json.dumps(report['prime_vs_blend'])}",
              f"agreement: {json.dumps(report['agreement'])}"]
    priced = report.get("obtainable_prices")
    if priced:
        lines += ["", f"at the best price 10 minutes before the off: {priced['races_with_full_prices']} races, "
                  f"average book {priced['avg_book_at_t10']}",
                  f"{'model':<18}{'ROI at T-10 %':>14}{'ROI at SP %':>13}{'beat close %':>14}{'share beating':>15}"]
        for model in h2h.MODELS:
            row = priced[model]
            lines.append(f"{model:<18}{row['roi_at_t10_pct']!s:>14}{row['roi_at_sp_pct_same_races']!s:>13}"
                         f"{row['avg_beat_close_pct']!s:>14}{row['beat_close_share_pct']!s:>15}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    report = h2h.evaluate(**fetch(args.date_from, args.date_to))
    report["window"] = {"from": args.date_from, "to": args.date_to}
    out = ROOT / "data" / "reports" / f"formfav_head_to_head_{args.date_from}_{args.date_to}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(render(report))
    print(f"\nreport: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
