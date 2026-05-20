#!/usr/bin/env python3
"""
VÉLØ CASH RUN — Standout Picks Only
★★★ and ★★ horses with full OR/TS history, Spotlight, Trainer, Jockey
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "racecard_merged"
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-04-27"
VENUES = sys.argv[2:] if len(sys.argv) > 2 else ["WOL", "BAT", "LIN"]

def stars(conv):
    if conv is None or conv == 0: return None
    if conv >= 0.90: return "★★★"
    if conv >= 0.80: return "★★"
    return None  # below ★★ = not included

def fmt_or(runs, n=6):
    if not runs: return "no data"
    parts = []
    for r in (runs or [])[:n]:
        pos = r.get("pos", "-")
        val = r.get("or", "-")
        parts.append(f"{pos}/{val}")
    return "  ".join(parts)

def fmt_ts(runs, n=6):
    if not runs: return "no data"
    parts = []
    for r in (runs or [])[:n]:
        pos = r.get("pos") or "-"
        val = r.get("ts") or "-"
        going = r.get("going") or ""
        if pos == "-" and val == "-":
            parts.append("-")
        else:
            parts.append(f"{pos}/{val}{going}")
    return "  ".join(parts)

lines = []
lines.append(f"# VÉLØ CASH RUN — {DATE}")
lines.append(f"## STANDOUT PICKS — ★★★ and ★★ only")
lines.append(f"### OR history: pos/rating (latest first) | TS history: pos/TS/going (latest first)")
lines.append("")

triple_stars = []
double_stars = []

for venue in VENUES:
    path = DATA_DIR / f"racecard_{venue}_{DATE}.json"
    if not path.exists():
        continue

    with open(path) as f:
        data = json.load(f)

    races = data.get("races", {})
    venue_lines = []
    has_picks = False

    for race_time in sorted(races.keys()):
        race = races[race_time]
        race_info = race.get("race_info", "")
        pd_pick = race.get("postdata_pick", "")
        ts_pick = race.get("topspeed_pick", "")
        sv = race.get("spotlight_verdict", "")

        race_picks = []
        for h in sorted(race.get("horses", []), key=lambda x: -(x.get("plot_conviction") or 0)):
            conv = h.get("plot_conviction") or 0
            s = stars(conv)
            if not s:
                continue

            name = h.get("horse_name", "?")
            current_or = h.get("current_or", "?")
            bwl = h.get("best_winning_life", "?")
            delta = h.get("or_delta_to_best_win")
            delta_str = f"{delta:+d}" if delta is not None else "?"
            trainer = h.get("trainer") or h.get("trainer_name") or "?"
            jockey = h.get("jockey") or "?"
            form = h.get("form_string") or h.get("form") or "?"
            stall = h.get("stall") or h.get("draw") or ""
            headgear = h.get("headgear") or ""
            cd_flags = []
            if h.get("course_winner"): cd_flags.append("C")
            if h.get("distance_winner"): cd_flags.append("D")
            cd = "/".join(cd_flags) if cd_flags else ""

            or_history = fmt_or(h.get("or_run_history"), 6)
            ts_history = fmt_ts(h.get("ts_run_history"), 6)

            spotlight = (h.get("spotlight_comment") or "").strip()

            # Signals
            signals = []
            if h.get("ts_improving"): signals.append("TS↑")
            if h.get("trainer_positive"): signals.append("TRN+")
            if h.get("is_postdata_pick"): signals.append("PD✓")
            if h.get("is_topspeed_pick"): signals.append("TS✓")
            or_drops = h.get("consecutive_or_drops") or 0
            if or_drops >= 2: signals.append(f"OR↓×{or_drops}")

            pick = {
                "stars": s, "conv": conv, "venue": venue,
                "race_time": race_time, "race_info": race_info,
                "name": name, "stall": stall, "headgear": headgear, "cd": cd,
                "form": form, "current_or": current_or, "bwl": bwl,
                "delta_str": delta_str, "trainer": trainer, "jockey": jockey,
                "or_history": or_history, "ts_history": ts_history,
                "signals": signals, "spotlight": spotlight,
                "pd_pick": pd_pick, "ts_pick": ts_pick, "sv": sv
            }
            race_picks.append(pick)
            if s == "★★★":
                triple_stars.append(pick)
            else:
                double_stars.append(pick)

        if race_picks:
            has_picks = True
            venue_lines.append(f"\n### {venue} {race_time}  {race_info}")
            if sv:
                venue_lines.append(f"> **RACE VERDICT:** {sv[:300]}")
            if pd_pick:
                venue_lines.append(f"> PD Pick: **{pd_pick}** | TS Pick: **{ts_pick}**")
            venue_lines.append("")

            for p in race_picks:
                stall_str = f"[{p['stall']}]" if p['stall'] else ""
                hg_str = p['headgear'] if p['headgear'] else ""
                cd_str = f"({p['cd']})" if p['cd'] else ""
                sig_str = "  ".join(p['signals']) if p['signals'] else ""

                venue_lines.append(f"**{p['stars']} {p['name']}** {stall_str}{hg_str}{cd_str}  —  OR {p['current_or']} vs BWL {p['bwl']} ({p['delta_str']})  |  {p['trainer']} / {p['jockey']}  |  Form: {p['form']}  |  Conv: {p['conv']:.3f}")
                venue_lines.append(f"OR (last 6): {p['or_history']}")
                venue_lines.append(f"TS (last 6): {p['ts_history']}")
                if sig_str:
                    venue_lines.append(f"Signals: {sig_str}")
                if p['spotlight']:
                    venue_lines.append(f"Spotlight: *{p['spotlight']}*")
                venue_lines.append("")

    if has_picks:
        lines.append(f"\n---\n## {venue}")
        lines.extend(venue_lines)

# MULTIPLES
lines.append("\n---")
lines.append("## MULTIPLES")
lines.append("")

if triple_stars:
    lines.append(f"### ★★★ Picks ({len(triple_stars)} horses)")
    for p in triple_stars:
        lines.append(f"- **{p['venue']} {p['race_time']} {p['name']}** ({p['conv']:.3f})")
    lines.append("")

    if len(triple_stars) >= 2:
        lines.append("**Doubles (★★★):**")
        for i in range(len(triple_stars)):
            for j in range(i+1, len(triple_stars)):
                a, b = triple_stars[i], triple_stars[j]
                if a['race_time'] != b['race_time'] or a['venue'] != b['venue']:
                    lines.append(f"- {a['name']} ({a['venue']} {a['race_time']}) + {b['name']} ({b['venue']} {b['race_time']})")
        lines.append("")

    if len(triple_stars) >= 3:
        lines.append("**Trebles (★★★):**")
        for i in range(len(triple_stars)):
            for j in range(i+1, len(triple_stars)):
                for k in range(j+1, len(triple_stars)):
                    a, b, c = triple_stars[i], triple_stars[j], triple_stars[k]
                    races = {(a['venue'],a['race_time']), (b['venue'],b['race_time']), (c['venue'],c['race_time'])}
                    if len(races) == 3:
                        lines.append(f"- {a['name']} / {b['name']} / {c['name']}")
        lines.append("")

    if len(triple_stars) >= 4:
        lines.append("**4-Fold (★★★):**")
        for i in range(len(triple_stars)):
            for j in range(i+1, len(triple_stars)):
                for k in range(j+1, len(triple_stars)):
                    for l in range(k+1, len(triple_stars)):
                        picks = [triple_stars[i], triple_stars[j], triple_stars[k], triple_stars[l]]
                        races = {(p['venue'],p['race_time']) for p in picks}
                        if len(races) == 4:
                            lines.append(f"- {' / '.join(p['name'] for p in picks)}")
        lines.append("")

lines.append(f"---")
lines.append(f"**{len(triple_stars)} ★★★ picks | {len(double_stars)} ★★ picks**")

out_path = DATA_DIR / f"STANDOUT_{DATE}.md"
out_path.write_text("\n".join(lines))
print(f"Saved: {out_path}")
print(f"★★★: {len(triple_stars)} | ★★: {len(double_stars)}")
