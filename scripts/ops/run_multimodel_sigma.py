#!/usr/bin/env python3
"""
Multi-Model Sigma — tracks Old VELO, No-RPR, and New Build independently.

Run AFTER run_results_sigma.py so sigma_results_{date}.json exists.

Usage:
    python scripts/ops/run_multimodel_sigma.py --date 2026-06-20 [--execute]

--execute  appends to the ledger CSV (default: dry-run print only)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

LEDGER_PATH = ROOT / "data" / "model_comparison_ledger.csv"
LEDGER_COLS = [
    "date", "race_id", "course", "off",
    "velo_top_pick", "velo_outcome", "velo_assigned_product", "velo_ew_outcome",
    "norpr_top_pick", "norpr_prob", "norpr_outcome",
    "nb_top_pick", "nb_prob", "nb_outcome",
    "winner", "top3",
]


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def _outcome(pick: str | None, winner: str, top3: list[str]) -> str:
    if not pick:
        return "NO_DATA"
    p = _norm(pick)
    if p == _norm(winner):
        return "WIN"
    if any(p == _norm(h) for h in top3):
        return "PLACE"
    return "MISS"


def _load_sigma(date_str: str) -> list[dict]:
    path = ROOT / "data" / "sigma_results" / f"sigma_results_{date_str.replace('-','_')}.json"
    if not path.exists():
        path = ROOT / "data" / "sigma_results" / f"sigma_results_{date_str}.json"
    if not path.exists():
        raise FileNotFoundError(f"Sigma results not found for {date_str}")
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("rows", [])


def _load_rp_results(date_str: str) -> dict[str, dict]:
    """Returns {race_id: {winner, top3_names}} from RP results JSON."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "results" / f"rp_results_{date_tag}.json"
    if not path.exists():
        path = ROOT / "data" / "results" / f"rp_results_{date_str}.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    results = d.get("results", [])
    index: dict[str, dict] = {}
    for r in results:
        rid = str(r.get("race_id", ""))
        if rid:
            index[rid] = {
                "winner": r.get("winner_horse", ""),
                "top3": r.get("top3_names", []),
            }
    return index


def _load_supabase_predictions(date_str: str) -> dict[str, list[dict]]:
    """Returns {race_id: [runner_pred_dicts]} from Supabase velo_verdicts."""
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        rows = (
            sb.table("velo_verdicts")
            .select("race_id, full_analysis")
            .gte("generated_at", f"{date_str}T00:00:00")
            .lte("generated_at", f"{date_str}T23:59:59")
            .execute()
        )
        result: dict[str, list[dict]] = {}
        for row in rows.data or []:
            rid = str(row.get("race_id", ""))
            fa = row.get("full_analysis") or {}
            preds = fa.get("predictions", []) if isinstance(fa, dict) else []
            if rid and preds:
                result[rid] = preds
        return result
    except Exception as e:
        print(f"  [WARN] Supabase unavailable: {e}")
        return {}


def _load_nb_scorecards(date_str: str) -> dict[str, dict]:
    """Returns {race_id: {horse, prob}} for Lane A top pick from NB report."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "new_build" / "reports" / f"two_lane_readiness_{date_tag}.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for sc in d.get("race_day_scorecards", []):
        rid = str(sc.get("race_id", ""))
        top3 = sc.get("lane_a_top3", [])
        if rid and top3:
            result[rid] = {
                "horse": top3[0].get("horse"),
                "prob": top3[0].get("prob"),
            }
    return result


def _no_rpr_top_pick(preds: list[dict]) -> tuple[str | None, float | None]:
    best = max(
        preds,
        key=lambda p: float(p.get("sqpe_no_rpr_shadow_prob") or 0),
        default=None,
    )
    if best is None:
        return None, None
    return best.get("horse"), float(best.get("sqpe_no_rpr_shadow_prob") or 0)


def _print_summary(rows: list[dict]) -> None:
    models = [
        ("Old VELO", "velo_outcome"),
        ("No-RPR",   "norpr_outcome"),
        ("New Build","nb_outcome"),
    ]
    print("\n  +-----------------------------------------------------+")
    print(  "  |  MULTI-MODEL SIGMA SUMMARY                          |")
    print(  "  +------------+-------+-------+-------+---------------+")
    print(  "  |  Model     |  n    |  WIN  | PLACE |   SR   Frame  |")
    print(  "  +------------+-------+-------+-------+---------------+")
    for label, col in models:
        vals = [r[col] for r in rows if r[col] not in ("NO_DATA", "")]
        n = len(vals)
        if n == 0:
            print(f"  |  {label:<10}|  n/a  |  n/a  |  n/a  |  n/a          |")
            continue
        wins   = sum(1 for v in vals if v == "WIN")
        places = sum(1 for v in vals if v in ("WIN", "PLACE"))
        sr     = wins / n
        frame  = places / n
        print(f"  |  {label:<10}|  {n:<5}|  {wins:<5}|  {places:<5}|  {sr:.1%}   {frame:.1%}  |")
    print(  "  +------------+-------+-------+-------+---------------+")

    # EW_CANDIDATE split for Old VELO
    ew_rows = [r for r in rows if r.get("velo_assigned_product") == "EW_CANDIDATE"]
    win_rows = [r for r in rows if r.get("velo_assigned_product") == "WIN_ONLY"]
    if ew_rows or win_rows:
        print()
        print("  VELO PRODUCT SPLIT:")
        if win_rows:
            wo_wins = sum(1 for r in win_rows if r.get("velo_outcome") == "WIN")
            wo_sr = wo_wins / len(win_rows)
            print(f"    WIN_ONLY   n={len(win_rows):3d}  wins={wo_wins:3d}  SR={wo_sr:.1%}")
        if ew_rows:
            ew_placed = sum(1 for r in ew_rows if r.get("velo_ew_outcome") in ("EW_WIN", "EW_PLACE"))
            ew_won = sum(1 for r in ew_rows if r.get("velo_ew_outcome") == "EW_WIN")
            ew_pr = ew_placed / len(ew_rows)
            print(f"    EW_CAND    n={len(ew_rows):3d}  placed={ew_placed:3d}  place%={ew_pr:.1%}  wins={ew_won}")
        unknown_n = sum(1 for r in rows if r.get("velo_assigned_product", "UNKNOWN") not in ("WIN_ONLY", "EW_CANDIDATE", "FRAME_ONLY", "VISION_ONLY", "PASS"))
        if unknown_n:
            print(f"    UNKNOWN    n={unknown_n:3d}  (pre-fix rows — no assigned_product stored)")


def run(date_str: str, execute: bool = False) -> list[dict]:
    print(f"\nMULTI-MODEL SIGMA — {date_str}")
    print("=" * 50)

    sigma_rows = _load_sigma(date_str)
    rp_results = _load_rp_results(date_str)
    sb_preds   = _load_supabase_predictions(date_str)
    nb_cards   = _load_nb_scorecards(date_str)

    print(f"  Sigma rows : {len(sigma_rows)}")
    print(f"  RP results : {len(rp_results)} races")
    print(f"  Supabase   : {len(sb_preds)} races")
    print(f"  New Build  : {len(nb_cards)} races")

    new_rows: list[dict] = []

    for sr in sigma_rows:
        race_id = str(sr.get("race_id", ""))
        result  = rp_results.get(race_id, {})
        winner  = result.get("winner", "")
        top3    = result.get("top3", [])

        # Old VELO: sigma already has the top pick + outcome
        # sigma uses "PLACED" — normalise to "PLACE" for consistency
        velo_pick    = sr.get("predicted", "")
        _raw_outcome = sr.get("outcome", "MISS")
        velo_outcome = "PLACE" if _raw_outcome == "PLACED" else _raw_outcome
        velo_assigned_product = sr.get("assigned_product", "UNKNOWN")
        velo_ew_outcome = sr.get("ew_outcome", "")

        # No-RPR: highest sqpe_no_rpr_shadow_prob in Supabase
        norpr_pick, norpr_prob, norpr_outcome = None, None, "NO_DATA"
        if race_id in sb_preds:
            norpr_pick, norpr_prob = _no_rpr_top_pick(sb_preds[race_id])
            if winner:
                norpr_outcome = _outcome(norpr_pick, winner, top3)

        # New Build: lane_a_top3[0]
        nb_entry = nb_cards.get(race_id, {})
        nb_pick  = nb_entry.get("horse")
        nb_prob  = nb_entry.get("prob")
        nb_outcome = "NO_DATA"
        if nb_pick and winner:
            nb_outcome = _outcome(nb_pick, winner, top3)

        row = {
            "date":          date_str,
            "race_id":       race_id,
            "course":        sr.get("course", ""),
            "off":           sr.get("off", ""),
            "velo_top_pick": velo_pick,
            "velo_outcome":  velo_outcome,
            "velo_assigned_product": velo_assigned_product,
            "velo_ew_outcome": velo_ew_outcome or "",
            "norpr_top_pick": norpr_pick or "",
            "norpr_prob":    round(norpr_prob, 4) if norpr_prob else "",
            "norpr_outcome": norpr_outcome,
            "nb_top_pick":   nb_pick or "",
            "nb_prob":       round(nb_prob, 4) if nb_prob else "",
            "nb_outcome":    nb_outcome,
            "winner":        winner,
            "top3":          "|".join(top3),
        }
        new_rows.append(row)

        agree = sum([
            _norm(velo_pick) == _norm(norpr_pick) if norpr_pick else False,
            _norm(velo_pick) == _norm(nb_pick) if nb_pick else False,
            _norm(norpr_pick) == _norm(nb_pick) if (norpr_pick and nb_pick) else False,
        ])
        status = f"V:{velo_outcome[0]} N:{norpr_outcome[0]} B:{nb_outcome[0]}"
        print(f"  {race_id} {sr.get('course',''):12} {sr.get('off',''):5}  {status}")

    _print_summary(new_rows)

    if execute:
        # Load existing rows, deduplicate before writing
        existing: list[dict] = []
        if LEDGER_PATH.exists():
            with open(LEDGER_PATH, newline="", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))
        existing_keys = {(r["date"], r["race_id"]) for r in existing}
        added = [r for r in new_rows if (r["date"], r["race_id"]) not in existing_keys]
        all_rows_out = existing + added
        with open(LEDGER_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS, restval="", extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows_out)
        print(f"\n  Ledger: +{len(added)} new rows ({len(existing)} existing) -> {LEDGER_PATH.name}")

        # Print cumulative summary across all dates
        all_rows = []
        with open(LEDGER_PATH, newline="", encoding="utf-8") as f:
            all_rows = list(csv.DictReader(f))
        print(f"\n  CUMULATIVE ({len(set(r['date'] for r in all_rows))} days, {len(all_rows)} races):")
        _print_summary(all_rows)
    else:
        print("\n  [DRY RUN] pass --execute to write ledger")

    return new_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    run(args.date, execute=args.execute)


if __name__ == "__main__":
    main()
