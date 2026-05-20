"""Check data quality for a given date across venues."""
import json
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "racecard_merged"
date = sys.argv[1] if len(sys.argv) > 1 else "2026-04-28"
venues = sys.argv[2:] if len(sys.argv) > 2 else ["LIN", "STH", "YAR", "EPS", "PUN"]

for v in venues:
    f = DATA / f"racecard_{v}_{date}.json"
    if not f.exists():
        print(f"{v}: FILE MISSING")
        continue
    data = json.loads(f.read_text())
    races = data.get("races", {})
    horses = []
    if isinstance(races, dict):
        for rtime, r in races.items():
            if isinstance(r, dict):
                for h in r.get("horses", []):
                    if isinstance(h, dict):
                        horses.append(h)
    elif isinstance(races, list):
        for r in races:
            if isinstance(r, dict):
                for h in r.get("horses", []):
                    if isinstance(h, dict):
                        horses.append(h)
    with_spot = sum(1 for h in horses if h.get("spotlight_comment", "").strip())
    with_or = sum(1 for h in horses if h.get("or_run_history"))
    with_ts = sum(1 for h in horses if h.get("ts_run_history"))
    bad_names = [h["horse_name"] for h in horses if any(c.isdigit() for c in h.get("horse_name", ""))]
    print(f"{v}: {len(horses)} horses | OR:{with_or} | TS:{with_ts} | Spotlight:{with_spot} | BadNames:{len(bad_names)} {bad_names[:3] if bad_names else ''}")
