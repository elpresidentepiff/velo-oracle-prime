"""Forward-only monitor for the frozen Prime + exactly-one-dissenter hypothesis.

Research only.  It reads settled canonical scorecards, writes a report, and has
no scoring, staking, learning, weighting, promotion, or Supabase write path.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reports"
FROZEN_AFTER = "2026-11-03"
HYPOTHESIS_VERSION = "prime_plus_four_of_five_v1"
PRIME = "MAIN_VELO_PRIME"
COMPARATORS = (
    "MDS_HEAVY_SHADOW_V1",
    "MARKET_BLIND_CORE_SHADOW_V1",
    "CHAMPION_INTENT_SHADOW",
    "NEW_BUILD_LANE_A_MODEL",
    "NEW_BUILD_LANE_B_MODEL",
)


def _fetch_rows(start: str, end: str) -> list[dict]:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    models = ",".join((PRIME, *COMPARATORS))
    query = {
        "select": "run_date,race_id,course,off_time,model_name,rank,horse,settled_sp_dec,sp_dec,result_position,win,frame,official_evaluation_eligible",
        "model_name": f"in.({models})",
        "rank": "eq.1",
        "and": f"(run_date.gte.{start},run_date.lte.{end})",
        "order": "run_date.asc,race_id.asc,model_name.asc",
        "limit": "10000",
    }
    request = urllib.request.Request(
        f"{url}/rest/v1/canonical_model_scorecards?{urllib.parse.urlencode(query)}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Canonical scorecard query returned a non-list payload")
    return payload


def build_cohort(rows: list[dict]) -> dict:
    grouped: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for row in rows:
        grouped[(str(row.get("run_date")), str(row.get("race_id")))][str(row.get("model_name"))] = row

    eligible: list[dict] = []
    incomplete = 0
    for (run_date, race_id), by_model in sorted(grouped.items()):
        if PRIME not in by_model or any(model not in by_model for model in COMPARATORS):
            incomplete += 1
            continue
        prime = by_model[PRIME]
        if prime.get("official_evaluation_eligible") is False:
            continue
        prime_horse = str(prime.get("horse") or "").strip().casefold()
        agreeing = [
            model for model in COMPARATORS if str(by_model[model].get("horse") or "").strip().casefold() == prime_horse
        ]
        dissenting = [model for model in COMPARATORS if model not in agreeing]
        if len(agreeing) != 4:
            continue
        settled = prime.get("result_position") is not None or bool(prime.get("win")) or bool(prime.get("frame"))
        sp = float(prime.get("settled_sp_dec") or prime.get("sp_dec") or 0.0)
        eligible.append(
            {
                "run_date": run_date,
                "race_id": race_id,
                "course": prime.get("course"),
                "off_time": prime.get("off_time"),
                "horse": prime.get("horse"),
                "agreeing_models": agreeing,
                "dissenting_model": dissenting[0],
                "settled": settled,
                "win": bool(prime.get("win")) if settled else None,
                "frame": bool(prime.get("frame")) if settled else None,
                "settled_sp_dec": sp if settled else None,
                "profit_1u": (sp - 1.0 if prime.get("win") else -1.0) if settled else None,
            }
        )

    settled_rows = [row for row in eligible if row["settled"]]
    profit = sum(float(row["profit_1u"]) for row in settled_rows)
    return {
        "hypothesis_version": HYPOTHESIS_VERSION,
        "frozen_after": FROZEN_AFTER,
        "definition": "Prime top pick matched by exactly four of five frozen comparator models",
        "comparator_models": list(COMPARATORS),
        "complete_races_checked": len(grouped) - incomplete,
        "incomplete_model_sets": incomplete,
        "eligible_races": len(eligible),
        "settled_races": len(settled_rows),
        "wins": sum(1 for row in settled_rows if row["win"]),
        "frames": sum(1 for row in settled_rows if row["frame"]),
        "profit_1u": round(profit, 2),
        "roi_pct": round((profit / len(settled_rows)) * 100, 2) if settled_rows else None,
        "rows": eligible,
        "status": "PAPER_SHADOW_ONLY_NO_PROMOTION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-11-04")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--output", default="one_dissenter_forward_monitor.json")
    args = parser.parse_args()
    if args.start <= FROZEN_AFTER:
        raise SystemExit(f"Forward monitor start must be after frozen date {FROZEN_AFTER}")
    report = build_cohort(_fetch_rows(args.start, args.end))
    DATA.mkdir(parents=True, exist_ok=True)
    output = DATA / args.output
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
