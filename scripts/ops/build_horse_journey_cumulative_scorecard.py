#!/usr/bin/env python3
"""Aggregate immutable daily Horse Journey matched-control reports.

This is an outcome-only shadow scorecard.  It reads persisted daily reports
only, never recomputes tags, never inspects post-race inputs to create a new
signal, and cannot affect Prime, learning, promotion, routing or staking.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
REPORT_VERSION = "horse_journey_matched_control_cumulative_v1"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rate(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def aggregate(daily_by_date: dict[str, dict[str, Any]], as_of_date: str) -> dict[str, Any]:
    """Sum runner counts from usable reports through the requested date only."""
    totals: dict[str, dict[str, int]] = {}
    included: list[str] = []
    excluded: list[dict[str, str]] = []
    for date, report in sorted(daily_by_date.items()):
        if date > as_of_date:
            continue
        if not isinstance(report, dict) or report.get("status") != "OK":
            excluded.append({"date": date, "reason": str((report or {}).get("status") or "MALFORMED_REPORT")})
            continue
        cards = report.get("tag_scorecards")
        if not isinstance(cards, list):
            excluded.append({"date": date, "reason": "MALFORMED_TAG_SCORECARDS"})
            continue
        included.append(date)
        for card in cards:
            if not isinstance(card, dict) or not str(card.get("tag") or "").strip():
                continue
            tag = str(card["tag"]).strip()
            treatment = card.get("treatment") if isinstance(card.get("treatment"), dict) else {}
            control = card.get("same_race_control") if isinstance(card.get("same_race_control"), dict) else {}
            row = totals.setdefault(tag, {"report_days": 0, "tn": 0, "tw": 0, "tt": 0, "cn": 0, "cw": 0, "ct": 0})
            row["report_days"] += 1
            for key, source, field in (("tn", treatment, "n"), ("tw", treatment, "wins"), ("tt", treatment, "top_3"), ("cn", control, "n"), ("cw", control, "wins"), ("ct", control, "top_3")):
                row[key] += _int(source.get(field))
    cards: list[dict[str, Any]] = []
    for tag, row in sorted(totals.items()):
        tw, cw, tt, ct = _rate(row["tw"], row["tn"]), _rate(row["cw"], row["cn"]), _rate(row["tt"], row["tn"]), _rate(row["ct"], row["cn"])
        cards.append({"tag": tag, "report_days": row["report_days"], "treatment": {"n": row["tn"], "wins": row["tw"], "top_3": row["tt"], "win_rate_pct": tw, "top_3_rate_pct": tt}, "same_race_control": {"n": row["cn"], "wins": row["cw"], "top_3": row["ct"], "win_rate_pct": cw, "top_3_rate_pct": ct}, "delta_win_rate_pp": round(tw-cw,1) if tw is not None and cw is not None else None, "delta_top_3_rate_pp": round(tt-ct,1) if tt is not None and ct is not None else None, "interpretation": "DESCRIPTIVE_ONLY_INSUFFICIENT_SAMPLE"})
    return {"report_version": REPORT_VERSION, "as_of_date": as_of_date, "status": "OK" if cards else "NO_SETTLED_JOURNEY_EVIDENCE", "included_report_dates": included, "excluded_report_dates": excluded, "days_with_usable_evidence": len(included), "tag_scorecards": cards, "guardrails": {"source": "daily_immutable_pre_off_journey_reports_only", "same_race_controls_only": True, "retrospective_retagging": "DISALLOWED", "scoring_effect": "NONE", "learning_effect": "NONE", "promotion_effect": "NONE", "execution_effect": "NONE"}}


def _fetch_reports() -> dict[str, dict[str, Any]]:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    query = urllib.parse.urlencode({"artifact_type": "eq.horse_journey_matched_control", "select": "run_date,payload", "order": "run_date.asc"}, safe=",")
    request = urllib.request.Request(f"{url}/rest/v1/velo_report_artifacts?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = json.loads(response.read().decode("utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = row.get("payload")
        if isinstance(payload, str):
            try: payload = json.loads(payload)
            except json.JSONDecodeError: payload = None
        if isinstance(payload, dict) and row.get("run_date"):
            out[str(row["run_date"])] = payload
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); parser.add_argument("--date", required=True); args = parser.parse_args()
    try: datetime.fromisoformat(args.date)
    except ValueError: raise SystemExit("--date must be YYYY-MM-DD") from None
    reports = _fetch_reports(); tag = args.date.replace("-", "_")
    local = ROOT / "data" / "reports" / f"horse_journey_matched_control_{tag}.json"
    if local.exists(): reports[args.date] = json.loads(local.read_text(encoding="utf-8"))
    report = aggregate(reports, args.date); report["generated_at"] = datetime.now(UTC).isoformat(); report["current_date_local_report_included"] = local.exists()
    output = ROOT / "data" / "reports" / f"horse_journey_matched_control_cumulative_{tag}.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"HORSE JOURNEY CUMULATIVE — {args.date}: {report['status']} ({len(report['tag_scorecards'])} tags / {report['days_with_usable_evidence']} days)")


if __name__ == "__main__": main()
