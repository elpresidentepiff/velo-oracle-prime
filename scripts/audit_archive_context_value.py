#!/usr/bin/env python3
"""Audit archive-only RP context flags against known Sigma outcomes where available."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"
OUTCOME_BRIDGE_PATH = PARSED_ROOT / "rp_archive_outcome_bridge.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _sigma_outcomes(date: str) -> dict[str, dict[str, Any]]:
    payload = _load(ROOT / "data" / "sigma_results" / f"sigma_results_{date.replace('-', '_')}.json", {})
    rows = payload.get("learning_candidate_rows") or payload.get("raw_sigma_audits_preserved") or []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            horse = row.get("horse") or row.get("selection") or row.get("top_horse")
            if horse:
                out[_norm(horse)] = row
    return out


def _outcome_bridge_rows(start_date: str, end_date: str) -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load(OUTCOME_BRIDGE_PATH, {})
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in payload.get("rows") or []:
        date = row.get("race_date")
        if not date or date < start_date or date > end_date:
            continue
        if row.get("classification") != "OUTCOME_CONFIRMED":
            continue
        if (row.get("identity_confidence") or 0) < 0.86:
            continue
        out[(date, _norm(row.get("rp_horse_name")))] = row
    return out


def _is_win(row: dict[str, Any]) -> bool:
    if row.get("won") is not None:
        return row.get("won") is True
    value = str(row.get("result") or row.get("outcome") or row.get("finish_position") or "").lower()
    return value in {"win", "winner", "1", "1st", "won"} or row.get("won") is True


def _is_frame(row: dict[str, Any]) -> bool:
    if row.get("framed") is not None:
        return row.get("framed") is True
    value = str(row.get("result") or row.get("outcome") or row.get("finish_position") or "").lower()
    return _is_win(row) or value in {"frame", "placed", "place", "2", "2nd", "3", "3rd"} or row.get("framed") is True


def _signal_rows(dossier: dict[str, Any]) -> list[str]:
    signals = list(dossier.get("archive_flags") or [])
    if (dossier.get("tip_count") or 0) >= 7:
        signals.append("TIP_COUNT_HIGH")
    if dossier.get("headgear_first_time"):
        signals.append("FIRST_TIME_HEADGEAR")
    if dossier.get("wind_surgery"):
        signals.append("WIND_SURGERY")
    if dossier.get("entries"):
        signals.append("ENTRIES_PRESENT")
    return sorted(set(signals))


def build(start_date: str, end_date: str, execute: bool) -> dict[str, Any]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"sample": 0, "wins": 0, "frames": 0, "false_positive": 0})
    dates_checked = []
    outcome_bridge = _outcome_bridge_rows(start_date, end_date)
    for day in sorted(PARSED_ROOT.glob("20*-*-*")):
        date = day.name
        if date < start_date or date > end_date:
            continue
        dossiers = _load(day / "horse_dossiers.json", {}).get("dossiers") or []
        sigma = {horse: row for (row_date, horse), row in outcome_bridge.items() if row_date == date}
        if not sigma:
            continue
        dates_checked.append(date)
        for dossier in dossiers:
            outcome = sigma.get(_norm(dossier.get("horse")))
            if not outcome:
                continue
            for signal in _signal_rows(dossier):
                buckets[signal]["sample"] += 1
                if _is_win(outcome):
                    buckets[signal]["wins"] += 1
                if _is_frame(outcome):
                    buckets[signal]["frames"] += 1
                if not _is_frame(outcome):
                    buckets[signal]["false_positive"] += 1
    signals = []
    for signal, stats in sorted(buckets.items()):
        sample = stats["sample"]
        sr = stats["wins"] / sample if sample else 0.0
        fr = stats["frames"] / sample if sample else 0.0
        fp = stats["false_positive"] / sample if sample else 0.0
        if sample < 20:
            verdict = "INSUFFICIENT_SAMPLE"
        elif sr >= 0.20 or fr >= 0.45:
            verdict = "CONTEXT_VALUE_POSITIVE"
        elif fp >= 0.70:
            verdict = "TRAP_WARNING"
        else:
            verdict = "NOISE"
        signals.append({
            "signal": signal,
            "sample_size": sample,
            "strike_rate": round(sr, 4),
            "frame_rate": round(fr, 4),
            "false_positive_rate": round(fp, 4),
            "classification": verdict,
            "policy": "ARCHIVE_ONLY_KEEP" if verdict in {"NOISE", "INSUFFICIENT_SAMPLE"} else "SHADOW_RESEARCH_CANDIDATE",
        })
    payload = {
        "generated_at": _utc_now(),
        "start_date": start_date,
        "end_date": end_date,
        "dates_checked": dates_checked,
        "signal_count": len(signals),
        "scoring_impact": "NONE",
        "signals": signals,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_ROOT / "archive_context_value_latest.json"
        md_path = REPORT_ROOT / "archive_context_value_latest.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = ["# Archive Context Value Audit", "", f"- Dates checked: `{', '.join(dates_checked) or 'none'}`", f"- Signals: `{len(signals)}`", "- Scoring impact: `NONE`", ""]
        if not signals:
            lines.append("No overlapping RP dossier + Sigma outcome sample yet. Keep collecting; do not promote anything.")
        for row in signals:
            lines.append(f"- {row['signal']}: n={row['sample_size']} SR={row['strike_rate']:.1%} Frame={row['frame_rate']:.1%} FP={row['false_positive_rate']:.1%} => {row['classification']}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["json_path"] = str(json_path)
        payload["md_path"] = str(md_path)
    else:
        payload["status"] = "DRY_RUN"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit archive context value against Sigma outcomes.")
    parser.add_argument("--start-date", default="2026-05-25")
    parser.add_argument("--end-date", default="2026-05-25")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.start_date, args.end_date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
