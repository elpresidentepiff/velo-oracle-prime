"""
VÉLØ Multiples Builder — 23 April 2026
★★★ selections only. One horse per race slot. Ranked by conviction strength.
"""
from pathlib import Path

DATE = "2026-04-23"
MERGED_DIR = Path(__file__).parent.parent / "data" / "racecard_merged"

# ★★★ horses ranked by conviction strength
# Format: (rank, horse, venue, time, or_drop, peak_ts, key_signals)
# Ranking criteria: OR drop size + engine strength + number of signals + OR trend
# Exclude: same-race duplicates (keep best), OR drop of 69pts (data anomaly)

POOL = [
    # Tier 1 — OR trend + strong engine + multiple signals
    (1,  "Vaguely Royal",   "Southwell", "6.00", 19, 65,  "19lb drop · OR trend 15pts · 6 setup runs · cold stable · TS improving"),
    (2,  "Stoner'S Choice", "Perth",     "2.40", 23, 90,  "23lb drop · engine proven TS 90 · 4 setup runs · TS improving"),
    (3,  "Fuji Mountain",   "Beverley",  "2.52", 15, 87,  "15lb drop · OR trend 8pts · TS 87 · cold stable · TS improving"),
    (4,  "Kitsune Power",   "Beverley",  "3.52", 29, 77,  "29lb drop · OR trend 9pts · TS 77 · 3 setup runs"),
    (5,  "Malangen",        "Perth",     "4.40", 22, 92,  "22lb drop · TS 92 · education runs · TS improving"),
    (6,  "Everyonesgame",   "Warwick",   "2.30", 13, 99,  "13lb drop · TS 99 · 3 setup runs · cold stable"),
    (7,  "Ballywood",       "Warwick",   "4.00", 59, 87,  "59lb drop · OR trend 10pts · TS 87 · cold stable · TS improving"),
    (8,  "Inis Oirr",       "Perth",     "5.15", 17, 97,  "17lb drop · TS 97 · 3 setup runs"),
    # Tier 2 — strong OR drop + engine
    (9,  "Adelaide Bay",    "Southwell", "8.00", 8,  58,  "8lb drop · OR trend 11pts · 6 setup runs · TS improving"),
    (10, "Fools Rush In",   "Southwell", "8.00", 16, 57,  "16lb drop · 4 setup runs"),
    (11, "Copper And Five", "Beverley",  "4.22", 33, 66,  "33lb drop · OR trend 5pts · 3 setup runs"),
    (12, "Bantz",           "Beverley",  "4.52", 5,  66,  "5lb drop · OR trend 6pts · 4 setup runs"),
    (13, "William Of York", "Perth",     "5.15", 13, 62,  "13lb drop · strong engine"),
    (14, "Imperial Fighter","Dundalk",   "6.45", 13, 51,  "13lb drop · 4 setup runs · cold stable · TS improving"),
]

# One horse per race slot — resolve conflicts
# Perth 5.15 has Harry, Uptown Harry, Inis Oirr, Nights In Venice, William Of York
#   → Harry/Uptown Harry have 69pt OR drop (data anomaly — exclude)
#   → Take Inis Oirr (rank 8) as the Perth 5.15 representative
# Southwell 8.00 has Adelaide Bay, Fools Rush In, Enpassant, Mereside Madness
#   → Take Adelaide Bay (rank 9) as representative
# Beverley 4.52 has Bantz, Bizarre Law, Hostelry, Mini Mac, Sunny Orange, Coolree
#   → Take Bantz (rank 12) as representative

# Clean pool: 1 per race slot
CLEAN_POOL = [
    (1,  "Vaguely Royal",   "Southwell", "6.00", "19lb drop · OR trend 15pts · 6 setup runs · cold stable · TS improving"),
    (2,  "Stoner'S Choice", "Perth",     "2.40", "23lb drop · engine TS 90 · 4 setup runs · TS improving"),
    (3,  "Fuji Mountain",   "Beverley",  "2.52", "15lb drop · OR trend 8pts · TS 87 · cold stable · TS improving"),
    (4,  "Kitsune Power",   "Beverley",  "3.52", "29lb drop · OR trend 9pts · TS 77 · 3 setup runs"),
    (5,  "Malangen",        "Perth",     "4.40", "22lb drop · TS 92 · education runs · TS improving"),
    (6,  "Everyonesgame",   "Warwick",   "2.30", "13lb drop · TS 99 · 3 setup runs · cold stable"),
    (7,  "Ballywood",       "Warwick",   "4.00", "59lb drop · OR trend 10pts · TS 87 · cold stable"),
    (8,  "Inis Oirr",       "Perth",     "5.15", "17lb drop · TS 97 · 3 setup runs"),
    (9,  "Adelaide Bay",    "Southwell", "8.00", "8lb drop · OR trend 11pts · 6 setup runs · TS improving"),
    (10, "Copper And Five", "Beverley",  "4.22", "33lb drop · OR trend 5pts · 3 setup runs"),
    (11, "Bantz",           "Beverley",  "4.52", "5lb drop · OR trend 6pts · 4 setup runs"),
    (12, "William Of York", "Perth",     "5.15", "13lb drop · strong engine"),
]

lines = []
lines.append(f"# VÉLØ MULTIPLES — {DATE}")
lines.append("")
lines.append("★★★ selections only · One horse per race · Ranked by conviction")
lines.append("")
lines.append("---")
lines.append("")

for n in [4, 5, 6, 7, 8]:
    sel = CLEAN_POOL[:n]
    names = {4:"FOURFOLD", 5:"FIVEFOLD", 6:"SIXFOLD", 7:"SEVENFOLD", 8:"EIGHTFOLD"}[n]
    lines.append(f"## {names}")
    lines.append("")
    lines.append("| # | Horse | Venue | Time | Why |")
    lines.append("|---|---|---|---|---|")
    for rank, horse, venue, time, reason in sel:
        lines.append(f"| {rank} | **{horse}** | {venue} | {time} | {reason} |")
    lines.append("")

lines.append("---")
lines.append("")
lines.append("## Full ★★★ Pool")
lines.append("")
lines.append("| Horse | Venue | Time | Why |")
lines.append("|---|---|---|---|")
for rank, horse, venue, time, reason in CLEAN_POOL:
    lines.append(f"| **{horse}** | {venue} | {time} | {reason} |")
lines.append("")
lines.append("> Note: Harry and Uptown Harry (Perth 5.15) excluded — 69pt OR drop is a data anomaly.")

report = "\n".join(lines)
output = MERGED_DIR / f"MULTIPLES_{DATE}.md"
output.write_text(report)
print(report)
print(f"\nSaved: {output}")
