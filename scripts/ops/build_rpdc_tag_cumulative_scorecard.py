#!/usr/bin/env python3
"""Build a cumulative, outcome-only RPDC tag matched-control scorecard.

The only input evidence is the daily report produced by
``evaluate_rpdc_tag_matched_controls.py`` from immutable pre-race tags and
settled results.  This script does not inspect raw race results, calculate a
new tag, estimate ROI, or affect scoring, promotion, routing, or execution.

At EOD the newest daily report is still local until artifact persistence runs.
It is included exactly once, replacing a persisted row for the same race date
if one exists.  This makes the cumulative card current without relying on a
stale next-day rebuild.
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
REPORT_VERSION = "rpdc_matched_control_cumulative_v1"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


def aggregate(daily_by_date: dict[str, dict[str, Any]], as_of_date: str) -> dict[str, Any]:
    """Aggregate only usable dated daily reports through ``as_of_date``.

    Results are sums of runner-level numerator and denominator counts, not an
    unweighted average of daily percentages.  Each tag remains a descriptive
    within-race comparison; a positive delta is not a causal or profitability
    claim.
    """
    totals: dict[str, dict[str, int]] = {}
    included_dates: list[str] = []
    excluded_dates: list[dict[str, str]] = []
    for date, report in sorted(daily_by_date.items()):
        if date > as_of_date:
            continue
        if not isinstance(report, dict) or report.get("status") != "OK":
            excluded_dates.append({"date": date, "reason": str((report or {}).get("status") or "MALFORMED_REPORT")})
            continue
        cards = report.get("tag_scorecards")
        if not isinstance(cards, list):
            excluded_dates.append({"date": date, "reason": "MALFORMED_TAG_SCORECARDS"})
            continue
        included_dates.append(date)
        for card in cards:
            if not isinstance(card, dict):
                continue
            tag = str(card.get("tag") or "").strip()
            treatment = card.get("treatment") if isinstance(card.get("treatment"), dict) else {}
            control = card.get("same_race_control") if isinstance(card.get("same_race_control"), dict) else {}
            if not tag:
                continue
            row = totals.setdefault(tag, {
                "report_days": 0, "treatment_n": 0, "treatment_wins": 0, "treatment_top_3": 0,
                "treatment_sp_covered": 0, "control_n": 0, "control_wins": 0, "control_top_3": 0,
            })
            row["report_days"] += 1
            row["treatment_n"] += _int(treatment.get("n"))
            row["treatment_wins"] += _int(treatment.get("wins"))
            row["treatment_top_3"] += _int(treatment.get("top_3"))
            row["treatment_sp_covered"] += _int(treatment.get("sp_decimal_coverage"))
            row["control_n"] += _int(control.get("n"))
            row["control_wins"] += _int(control.get("wins"))
            row["control_top_3"] += _int(control.get("top_3"))

    scorecards: list[dict[str, Any]] = []
    for tag in sorted(totals):
        row = totals[tag]
        treatment_win = _rate(row["treatment_wins"], row["treatment_n"])
        control_win = _rate(row["control_wins"], row["control_n"])
        treatment_top_3 = _rate(row["treatment_top_3"], row["treatment_n"])
        control_top_3 = _rate(row["control_top_3"], row["control_n"])
        scorecards.append({
            "tag": tag,
            "report_days": row["report_days"],
            "treatment": {
                "n": row["treatment_n"], "wins": row["treatment_wins"], "top_3": row["treatment_top_3"],
                "win_rate_pct": treatment_win, "top_3_rate_pct": treatment_top_3,
                "sp_decimal_coverage": row["treatment_sp_covered"],
                "sp_decimal_coverage_pct": _rate(row["treatment_sp_covered"], row["treatment_n"]),
            },
            "same_race_control": {
                "n": row["control_n"], "wins": row["control_wins"], "top_3": row["control_top_3"],
                "win_rate_pct": control_win, "top_3_rate_pct": control_top_3,
            },
            "delta_win_rate_pp": round(treatment_win - control_win, 1) if treatment_win is not None and control_win is not None else None,
            "delta_top_3_rate_pp": round(treatment_top_3 - control_top_3, 1) if treatment_top_3 is not None and control_top_3 is not None else None,
            "interpretation": "DESCRIPTIVE_ONLY_INSUFFICIENT_SAMPLE",
        })

    return {
        "report_version": REPORT_VERSION,
        "as_of_date": as_of_date,
        "status": "OK" if scorecards else "NO_SETTLED_TAG_EVIDENCE",
        "included_report_dates": included_dates,
        "excluded_report_dates": excluded_dates,
        "days_with_usable_evidence": len(included_dates),
        "tag_scorecards": scorecards,
        "guardrails": {
            "source": "daily_immutable_pre_race_tag_reports_only",
            "same_race_controls_only": True,
            "retrospective_retagging": "DISALLOWED",
            "roi_protocol": "NOT_RUN",
            "scoring_effect": "NONE",
            "promotion_effect": "NONE",
            "execution_effect": "NONE",
        },
    }


def _env() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return url, key


def _fetch_persisted_daily_reports() -> dict[str, dict[str, Any]]:
    url, key = _env()
    out: dict[str, dict[str, Any]] = {}
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            "artifact_type": "eq.rpdc_tag_matched_control", "select": "run_date,payload",
            "order": "run_date.asc", "limit": 1000, "offset": offset,
        }, safe=",")
        request = urllib.request.Request(
            f"{url}/rest/v1/velo_report_artifacts?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            rows = json.loads(response.read().decode("utf-8"))
        for row in rows:
            date = str(row.get("run_date") or "")
            payload = row.get("payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = None
            if date and isinstance(payload, dict):
                out[date] = payload
        if len(rows) < 1000:
            return out
        offset += len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--date", required=True, help="as-of race date YYYY-MM-DD")
    args = parser.parse_args()
    try:
        datetime.fromisoformat(args.date)
    except ValueError:
        raise SystemExit("--date must be YYYY-MM-DD") from None

    reports = _fetch_persisted_daily_reports()
    tag = args.date.replace("-", "_")
    local_path = ROOT / "data" / "reports" / f"rpdc_tag_matched_control_{tag}.json"
    if local_path.exists():
        try:
            local_report = json.loads(local_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"INVALID_CURRENT_DAILY_REPORT {local_path}: {exc}") from None
        if not isinstance(local_report, dict):
            raise SystemExit(f"INVALID_CURRENT_DAILY_REPORT {local_path}: expected JSON object")
        reports[args.date] = local_report

    report = aggregate(reports, args.date)
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["current_date_local_report_included"] = local_path.exists()
    output = ROOT / "data" / "reports" / f"rpdc_tag_matched_control_cumulative_{tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"RPDC TAG CUMULATIVE — {args.date}: {report['status']} ({len(report['tag_scorecards'])} tags / {report['days_with_usable_evidence']} days)")


if __name__ == "__main__":
    main()
