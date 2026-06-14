"""Diagnose why horse name matching fails for early dates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

def norm(s):
    return str(s or "").strip().lower().replace("'","").replace("-"," ").replace("(aw)","").strip()

# Check a March verdict vs March results
vf = DATA / "velo_prime_verdicts_2026_03_21.json"
rf = DATA / "results_2026_03_21.json"

verdicts = json.loads(vf.read_text("utf-8"))
results_raw = json.loads(rf.read_text("utf-8"))
races = results_raw.get("results", results_raw) if isinstance(results_raw, dict) else results_raw

print("=== VERDICT format (first 2 rows) ===")
for v in verdicts[:2]:
    top = v.get("top") or {}
    print(f"  course={v.get('course')!r}  off={v.get('off_time')!r}  horse={top.get('horse')!r}  tier={v.get('tier')!r}")

print("\n=== RESULTS format (first 2 races, top finishers) ===")
for r in races[:2]:
    runners = r.get("runners",[])
    top = [x for x in runners if str(x.get("position","")) in ["1","2","3"]]
    top.sort(key=lambda x: int(x.get("position",99)))
    print(f"  course={r.get('course')!r}  off={r.get('off')!r}")
    for t in top[:2]:
        print(f"    pos={t.get('position')}  horse={t.get('horse')!r}")

print("\n=== Checking off_time format in verdicts ===")
for v in verdicts[:3]:
    print(f"  off_time={v.get('off_time')!r}")

# Check if runner position is stored differently in old results
print("\n=== Runner fields in old results ===")
r0 = races[0]
if r0.get("runners"):
    print(f"  runner keys: {list(r0['runners'][0].keys())[:10]}")
    print(f"  first runner position field: {r0['runners'][0].get('position')!r}")
