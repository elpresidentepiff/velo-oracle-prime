#!/usr/bin/env python3
"""
VFU-24: First Prospective EW Watchlist Settlement — June 17 2026

Settles the VFU-23 June 17 watchlist against actual RP results.
PAPER-ONLY. No staking. No Supabase writes. No Telegram.

Governance:
  paper_only = True
  blocked_from_live_use = True
  No VP threshold change
  No model promotion
  No live scoring change
  No Supabase writes
  No Telegram
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = DATA / "reports"
RESULTS_DIR = DATA / "results"

VFU24_VERSION = "VFU_24_EW_SETTLEMENT_V1"
EW_STAKE = 1.0  # 1-unit EW = 2 units total


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _place_terms(field_size) -> tuple[int, int]:
    """Returns (n_places, divisor). Mirrors VFU-22 formula."""
    try:
        fs = int(float(field_size or 0))
    except (TypeError, ValueError):
        fs = 8
    if fs < 5:
        return 0, 4
    elif fs < 8:
        return 2, 4
    elif fs < 16:
        return 3, 4
    else:
        return 4, 5


def _ew_calc(sp_dec: float, position: int, field_size: int) -> dict:
    """
    Calculate EW settlement for a 1-unit EW bet.
    Returns dict with stake, win_return, place_return, ew_return, profit, outcome_label.
    """
    n_places, divisor = _place_terms(field_size)
    stake = EW_STAKE * 2

    if position == 1:
        outcome_label = "WIN"
        win_ret = EW_STAKE * sp_dec
        place_ret = (EW_STAKE + EW_STAKE * (sp_dec - 1) / divisor) if n_places > 0 else 0.0
        ew_ret = win_ret + place_ret
    elif n_places > 0 and position <= n_places:
        outcome_label = "PLACED"
        win_ret = 0.0
        place_ret = EW_STAKE + EW_STAKE * (sp_dec - 1) / divisor
        ew_ret = place_ret
    elif n_places == 0 and position > 1:
        outcome_label = "PLACED_NO_TERMS"
        win_ret = 0.0
        place_ret = 0.0
        ew_ret = 0.0
    else:
        outcome_label = "MISS"
        win_ret = 0.0
        place_ret = 0.0
        ew_ret = 0.0

    return {
        "ew_stake": round(stake, 4),
        "win_return": round(win_ret, 4),
        "place_return": round(place_ret, 4),
        "ew_return": round(ew_ret, 4),
        "ew_profit": round(ew_ret - stake, 4),
        "outcome_label": outcome_label,
        "ew_place_terms_apply": n_places > 0,
        "n_places": n_places,
        "divisor": divisor,
    }


def load_results_index(date_str: str, results_dir: pathlib.Path | None = None) -> dict:
    """Load RP results for a date, return {race_id: {horse_name: runner_dict}}."""
    d = results_dir or RESULTS_DIR
    date_key = date_str.replace("-", "_")
    path = d / f"rp_results_{date_key}.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    index: dict = {}
    for race in data.get("results", []):
        rid = race["race_id"]
        runners_by_name: dict = {}
        for rn in race.get("runners", []):
            name = (rn.get("horse") or "").strip()
            runners_by_name[name.lower()] = {
                "horse": name,
                "position": rn.get("position"),
                "sp_fractional": rn.get("sp"),
                "sp_decimal": rn.get("sp_dec"),
                "non_runner": rn.get("non_runner", False),
            }
        index[rid] = {
            "race_id": rid,
            "course": race.get("course", ""),
            "off": race.get("off", ""),
            "field_size": race.get("field_size", 0),
            "runners_by_name": runners_by_name,
        }
    return index


def settle_entry(entry: dict, results_index: dict) -> dict:
    """Match a watchlist entry to results and compute EW settlement."""
    race_id = entry["race_id"]
    horse_name = entry["horse_name"]

    settled = dict(entry)
    settled["settlement_status"] = "SETTLED"
    settled["paper_only"] = True
    settled["blocked_from_live_use"] = True

    if race_id not in results_index:
        settled["settlement_status"] = "RACE_NOT_FOUND"
        settled["settlement_note"] = f"Race {race_id} not in results file"
        return settled

    race_result = results_index[race_id]
    runner = race_result["runners_by_name"].get(horse_name.lower())

    if runner is None:
        settled["settlement_status"] = "HORSE_NOT_FOUND"
        settled["settlement_note"] = f"Horse '{horse_name}' not found in race {race_id}"
        return settled

    if runner.get("non_runner"):
        settled["settlement_status"] = "NON_RUNNER"
        settled["outcome"] = "NON_RUNNER"
        settled["finish_position"] = None
        settled["win_return"] = 0.0
        settled["place_return"] = 0.0
        settled["EW_return"] = 0.0
        settled["EW_profit"] = 0.0
        settled["ew_stake"] = 0.0
        return settled

    pos = runner["position"]
    sp_dec = runner["sp_decimal"]
    field_size = race_result["field_size"]

    try:
        position_int = int(pos)
    except (TypeError, ValueError):
        settled["settlement_status"] = "POSITION_PARSE_ERROR"
        settled["settlement_note"] = f"Cannot parse position: {pos!r}"
        return settled

    if sp_dec is None or sp_dec <= 0:
        settled["settlement_status"] = "SP_MISSING"
        settled["settlement_note"] = "sp_decimal not available"
        return settled

    calc = _ew_calc(float(sp_dec), position_int, field_size)

    settled["finish_position"] = position_int
    settled["sp_fractional"] = runner["sp_fractional"]
    settled["sp_decimal"] = sp_dec
    settled["results_field_size"] = field_size
    settled["outcome"] = calc["outcome_label"]
    settled["ew_stake"] = calc["ew_stake"]
    settled["win_return"] = calc["win_return"]
    settled["place_return"] = calc["place_return"]
    settled["EW_return"] = calc["ew_return"]
    settled["EW_profit"] = calc["ew_profit"]
    settled["ew_place_terms_apply"] = calc["ew_place_terms_apply"]
    settled["n_places"] = calc["n_places"]

    if not calc["ew_place_terms_apply"]:
        settled["governance_note"] = (
            f"Field size {field_size} < 5: no EW place terms apply. "
            "Consider adding field_size >= 5 filter to VFU-23 watchlist (VFU-25 scope)."
        )

    return settled


def settle_watchlist(
    date_str: str,
    template: dict,
    results_index: dict,
) -> dict:
    """Settle all entries in the template. Returns the full settled report dict."""
    entries = template.get("entries", [])
    settled_entries = [settle_entry(e, results_index) for e in entries]

    total_stake = sum(e.get("ew_stake", 0.0) for e in settled_entries)
    total_return = sum(e.get("EW_return", 0.0) for e in settled_entries)
    total_profit = total_return - total_stake
    roi = (total_profit / total_stake * 100) if total_stake else None

    counts = {
        "WIN": 0, "PLACED": 0, "PLACED_NO_TERMS": 0, "MISS": 0,
        "NON_RUNNER": 0, "SETTLED": 0, "ERRORS": 0,
    }
    for e in settled_entries:
        ol = e.get("outcome", e.get("settlement_status", ""))
        if ol in counts:
            counts[ol] += 1
        else:
            counts["ERRORS"] += 1
        if e.get("settlement_status") == "SETTLED":
            counts["SETTLED"] += 1

    day_verdict = (
        "WIN" if total_profit > 0 else
        "BREAK_EVEN" if abs(total_profit) < 0.05 else
        "LOSS"
    )

    return {
        "vfu": "VFU-24",
        "race_date": date_str,
        "settlement_run_at": _utc_now(),
        "version": VFU24_VERSION,
        "settlement_status": "SETTLED",
        "paper_only": True,
        "blocked_from_live_use": True,
        "no_supabase_writes": True,
        "no_telegram": True,
        "no_model_promotion": True,
        "no_vp_threshold_change": True,
        "no_live_scoring_change": True,
        "candidates_settled": len(settled_entries),
        "total_staked_units": round(total_stake, 4),
        "total_return_units": round(total_return, 4),
        "profit_units": round(total_profit, 4),
        "roi_pct": round(roi, 1) if roi is not None else None,
        "outcome_counts": counts,
        "day_verdict": day_verdict,
        "entries": settled_entries,
        "classifications": [
            "VFU_24_EW_SETTLEMENT_COMPLETE",
            "PAPER_ONLY_MODE_CONFIRMED",
            "NO_STAKING_EXECUTION",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM_BETTING_OUTPUT",
            "NO_MODEL_PROMOTION",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        ],
    }


def _md_report(report: dict) -> str:
    date = report["race_date"]
    roi = report["roi_pct"]
    roi_str = f"{roi:+.1f}%" if roi is not None else "n/a"
    entries = report["entries"]

    rows = []
    for e in entries:
        pos = e.get("finish_position", "?")
        sp = e.get("sp_fractional", "?")
        outcome = e.get("outcome", e.get("settlement_status", "?"))
        profit = e.get("EW_profit")
        profit_str = f"{profit:+.4f}" if profit is not None else "n/a"
        note = e.get("governance_note", "")
        rows.append(
            f"| {e['horse_name']} | {e['VP']:.4f} | {e['course']} {e['off_time']} "
            f"| {pos} | {sp} | {outcome} | {profit_str} | {note} |"
        )

    table = "\n".join(rows)
    governance_notes = [
        e.get("governance_note") for e in entries if e.get("governance_note")
    ]
    notes_block = "\n".join(f"- {n}" for n in governance_notes) or "None"

    return f"""# VFU-24: First Prospective EW Settlement — {date}

Generated: {report['settlement_run_at']}

## Day 1 Result

| Metric | Value |
|---|---|
| Candidates settled | {report['candidates_settled']} |
| Total staked (units) | {report['total_staked_units']} |
| Total return (units) | {report['total_return_units']} |
| Profit (units) | {report['profit_units']:+.4f} |
| ROI | {roi_str} |
| Day verdict | **{report['day_verdict']}** |

## Settlement Table (1-unit EW per horse)

| Horse | VP | Race | Pos | SP | Outcome | EW Profit | Note |
|---|---|---|---|---|---|---|---|
{table}

## Governance Notes

{notes_block}

## Governance

- `paper_only = True` — no funds at risk
- `blocked_from_live_use = True`
- NO Supabase writes
- NO Telegram
- NO model promotion
- NO VP threshold change
- NO live scoring change

## STOP

STOP — operator review required before VFU-25.
"""


def main(date_str: str = "2026-06-17") -> None:
    print(f"VFU-24: EW Settlement {date_str} — {_utc_now()}")

    template_path = REPORTS / "vfu_23_settlement_template.json"
    with open(template_path, encoding="utf-8") as fh:
        template = json.load(fh)
    print(f"Loaded template: {len(template['entries'])} entries")

    results_index = load_results_index(date_str)
    print(f"Loaded results index: {len(results_index)} races")

    report = settle_watchlist(date_str, template, results_index)

    print(f"\nSettlement summary:")
    for e in report["entries"]:
        outcome = e.get("outcome", e.get("settlement_status", "?"))
        sp = e.get("sp_fractional", "?")
        pos = e.get("finish_position", "?")
        profit = e.get("EW_profit")
        profit_str = f"{profit:+.4f}" if profit is not None else "n/a"
        note = " *** " + e.get("governance_note", "")[:60] if e.get("governance_note") else ""
        print(
            f"  {e['horse_name']:25} VP={e['VP']:.4f}  pos={str(pos):3}  SP={str(sp):8}"
            f"  {outcome:18}  EW_profit={profit_str}{note}"
        )

    print(f"\n  Total staked: {report['total_staked_units']} units")
    print(f"  Total return: {report['total_return_units']} units")
    print(f"  Profit:       {report['profit_units']:+.4f} units  ROI={report['roi_pct']}%")
    print(f"  Day verdict:  {report['day_verdict']}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS / f"vfu_24_ew_settlement_{date_str.replace('-', '_')}.json"
    out_md = REPORTS / f"vfu_24_settlement_report_{date_str.replace('-', '_')}.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(_md_report(report), encoding="utf-8")

    # Append to VFU-23 audit trail
    audit_path = REPORTS / "vfu_23_watchlist_audit_trail.jsonl"
    if audit_path.exists():
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event": "VFU_24_SETTLEMENT",
                "date": date_str,
                "settlement_run_at": report["settlement_run_at"],
                "day_verdict": report["day_verdict"],
                "roi_pct": report["roi_pct"],
                "profit_units": report["profit_units"],
                "paper_only": True,
                "blocked_from_live_use": True,
            }) + "\n")

    print(f"\nWritten: {out_json.name}  |  {out_md.name}")
    print(f"Classification: VFU_24_EW_SETTLEMENT_COMPLETE")


if __name__ == "__main__":
    main()
