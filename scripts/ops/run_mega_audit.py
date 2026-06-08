import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

def get_week_start(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start = dt - timedelta(days=dt.weekday())
    return start.strftime("%Y-%m-%d")

def get_month(date_str):
    return date_str[:7]

def _norm_t(t):
    if ":" in t: return t
    parts = t.split(".")
    if len(parts) < 2: return f"{int(t):02}:00"
    h = int(parts[0])
    if h < 11: h += 12
    return f"{h:02}:{parts[1]}"

def _norm_c(c):
    return c.lower().split(" (")[0].strip()

def run_mega_audit():
    ROOT = Path(".")
    
    # 1. Gather all Verdicts
    verdict_files = list(ROOT.glob("data/velo_prime_verdicts_202*.json"))
    verdict_data = {} # (date, course, time) -> horse
    for vf in verdict_files:
        date_match = re.search(r"(\d{4}_\d{2}_\d{2})", vf.name)
        if not date_match: continue
        date_str = date_match.group(1).replace("_", "-")
        try:
            with vf.open(encoding="utf-8") as f:
                data = json.load(f)
                for v in data:
                    key = (date_str, _norm_c(v["course"]), v["off_time"])
                    verdict_data[key] = v["top"]["horse"].lower()
        except: continue
    
    # 2. Gather all Results
    results_files = list(ROOT.glob("data/results_202*.json")) + list(ROOT.glob("data/results/rp_results_202*.json"))
    results_data = {} # (date, course, time) -> winner
    for rf in results_files:
        date_match = re.search(r"(\d{4}[_-]\d{2}[_-]\d{2})", rf.name)
        if not date_match: continue
        date_str = date_match.group(1).replace("_", "-")
        try:
            with rf.open(encoding="utf-8") as f:
                data = json.load(f)
                # Handle different formats
                res_list = data.get("results") if isinstance(data, dict) else data
                if not res_list: continue
                for r in res_list:
                    winner = next((h["horse"] for h in r["runners"] if h.get("position") == "1"), None)
                    if winner:
                        key = (date_str, _norm_c(r["course"]), _norm_t(r["off"]))
                        results_data[key] = winner.lower()
        except: continue

    # 3. Gather all Institutional Selections (Parsed Injection Files)
    # These contain the 'top_newspaper_tips' list
    injection_dirs = list((ROOT / "data/racing_post_account_parsed/").glob("202*"))
    npc_data = {} # (date, course, time) -> horse
    for idir in injection_dirs:
        inj_file = idir / "racecard_injection.json"
        if not inj_file.exists(): continue
        date_str = idir.name[:10]
        try:
            with inj_file.open(encoding="utf-8") as f:
                data = json.load(f)
                for race in data.get("races", []):
                    tips = race.get("top_newspaper_tips", [])
                    if tips:
                        # NPC is the horse with the most tips
                        npc_horse = tips[0]["horse"].lower()
                        # Time in injection is ISO
                        t_norm = race["race_time"].split("T")[1][:5]
                        key = (date_str, _norm_c(race["course"]), t_norm)
                        npc_data[key] = npc_horse
        except: continue

    # 4. Reconcile
    all_keys = set(results_data.keys()) & (set(verdict_data.keys()) | set(npc_data.keys()))
    
    stats = defaultdict(lambda: {"total": 0, "velo": 0, "npc": 0})
    
    for key in all_keys:
        date_str, course, off = key
        winner = results_data[key]
        
        velo_pick = verdict_data.get(key)
        npc_pick = npc_data.get(key)
        
        # Monthly/Weekly/All-Time buckets
        month = get_month(date_str)
        week = get_week_start(date_str)
        buckets = ["all-time", month, week]
        
        for b in buckets:
            stats[b]["total"] += 1
            if velo_pick and velo_pick == winner:
                stats[b]["velo"] += 1
            if npc_pick and npc_pick == winner:
                stats[b]["npc"] += 1
                
    # 5. Output Tables
    def _print_table(title, items):
        print(f"\n### {title}")
        print("| Period | Races | VÉLØ SR | NPC SR | Delta |")
        print("| :--- | :--- | :--- | :--- | :--- |")
        for period in sorted(items, reverse=True):
            s = stats[period]
            v_sr = (s["velo"]/s["total"])*100 if s["total"] > 0 else 0
            n_sr = (s["npc"]/s["total"])*100 if s["total"] > 0 else 0
            print(f"| {period} | {s['total']} | {v_sr:.1f}% | {n_sr:.1f}% | {v_sr - n_sr:+.1f}% |")

    # Filter buckets
    months = [k for k in stats.keys() if len(k) == 7]
    weeks = [k for k in stats.keys() if len(k) == 10]
    
    _print_table("MONTHLY LEAGUE TABLE", months)
    _print_table("WEEKLY LEAGUE TABLE (LAST 4)", sorted(weeks, reverse=True)[:4])
    _print_table("ALL-TIME CHAMPIONSHIP", ["all-time"])

if __name__ == "__main__":
    run_mega_audit()
