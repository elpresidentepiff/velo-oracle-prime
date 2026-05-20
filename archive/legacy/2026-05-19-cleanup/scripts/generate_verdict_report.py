#!/usr/bin/env python3
"""
VÉLØ Daily Verdict Report
One line per plot candidate. Engine reads the run history. You see the verdict.
"""
import json
from pathlib import Path

MERGED_DIR = Path(__file__).parent.parent / "data" / "racecard_merged"
DATE = "2026-04-23"
VENUES = [
    ("STH", "Southwell"),
    ("DUN", "Dundalk"),
    ("BEV", "Beverley"),
    ("PER", "Perth"),
    ("WAR", "Warwick"),
]
OUTPUT = MERGED_DIR / f"VERDICTS_{DATE}.md"


def analyse_runs(ts_runs, or_runs):
    """
    Engine reads the last 6 runs and returns:
    - or_trend: how much OR has dropped across runs (positive = dropping = good)
    - ts_peak: best TS in last 6 runs (true ability)
    - ts_latest: most recent TS
    - ts_improving: is TS trending up recently?
    - engine_on: horse has shown a strong run (TS >= 60) in last 6
    - setup_runs: number of unplaced runs (pos=0 or pos>=6) in last 6 = possible education
    - true_run_detected: at least one top-3 finish with TS >= 55
    """
    ts_vals = [r["ts"] for r in ts_runs if r.get("ts") is not None][-6:]
    or_vals = [r["or"] for r in or_runs if r.get("or") is not None][-6:]
    pos_vals = [r["pos"] for r in ts_runs if r.get("pos") is not None][-6:]

    or_trend = None
    if len(or_vals) >= 2:
        or_trend = or_vals[0] - or_vals[-1]  # positive = OR dropped (good for plot)

    ts_peak = max(ts_vals) if ts_vals else None
    ts_latest = ts_vals[-1] if ts_vals else None
    ts_improving = None
    if len(ts_vals) >= 3:
        recent_avg = sum(ts_vals[-2:]) / 2
        older_avg = sum(ts_vals[:-2]) / max(len(ts_vals) - 2, 1)
        ts_improving = recent_avg > older_avg

    engine_on = ts_peak is not None and ts_peak >= 60
    setup_runs = sum(1 for p in pos_vals if p == 0 or p >= 6)
    true_run_detected = any(
        p is not None and ts is not None and p <= 3 and ts >= 55
        for p, ts in zip(pos_vals, ts_vals)
    )

    return {
        "or_trend": or_trend,
        "ts_peak": ts_peak,
        "ts_latest": ts_latest,
        "ts_improving": ts_improving,
        "engine_on": engine_on,
        "setup_runs": setup_runs,
        "true_run_detected": true_run_detected,
    }


def build_verdict(h):
    """Build a single verdict string for a horse."""
    ts_runs = [r for r in (h.get("ts_run_history") or []) if r.get("ts") is not None]
    or_runs = [r for r in (h.get("or_run_history") or []) if r.get("or") is not None]
    eng = analyse_runs(ts_runs, or_runs)

    delta = h.get("or_delta_to_best_win")
    hg = h.get("headgear_code", "")
    tf = h.get("trainer_form", "")
    signals = h.get("intent_signals", []) or []
    conv = h.get("plot_conviction", 0) or 0

    parts = []

    # OR drop
    if isinstance(delta, (int, float)) and delta <= 0:
        parts.append(f"{abs(int(delta))}lb below winning mark")
    elif isinstance(delta, (int, float)) and delta <= 3:
        parts.append(f"at winning mark")

    # OR trend from run history
    if eng["or_trend"] and eng["or_trend"] >= 5:
        parts.append(f"OR dropped {eng['or_trend']}pts in last 6")

    # Engine assessment
    if eng["true_run_detected"] and eng["engine_on"]:
        parts.append(f"engine proven (peak TS {eng['ts_peak']})")
    elif eng["engine_on"]:
        parts.append(f"strong engine (peak TS {eng['ts_peak']})")
    elif eng["ts_peak"]:
        parts.append(f"limited engine (peak TS {eng['ts_peak']})")

    # Setup runs
    if eng["setup_runs"] >= 3:
        parts.append(f"{eng['setup_runs']} setup runs")
    elif eng["setup_runs"] >= 2:
        parts.append(f"possible education ({eng['setup_runs']} poor runs)")

    # Gear
    gear_names = {
        "b1": "blinkers 1st time", "v1": "visor 1st time",
        "p1": "cheekpieces 1st time", "t1": "tongue tie 1st time",
        "b": "blinkers", "v": "visor", "p": "cheekpieces",
    }
    if hg:
        parts.append(gear_names.get(hg, f"{hg} headgear"))

    # Stable
    if tf == "negative":
        parts.append("cold stable")
    elif tf == "strong_positive":
        parts.append("hot stable")

    # TS improving
    if eng["ts_improving"]:
        parts.append("TS improving")

    # Conviction rating
    if conv >= 0.85:
        rating = "★★★"
    elif conv >= 0.75:
        rating = "★★"
    else:
        rating = "★"

    verdict = " · ".join(parts) if parts else "at winning mark"
    return rating, verdict


lines = []
lines.append(f"# VÉLØ Verdicts — {DATE}\n")

total = 0

for code, name in VENUES:
    fpath = MERGED_DIR / f"racecard_{code}_{DATE}.json"
    if not fpath.exists():
        continue
    data = json.load(open(fpath))

    picks = []
    for race_time in sorted(data["races"].keys()):
        race = data["races"][race_time]
        race_info = race.get("race_info", "")
        # Extract short race description
        race_short = race_info.split("Last")[0].strip() if "Last" in race_info else race_info[:40]

        for h in race.get("horses", []):
            conv = h.get("plot_conviction", 0) or 0
            if conv < 0.7:
                continue
            hname = h.get("horse_name", "?")
            # Skip form parser artifacts
            if "wins plcs" in hname.lower() or hname.lower() == "spotlight verdict" or hname.lower().startswith("xj "):
                continue
            # Skip names that end in a long number suffix (form parser duplicate)
            import re
            if re.search(r'\s+\d{4,}$', hname):
                continue

            rating, verdict = build_verdict(h)
            picks.append((race_time, race_short, hname, rating, verdict))
            total += 1

    # Deduplicate: if same horse name appears twice in same race, keep first (highest conviction)
    seen = set()
    deduped = []
    for item in picks:
        key = (item[0], item[2].lower().split()[0])  # race_time + first word of name
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    picks = deduped
    total = total - (len(picks) - len(deduped)) if len(deduped) < len(picks) else total

    if not picks:
        continue

    lines.append(f"## {name}\n")
    lines.append(f"| Time | Horse | Rating | Verdict |")
    lines.append(f"|---|---|---|---|")
    for race_time, race_short, hname, rating, verdict in picks:
        lines.append(f"| {race_time} | **{hname}** | {rating} | {verdict} |")
    lines.append("")

lines.append(f"---\n**{total} plot candidates identified**")

report = "\n".join(lines)
OUTPUT.write_text(report)
print(report)
print(f"\nSaved: {OUTPUT}")
