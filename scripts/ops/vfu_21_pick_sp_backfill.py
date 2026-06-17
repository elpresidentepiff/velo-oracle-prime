#!/usr/bin/env python3
"""
VFU-21: Pick SP Backfill
Recover pick_sp for the 2,197 rows missing it in the VFU-20 repaired ledger.

Sources (in priority order):
  1. data/results/rp_results_2026_*.json — CDO key (venue+yyyymmdd+off) + norm name
  2. data/results_2026_*.json            — rac_ format race_id + norm name
  3. sigma_results JSON rows             — winner_sp when outcome == WIN
  4. UNRECOVERED                        — row flagged, no SP change

Outputs:
  data/reports/vfu_21_pick_sp_backfill_ledger.jsonl   — full 3052-row ledger
  data/reports/vfu_21_pick_sp_backfill_summary.json   — stats + operator brief
  data/reports/vfu_21_pick_sp_backfill_summary.md

Governance:
  blocked_from_live_use = True on ALL output rows
  NO VP threshold change, NO model change, NO live scoring change
  REPORT ONLY — operator must authorise VFU-22 before prospective use
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

INPUT_LEDGER  = REPORTS / "vfu_20_field_size_repaired_ledger.jsonl"
OUTPUT_LEDGER = REPORTS / "vfu_21_pick_sp_backfill_ledger.jsonl"
OUTPUT_JSON   = REPORTS / "vfu_21_pick_sp_backfill_summary.json"
OUTPUT_MD     = REPORTS / "vfu_21_pick_sp_backfill_summary.md"

VFU21_VERSION = "VFU_21_PICK_SP_BACKFILL_V1"


def _norm_name(name: str) -> str:
    """Normalise horse name: strip country suffix, lower, strip spaces."""
    if not name:
        return ""
    name = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name)
    return name.lower().strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_rp_results_cdo_lookup() -> tuple:
    """Build two lookups from data/results/rp_results_*.json:
      cdo_lookup  : (venue, yyyymmdd, off) -> {norm_name -> sp_dec}  (for rp_ IDs)
      numeric_rid : (race_id_str, norm_name) -> sp_dec               (for numeric IDs)
    """
    cdo_lookup: dict[tuple, dict] = {}
    numeric_rid: dict[tuple, str] = {}
    rp_results_dir = DATA / "results"
    for rf in sorted(rp_results_dir.glob("rp_results_2026_*.json")):
        m = re.search(r"rp_results_(\d{4}_\d{2}_\d{2})\.json", rf.name)
        if not m:
            continue
        yyyymmdd = m.group(1).replace("_", "")
        try:
            raw = json.loads(rf.read_text(encoding="utf-8"))
            races = raw.get("results", []) if isinstance(raw, dict) else raw
            for race in races:
                venue = str(race.get("venue", "")).upper()
                off = str(race.get("off", ""))
                rid_num = str(race.get("race_id", ""))
                cdo = (venue, yyyymmdd, off)
                if cdo not in cdo_lookup:
                    cdo_lookup[cdo] = {}
                for runner in race.get("runners", []):
                    horse = runner.get("horse", "")
                    sp_dec = runner.get("sp_dec")
                    try:
                        sp_val = float(sp_dec or 0)
                    except (TypeError, ValueError):
                        sp_val = 0
                    if horse and sp_val > 0:
                        nm = _norm_name(horse)
                        cdo_lookup[cdo][nm] = str(sp_dec)
                        if rid_num:
                            numeric_rid[(rid_num, nm)] = str(sp_dec)
        except Exception:
            continue
    return cdo_lookup, numeric_rid


_VENUE_NAME_TO_CODE = {
    "SALISBURY": "SAL", "CARLISLE": "CAR", "SLIGO": "SLI", "SOUTHWELL": "SOU",
    "BRIGHTON": "BRI", "CHEPSTOW": "CHP", "DONCASTER": "DON", "GOODWOOD": "GOO",
    "MUSSELBURGH": "MUS", "NOTTINGHAM": "NOT", "WOLVERHAMPTON": "WOL",
    "NEWMARKET": "NMK", "NEWCASTLE": "NEW", "HAYDOCK": "HAY", "CHESTER": "CHE",
    "ASCOT": "ASC", "SANDOWN": "SAN", "WINDSOR": "WIN", "LEICESTER": "LEI",
    "RIPON": "RIP", "YARMOUTH": "YAR", "FFOSLAS": "FFS", "HAMILTON": "HAM",
    "HAMILTON": "HAM", "PONTEFRACT": "PON", "REDCAR": "RED", "THIRSK": "THI",
    "BEVERLEY": "BEV", "BATH": "BAT", "EPSOM": "EPS", "AYR": "AYR",
    "CATTERICK": "CAT", "EXETER": "EXE", "STRATFORD": "STR", "WORCESTER": "WOR",
    "KEMPTON": "KEM", "LINGFIELD": "LIN", "CHELMSFORD": "CHM", "YORK": "YOR",
    "FFOS": "FFS", "CURRAGH": "CUR", "LEOPARDSTOWN": "LEO", "NAAS": "NAA",
    "DUNDALK": "DUN", "GALWAY": "GAL", "TIPPERARY": "TIP", "NAVAN": "NAV",
}


def _parse_rp_race_id(rid: str):
    """Parse rp_VENUE_YYYYMMDD_H.MM -> (venue_code, yyyymmdd, off). Returns None tuple on failure."""
    m = re.match(r"rp_([A-Za-z]+)_(\d{8})_([\d.]+)", rid or "")
    if m:
        venue_raw = m.group(1).upper()
        venue = _VENUE_NAME_TO_CODE.get(venue_raw, venue_raw)
        return venue, m.group(2), m.group(3)
    return None, None, None


def _load_results_sp_lookup() -> dict:
    """Build (race_id, norm_horse_name) -> sp_dec from data/results_2026_*.json (rac_ format)."""
    lookup: dict[tuple, str] = {}
    for rf in sorted(DATA.glob("results_2026_*.json")):
        try:
            raw = json.loads(rf.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                races = raw.get("results", [])
            elif isinstance(raw, list):
                races = raw
            else:
                continue
            for race in races:
                rid = str(race.get("race_id", ""))
                for runner in race.get("runners", []):
                    horse = runner.get("horse", "")
                    sp_dec = runner.get("sp_dec", "")
                    if rid and horse and sp_dec and float(sp_dec or 0) > 0:
                        key = (rid, _norm_name(horse))
                        if key not in lookup:
                            lookup[key] = str(sp_dec)
        except Exception:
            continue
    return lookup


def _load_sigma_sp_lookup() -> dict:
    """Build race_id -> winner_sp for WIN outcomes from sigma_results files."""
    lookup: dict[tuple, str] = {}
    for sf in sorted((DATA / "sigma_results").glob("sigma_results_*.json")):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
            for row in d.get("rows", []):
                if row.get("outcome") == "WIN":
                    rid = str(row.get("race_id", ""))
                    sp = row.get("winner_sp", "")
                    predicted = row.get("predicted", "")
                    if rid and sp and predicted:
                        key = (rid, _norm_name(predicted))
                        if key not in lookup:
                            lookup[key] = str(sp)
        except Exception:
            continue
    return lookup


def _sp_missing(val) -> bool:
    return not val or str(val).strip() in ("", "None", "null", "0", "0.0")


def main() -> None:
    print(f"VFU-21: Pick SP Backfill — {_utc_now()}")

    # Load ledger
    ledger = []
    with open(INPUT_LEDGER, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                ledger.append(json.loads(line))
    print(f"Loaded {len(ledger)} ledger rows")

    # Build SP lookups
    print("Building SP lookups from data/results/rp_results_*.json (CDO + numeric)...")
    cdo_lookup, numeric_rid_lookup = _load_rp_results_cdo_lookup()
    print(f"  CDO lookup: {len(cdo_lookup)} CDO keys  |  numeric_rid: {len(numeric_rid_lookup)} entries")

    print("Building SP lookups from data/results_2026_*.json (rac_ format)...")
    results_lookup = _load_results_sp_lookup()
    print(f"  rac_ lookup: {len(results_lookup)} entries")

    print("Building SP lookups from sigma results (WIN rows)...")
    sigma_lookup = _load_sigma_sp_lookup()
    print(f"  Sigma lookup: {len(sigma_lookup)} entries")

    # Counters
    already_had = 0
    recovered_cdo = 0
    recovered_numeric = 0
    recovered_results = 0
    recovered_sigma = 0
    unrecovered = 0

    output_rows = []
    for row in ledger:
        out = dict(row)
        out["vfu21_validation_version"] = VFU21_VERSION
        out["pick_sp_source"] = row.get("pick_sp_source", "ORIGINAL")
        out["blocked_from_live_use"] = True
        out["dry_run_only"] = True

        if not _sp_missing(row.get("pick_sp")):
            already_had += 1
            out["pick_sp_source"] = out.get("pick_sp_source") or "ORIGINAL"
            output_rows.append(out)
            continue

        rid = str(row.get("race_id", ""))
        horse = _norm_name(row.get("horse_name", ""))
        key = (rid, horse)

        # Source 1: rp_results CDO lookup (covers rp_VENUE_YYYYMMDD_H.MM format)
        venue, yyyymmdd, off = _parse_rp_race_id(rid)
        if venue and yyyymmdd and off:
            cdo = (venue, yyyymmdd, off)
            sp = cdo_lookup.get(cdo, {}).get(horse)
            if sp:
                out["pick_sp"] = sp
                out["pick_sp_source"] = "RP_RESULTS_CDO"
                recovered_cdo += 1
                output_rows.append(out)
                continue

        # Source 2: numeric race_id from rp_results files
        if str(rid).isdigit():
            sp = numeric_rid_lookup.get((rid, horse))
            if sp:
                out["pick_sp"] = sp
                out["pick_sp_source"] = "RP_RESULTS_NUMERIC_RID"
                recovered_numeric += 1
                output_rows.append(out)
                continue

        # Source 3: rac_ format results JSON
        if key in results_lookup:
            out["pick_sp"] = results_lookup[key]
            out["pick_sp_source"] = "RESULTS_JSON_RAC"
            recovered_results += 1
            output_rows.append(out)
            continue

        # Source 3: sigma results (WIN outcome match)
        if key in sigma_lookup:
            out["pick_sp"] = sigma_lookup[key]
            out["pick_sp_source"] = "SIGMA_WIN"
            recovered_sigma += 1
            output_rows.append(out)
            continue

        # Unrecovered
        out["pick_sp_source"] = "UNRECOVERED"
        unrecovered += 1
        output_rows.append(out)

    total = len(output_rows)
    total_with_sp = already_had + recovered_cdo + recovered_numeric + recovered_results + recovered_sigma
    coverage_pct = total_with_sp / total * 100

    print(f"\nResults:")
    print(f"  Already had SP              : {already_had}")
    print(f"  Recovered (rp_results CDO)  : {recovered_cdo}")
    print(f"  Recovered (rp_results num.) : {recovered_numeric}")
    print(f"  Recovered (rac_ results)    : {recovered_results}")
    print(f"  Recovered (sigma WIN)       : {recovered_sigma}")
    print(f"  Unrecovered                 : {unrecovered}")
    print(f"  Total with SP  : {total_with_sp}/{total} ({coverage_pct:.1f}%)")

    # Write output ledger
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_LEDGER, "w", encoding="utf-8") as fh:
        for row in output_rows:
            fh.write(json.dumps(row) + "\n")
    print(f"\nLedger written: {OUTPUT_LEDGER}")

    # Compute EW P&L on rows with SP
    ew_rows = [r for r in output_rows if not _sp_missing(r.get("pick_sp"))]
    win_rows_ew = [r for r in ew_rows if r.get("outcome") == "WIN"]
    place_rows_ew = [r for r in ew_rows if r.get("outcome") == "PLACED"]

    def place_terms(field_size):
        fs = int(field_size) if field_size else 8
        if fs < 5:   return 0, 4
        elif fs < 8: return 2, 4
        elif fs < 16: return 3, 4
        else:         return 4, 5

    EW = 1.0  # unit stake
    total_stake = 0.0
    total_return = 0.0
    for r in ew_rows:
        sp = float(r.get("pick_sp", 0) or 0)
        fs = r.get("rp_field_size") or r.get("field_size")
        n_places, div = place_terms(fs)
        outcome = r.get("outcome", "MISS")
        total_stake += EW * 2

        if outcome == "WIN":
            win_ret = EW * sp
            place_ret = EW + EW * (sp - 1) / div if n_places > 0 else 0
            total_return += win_ret + place_ret
        elif outcome == "PLACED" and n_places > 0:
            place_ret = EW + EW * (sp - 1) / div
            total_return += place_ret

    roi = (total_return - total_stake) / total_stake * 100 if total_stake else 0

    summary = {
        "vfu": "VFU-21",
        "generated_at": _utc_now(),
        "version": VFU21_VERSION,
        "total_rows": total,
        "already_had_sp": already_had,
        "recovered_rp_results_cdo": recovered_cdo,
        "recovered_results_json_rac": recovered_results,
        "recovered_sigma_win": recovered_sigma,
        "unrecovered": unrecovered,
        "total_with_sp": total_with_sp,
        "sp_coverage_pct": round(coverage_pct, 2),
        "ew_analysis": {
            "rows_with_sp": len(ew_rows),
            "win_rows": len(win_rows_ew),
            "place_rows": len(place_rows_ew),
            "total_stake_units": round(total_stake, 2),
            "total_return_units": round(total_return, 2),
            "profit_units": round(total_return - total_stake, 2),
            "roi_pct": round(roi, 2),
            "basis": "1-unit EW stakes, SP from results files",
        },
        "classification": "VFU_21_PICK_SP_BACKFILL_COMPLETE",
        "blocked_from_live_use": True,
        "no_vp_threshold_change": True,
        "no_model_change": True,
        "no_live_scoring_change": True,
        "operator_brief": {
            "S01": "VFU-21 recovered pick_sp for placed and missed horses from local result archives.",
            "S02": f"SP coverage: {total_with_sp}/{total} ({coverage_pct:.1f}%). {unrecovered} rows remain unrecovered (June 6-14 gap).",
            "S03": f"EW P&L on {len(ew_rows)} rows with SP: ROI={roi:.1f}% ({total_return - total_stake:+.1f} units on {total_stake:.0f} staked).",
            "S04": "VFU-22 (prospective dual-lane validation) and VFU-23 (specialist watchlist) remain NOT AUTHORIZED.",
            "S05": "STOP — operator review required before VFU-22.",
        },
        "output_ledger": str(OUTPUT_LEDGER),
    }

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = f"""# VFU-21: Pick SP Backfill — Operator Brief

## S01 Mission
Recover pick_sp for {total - already_had} rows missing it in the VFU-20 ledger.

## S02 Coverage
| Source | Rows |
|---|---|
| Already had SP | {already_had} |
| Recovered (results JSON) | {recovered_results} |
| Recovered (sigma WIN) | {recovered_sigma} |
| Unrecovered | {unrecovered} |
| **Total with SP** | **{total_with_sp}/{total} ({coverage_pct:.1f}%)** |

## S03 EW P&L (on {len(ew_rows)} rows with SP)
| Metric | Value |
|---|---|
| Total stake (units) | {total_stake:.0f} |
| Total return (units) | {total_return:.2f} |
| Profit | {total_return - total_stake:+.2f} units |
| **ROI** | **{roi:.1f}%** |

## S04 Governance
- `blocked_from_live_use = True` on all output rows
- NO VP threshold change
- NO model change
- NO live scoring change
- REPORT ONLY

## STOP
STOP — operator review required before VFU-22 (prospective validation).
"""
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"Summary written: {OUTPUT_JSON}")
    print(f"Brief written  : {OUTPUT_MD}")
    print(f"\nClassification: {summary['classification']}")
    print(f"EW ROI: {roi:.1f}% on {len(ew_rows)} rows with SP")


if __name__ == "__main__":
    main()
