#!/usr/bin/env python3.11
"""
VÉLØ Full Verdict Report Generator
====================================
Generates a comprehensive verdict report from merged JSON files.
Includes all 5 data sources: OR, TS, Spotlight, Postdata, Colour Card.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent


def star_rating(conviction: float) -> str:
    if conviction >= 0.90:
        return "★★★"
    elif conviction >= 0.80:
        return "★★"
    elif conviction >= 0.70:
        return "★"
    return ""


def format_ts_history(ts_hist: list) -> str:
    """Format last 6 TS values as a trend string."""
    if not ts_hist:
        return ""
    vals = [str(r.get("ts", "-")) if r.get("ts") else "-" for r in ts_hist[:6]]
    return " → ".join(vals)


def format_or_history(or_hist: list) -> str:
    """Format last 6 OR values as a trend string."""
    if not or_hist:
        return ""
    vals = [str(r.get("or", "-")) if r.get("or") else "-" for r in or_hist[:6]]
    return " → ".join(vals)


def generate_verdict_report(date: str, venues: list, output_dir: Path) -> tuple[str, list]:
    """Generate full verdict report for given date and venues."""
    
    report_lines = []
    all_picks = []  # (venue, race_time, horse_name, conviction, stars)
    
    report_lines.append(f"# VÉLØ VERDICT REPORT — {date}")
    report_lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
    report_lines.append(f"*Sources: OR (last 6 runs) + TS (last 6 runs) + Spotlight + Postdata + Colour Card*")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    for venue in venues:
        json_path = output_dir / f"racecard_{venue}_{date}.json"
        if not json_path.exists():
            report_lines.append(f"## {venue} — FILE NOT FOUND")
            report_lines.append("")
            continue
        
        data = json.loads(json_path.read_text())
        races = data.get("races", {})
        
        venue_picks = []
        venue_lines = []
        
        for race_time in sorted(races.keys()):
            race = races[race_time]
            race_info = race.get("race_info", "")
            betting_forecast = race.get("betting_forecast", "")
            spotlight_verdict = race.get("spotlight_verdict", "")
            postdata_pick = race.get("postdata_pick", "")
            topspeed_pick = race.get("topspeed_pick", "")
            horses = race.get("horses", [])
            
            # Sort by conviction descending
            horses_sorted = sorted(
                [h for h in horses if h.get("plot_conviction", 0) >= 0.70],
                key=lambda h: h.get("plot_conviction", 0),
                reverse=True
            )
            
            if not horses_sorted:
                continue
            
            race_header = f"### {venue} {race_time}"
            if race_info:
                race_header += f" — {race_info[:80]}"
            venue_lines.append(race_header)
            
            if betting_forecast:
                venue_lines.append(f"*Forecast: {betting_forecast[:120]}*")
            
            venue_lines.append("")
            venue_lines.append(f"| Stars | Horse | OR | BWL | Δ | TS | RPR | Conv | Jockey | Trainer | Form | Flags |")
            venue_lines.append(f"|-------|-------|-----|-----|---|-----|-----|------|--------|---------|------|-------|")
            
            for h in horses_sorted:
                stars = star_rating(h.get("plot_conviction", 0))
                if not stars:
                    continue
                
                name = h.get("horse_name", "?")
                current_or = h.get("current_or", "-")
                bwl = h.get("best_winning_life", "-")
                delta = h.get("or_delta_to_best_win")
                delta_str = f"{delta:+d}" if delta is not None else "-"
                ts_latest = h.get("ts_latest", "-")
                rpr = h.get("rpr_master", "-")
                conv = h.get("plot_conviction", 0)
                jockey = (h.get("jockey") or "")[:18]
                trainer = (h.get("trainer") or "")[:18]
                form_str = h.get("form_string", "")[:10]
                
                # Build flags
                flags = []
                if h.get("ts_trend_signal", 0) >= 0.15:
                    flags.append("TS↑")
                elif h.get("ts_trend_signal", 0) <= -0.05:
                    flags.append("TS↓")
                if h.get("or_trend_drops", 0) >= 2:
                    flags.append(f"OR↓×{h['or_trend_drops']}")
                if h.get("trainer_form_signal", 0) > 0:
                    flags.append("TRN+")
                if h.get("course_winner_cc"):
                    flags.append("C")
                if h.get("dist_winner_cc"):
                    flags.append("D")
                if h.get("bf_flag"):
                    flags.append("BF")
                if h.get("is_postdata_pick"):
                    flags.append("PD✓")
                if h.get("is_topspeed_pick"):
                    flags.append("TS✓")
                if h.get("headgear_cc"):
                    flags.append(h["headgear_cc"].upper())
                flags_str = " ".join(flags)
                
                venue_lines.append(
                    f"| {stars} | **{name}** | {current_or} | {bwl} | {delta_str} | "
                    f"{ts_latest} | {rpr} | {conv:.3f} | {jockey} | {trainer} | {form_str} | {flags_str} |"
                )
                
                venue_picks.append((venue, race_time, name, conv, stars))
                all_picks.append((venue, race_time, name, conv, stars))
            
            venue_lines.append("")
            
            # TS History for top picks
            top_picks_in_race = [h for h in horses_sorted if star_rating(h.get("plot_conviction", 0)) == "★★★"]
            for h in top_picks_in_race[:3]:
                name = h.get("horse_name", "?")
                ts_hist = format_ts_history(h.get("ts_run_history", []))
                or_hist = format_or_history(h.get("or_run_history", []))
                days = h.get("days_since_last_run")
                age = h.get("age")
                stall = h.get("stall")
                
                venue_lines.append(f"**{name}** detail:")
                if ts_hist:
                    venue_lines.append(f"  - TS history (latest→oldest): {ts_hist}")
                if or_hist:
                    venue_lines.append(f"  - OR history (latest→oldest): {or_hist}")
                if days:
                    venue_lines.append(f"  - Days since last run: {days}")
                if stall:
                    venue_lines.append(f"  - Stall: {stall}, Age: {age}")
                venue_lines.append("")
            
            # Spotlight verdict
            if spotlight_verdict:
                venue_lines.append(f"> **SPOTLIGHT:** {spotlight_verdict[:300]}")
                venue_lines.append("")
            
            # Postdata picks
            if postdata_pick or topspeed_pick:
                pd_info = []
                if postdata_pick:
                    pd_info.append(f"Postdata pick: **{postdata_pick}**")
                if topspeed_pick:
                    pd_info.append(f"TopSpeed pick: **{topspeed_pick}**")
                venue_lines.append(f"*{' | '.join(pd_info)}*")
                venue_lines.append("")
            
            venue_lines.append("---")
            venue_lines.append("")
        
        if venue_picks:
            report_lines.append(f"## {venue} — {len(venue_picks)} picks")
            report_lines.extend(venue_lines)
        else:
            report_lines.append(f"## {venue} — **BLANK** (no horses at/near winning mark)")
            report_lines.append("")
    
    return "\n".join(report_lines), all_picks


def generate_multiples(picks: list) -> str:
    """Generate multiples from ★★★ picks across different races."""
    from itertools import combinations
    
    triple_star = [(v, rt, name, conv) for v, rt, name, conv, stars in picks if stars == "★★★"]
    double_star = [(v, rt, name, conv) for v, rt, name, conv, stars in picks if stars == "★★"]
    
    lines = []
    lines.append("# VÉLØ MULTIPLES")
    lines.append("")
    lines.append(f"## ★★★ Selections ({len(triple_star)} picks)")
    lines.append("")
    
    if triple_star:
        lines.append("| # | Venue | Time | Horse | Conv |")
        lines.append("|---|-------|------|-------|------|")
        for i, (v, rt, name, conv) in enumerate(triple_star, 1):
            lines.append(f"| {i} | {v} | {rt} | **{name}** | {conv:.3f} |")
        lines.append("")
        
        # Combinations
        n = len(triple_star)
        if n >= 2:
            lines.append("## Combination Bets (★★★ only)")
            lines.append("")
            
            for r in range(min(n, 6), 1, -1):
                combos = list(combinations(range(n), r))
                label = {2: "Doubles", 3: "Trebles", 4: "4-Folds", 5: "5-Folds", 6: "6-Folds"}.get(r, f"{r}-Folds")
                lines.append(f"### {label} ({len(combos)} bets)")
                for combo in combos[:20]:  # cap at 20 per fold level
                    horses_in_combo = [f"{triple_star[i][0]} {triple_star[i][1]} {triple_star[i][2]}" for i in combo]
                    lines.append(f"- {' / '.join(horses_in_combo)}")
                lines.append("")
    
    if double_star:
        lines.append(f"## ★★ Selections ({len(double_star)} picks)")
        lines.append("")
        lines.append("| # | Venue | Time | Horse | Conv |")
        lines.append("|---|-------|------|-------|------|")
        for i, (v, rt, name, conv) in enumerate(double_star, 1):
            lines.append(f"| {i} | {v} | {rt} | **{name}** | {conv:.3f} |")
        lines.append("")
        
        # Combined multiples (★★★ + ★★)
        all_bankers = triple_star + double_star
        if len(all_bankers) >= 3:
            lines.append("## Mixed Multiples (★★★ + ★★)")
            lines.append("")
            combos = list(combinations(range(len(all_bankers)), 3))
            lines.append(f"### Trebles ({min(len(combos), 20)} shown)")
            for combo in combos[:20]:
                horses_in_combo = [f"{all_bankers[i][0]} {all_bankers[i][1]} {all_bankers[i][2]}" for i in combo]
                lines.append(f"- {' / '.join(horses_in_combo)}")
            lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-04-24"
    venues = sys.argv[2:] if len(sys.argv) > 2 else ["FON", "CHP", "DON", "PER", "SAN", "COR"]
    
    output_dir = ROOT / "data" / "racecard_merged"
    
    print(f"Generating verdict report for {date}: {venues}")
    
    report, picks = generate_verdict_report(date, venues, output_dir)
    multiples = generate_multiples(picks)
    
    verdict_path = output_dir / f"VERDICTS_{date}.md"
    multiples_path = output_dir / f"MULTIPLES_{date}.md"
    
    verdict_path.write_text(report)
    multiples_path.write_text(multiples)
    
    print(f"Saved: {verdict_path}")
    print(f"Saved: {multiples_path}")
    print(f"Total picks: {len(picks)}")
    print(f"  ★★★: {sum(1 for *_, s in picks if s == '★★★')}")
    print(f"  ★★:  {sum(1 for *_, s in picks if s == '★★')}")
    print(f"  ★:   {sum(1 for *_, s in picks if s == '★')}")
