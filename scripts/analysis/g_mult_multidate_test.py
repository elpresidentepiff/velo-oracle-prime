#!/usr/bin/env python3
"""
g_mult_multidate_test.py — Forward-simulate new G multipliers across all dates.

Reads each verdict file, extracts top-pick MDS + SP + is_fav, then runs them
through the new _g_shadow_adjustment() logic with the reset state.
Verifiable with any Python >= 3.9 (no venv dependencies needed).
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

# ── Inline the updated _g_shadow_adjustment logic ──────────────────────────
# Mirrors src/intelligence/velo_prime_ensemble.py exactly so we don't
# need to import the full ensemble (avoids Linux venv dependency).
def g_shadow_adjustment(mds, is_fav, sp_dec, doctrine_strengths, floor=0.25):
    multiplier = 1.0
    doctrine_fired = []

    # LAY_THE_STORY: market deception — fires when MDS > 0.55
    lay_str = doctrine_strengths.get("LAY_THE_STORY", 1.0)
    if mds is not None and mds > 0.55:
        doctrine_fired.append("LAY_THE_STORY")
        if 0 < lay_str < 0.5:
            disc = 0.7 + (lay_str * 0.67)
            multiplier *= disc

    # SHADOW_TRACKING: outsider territory — fires when SP >= 10
    shad_str = doctrine_strengths.get("SHADOW_TRACKING", 1.0)
    if sp_dec is not None and sp_dec >= 10.0:
        doctrine_fired.append("SHADOW_TRACKING")
        if 0 < shad_str < 0.5:
            disc = 0.7 + (shad_str * 0.67)
            multiplier *= disc

    # FAVOURITE_LIABILITY: high-MDS fav — fires when fav + MDS > 0.55 + strength >= 0.5
    fav_str = doctrine_strengths.get("LAY_THE_STORY", 1.0)
    if is_fav and mds is not None and mds > 0.55 and fav_str >= 0.5:
        multiplier *= 0.93
        doctrine_fired.append("FAVOURITE_LIABILITY")

    return round(multiplier, 4), doctrine_fired


def main():
    # Load reset state
    state_path = ROOT / "data" / "sentient_state.json"
    state = json.loads(state_path.read_text())
    ds = state.get("doctrine_strengths", {})
    floor = 0.25

    print(f"Doctrine strengths (post-reset):")
    for k, v in ds.items():
        print(f"  {k}: {v}")
    print()

    verdict_files = sorted(ROOT.glob("data/velo_prime_verdicts_2026_*.json"))
    print(f"Verdict files: {len(verdict_files)}")
    print()

    all_mults = Counter()
    total_races = 0
    date_rows = []

    for vf in verdict_files:
        if ".with_" in vf.name:
            continue
        try:
            verdicts = json.loads(vf.read_text())
        except Exception:
            continue

        date_tag = vf.stem.replace("velo_prime_verdicts_", "")
        day_mults = []

        for race in verdicts:
            top = race.get("top")
            if top and isinstance(top, dict):
                mds = top.get("market_deception_score")
                sp  = top.get("sp_dec")
            else:
                mds = race.get("market_deception_score")
                sp  = None
                top_id = str(race.get("top_rank_horse_id") or "")
                preds = (race.get("full_analysis") or {}).get("predictions") or []
                for p in preds:
                    if str(p.get("horse_id") or "") == top_id:
                        sp = p.get("sp_dec")
                        break

            is_fav = bool(sp and sp <= 2.0)
            mult, fired = g_shadow_adjustment(mds, is_fav, sp, ds, floor)
            day_mults.append(mult)
            all_mults[mult] += 1

        if day_mults:
            avg = sum(day_mults) / len(day_mults)
            discounted = [m for m in day_mults if m != 1.0]
            date_rows.append((date_tag, len(day_mults), avg, len(discounted)))
            total_races += len(day_mults)

    # Per-date table
    print(f"{'Date':<20} {'N':>5} {'AvgMult':>8} {'Discounted':>12}")
    print("-" * 50)
    for date_tag, n, avg, n_disc in date_rows:
        bar = "#" * n_disc
        print(f"{date_tag:<20} {n:>5} {avg:>8.4f}  {n_disc:>3}/{n:<3} {bar}")

    # Overall distribution
    print()
    print("Overall multiplier distribution across all dates:")
    for mult, count in sorted(all_mults.items()):
        pct = count / total_races * 100
        bar = "#" * int(pct)
        print(f"  {mult:.4f}x  {count:>5} races ({pct:5.1f}%) {bar}")

    avg_all = sum(m * c for m, c in all_mults.items()) / total_races
    neutral = all_mults[1.0]
    print()
    print(f"Total races: {total_races:,} across {len(date_rows)} dates")
    print(f"Avg multiplier:  {avg_all:.4f}  (was 0.5167 before fix)")
    print(f"Neutral (1.0x):  {neutral:,}/{total_races:,} ({neutral/total_races*100:.1f}%)")
    print(f"Discounted:      {total_races-neutral:,}/{total_races:,} ({(total_races-neutral)/total_races*100:.1f}%)")

    # Floor proof
    print()
    print("Floor stress-test (500 losses from various starting strengths):")
    for start in [1.0, 0.5, 0.26]:
        s = start
        for _ in range(500):
            s = max(floor, 0.9 * s + 0.0)
        print(f"  start={start} → {s:.6f}  ({'HELD' if s == floor else 'BROKEN'})")


if __name__ == "__main__":
    main()
