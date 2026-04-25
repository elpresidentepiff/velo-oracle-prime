#!/usr/bin/env python3
"""Generate a clean daily report — plot candidates with full run history."""
import json
from pathlib import Path

MERGED_DIR = Path(__file__).parent.parent / "data" / "racecard_merged"
OUTPUT = MERGED_DIR / "PICKS_2026-04-21.md"

VENUES = [
    ("PON", "Pontefract"),
    ("FFO", "Ffos Las"),
    ("WOL", "Wolverhampton"),
    ("YAR", "Yarmouth"),
]

DATE = "2026-04-21"

GOING_LABELS = {
    "f": "Firm", "gf": "GF", "g": "Good", "gs": "GS",
    "s": "Soft", "hy": "Heavy", "sd": "SD", "vs": "VS",
    "ft": "Fast", "fz": "Frozen", "ss": "Slow", "ys": "Yielding"
}

def going_label(g):
    return GOING_LABELS.get(g, g or "?")

def pos_label(p):
    if p is None:
        return "?"
    if p == 0:
        return "U/P"
    return str(p)

lines = []
lines.append(f"# VÉLØ Plot Candidates — {DATE}\n")
lines.append("> Horses at or near their winning mark with trainer intent signals\n")

total_picks = 0

for code, name in VENUES:
    fpath = MERGED_DIR / f"racecard_{code}_{DATE}.json"
    if not fpath.exists():
        continue
    data = json.load(open(fpath))

    venue_plots = []

    for race_time in sorted(data["races"].keys()):
        race = data["races"][race_time]
        race_info = race.get("race_info", "")

        for h in race.get("horses", []):
            conv = h.get("plot_conviction", 0) or 0
            if conv < 0.7:
                continue
            hname = h.get("horse_name", "?")
            if "wins plcs" in hname.lower() or hname.lower() == "spotlight verdict":
                continue

            venue_plots.append((race_time, race_info, h))

    if not venue_plots:
        continue

    total_picks += len(venue_plots)
    lines.append(f"---\n## {name} — {len(venue_plots)} picks\n")

    for race_time, race_info, h in venue_plots:
        hname = h.get("horse_name", "?")
        or_val = h.get("current_or", "?")
        bwl = h.get("best_winning_life", "?")
        delta = h.get("or_delta_to_best_win", None)
        conv = h.get("plot_conviction", 0)
        hg = h.get("headgear_code", "")
        tf = h.get("trainer_form", "")
        signals = h.get("intent_signals", []) or []
        spotlight = h.get("spotlight_comment", "")

        # Delta string
        if isinstance(delta, (int, float)):
            if delta <= 0:
                delta_str = f"**{abs(int(delta))}lb BELOW winning mark**"
            else:
                delta_str = f"{int(delta)}lb above winning mark"
        else:
            delta_str = "at winning mark"

        lines.append(f"### {race_time} — **{hname}**")
        lines.append(f"*{race_info}*\n")

        # Key facts line
        facts = [f"OR: {or_val}", f"Won off: {bwl}", delta_str, f"Conviction: {conv:.2f}"]
        if hg:
            gear_names = {
                "b1": "BLINKERS 1ST TIME", "v1": "VISOR 1ST TIME",
                "p1": "CHEEKPIECES 1ST TIME", "t1": "TONGUE TIE 1ST TIME",
                "b": "blinkers", "v": "visor", "p": "cheekpieces",
                "e1": "EYE SHIELD 1ST TIME", "h": "hood"
            }
            facts.append(f"Gear: {gear_names.get(hg, hg.upper())}")
        if tf == "negative":
            facts.append("Stable: COLD (deliberate?)")
        elif tf == "strong_positive":
            facts.append("Stable: HOT")
        lines.append(" | ".join(facts) + "\n")

        # Intent signals
        if signals:
            sig_labels = {
                "hidden_ability": "Hidden ability",
                "all_systems_go": "All systems go",
                "cold_stable": "Cold stable",
                "hot_stable": "Hot stable",
                "education_run_profile": "Education run",
                "new_course_test": "New course",
                "unproven_going": "Unproven going",
            }
            sig_str = " · ".join(sig_labels.get(s, s) for s in signals)
            lines.append(f"**Signals:** {sig_str}\n")

        # TS run history
        ts_runs = h.get("ts_run_history", [])
        ts_runs = [r for r in ts_runs if r.get("ts") is not None]
        if ts_runs:
            ts_cells = []
            for r in ts_runs[-6:]:  # last 6
                p = pos_label(r.get("pos"))
                ts = r.get("ts", "?")
                g = going_label(r.get("going", ""))
                ts_cells.append(f"{p}st/{ts}ts/{g}")
            lines.append(f"**TS runs (oldest→latest):** {' → '.join(ts_cells)}\n")

        # OR run history
        or_runs = h.get("or_run_history", [])
        or_runs = [r for r in or_runs if r.get("or") is not None]
        if or_runs:
            or_cells = []
            for r in or_runs[-6:]:  # last 6
                p = pos_label(r.get("pos"))
                o = r.get("or", "?")
                or_cells.append(f"{p}st/OR{o}")
            lines.append(f"**OR runs (oldest→latest):** {' → '.join(or_cells)}\n")

        # Spotlight comment
        if spotlight and len(spotlight) > 20:
            # Trim to 200 chars
            short = spotlight[:200].strip()
            if len(spotlight) > 200:
                short += "..."
            lines.append(f"**Spotlight:** *{short}*\n")

        lines.append("")

lines.append("---")
lines.append(f"\n**Total picks: {total_picks}**\n")

report = "\n".join(lines)
OUTPUT.write_text(report)
print(f"Saved: {OUTPUT}")
print(f"Total picks: {total_picks}")
