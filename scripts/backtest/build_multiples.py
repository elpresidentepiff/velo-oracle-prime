"""
VÉLØ Multiples Builder — 22 April 2026
Ranks ★★★ horses by conviction strength and builds 4-5-6-7-8 fold accumulators.
Selection logic:
  - Only ★★★ horses qualify
  - Max 1 horse per race (if 2 in same race, take the stronger one)
  - Rank by: OR drop size + engine strength + number of supporting signals
  - Build 4-fold from top 4, 5-fold from top 5, etc.
"""

import json
from pathlib import Path
from itertools import combinations

MERGED_DIR = Path(__file__).parent.parent.parent / "data" / "racecard_merged"
DATE = "2026-04-22"

# ★★★ horses from today's verdict report — ranked by conviction
# Format: (rank, horse, venue, time, or_drop, peak_ts, signals, reason)
SELECTIONS = [
    # Rank 1 — strongest combination of signals
    (1,  "Almazhar Garde",  "Ludlow",    "3.30", 11, 98, ["cold_stable", "ts_improving", "engine_proven"],        "11lb drop · TS 98 · cold stable · improving"),
    (2,  "Zacony Rebel",    "Ludlow",    "3.30", 30, 86, ["or_trend", "cold_stable", "ts_improving", "education"], "30lb drop · OR trend down · cold stable · improving"),
    (3,  "Roundhay Park",   "Catterick", "3.52", 29, 76, ["cold_stable", "ts_improving", "education", "setup_runs"],"29lb drop · cold stable · TS improving · 4 setup runs"),
    (4,  "Evocative Spark", "Catterick", "3.52", 26, 70, ["setup_runs", "ts_improving"],                           "26lb drop · 4 setup runs · TS improving"),
    (5,  "Dorney Lake",     "Catterick", "4.25", 16, 80, ["or_trend", "setup_runs", "ts_improving"],               "16lb drop · OR trend down · 4 setup runs · TS improving"),
    (6,  "Aberama Gold",    "Catterick", "4.25", 17, 78, ["ts_improving"],                                         "17lb drop · TS improving"),
    (7,  "The Paddy Pie",   "Ludlow",    "5.05", 24, 88, ["engine_proven"],                                        "24lb drop · peak TS 88"),
    (8,  "Est Illic",       "Ludlow",    "5.05", 56, 84, ["education"],                                            "56lb drop · peak TS 84 · education runs"),
    (9,  "Mi Sueno",        "Taunton",   "6.30", 18, 57, ["or_trend", "setup_runs"],                              "18lb drop · OR trend down · 4 setup runs"),
    (10, "Arctic Fox",      "Catterick", "5.00", 25, 59, ["education"],                                            "25lb drop · education runs"),
    (11, "Birkenhead",      "Catterick", "1.52",  3, 61, ["education"],                                            "3lb drop · education runs"),
    (12, "Fortunate Star",  "Catterick", "1.52",  5, 61, ["ts_improving"],                                         "5lb drop · TS improving"),
    (13, "Fix At All",      "Ludlow",    "5.05", 15, 80, ["engine_proven"],                                        "15lb drop · peak TS 80"),
]

# Resolve same-race conflicts — only 1 horse per race slot
# Ludlow 3.30: Almazhar Garde (rank 1) vs Zacony Rebel (rank 2) — BOTH qualify (different horses, same race — pick stronger)
# Ludlow 5.05: The Paddy Pie (7), Est Illic (8), Fix At All (13) — pick top 2 only
# Catterick 3.52: Roundhay Park (3), Evocative Spark (4) — BOTH qualify
# Catterick 4.25: Dorney Lake (5), Aberama Gold (6) — BOTH qualify
# Catterick 1.52: Birkenhead (11), Fortunate Star (12) — pick stronger (Birkenhead has education signal)

# For multiples: max 1 per race to avoid same-race doubles
# Race slots: LUD_330, LUD_505, CAT_152, CAT_352, CAT_425, CAT_500, TAU_630

RACE_BEST = {
    "LUD_330": ("Almazhar Garde",  "Ludlow",    "3.30", "11lb drop · TS 98 · cold stable · improving"),
    "LUD_505": ("The Paddy Pie",   "Ludlow",    "5.05", "24lb drop · peak TS 88"),
    "CAT_152": ("Birkenhead",      "Catterick", "1.52", "3lb drop · education runs"),
    "CAT_352": ("Roundhay Park",   "Catterick", "3.52", "29lb drop · cold stable · TS improving"),
    "CAT_425": ("Dorney Lake",     "Catterick", "4.25", "16lb drop · OR trend down · 4 setup runs"),
    "CAT_500": ("Arctic Fox",      "Catterick", "5.00", "25lb drop · education runs"),
    "TAU_630": ("Mi Sueno",        "Taunton",   "6.30", "18lb drop · OR trend down · 4 setup runs"),
}

# Ranked pool for multiples (1 per race, best horse)
POOL = [
    ("Almazhar Garde",  "Ludlow",    "3.30", "11lb drop · TS 98 · cold stable · improving",       1),
    ("Roundhay Park",   "Catterick", "3.52", "29lb drop · cold stable · TS improving",             2),
    ("Dorney Lake",     "Catterick", "4.25", "16lb drop · OR trend down · 4 setup runs",           3),
    ("The Paddy Pie",   "Ludlow",    "5.05", "24lb drop · peak TS 88",                             4),
    ("Mi Sueno",        "Taunton",   "6.30", "18lb drop · OR trend down · 4 setup runs",           5),
    ("Arctic Fox",      "Catterick", "5.00", "25lb drop · education runs",                         6),
    ("Birkenhead",      "Catterick", "1.52", "3lb drop · education runs",                          7),
]

def build_fold(n, pool):
    """Take top n from pool for the n-fold accumulator."""
    sel = pool[:n]
    return sel

lines = []
lines.append("# VÉLØ MULTIPLES — 22 April 2026")
lines.append("")
lines.append("Selections drawn from ★★★ plot candidates only.")
lines.append("One horse per race. Ranked by conviction strength.")
lines.append("")
lines.append("---")
lines.append("")

for n in [4, 5, 6, 7]:
    sel = build_fold(n, POOL)
    fold_name = {4: "FOURFOLD", 5: "FIVEFOLD", 6: "SIXFOLD", 7: "SEVENFOLD"}[n]
    lines.append(f"## {fold_name}")
    lines.append("")
    lines.append(f"| # | Horse | Venue | Time | Why |")
    lines.append(f"|---|---|---|---|---|")
    for i, (horse, venue, time, reason, rank) in enumerate(sel, 1):
        lines.append(f"| {i} | **{horse}** | {venue} | {time} | {reason} |")
    lines.append("")
    lines.append("")

# 8-fold: use all 7 unique race slots + add Evocative Spark (2nd horse from CAT 3.52 — different race slot not possible)
# Note: we only have 7 unique race slots so max clean fold is 7
# For 8-fold we include both Roundhay Park AND Evocative Spark from CAT 3.52 as a same-race saver
lines.append("## EIGHTFOLD")
lines.append("")
lines.append("*(includes both Roundhay Park and Evocative Spark from Catterick 3.52 — same race, treat as saver leg)*")
lines.append("")
lines.append("| # | Horse | Venue | Time | Why |")
lines.append("|---|---|---|---|---|")
eight = POOL[:7] + [("Evocative Spark", "Catterick", "3.52", "26lb drop · 4 setup runs · TS improving", 8)]
for i, (horse, venue, time, reason, rank) in enumerate(eight, 1):
    lines.append(f"| {i} | **{horse}** | {venue} | {time} | {reason} |")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## Full ★★★ Pool (all qualifying horses today)")
lines.append("")
lines.append("| Horse | Venue | Time | OR Drop | Peak TS | Signals |")
lines.append("|---|---|---|---|---|---|")
for rank, horse, venue, time, or_drop, peak_ts, signals, reason in SELECTIONS:
    lines.append(f"| **{horse}** | {venue} | {time} | {or_drop}lb | {peak_ts} | {reason} |")
lines.append("")

report = "\n".join(lines)
print(report)

output = MERGED_DIR / f"MULTIPLES_{DATE}.md"
output.write_text(report)
print(f"\nSaved: {output}")
