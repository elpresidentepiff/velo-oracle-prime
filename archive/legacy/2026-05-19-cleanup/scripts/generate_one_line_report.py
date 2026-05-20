"""
VÉLØ One-Line-Per-Horse Report — 25 Apr 2026 only
===================================================
FORMAT PER HORSE (one line):
STARS | RACE | HORSE | OR-history(6) | TS-history(6) | Trainer | Jockey | Form | Spotlight

Then the full spotlight comment on the next line, indented.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "racecard_merged"
DATE = "2026-04-25"
VENUES = ["SAN", "HAY", "LEI", "LIM", "NAV"]


def stars(conv):
    if conv is None or conv == 0:
        return "   "
    if conv >= 0.90:
        return "★★★"
    if conv >= 0.80:
        return "★★ "
    if conv >= 0.70:
        return "★  "
    return "   "


def or_hist(history, n=6):
    if not history:
        return "[-,-,-,-,-,-]"
    parts = []
    for r in (history or [])[:n]:
        pos = r.get("pos") or r.get("position") or "-"
        val = r.get("or") or r.get("or_val") or "-"
        parts.append(f"{pos}/{val}")
    while len(parts) < n:
        parts.append("-/-")
    return "[" + ", ".join(parts) + "]"


def ts_hist(history, n=6):
    if not history:
        return "[-,-,-,-,-,-]"
    parts = []
    for r in (history or [])[:n]:
        pos = r.get("pos") or r.get("position") or "-"
        val = r.get("ts") or r.get("ts_val") or "-"
        parts.append(f"{pos}/{val}")
    while len(parts) < n:
        parts.append("-/-")
    return "[" + ", ".join(parts) + "]"


def run():
    out_path = DATA_DIR / f"CASHRUN_{DATE}.md"
    lines = []
    lines.append(f"# VÉLØ CASH RUN — {DATE}")
    lines.append(f"**One line per horse. Last 6 OR. Last 6 TS. Spotlight. Form. Trainer. Jockey.**")
    lines.append(f"**OR/TS format: pos/rating, latest first**")
    lines.append("")

    total_horses = 0
    total_picks = 0

    for venue in VENUES:
        path = DATA_DIR / f"racecard_{venue}_{DATE}.json"
        if not path.exists():
            lines.append(f"## {venue} — NOT FOUND")
            continue

        with open(path) as f:
            data = json.load(f)

        races = data.get("races", {})
        lines.append(f"---")
        lines.append(f"## {venue}")
        lines.append("")

        for race_time in sorted(races.keys()):
            race = races[race_time]
            race_info = race.get("race_info", "")
            pd_pick = race.get("postdata_pick", "")
            ts_pick = race.get("topspeed_pick", "")
            sv = race.get("spotlight_verdict", "")

            lines.append(f"### {venue} {race_time}  {race_info}")
            if pd_pick:
                lines.append(f"*PD pick: {pd_pick}*  |  *TS pick: {ts_pick}*")
            if sv:
                lines.append(f"*VERDICT: {sv[:200]}*")
            lines.append("")

            # Column header
            lines.append("```")
            lines.append(f"{'STARS':<5} {'HORSE':<28} {'OR [6 runs: pos/OR latest→oldest]':<45} {'TS [6 runs: pos/TS latest→oldest]':<45} {'TRAINER':<25} {'JOCKEY':<22} {'FORM':<18} CONV")
            lines.append("-" * 200)

            for h in race.get("horses", []):
                name = h.get("horse_name", "?")
                # Skip meta entries
                if name in ("Spotlight Verdict", "SPOTLIGHT VERDICT"):
                    continue

                conv = h.get("plot_conviction") or 0
                total_horses += 1
                if conv >= 0.70:
                    total_picks += 1

                s = stars(conv)
                oh = or_hist(h.get("or_run_history"), 6)
                th = ts_hist(h.get("ts_run_history"), 6)
                trainer = (h.get("trainer") or "")[:24]
                jockey = (h.get("jockey") or "")[:21]
                form = (h.get("form_string") or "")[:17]
                conv_str = f"{conv:.3f}" if conv else "0.000"

                line = f"{s:<5} {name:<28} {oh:<45} {th:<45} {trainer:<25} {jockey:<22} {form:<18} {conv_str}"
                lines.append(line)

                # Spotlight comment on next line, indented
                comment = (h.get("spotlight_comment") or "").strip()
                if comment:
                    # Wrap at 180 chars
                    words = comment.split()
                    cur = "      > "
                    for w in words:
                        if len(cur) + len(w) + 1 > 188:
                            lines.append(cur)
                            cur = "        " + w
                        else:
                            cur += " " + w
                    if cur.strip():
                        lines.append(cur)
                lines.append("")

            lines.append("```")
            lines.append("")

    lines.append("---")
    lines.append(f"**TOTAL: {total_horses} horses | {total_picks} picks (★ and above)**")

    out_path.write_text("\n".join(lines))
    print(f"Saved: {out_path}")
    print(f"Horses: {total_horses} | Picks: {total_picks}")


if __name__ == "__main__":
    run()
