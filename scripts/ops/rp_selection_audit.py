"""
RP Selections Cross-Reference Audit (v3 - with debug)
Compares VELO Tier A picks against Racing Post selections.
"""
import json
import os
from pathlib import Path
import pandas as pd
import re

ROOT = Path(".")
DATA_DIR = ROOT / "data"
MERGED_DIR = ROOT / "data" / "racecard_merged"
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def norm(s):
    if not s: return ""
    v = str(s).strip().lower()
    v = v.replace("(aw)", "").replace("aw", "")
    v = re.sub(r"\([a-z]{2,3}\)", "", v)
    return re.sub(r"[^a-z]", "", v).strip()

def norm_time(t):
    if not t: return ""
    t = str(t).replace(":", ".")
    try:
        parts = t.split(".")
        h = int(parts[0])
        m = parts[1]
        if h > 12: h -= 12
        return f"{h}.{m}"
    except:
        return t

def get_last_10_dates():
    files = sorted(DATA_DIR.glob("velo_prime_verdicts_2026_*.json"))
    dates = [f.name.replace("velo_prime_verdicts_", "").replace(".json", "") for f in files]
    return dates[-10:]

def run_audit():
    dates = get_last_10_dates()
    if not dates:
        print("No verdict files found.")
        return

    audit_records = []
    merged_files = list(MERGED_DIR.glob("racecard_*.json"))
    
    for df in dates:
        print(f"Auditing {df}...")
        date_iso = df.replace("_", "-")
        
        verdicts_path = DATA_DIR / f"velo_prime_verdicts_{df}.json"
        if not verdicts_path.exists(): continue
        verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
        
        results_path = DATA_DIR / f"results_{df}.json"
        results_map = {}
        if results_path.exists():
            res_data = json.loads(results_path.read_text(encoding="utf-8"))
            res_list = res_data.get("results", []) if isinstance(res_data, dict) else res_data
            for r in res_list:
                results_map[(norm(r.get("course")), norm_time(r.get("off")))] = r

        daily_merged = {} 
        for mf in [f for f in merged_files if date_iso in f.name]:
            try:
                m_data = json.loads(mf.read_text(encoding="utf-8"))
                venue = norm(m_data.get("venue"))
                venue_code = norm(m_data.get("venue_code"))
                for r_time, r_data in m_data.get("races", {}).items():
                    r_time_norm = norm_time(r_time)
                    daily_merged[(venue, r_time_norm)] = r_data
                    if venue_code:
                        daily_merged[(venue_code, r_time_norm)] = r_data
            except: pass

        if not daily_merged:
            print(f"  [WARN] No merged racecards found for {df}")
            continue
            
        print(f"  [DEBUG] Sample indexed keys: {list(daily_merged.keys())[:3]}")

        for v in verdicts:
            if v.get("tier") != "A": continue
            
            top = v.get("top") or {}
            horse = top.get("horse")
            course = v.get("course")
            off = norm_time(v.get("off_time", ""))
            course_norm = norm(course)
            
            print(f"    Checking {course_norm} @ {off} ({horse})")
            
            m_race = daily_merged.get((course_norm, off))
            if not m_race:
                print(f"      No match found for {(course_norm, off)}")
                continue
            
            rp_pick = m_race.get("postdata_pick") or m_race.get("topspeed_pick") or ""
            print(f"      Match found! RP Pick: {rp_pick}")
            
            category = "RP_NO_DATA"
            if not rp_pick:
                category = "RP_NO_DATA"
            elif norm(horse) == norm(rp_pick):
                category = "AGREE"
            else:
                category = "DISAGREE"
            
            outcome = "UNKNOWN"
            res = results_map.get((course_norm, off))
            if res:
                winner = ""
                for rnr in res.get("runners", []):
                    if str(rnr.get("position")) == "1":
                        winner = rnr.get("horse")
                        break
                if norm(horse) == norm(winner):
                    outcome = "WIN"
                else:
                    outcome = "MISS"
            
            audit_records.append({
                "date": date_iso,
                "course": course,
                "off": off,
                "horse": horse,
                "rp_selection": rp_pick,
                "category": category,
                "outcome": outcome
            })

    if not audit_records:
        print("No Tier A matches found.")
        return

    df = pd.DataFrame(audit_records)
    summary = {}
    for cat in ["AGREE", "DISAGREE", "RP_NO_DATA"]:
        sub = df[df["category"] == cat]
        valid = sub[sub["outcome"] != "UNKNOWN"]
        summary[cat] = {
            "total": len(sub),
            "wins": len(valid[valid["outcome"] == "WIN"]),
            "misses": len(valid[valid["outcome"] == "MISS"]),
            "sr": round(len(valid[valid["outcome"] == "WIN"]) / len(valid), 4) if len(valid) > 0 else 0
        }

    out_json = REPORTS_DIR / "rp_selection_agreement_audit_latest.json"
    out_json.write_text(json.dumps({"summary": summary, "records": audit_records}, indent=2))
    print(f"Audit complete. Results in {out_json}")
    
    print("\n[Audit Summary]")
    for cat, stats in summary.items():
        print(f"{cat:<12}: n={stats['total']:>2}, SR={stats['sr']:.1%}")

if __name__ == "__main__":
    run_audit()
