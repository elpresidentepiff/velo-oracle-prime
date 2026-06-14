import json
from pathlib import Path

def _norm_time(t: str) -> str:
    # Convert '2.21' -> '14:21' (assuming afternoon if < 11)
    if ":" in t:
        return t
    parts = t.split(".")
    h = int(parts[0])
    m = parts[1]
    if h < 11:
        h += 12
    return f"{h:02}:{m}"

def verify_honest():
    ROOT = Path(".")
    verdicts_path = ROOT / "data" / "velo_prime_verdicts_2026_06_04.json"
    results_path = ROOT / "data" / "results_2026_06_04.json"
    
    if not verdicts_path.exists() or not results_path.exists():
        print("Missing data files.")
        return

    verdicts = json.load(verdicts_path.open(encoding="utf-8"))
    results = json.load(results_path.open(encoding="utf-8"))["results"]
    
    # Map verdicts by (course, off_time)
    v_map = {}
    for v in verdicts:
        course = v["course"].lower().replace(" (aw)", "").split(" (")[0].strip()
        v_map[(course, v["off_time"])] = v
        
    print("| Race | VÉLØ Top Pick | Tier | Winner | Pos | SP | Result |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    hits = 0
    total = 0
    
    for r in results:
        course = r["course"].lower().replace(" (aw)", "").split(" (")[0].strip()
        off = _norm_time(r["off"])
        key = (course, off)
        
        v = v_map.get(key)
        if not v:
            # Try fuzzy match if exact fails
            continue
            
        total += 1
        pick = v["top"]["horse"]
        tier = v["tier"]
        
        winners = [h["horse"] for h in r["runners"] if h["position"] == "1"]
        winner = winners[0] if winners else "?"
        
        # Find pick position
        p_run = next((h for h in r["runners"] if h["horse"].lower() == pick.lower()), None)
        pos = p_run["position"] if p_run else "U"
        sp = p_run["sp"] if p_run else "-"
        
        res_str = "LOST"
        if pos == "1":
            res_str = "**HIT**"
            hits += 1
        elif pos in ("2", "3"):
            res_str = "*FRAME*"
            
        print(f"| {r['course']} {off} | {pick} | {tier} | {winner} | {pos} | {sp} | {res_str} |")
        
    print(f"\n**HITS: {hits} / {total} ({ (hits/total)*100 if total > 0 else 0:.1f}%)**")

if __name__ == "__main__":
    verify_honest()
