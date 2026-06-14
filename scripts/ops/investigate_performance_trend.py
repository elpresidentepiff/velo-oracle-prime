"""
Retrospective performance audit: match all verdict files against result files.
Shows SR and frame rate trend over time to identify when/if performance degraded.
"""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

def norm(s):
    return str(s or "").strip().lower().replace("'","").replace("-"," ").replace("(aw)","").strip()

def off_key(raw):
    """Normalise off-time to H.MM format."""
    s = str(raw or "").strip()
    if "T" in s:
        try:
            dt = datetime.fromisoformat(s)
            h, m = dt.hour, dt.minute
            if h > 12: h -= 12
            elif h == 0: h = 12
            return f"{h}.{m:02d}"
        except Exception:
            pass
    return s

def load_results(path):
    """Returns dict: (norm_course, off) -> {winner, 2nd, 3rd}."""
    raw = json.loads(path.read_text("utf-8"))
    races = raw.get("results", raw) if isinstance(raw, dict) else raw
    if not isinstance(races, list):
        return {}
    lookup = {}
    for r in races:
        course = norm(r.get("course",""))
        off = str(r.get("off","")).strip()
        runners = r.get("runners",[]) or []
        top3 = sorted([x for x in runners if str(x.get("position","")) in ["1","2","3"]],
                      key=lambda x: int(x.get("position",99)))
        if top3:
            lookup[(course, off)] = {
                "winner": norm(top3[0].get("horse","")),
                "2nd":    norm(top3[1].get("horse","")) if len(top3)>1 else None,
                "3rd":    norm(top3[2].get("horse","")) if len(top3)>2 else None,
            }
    return lookup

def load_verdicts(path):
    """Returns list of {course, off, horse, vp, tier}."""
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, list):
        return []
    rows = []
    for v in raw:
        top = v.get("top") or {}
        horse = top.get("horse") or ""
        if not horse:
            continue
        course = norm(v.get("course",""))
        off = off_key(v.get("off_time",""))
        vp = float(top.get("velo_prime_prob") or 0)
        tier = v.get("tier","?")
        rows.append({"course": course, "off": off, "horse": norm(horse),
                     "vp": vp, "tier": tier, "raw_horse": top.get("horse","")})
    return rows

# Find matching date pairs
dates = []
for vf in sorted(DATA.glob("velo_prime_verdicts_*.json")):
    date_tag = vf.stem.replace("velo_prime_verdicts_","")
    rf = DATA / f"results_{date_tag}.json"
    if rf.exists():
        dates.append((date_tag, vf, rf))

print(f"Found {len(dates)} matchable days\n")
print(f"{'Date':<12} {'N':>3} {'Wins':>4} {'SR%':>5} {'Frame':>5} {'FR%':>5}  Tier breakdown (A/B/C/D/X wins)")
print("-"*85)

weekly_sr = []
all_tier_a = {"n":0,"w":0,"fr":0}
all_tier_b = {"n":0,"w":0,"fr":0}
all_vp30 = {"n":0,"w":0,"fr":0}

for date_tag, vf, rf in dates:
    try:
        results = load_results(rf)
        verdicts = load_verdicts(vf)
    except Exception as e:
        print(f"{date_tag:<12} ERROR: {e}")
        continue

    wins = frames = total = 0
    tier_wins = {}
    tier_n = {}
    for v in verdicts:
        res = results.get((v["course"], v["off"]))
        if not res:
            continue
        total += 1
        win = res["winner"] == v["horse"]
        frame = v["horse"] in [res["winner"], res["2nd"], res["3rd"]]
        wins += win
        frames += frame
        t = v["tier"]
        tier_wins[t] = tier_wins.get(t, 0) + win
        tier_n[t] = tier_n.get(t, 0) + 1

        # accumulators
        if t == "A":
            all_tier_a["n"] += 1; all_tier_a["w"] += win; all_tier_a["fr"] += frame
        if t == "B":
            all_tier_b["n"] += 1; all_tier_b["w"] += win; all_tier_b["fr"] += frame
        if v["vp"] >= 0.30:
            all_vp30["n"] += 1; all_vp30["w"] += win; all_vp30["fr"] += frame

    if total == 0:
        continue

    sr = wins/total
    fr = frames/total
    # Tier summary string
    tier_str = " ".join(f"{t}:{tier_wins.get(t,0)}/{tier_n.get(t,0)}"
                        for t in ["A","B","C","D","X"] if t in tier_n)
    weekly_sr.append((date_tag, sr, fr, total))
    print(f"{date_tag:<12} {total:>3}  {wins:>3}   {sr*100:>4.1f}%  {frames:>3}  {fr*100:>4.1f}%  {tier_str}")

# Summary stats
print("\n" + "="*85)
print("OVERALL CUMULATIVE SIGNAL TRUTH")
print(f"  Tier A:  {all_tier_a['w']}/{all_tier_a['n']}  SR={all_tier_a['w']/max(all_tier_a['n'],1)*100:.1f}%  Frame={all_tier_a['fr']/max(all_tier_a['n'],1)*100:.1f}%")
print(f"  Tier B:  {all_tier_b['w']}/{all_tier_b['n']}  SR={all_tier_b['w']/max(all_tier_b['n'],1)*100:.1f}%  Frame={all_tier_b['fr']/max(all_tier_b['n'],1)*100:.1f}%")
print(f"  VP30+:   {all_vp30['w']}/{all_vp30['n']}   SR={all_vp30['w']/max(all_vp30['n'],1)*100:.1f}%  Frame={all_vp30['fr']/max(all_vp30['n'],1)*100:.1f}%")

# 4-week rolling window
print("\nROLLING 14-DAY WINDOWS (trend)")
for i in range(0, len(weekly_sr), 7):
    chunk = weekly_sr[i:i+14]
    if not chunk: break
    total_n = sum(x[3] for x in chunk)
    total_w = sum(x[3]*x[1] for x in chunk)
    total_fr = sum(x[3]*x[2] for x in chunk)
    period = f"{chunk[0][0]} to {chunk[-1][0]}"
    sr = total_w/total_n if total_n else 0
    fr = total_fr/total_n if total_n else 0
    print(f"  {period}  n={total_n}  SR={sr*100:.1f}%  Frame={fr*100:.1f}%")
