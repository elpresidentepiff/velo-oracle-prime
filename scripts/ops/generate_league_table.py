import json
from pathlib import Path

def generate_league_table():
    ROOT = Path(".")
    inj_path = ROOT / "data" / "racing_post_account_parsed" / "2026-06-04" / "racecard_injection.json"
    ver_path = ROOT / "data" / "velo_prime_verdicts_2026_06_04.json"
    res_path = ROOT / "data" / "results_2026_06_04.json"
    
    if not all([inj_path.exists(), ver_path.exists(), res_path.exists()]):
        print("Missing data files.")
        return

    inj_data = json.load(inj_path.open(encoding="utf-8"))
    ver_data = json.load(ver_path.open(encoding="utf-8"))
    res_data = json.load(res_path.open(encoding="utf-8"))["results"]
    
    # Normalizers
    def _norm_t(t):
        if ":" in t: return t
        parts = t.split(".")
        h = int(parts[0])
        if h < 11: h += 12
        return f"{h:02}:{parts[1]}"
    
    def _norm_c(c):
        return c.lower().split(" (")[0].strip()

    # Build Maps
    results_map = { (_norm_c(r["course"]), _norm_t(r["off"])): r for r in res_data }
    velo_map = { (_norm_c(v["course"]), v["off_time"]): v for v in ver_data }
    
    print("| Race | VÉLØ Pick | NP Consensus | Winner | VÉLØ | NPC |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    velo_hits = 0
    npc_hits = 0
    total = 0
    
    for race in inj_data["races"]:
        c_norm = _norm_c(race["course"])
        # Extract '14:00' from '2026-06-04T14:00:00+01:00'
        t_norm = race["race_time"].split("T")[1][:5]
        key = (c_norm, t_norm)
        
        res = results_map.get(key)
        if not res: continue
        
        v = velo_map.get(key)
        if not v: continue
        
        total += 1
        
        # 1. VÉLØ Pick
        velo_pick = v["top"]["horse"]
        
        # 2. Newspaper Consensus (most tips)
        top_tips = race.get("top_newspaper_tips", [])
        npc_pick = top_tips[0]["horse"] if top_tips else "?"
        
        # 3. Actual Winner
        winners = [h["horse"] for h in res["runners"] if h["position"] == "1"]
        winner = winners[0] if winners else "?"
        
        # Check Hits
        v_hit = velo_pick.lower() == winner.lower()
        n_hit = npc_pick.lower() == winner.lower()
        
        if v_hit: velo_hits += 1
        if n_hit: npc_hits += 1
        
        v_mark = "✅" if v_hit else "❌"
        n_mark = "✅" if n_hit else "❌"
        
        print(f"| {race['course']} {t_norm} | {velo_pick} | {npc_pick} | {winner} | {v_mark} | {n_mark} |")

    print(f"\n### LEAGUE TABLE — JUNE 4TH")
    print(f"| Rank | Entity | Strike Rate | Winners |")
    print(f"| :--- | :--- | :--- | :--- |")
    
    # Sort results
    entities = [
        ("VÉLØ ORACLE PRIME", velo_hits),
        ("NP CONSENSUS", npc_hits)
    ]
    entities.sort(key=lambda x: x[1], reverse=True)
    
    for i, (name, hits) in enumerate(entities):
        sr = (hits / total) * 100 if total > 0 else 0
        print(f"| {i+1} | {name} | {sr:.1f}% | {hits} |")
    
    print(f"\n*Total Races Scored: {total}*")

if __name__ == "__main__":
    generate_league_table()
