"""Check what's failing the tier gates on recent days."""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Check recent verdict files — look at top picks
recent_dates = ["2026_05_22","2026_05_23","2026_05_27","2026_05_29","2026_05_30",
                "2026_06_01","2026_06_02","2026_06_03"]

print("=== Tier Gate Diagnostics (A-gate: prob>=0.32, gap>=0.08, place>=0.52) ===\n")

for date_tag in recent_dates:
    path = DATA / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists(): continue
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, list): continue

    probs, gaps, places = [], [], []
    tier_a, tier_b, tier_c = 0, 0, 0

    for v in raw:
        top = v.get("top") or {}
        prob = float(top.get("velo_prime_prob") or 0)
        gap  = float(top.get("prob_gap") or 0)
        place = float(top.get("place_prob") or 0)
        tier = v.get("tier","?")
        probs.append(prob); gaps.append(gap); places.append(place)
        if tier == "A": tier_a += 1
        elif tier == "B": tier_b += 1
        elif tier == "C": tier_c += 1

    if not probs: continue
    above_prob = sum(1 for x in probs if x >= 0.32)
    above_gap  = sum(1 for x in gaps  if x >= 0.08)
    above_place= sum(1 for x in places if x >= 0.52)
    all_three  = sum(1 for p,g,pl in zip(probs,gaps,places) if p>=0.32 and g>=0.08 and pl>=0.52)

    print(f"{date_tag}  TierA={tier_a}  TierB={tier_b}  TierC={tier_c}")
    print(f"  prob:  med={statistics.median(probs):.3f}  max={max(probs):.3f}  above0.32={above_prob}/{len(probs)}")
    print(f"  gap:   med={statistics.median(gaps):.3f}   max={max(gaps):.3f}   above0.08={above_gap}/{len(gaps)}")
    print(f"  place: med={statistics.median(places):.3f} max={max(places):.3f}  above0.52={above_place}/{len(places)}")
    print(f"  ALL 3 gates met: {all_three}/{len(probs)}")
    print()

# Show early period for comparison (pre-surgery)
print("=== PRE-SURGERY SAMPLE (2026-05-04) ===")
path = DATA / "velo_prime_verdicts_2026_05_04.json"
if path.exists():
    raw = json.loads(path.read_text("utf-8"))
    probs = [float((v.get("top") or {}).get("velo_prime_prob") or 0) for v in raw]
    gaps  = [float((v.get("top") or {}).get("prob_gap") or 0) for v in raw]
    places= [float((v.get("top") or {}).get("place_prob") or 0) for v in raw]
    tier_counts = {}
    for v in raw: tier_counts[v.get("tier","?")] = tier_counts.get(v.get("tier","?"),0)+1
    print(f"  Tiers: {tier_counts}")
    above_prob = sum(1 for x in probs if x >= 0.32)
    above_gap  = sum(1 for x in gaps  if x >= 0.08)
    above_place= sum(1 for x in places if x >= 0.52)
    print(f"  prob:  med={statistics.median(probs):.3f}  max={max(probs):.3f}  above0.32={above_prob}/{len(probs)}")
    print(f"  gap:   med={statistics.median(gaps):.3f}   max={max(gaps):.3f}   above0.08={above_gap}/{len(gaps)}")
    print(f"  place: med={statistics.median(places):.3f} max={max(places):.3f}  above0.52={above_place}/{len(places)}")
    all_three = sum(1 for p,g,pl in zip(probs,gaps,places) if p>=0.32 and g>=0.08 and pl>=0.52)
    print(f"  ALL 3 gates met: {all_three}/{len(probs)}")
