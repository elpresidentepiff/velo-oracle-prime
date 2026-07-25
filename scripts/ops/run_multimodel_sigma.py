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
    "velo_top_pick", "velo_outcome", "velo_assigned_product", "velo_ew_outcome", "velo_miss_class",
    "norpr_top_pick", "norpr_prob", "norpr_outcome", "norpr_miss_class",
    "nb_top_pick", "nb_prob", "nb_outcome", "nb_miss_class",
    "champion_top_pick", "champion_prob", "champion_outcome", "champion_miss_class",
    "winner", "winner_sp", "top3",
]


def _classify_miss(sp: float | str | None) -> str:
    """SP band of the actual winner on a missed race. Thresholds match
    run_results_sigma.py exactly (short_fav_won <=3.0, outsider_won >10.0,
    else mid_priced_won) so miss classes are comparable across models."""
    try:
        sp = float(sp)
    except (TypeError, ValueError):
        return ""
    if sp > 0 and sp <= 3.0:
        return "short_fav_won"
    if sp > 10.0:
        return "outsider_won"
    return "mid_priced_won"


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
    """Returns {race_id: {winner, top3_names}} from RP results JSON.

    Indexed under BOTH the raw numeric RP race_id (e.g. "921398") and a
    synthesized VELO-style race_id (e.g. "rp_ASC_20260710_2.00") -- sigma_rows
    and Supabase/New Build predictions use the VELO format, so without this
    secondary key every lookup here silently missed and No-RPR/New Build
    always showed n/a (root-caused 2026-07-10).
    """
    date_tag = date_str.replace("-", "_")
    date_compact = date_str.replace("-", "")
    path = ROOT / "data" / "results" / f"rp_results_{date_tag}.json"
    if not path.exists():
        path = ROOT / "data" / "results" / f"rp_results_{date_str}.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    results = d.get("results", [])
    # Results-parser venue code -> VELO race_id venue code (mirrors the same
    # alias nightly_eod_learning_runner.py needs for the same reason).
    venue_aliases = {"CHE": "CHS"}
    index: dict[str, dict] = {}
    for r in results:
        entry = {
            "winner": r.get("winner_horse", ""),
            "winner_sp": r.get("winner_sp"),
            "top3": r.get("top3_names", []),
        }
        rid = str(r.get("race_id", ""))
        if rid:
            index[rid] = entry
        venue = venue_aliases.get(r.get("venue", ""), r.get("venue", ""))
        off = r.get("off", "")
        if venue and off:
            index[f"rp_{venue}_{date_compact}_{off}"] = entry
    return index


def _load_supabase_predictions(date_str: str) -> dict[str, list[dict]]:
    """Returns {race_id: [runner_pred_dicts]} from Supabase velo_verdicts.

    Uses the shared, bug-fixed loader -- see src/velo/verdict_loader.py for
    why this can't be a hand-rolled generated_at query. This script had
    exactly that bug until 2026-07-23.
    """
    try:
        from src.velo.verdict_loader import load_verdicts as _shared_load_verdicts
        rows, method = _shared_load_verdicts(date_str, select="race_id, full_analysis", root=ROOT)
        if method != "race_id":
            print(f"  [run_multimodel_sigma] verdict load used fallback method: {method}")
        result: dict[str, list[dict]] = {}
        for row in rows:
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


def _load_champion_scorecards(date_str: str) -> dict[str, dict]:
    """Returns {race_id: {horse, prob}} for the top_pick_shadow=True runner
    per race, from build_intent_shadow_scorecard.py's CSV. Keyed by the same
    raw numeric race_id as the results file (needs the same numeric->velo
    remap as New Build before joining against sigma_rows)."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "reports" / f"intent_shadow_scorecard_{date_tag}.csv"
    if not path.exists():
        return {}
    result: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("top_pick_shadow") == "True":
                rid = str(row.get("race_id", ""))
                if rid:
                    result[rid] = {
                        "horse": row.get("horse"),
                        "prob": row.get("champion_intent_shadow_prob"),
                    }
    return result


def _build_numeric_to_velo_map(date_str: str) -> dict[str, str]:
    """Maps raw numeric RP race_id (e.g. "921398") -> VELO race_id (e.g.
    "rp_NMK_20260710_1.50"), from the same results file _load_rp_results
    reads. New Build's two_lane_readiness scorecards are keyed by the raw
    numeric id, which 1:1-matches the results file's numeric id but not
    sigma's VELO id -- without this remap New Build always showed n/a
    (root-caused 2026-07-10, same family as the _load_rp_results fix above).
    """
    date_tag = date_str.replace("-", "_")
    date_compact = date_str.replace("-", "")
    path = ROOT / "data" / "results" / f"rp_results_{date_tag}.json"
    if not path.exists():
        path = ROOT / "data" / "results" / f"rp_results_{date_str}.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    venue_aliases = {"CHE": "CHS"}
    mapping: dict[str, str] = {}
    for r in d.get("results", []):
        rid = str(r.get("race_id", ""))
        venue = venue_aliases.get(r.get("venue", ""), r.get("venue", ""))
        off = r.get("off", "")
        if rid and venue and off:
            mapping[rid] = f"rp_{venue}_{date_compact}_{off}"
    return mapping


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
        ("Old VELO", "velo_outcome", "velo_miss_class"),
        ("No-RPR",   "norpr_outcome", "norpr_miss_class"),
        ("New Build","nb_outcome", "nb_miss_class"),
        ("Champion", "champion_outcome", "champion_miss_class"),
    ]
    print("\n  +-----------------------------------------------------+")
    print(  "  |  MULTI-MODEL SIGMA SUMMARY                          |")
    print(  "  +------------+-------+-------+-------+---------------+")
    print(  "  |  Model     |  n    |  WIN  | PLACE |   SR   Frame  |")
    print(  "  +------------+-------+-------+-------+---------------+")
    for label, col, _ in models:
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

    print("\n  MISS CLASSES (winner SP band, on missed races):")
    for label, col, miss_col in models:
        misses = [r[miss_col] for r in rows if r[col] == "MISS" and r[miss_col]]
        if not misses:
            continue
        from collections import Counter
        counts = Counter(misses)
        parts = ", ".join(f"{k}={v}" for k, v in counts.most_common())
        print(f"    {label:<10} n={len(misses):<3d} {parts}")

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
    numeric_to_velo = _build_numeric_to_velo_map(date_str)
    nb_cards_raw = _load_nb_scorecards(date_str)
    nb_cards = {
        numeric_to_velo.get(rid, rid): card for rid, card in nb_cards_raw.items()
    }
    champion_cards_raw = _load_champion_scorecards(date_str)
    champion_cards = {
        numeric_to_velo.get(rid, rid): card for rid, card in champion_cards_raw.items()
    }

    print(f"  Sigma rows : {len(sigma_rows)}")
    print(f"  RP results : {len(rp_results)} races")
    print(f"  Supabase   : {len(sb_preds)} races")
    print(f"  New Build  : {len(nb_cards)} races")
    print(f"  Champion   : {len(champion_cards)} races")

    new_rows: list[dict] = []

    for sr in sigma_rows:
        race_id = str(sr.get("race_id", ""))
        result     = rp_results.get(race_id, {})
        winner     = result.get("winner", "")
        winner_sp  = result.get("winner_sp")
        top3       = result.get("top3", [])

        # Old VELO: sigma already has the top pick + outcome
        # sigma uses "PLACED" — normalise to "PLACE" for consistency
        velo_pick    = sr.get("predicted", "")
        _raw_outcome = sr.get("outcome", "MISS")
        velo_outcome = "PLACE" if _raw_outcome == "PLACED" else _raw_outcome
        velo_assigned_product = sr.get("assigned_product", "UNKNOWN")
        velo_ew_outcome = sr.get("ew_outcome", "")
        velo_miss_class = _classify_miss(winner_sp) if velo_outcome == "MISS" else ""

        # No-RPR: highest sqpe_no_rpr_shadow_prob in Supabase
        norpr_pick, norpr_prob, norpr_outcome = None, None, "NO_DATA"
        if race_id in sb_preds:
            norpr_pick, norpr_prob = _no_rpr_top_pick(sb_preds[race_id])
            if winner:
                norpr_outcome = _outcome(norpr_pick, winner, top3)
        norpr_miss_class = _classify_miss(winner_sp) if norpr_outcome == "MISS" else ""

        # New Build: lane_a_top3[0]
        nb_entry = nb_cards.get(race_id, {})
        nb_pick  = nb_entry.get("horse")
        nb_prob  = nb_entry.get("prob")
        nb_outcome = "NO_DATA"
        if nb_pick and winner:
            nb_outcome = _outcome(nb_pick, winner, top3)
        nb_miss_class = _classify_miss(winner_sp) if nb_outcome == "MISS" else ""

        # Champion Intent Shadow: top_pick_shadow=True runner
        champion_entry = champion_cards.get(race_id, {})
        champion_pick  = champion_entry.get("horse")
        champion_prob  = champion_entry.get("prob")
        champion_outcome = "NO_DATA"
        if champion_pick and winner:
            champion_outcome = _outcome(champion_pick, winner, top3)
        champion_miss_class = _classify_miss(winner_sp) if champion_outcome == "MISS" else ""

        row = {
            "date":          date_str,
            "race_id":       race_id,
            "course":        sr.get("course", ""),
            "off":           sr.get("off", ""),
            "velo_top_pick": velo_pick,
            "velo_outcome":  velo_outcome,
            "velo_assigned_product": velo_assigned_product,
            "velo_ew_outcome": velo_ew_outcome or "",
            "velo_miss_class": velo_miss_class,
            "norpr_top_pick": norpr_pick or "",
            "norpr_prob":    round(norpr_prob, 4) if norpr_prob else "",
            "norpr_outcome": norpr_outcome,
            "norpr_miss_class": norpr_miss_class,
            "nb_top_pick":   nb_pick or "",
            "nb_prob":       round(nb_prob, 4) if nb_prob else "",
            "nb_outcome":    nb_outcome,
            "nb_miss_class": nb_miss_class,
            "champion_top_pick": champion_pick or "",
            "champion_prob": round(float(champion_prob), 4) if champion_prob else "",
            "champion_outcome": champion_outcome,
            "champion_miss_class": champion_miss_class,
            "winner":        winner,
            "winner_sp":     winner_sp if winner_sp is not None else "",
            "top3":          "|".join(top3),
        }
        new_rows.append(row)

        agree = sum([
            _norm(velo_pick) == _norm(norpr_pick) if norpr_pick else False,
            _norm(velo_pick) == _norm(nb_pick) if nb_pick else False,
            _norm(norpr_pick) == _norm(nb_pick) if (norpr_pick and nb_pick) else False,
        ])
        status = f"V:{velo_outcome[0]} N:{norpr_outcome[0]} B:{nb_outcome[0]} C:{champion_outcome[0]}"
        print(f"  {race_id} {sr.get('course',''):12} {sr.get('off',''):5}  {status}")

    _print_summary(new_rows)

    if execute:
        # Load existing rows; merge-in-place so a rerun with corrected data
        # (e.g. after a race_id-mapping fix) actually overwrites stale rows
        # instead of permanently keeping whatever was first written for that
        # (date, race_id) key (root-caused 2026-07-10 -- NO_DATA rows from a
        # broken run were never refreshed by the corrected rerun under the
        # old skip-if-exists logic).
        existing: list[dict] = []
        if LEDGER_PATH.exists():
            with open(LEDGER_PATH, newline="", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))
        existing_by_key = {(r["date"], r["race_id"]): r for r in existing}
        new_by_key = {(r["date"], r["race_id"]): r for r in new_rows}
        updated = sum(1 for k in new_by_key if k in existing_by_key)
        added = sum(1 for k in new_by_key if k not in existing_by_key)
        combined_by_key = dict(existing_by_key)
        combined_by_key.update(new_by_key)
        all_rows_out = list(combined_by_key.values())
        with open(LEDGER_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS, restval="", extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows_out)
        print(f"\n  Ledger: +{added} new rows, {updated} updated in place ({len(existing)} existing) -> {LEDGER_PATH.name}")

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
