import json
from pathlib import Path

def verify_new_build():
    ROOT = Path(".")
    nb_path = ROOT / "data" / "new_build" / "reports" / "two_lane_readiness_2026_06_04.json"
    res_path = ROOT / "data" / "results_2026_06_04.json"
    
    if not nb_path.exists() or not res_path.exists():
        print(f"Missing files: {nb_path.exists()} {res_path.exists()}")
        return

    nb_data = json.load(nb_path.open(encoding="utf-8"))
    results = json.load(res_path.open(encoding="utf-8"))["results"]
    
    # Map results by (course, time)
    r_map = {}
    for r in results:
        course = r["course"].lower().split(" (")[0].strip()
        # Convert '2.21' -> '14:21'
        t = r["off"]
        if ":" not in t:
            parts = t.split(".")
            h = int(parts[0])
            if h < 11: h += 12
            t = f"{h:02}:{parts[1]}"
        r_map[(course, t)] = r
        
    print("| Race | New Build (Lane A) Top Pick | Prob | Winner | Pos | SP | Result |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    hits = 0
    total = 0
    
    for race in nb_data.get("race_day_scorecards", []):
        course = race["course"].lower().split(" (")[0].strip()
        # Off time in scorecard is ISO '2026-06-04T14:00:00+01:00'
        off_iso = race["off_time"]
        off_time = off_iso.split("T")[1][:5] # '14:00'
        key = (course, off_time)
        
        res = r_map.get(key)
        if not res:
            continue
            
        total += 1
        
        # New Build Lane A Top Pick
        lane_a = race.get("lane_a_top3", [])
        if not lane_a:
            continue
            
        pick_data = lane_a[0]
        pick = pick_data["horse"]
        prob = pick_data.get("prob", 0)
        
        winners = [h["horse"] for h in res["runners"] if h["position"] == "1"]
        winner = winners[0] if winners else "?"
        
        p_run = next((h for h in res["runners"] if h["horse"].lower() == pick.lower()), None)
        pos = p_run["position"] if p_run else "U"
        sp = p_run["sp"] if p_run else "-"
        
        res_str = "LOST"
        if pos == "1":
            res_str = "**HIT**"
            hits += 1
        elif pos in ("2", "3"):
            res_str = "*FRAME*"
            
        print(f"| {race['course']} {off_time} | {pick} | {prob:.3f} | {winner} | {pos} | {sp} | {res_str} |")
        
    print(f"\n**NEW BUILD HITS: {hits} / {total} ({ (hits/total)*100 if total > 0 else 0:.1f}%)**")

if __name__ == "__main__":
    verify_new_build()
