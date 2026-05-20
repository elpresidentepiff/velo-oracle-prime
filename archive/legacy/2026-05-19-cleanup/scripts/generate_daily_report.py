#!/usr/bin/env python3
"""Generate a clean, readable daily report from merged racecard JSONs."""
import json
from pathlib import Path

MERGED_DIR = Path(__file__).parent.parent / "data" / "racecard_merged"
OUTPUT = Path(__file__).parent.parent / "data" / "racecard_merged" / "DAILY_REPORT_2026-04-21.md"

VENUES = [
    ("PON", "Pontefract"),
    ("FFO", "Ffos Las"),
    ("WOL", "Wolverhampton"),
    ("YAR", "Yarmouth"),
]

DATE = "2026-04-21"

lines = []
lines.append(f"# VÉLØ Daily Intelligence Report — {DATE}\n")
lines.append("")

total_horses = 0
total_plots = 0

for code, name in VENUES:
    fpath = MERGED_DIR / f"racecard_{code}_{DATE}.json"
    if not fpath.exists():
        continue
    data = json.load(open(fpath))
    
    lines.append(f"---\n")
    lines.append(f"## {name}\n")
    
    for race_time in sorted(data["races"].keys()):
        race = data["races"][race_time]
        race_info = race.get("race_info", "")
        horses = race.get("horses", [])
        total_horses += len(horses)
        
        # Postdata/Topspeed picks
        pd_pick = race.get("postdata_pick", "")
        ts_pick = race.get("topspeed_pick", "")
        
        lines.append(f"### {race_time} — {race_info}\n")
        
        if pd_pick or ts_pick:
            picks = []
            if pd_pick:
                picks.append(f"**Postdata Pick:** {pd_pick}")
            if ts_pick:
                picks.append(f"**Topspeed Pick:** {ts_pick}")
            lines.append("> " + " | ".join(picks) + "\n")
            lines.append("")
        
        # Table header
        lines.append("| Horse | OR | BWL | Δ | TS | RPR | Plot | Conv | Flags | Signals |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        
        # Sort: plot candidates first (by conviction desc), then rest by OR desc
        def sort_key(h):
            conv = h.get("plot_conviction", 0) or 0
            or_val = h.get("current_or", 0) or 0
            is_plot = 1 if conv >= 0.7 else 0
            return (-is_plot, -conv, -or_val)
        
        for h in sorted(horses, key=sort_key):
            hname = h.get("horse_name", "?")
            # Skip junk entries
            if hname.lower() in ("spotlight verdict",):
                continue
            if "wins plcs runs" in hname.lower():
                continue
            if len(hname) < 2:
                continue
                
            or_val = h.get("current_or", "")
            bwl = h.get("best_winning_life", "")
            delta = h.get("or_delta_to_best_win", "")
            ts = h.get("ts_latest", "") or h.get("ts_master", "")
            rpr = h.get("rpr_master", "")
            plot = h.get("handicap_plot_score", "")
            conv = h.get("plot_conviction", "")
            
            # Format plot score
            if isinstance(plot, (int, float)):
                plot_str = f"{plot:.2f}"
            else:
                plot_str = ""
            
            if isinstance(conv, (int, float)):
                conv_str = f"{conv:.2f}"
            else:
                conv_str = ""
            
            # Flags summary
            flags = []
            hg = h.get("headgear_code", "")
            if hg:
                flags.append(f"🔧{hg}")
            spot_sent = h.get("spotlight_sentiment", 0) or 0
            if spot_sent >= 1:
                flags.append(f"📰+{int(spot_sent)}")
            elif spot_sent <= -1:
                flags.append(f"📰{int(spot_sent)}")
            
            tf = h.get("trainer_form", "")
            if tf == "strong_positive":
                flags.append("🔥stable")
            elif tf == "negative":
                flags.append("❄️stable")
            
            af = h.get("ability_flag", "")
            if af == "strong_positive":
                flags.append("💪ability")
            
            is_pd = h.get("is_postdata_pick", False)
            is_ts = h.get("is_topspeed_pick", False)
            if is_pd:
                flags.append("📊PD")
            if is_ts:
                flags.append("⚡TS")
            
            flags_str = " ".join(flags)
            
            # Intent signals
            signals = h.get("intent_signals", []) or []
            signals_str = ", ".join(signals) if signals else ""
            
            # Mark plot candidates
            is_plot_candidate = isinstance(conv, (int, float)) and conv >= 0.7
            if is_plot_candidate:
                total_plots += 1
                hname = f"**{hname}** ◆"
            
            # Format delta
            if isinstance(delta, (int, float)):
                delta_str = f"{delta:+d}" if delta != 0 else "0"
            else:
                delta_str = ""
            
            lines.append(f"| {hname} | {or_val} | {bwl} | {delta_str} | {ts} | {rpr} | {plot_str} | {conv_str} | {flags_str} | {signals_str} |")
        
        lines.append("")

lines.append("---\n")
lines.append(f"## Summary\n")
lines.append(f"| Metric | Value |")
lines.append(f"|---|---|")
lines.append(f"| Total Horses | {total_horses} |")
lines.append(f"| Plot Candidates (Conv >= 0.7) | {total_plots} |")
lines.append(f"| Venues | {len(VENUES)} |")
lines.append("")
lines.append("> **◆ = Plot Candidate** (conviction >= 0.7 — horse at/near winning mark with supporting signals)")
lines.append("")
lines.append("> **Key:** OR = Official Rating, BWL = Best Winning Life, Δ = OR minus BWL (negative = below winning mark), TS = Top Speed, RPR = Racing Post Rating, Plot = Handicap Plot Score (1.0 = at mark), Conv = Plot Conviction (composite)")
lines.append("")

report = "\n".join(lines)
OUTPUT.write_text(report)
print(f"Report saved: {OUTPUT}")
print(f"Total: {total_horses} horses, {total_plots} plot candidates")
