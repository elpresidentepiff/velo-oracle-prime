"""
VÉLØ Full Intelligence Report Generator
========================================
Every race. Every horse. Last 6 OR runs. Last 6 TS runs. Spotlight comment. Nothing omitted.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "racecard_merged"


def format_run_history(history, key, n=6):
    """Format last N runs from history list as a clean string."""
    if not history:
        return "-"
    vals = []
    for r in history[:n]:
        v = r.get(key)
        pos = r.get("pos", "")
        if v and v != 0:
            if pos:
                vals.append(f"{pos}/{v}")
            else:
                vals.append(str(v))
        else:
            vals.append("-")
    return "  |  ".join(vals) if vals else "-"


def format_or_history(history, n=6):
    """Format OR run history: pos/OR for last N runs."""
    if not history:
        return "-"
    parts = []
    for r in (history or [])[:n]:
        or_val = r.get("or") or r.get("or_val") or ""
        pos = r.get("pos") or r.get("position") or ""
        dist = r.get("dist", "")
        going = r.get("going", "")
        if or_val:
            entry = f"{pos}/{or_val}" if pos else str(or_val)
            if dist:
                entry += f"({dist})"
            parts.append(entry)
        else:
            parts.append("-")
    return "  →  ".join(parts) if parts else "-"


def format_ts_history(history, n=6):
    """Format TS run history: pos/TS for last N runs."""
    if not history:
        return "-"
    parts = []
    for r in (history or [])[:n]:
        ts_val = r.get("ts") or r.get("ts_val") or ""
        pos = r.get("pos") or r.get("position") or ""
        if ts_val:
            entry = f"{pos}/{ts_val}" if pos else str(ts_val)
            parts.append(entry)
        else:
            parts.append("-")
    return "  →  ".join(parts) if parts else "-"


def star_rating(conviction):
    if conviction is None:
        return ""
    if conviction >= 0.90:
        return "★★★"
    elif conviction >= 0.80:
        return "★★"
    elif conviction >= 0.70:
        return "★"
    return ""


def generate_report(date, venues, output_path):
    lines = []
    lines.append(f"# VÉLØ FULL INTELLIGENCE REPORT — {date}")
    lines.append(f"**Every race. Every horse. Last 6 OR. Last 6 TS. Spotlight. Nothing omitted.**")
    lines.append("")

    total_horses = 0
    total_picks = 0

    for venue in venues:
        json_path = DATA_DIR / f"racecard_{venue}_{date}.json"
        if not json_path.exists():
            lines.append(f"## {venue} — FILE NOT FOUND")
            lines.append("")
            continue

        with open(json_path) as f:
            data = json.load(f)

        races = data.get("races", {})
        if not races:
            lines.append(f"## {venue} — NO RACES")
            lines.append("")
            continue

        lines.append(f"---")
        lines.append(f"# {venue}")
        lines.append("")

        # Race-level picks summary
        venue_picks = []
        for race_time in sorted(races.keys()):
            race = races[race_time]
            for h in race["horses"]:
                conv = h.get("plot_conviction", 0) or 0
                if conv >= 0.70:
                    venue_picks.append((race_time, h["horse_name"], conv))

        if venue_picks:
            lines.append(f"**PICKS: {len(venue_picks)}**")
            for rt, name, conv in sorted(venue_picks, key=lambda x: -x[2]):
                stars = star_rating(conv)
                lines.append(f"- {stars} {rt} **{name}** ({conv:.3f})")
            lines.append("")

        # Full race-by-race breakdown
        for race_time in sorted(races.keys()):
            race = races[race_time]
            race_info = race.get("race_info", "")
            pd_pick = race.get("postdata_pick", "")
            ts_pick = race.get("topspeed_pick", "")
            forecast = race.get("betting_forecast", "")
            spotlight_verdict = race.get("spotlight_verdict", "")

            lines.append(f"## {venue} {race_time} — {race_info}")
            if pd_pick:
                lines.append(f"*Postdata pick: **{pd_pick}***")
            if ts_pick:
                lines.append(f"*TopSpeed pick: **{ts_pick}***")
            if forecast:
                lines.append(f"*Forecast: {forecast}*")
            if spotlight_verdict:
                lines.append(f"*Spotlight verdict: {spotlight_verdict}*")
            lines.append("")

            horses = race.get("horses", [])
            total_horses += len(horses)

            for h in horses:
                name = h.get("horse_name", "?")
                conv = h.get("plot_conviction", 0) or 0
                stars = star_rating(conv)
                if conv >= 0.70:
                    total_picks += 1

                current_or = h.get("current_or", "-")
                bwl = h.get("best_winning_life", "-")
                delta = h.get("or_delta_to_best_win")
                delta_str = f"{delta:+d}" if delta is not None else "-"
                ts_latest = h.get("ts_latest", "-")
                ts_master = h.get("ts_master", "-")
                rpr = h.get("rpr_master", "-")
                jockey = h.get("jockey", "")
                trainer = h.get("trainer", "")
                form_str = h.get("form_string", "")
                running_style = h.get("running_style", "")
                stall = h.get("stall", "")
                age = h.get("age", "")
                headgear = h.get("headgear_cc", "") or h.get("headgear", "")
                days = h.get("days_since_last_run", "")
                trainer_win_pct = h.get("trainer_win_pct_14d")
                sp_forecast = h.get("sp_forecast", "")

                # Flags
                flags = []
                if h.get("ts_trend_signal", 0) > 0.1:
                    flags.append("TS↑")
                elif h.get("ts_trend_signal", 0) < 0:
                    flags.append("TS↓")
                or_drops = h.get("or_trend_drops", 0)
                if or_drops >= 2:
                    flags.append(f"OR↓×{or_drops}")
                if h.get("trainer_form_signal", 0) > 0:
                    flags.append("TRN+")
                if h.get("is_postdata_pick"):
                    flags.append("PD✓")
                if h.get("is_topspeed_pick"):
                    flags.append("TS✓")
                if h.get("course_winner_cc") or h.get("cd_winner_cc"):
                    flags.append("CD")
                if h.get("bf_flag"):
                    flags.append("BF")

                # OR run history (last 6)
                or_hist = h.get("or_run_history") or []
                ts_hist = h.get("ts_run_history") or []
                or_history_str = format_or_history(or_hist, 6)
                ts_history_str = format_ts_history(ts_hist, 6)

                # Spotlight comment
                spotlight = h.get("spotlight_comment", "") or ""

                # Build horse block
                horse_header = f"### {stars} {name}"
                if stall:
                    horse_header += f" (Stall {stall})"
                lines.append(horse_header)

                # Key stats line
                stats_parts = []
                stats_parts.append(f"OR: **{current_or}** | BWL: **{bwl}** | Δ: **{delta_str}**")
                stats_parts.append(f"TS: {ts_latest} | TSM: {ts_master} | RPR: {rpr}")
                stats_parts.append(f"Conv: **{conv:.3f}**")
                lines.append("  ".join(stats_parts))

                # Horse details line
                details = []
                if form_str:
                    details.append(f"Form: `{form_str}`")
                if running_style:
                    details.append(f"Style: {running_style}")
                if age:
                    details.append(f"Age: {age}")
                if headgear:
                    details.append(f"Gear: {headgear}")
                if days:
                    details.append(f"Days off: {days}")
                if sp_forecast:
                    details.append(f"SP: {sp_forecast}")
                if details:
                    lines.append("  ".join(details))

                # Jockey / Trainer
                jt_parts = []
                if jockey:
                    jt_parts.append(f"Jockey: **{jockey}**")
                if trainer:
                    jt_parts.append(f"Trainer: **{trainer}**")
                if trainer_win_pct is not None:
                    jt_parts.append(f"Trainer 14d: {trainer_win_pct}%")
                if jt_parts:
                    lines.append("  ".join(jt_parts))

                # Flags
                if flags:
                    lines.append(f"Signals: {' | '.join(flags)}")

                # OR history
                lines.append(f"OR history (latest→oldest): {or_history_str}")

                # TS history
                lines.append(f"TS history (latest→oldest): {ts_history_str}")

                # Spotlight comment — full text
                if spotlight and len(spotlight) > 10:
                    lines.append(f"> **Spotlight:** {spotlight}")
                else:
                    lines.append(f"> **Spotlight:** *(no comment)*")

                lines.append("")

            lines.append("")

    lines.append("---")
    lines.append(f"**TOTALS: {total_horses} horses | {total_picks} picks (★ and above)**")
    lines.append("")

    output_path.write_text("\n".join(lines))
    print(f"Saved: {output_path}")
    print(f"Total horses: {total_horses} | Picks: {total_picks}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_full_intel_report.py DATE VENUE1 VENUE2 ...")
        sys.exit(1)

    date = sys.argv[1]
    venues = [v.upper() for v in sys.argv[2:]]
    output_path = DATA_DIR / f"FULL_INTEL_{date}.md"
    generate_report(date, venues, output_path)
