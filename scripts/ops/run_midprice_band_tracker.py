#!/usr/bin/env python3
"""
Mid-Price SP Band Tracker
=========================
Reads the multi-model comparison ledger + RP results to measure per-model
performance inside the mid-price SP band (3.0–8.5) vs outside it.

This band accounts for ~58% of misses and is the primary unsolved
commercial problem for the three-model architecture.

Usage:
    python scripts/ops/run_midprice_band_tracker.py
    python scripts/ops/run_midprice_band_tracker.py --lo 3.0 --hi 8.5
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LEDGER_PATH  = ROOT / "data" / "model_comparison_ledger.csv"
RESULTS_DIR  = ROOT / "data" / "results"
BAND_LO_DEF  = 3.0
BAND_HI_DEF  = 8.5

MODELS = [
    ("Old VELO",  "velo_outcome"),
    ("No-RPR",    "norpr_outcome"),
    ("New Build", "nb_outcome"),
]


def _load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        raise FileNotFoundError(f"Ledger not found: {LEDGER_PATH}")
    with open(LEDGER_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_winner_sp_index() -> dict[str, float]:
    """Returns {race_id: winner_sp_decimal} from all rp_results_*.json files."""
    index: dict[str, float] = {}
    for path in RESULTS_DIR.glob("rp_results_*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Support both root formats: list (old) and dict with "results" key (new)
        results = d if isinstance(d, list) else d.get("results", [])
        for r in results:
            rid = str(r.get("race_id", ""))
            sp  = r.get("winner_sp")
            if rid and sp is not None:
                try:
                    index[rid] = float(sp)
                except (TypeError, ValueError):
                    pass
    return index


def _sr_frame(vals: list[str]) -> tuple[float, float, int, int, int]:
    n = len(vals)
    if n == 0:
        return 0.0, 0.0, 0, 0, 0
    wins   = sum(1 for v in vals if v == "WIN")
    frames = sum(1 for v in vals if v in ("WIN", "PLACE"))
    return wins / n, frames / n, wins, frames, n


def _print_band_table(
    band_rows: list[dict],
    outside_rows: list[dict],
    no_sp_rows: list[dict],
    lo: float,
    hi: float,
) -> None:
    cols   = [f"SP {lo:.1f}–{hi:.1f} (MID)", "OUTSIDE BAND", "NO SP DATA"]
    groups = [band_rows, outside_rows, no_sp_rows]

    # Header
    print()
    print(f"  MID-PRICE SP BAND TRACKER  (band = {lo}–{hi})")
    print()
    w_col = 28
    print(f"  {'Model':<12}", end="")
    for c in cols:
        print(f"  {c:^22}", end="")
    print()
    print("  " + "-" * (12 + 3 * 24))

    for label, col in MODELS:
        print(f"  {label:<12}", end="")
        for rows in groups:
            vals = [r[col] for r in rows if r[col] not in ("NO_DATA", "")]
            sr, frame, wins, frames, n = _sr_frame(vals)
            if n == 0:
                cell = "    n/a    "
            else:
                cell = f"SR {sr:.1%} F {frame:.1%} (n={n})"
            print(f"  {cell:^22}", end="")
        print()

    # Show band SP distribution
    print()
    print(f"  Race counts : band={len(band_rows)}  outside={len(outside_rows)}  no-SP={len(no_sp_rows)}")
    if band_rows:
        sps = sorted(set(r.get("_sp", 0) for r in band_rows))
        print(f"  Band SP range seen : {min(sps):.2f} – {max(sps):.2f}")
    print()


def _print_band_winners(band_rows: list[dict], lo: float, hi: float) -> None:
    """Show which horses the models picked in the band, and outcomes."""
    hits: dict[str, list[str]] = {label: [] for label, _ in MODELS}
    for r in band_rows:
        sp   = r.get("_sp", 0)
        wins = r.get("winner", "")
        top3 = r.get("top3", "")
        for label, col in MODELS:
            outcome = r.get(col, "NO_DATA")
            if outcome == "WIN":
                hits[label].append(f"  WIN   SP={sp:.1f}  winner={wins}")

    print(f"  WINS inside band ({lo}–{hi}):")
    for label, _ in MODELS:
        print(f"    {label}: {len(hits[label])} wins")
        for line in hits[label][:10]:
            print(f"      {line}")
    print()


def run(lo: float = BAND_LO_DEF, hi: float = BAND_HI_DEF) -> None:
    print(f"\nMID-PRICE BAND TRACKER  band={lo}–{hi}")
    print("=" * 55)

    rows   = _load_ledger()
    sp_idx = _load_winner_sp_index()
    print(f"  Ledger rows : {len(rows)}")
    print(f"  SP index    : {len(sp_idx)} races with SP data")

    band_rows: list[dict]    = []
    outside_rows: list[dict] = []
    no_sp_rows: list[dict]   = []

    for r in rows:
        rid = str(r.get("race_id", ""))
        sp  = sp_idx.get(rid)
        if sp is None:
            no_sp_rows.append(r)
        elif lo <= sp <= hi:
            r = dict(r, _sp=sp)
            band_rows.append(r)
        else:
            r = dict(r, _sp=sp)
            outside_rows.append(r)

    _print_band_table(band_rows, outside_rows, no_sp_rows, lo, hi)
    _print_band_winners(band_rows, lo, hi)

    # Per-model miss breakdown inside the band
    print(f"  MISS breakdown inside band ({lo}–{hi}):")
    for label, col in MODELS:
        vals     = [r[col] for r in band_rows if r[col] not in ("NO_DATA", "")]
        misses   = sum(1 for v in vals if v == "MISS")
        wins     = sum(1 for v in vals if v == "WIN")
        places   = sum(1 for v in vals if v == "PLACE")
        n        = len(vals)
        print(f"    {label:<12} n={n:>3}  WIN={wins}  PLACE={places}  MISS={misses}"
              + (f"  (SR={wins/n:.1%} Frame={( wins+places)/n:.1%})" if n else ""))
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo",  type=float, default=BAND_LO_DEF, help="lower SP bound (default 3.0)")
    ap.add_argument("--hi",  type=float, default=BAND_HI_DEF, help="upper SP bound (default 8.5)")
    args = ap.parse_args()
    run(args.lo, args.hi)


if __name__ == "__main__":
    main()
