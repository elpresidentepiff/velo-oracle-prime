#!/usr/bin/env python3
"""
VÉLØ — SQPE v16 Validation: Kempton Cross-Check

Runs the real Kempton 4:40 (Oct 15, 2025) field through v16 and compares
rankings against the legacy CHAREX Five-Filter output.

THIS IS THE VALIDATION PROTOCOL:
  v16 is trained on real race outcomes.
  CHAREX was a manual multi-filter system.
  Agreement between them = model is capturing the right signals.
  Disagreement = investigate why.

Usage:
    python scripts/validate_v16_kempton.py

To validate a NEW race field, edit FIELD_TO_VALIDATE at the bottom.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.v16_predictor import V16Predictor

# ── Legacy CHAREX final scores (from kempton_440_analysis.txt) ──────────────
# Source of truth for the cross-validation
CHAREX_SCORES = {
    "El Bufalo":       {"composite": 61.3, "filters_passed": 4, "sqpe": 40, "recommendation": "RECOMMENDED"},
    "Tyger Bay":       {"composite": 61.2, "filters_passed": 3, "sqpe": 60, "recommendation": "RECOMMENDED"},
    "Mc Loven":        {"composite": 60.2, "filters_passed": 3, "sqpe": 30, "recommendation": "RECOMMENDED"},
    "Harry's Halo":    {"composite": 59.2, "filters_passed": 3, "sqpe": 30, "recommendation": "RECOMMENDED"},
    "One More Dream":  {"composite": 58.8, "filters_passed": 3, "sqpe": 60, "recommendation": "RECOMMENDED"},
    "Invincible Speed":{"composite": 54.8, "filters_passed": 3, "sqpe": 25, "recommendation": "RECOMMENDED"},
    "Hierarchy":       {"composite": 54.2, "filters_passed": 2, "sqpe": 35, "recommendation": "REJECT"},
    "Danger Alert":    {"composite": 45.4, "filters_passed": 3, "sqpe": 50, "recommendation": "REJECT"},
    "Lerwick":         {"composite": 38.8, "filters_passed": 1, "sqpe": 10, "recommendation": "REJECT"},
    "Treacherous":     {"composite": 33.6, "filters_passed": 1, "sqpe": 15, "recommendation": "REJECT"},
    "Lipsink":         {"composite": 32.7, "filters_passed": 1, "sqpe": 15, "recommendation": "REJECT"},
}

# ── Race context ─────────────────────────────────────────────────────────────
RACE = {
    "dist": "7f",
    "going": "Standard",  # AW Kempton
    "class_raw": "Class 6",
    "ran": 11,
}

# ── Field data (from kempton_440_race_data.py + race form) ──────────────────
# sp = decimal odds; or_rating = official rating; rpr = best recent speed fig;
# ts = second best recent speed fig; draw, age, wgt = standard fields
RUNNERS = [
    {"horse": "Tyger Bay",        "sp": "5/1",   "or_rating": 72, "rpr": 79, "ts": 70, "draw": 4,  "age": 8, "wgt": "9-6"},
    {"horse": "One More Dream",   "sp": "15/1",  "or_rating": 65, "rpr": 69, "ts": 65, "draw": 7,  "age": 6, "wgt": "9-2"},
    {"horse": "Danger Alert",     "sp": "7/1",   "or_rating": 68, "rpr": 69, "ts": 65, "draw": 2,  "age": 5, "wgt": "9-4"},
    {"horse": "El Bufalo",        "sp": "34/1",  "or_rating": 60, "rpr": 77, "ts": 72, "draw": 9,  "age": 4, "wgt": "9-0"},
    {"horse": "Hierarchy",        "sp": "4/1",   "or_rating": 75, "rpr": 71, "ts": 70, "draw": 3,  "age": 6, "wgt": "9-9"},
    {"horse": "Mc Loven",         "sp": "9/1",   "or_rating": 69, "rpr": 81, "ts": 79, "draw": 6,  "age": 4, "wgt": "9-3"},
    {"horse": "Harry's Halo",     "sp": "19/1",  "or_rating": 62, "rpr": 71, "ts": 68, "draw": 1,  "age": 5, "wgt": "9-1"},
    {"horse": "Invincible Speed", "sp": "10/1",  "or_rating": 66, "rpr": 80, "ts": 75, "draw": 5,  "age": 4, "wgt": "9-0"},
    {"horse": "Treacherous",      "sp": "8/2",   "or_rating": 60, "rpr": 79, "ts": 70, "draw": 8,  "age": 5, "wgt": "9-0"},
    {"horse": "Lipsink",          "sp": "19/1",  "or_rating": 58, "rpr": 70, "ts": 66, "draw": 10, "age": 8, "wgt": "8-11"},
    {"horse": "Lerwick",          "sp": "10/1",  "or_rating": 60, "rpr": 82, "ts": 78, "draw": 11, "age": 5, "wgt": "9-0"},
]


def run_validation():
    print("=" * 70)
    print("VÉLØ SQPE v16 — VALIDATION vs CHAREX (Kempton 4:40, Oct 15 2025)")
    print("=" * 70)
    print()

    predictor = V16Predictor()
    v16_results = predictor.rank_field(RUNNERS, RACE)

    # Attach CHAREX data
    for r in v16_results:
        r["charex"] = CHAREX_SCORES.get(r["horse"], {})

    # Build CHAREX ranking order for comparison
    charex_ranked = sorted(
        CHAREX_SCORES.items(),
        key=lambda x: x[1]["composite"],
        reverse=True
    )
    charex_rank_map = {name: i + 1 for i, (name, _) in enumerate(charex_ranked)}

    # ── Output table ──
    print(f"{'Rank':>4}  {'Horse':<20} {'v16%':>6} {'v16Score':>8} {'CHAREX_rank':>11} {'CHAREX_rec':<14} {'Drank':>6}")
    print("-" * 75)

    agreements = 0
    disagreements = 0
    for r in v16_results:
        name = r["horse"]
        charex_rank = charex_rank_map.get(name, "?")
        charex_rec = r["charex"].get("recommendation", "N/A")
        delta = (charex_rank - r["rank"]) if isinstance(charex_rank, int) else 0
        delta_str = f"{delta:+d}" if delta != 0 else "="
        flag = ""
        if isinstance(charex_rank, int):
            # Agreement: both in top 6 (RECOMMENDED) or both in bottom 5 (REJECT)
            v16_in_top = r["rank"] <= 6
            charex_in_top = charex_rank <= 6
            if v16_in_top == charex_in_top:
                agreements += 1
                flag = "OK"
            else:
                disagreements += 1
                flag = "!!"
        print(
            f"{r['rank']:>4}  {name:<20} {r['v16_prob']*100:>5.1f}%  {r['v16_score']:>7.1f}  "
            f"{str(charex_rank):>11}  {charex_rec:<14} {delta_str:>6}  {flag}"
        )

    total = agreements + disagreements
    agreement_pct = (agreements / total * 100) if total else 0

    print()
    print(f"Agreement rate: {agreements}/{total} ({agreement_pct:.0f}%)")
    print()

    # ── Notable divergences ──
    print("Notable divergences (rank shift > 3):")
    has_divergence = False
    for r in v16_results:
        name = r["horse"]
        charex_rank = charex_rank_map.get(name, r["rank"])
        delta = charex_rank - r["rank"]
        if abs(delta) > 3:
            has_divergence = True
            direction = "v16 HIGHER" if delta > 0 else "v16 LOWER"
            print(f"  {name}: CHAREX #{charex_rank} -> v16 #{r['rank']} ({direction}, {delta:+d})")
            print(f"    OR={r['or_rating']} RPR={r['rpr']} SP={r['sp']} CHAREX_SQPE={r['charex'].get('sqpe', '?')}/100")
    if not has_divergence:
        print("  None — rankings are closely aligned.")

    # ── Verdict ──
    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    if agreement_pct >= 80:
        print(f"STRONG AGREEMENT ({agreement_pct:.0f}%) — v16 and CHAREX are in alignment.")
        print("v16 is ready for live use. Trust the model.")
    elif agreement_pct >= 60:
        print(f"PARTIAL AGREEMENT ({agreement_pct:.0f}%) — investigate divergences above.")
        print("v16 signal is valid but manual context adds information.")
    else:
        print(f"LOW AGREEMENT ({agreement_pct:.0f}%) — significant divergences present.")
        print("Do NOT deploy without understanding why. Compare feature values vs form evidence.")

    print()
    print("Top 3 by v16:")
    for r in v16_results[:3]:
        print(f"  #{r['rank']} {r['horse']}: {r['v16_score']:.1f}/100 ({r['v16_prob']*100:.1f}%)")
    print()
    print("Top 3 by CHAREX:")
    for name, data in charex_ranked[:3]:
        print(f"  #{charex_rank_map[name]} {name}: {data['composite']:.1f}/100 ({data['recommendation']})")


if __name__ == "__main__":
    run_validation()
