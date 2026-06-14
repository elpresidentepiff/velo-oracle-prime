"""Check VP level trends and tier composition over recent verdict files."""
import json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Recent verdict files
verdict_files = sorted(DATA.glob("velo_prime_verdicts_2026_0[5-6]*.json"))

print(f"{'Date':<12} {'Races':>5} {'VPs':>5}  VP_med  VP_max  VP30+  TierA  TierB  TierC  T-A_VP")
print("-"*80)

for vf in verdict_files:
    raw = json.loads(vf.read_text("utf-8"))
    if not isinstance(raw, list) or not raw:
        continue

    vps = []
    tier_counts = {}
    tier_a_vps = []

    for v in raw:
        top = v.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0)
        tier = v.get("tier", "?")
        vps.append(vp)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if tier == "A":
            tier_a_vps.append(vp)

    if not vps:
        continue

    date_tag = vf.stem.replace("velo_prime_verdicts_", "")
    n_races = len(raw)
    med = statistics.median(vps)
    mx = max(vps)
    vp30 = sum(1 for v in vps if v >= 0.30)
    ta = tier_counts.get("A", 0)
    tb = tier_counts.get("B", 0)
    tc = tier_counts.get("C", 0)
    ta_med = f"{statistics.median(tier_a_vps):.3f}" if tier_a_vps else " n/a "

    print(f"{date_tag:<12} {n_races:>5}  {len(vps):>4}  {med:.3f}  {mx:.3f}  {vp30:>4}  {ta:>4}  {tb:>4}  {tc:>4}  {ta_med}")

# Also check the post-ensemble-surgery period (before/after 2026-05-08)
print("\n--- Pre-surgery avg (before May 8) vs Post (May 8+) ---")
pre_vps, post_vps = [], []
pre_ta, post_ta = 0, 0

for vf in sorted(DATA.glob("velo_prime_verdicts_2026_0[34]*.json")) + sorted(DATA.glob("velo_prime_verdicts_2026_05_0[1-7]*.json")):
    raw = json.loads(vf.read_text("utf-8"))
    if not isinstance(raw, list): continue
    for v in raw:
        top = v.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0)
        pre_vps.append(vp)
        if v.get("tier") == "A": pre_ta += 1

for vf in sorted(DATA.glob("velo_prime_verdicts_2026_05_0[89]*.json")) + sorted(DATA.glob("velo_prime_verdicts_2026_05_[1-9]*.json")) + sorted(DATA.glob("velo_prime_verdicts_2026_06*.json")):
    raw = json.loads(vf.read_text("utf-8"))
    if not isinstance(raw, list): continue
    for v in raw:
        top = v.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0)
        post_vps.append(vp)
        if v.get("tier") == "A": post_ta += 1

if pre_vps:
    print(f"Pre-surgery:  n={len(pre_vps)}  VP_med={statistics.median(pre_vps):.3f}  VP_mean={sum(pre_vps)/len(pre_vps):.3f}  VP30+={sum(1 for v in pre_vps if v>=0.30)}  TierA={pre_ta}")
if post_vps:
    print(f"Post-surgery: n={len(post_vps)}  VP_med={statistics.median(post_vps):.3f}  VP_mean={sum(post_vps)/len(post_vps):.3f}  VP30+={sum(1 for v in post_vps if v>=0.30)}  TierA={post_ta}")
