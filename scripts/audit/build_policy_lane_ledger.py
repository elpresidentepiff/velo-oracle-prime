"""
Build the New Build Decision Policy Lane Ledger.
Reconciles tactical lane picks against actual results to track forward evidence.
"""
import argparse
import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "data" / "new_build" / "reports"
RESULTS_DIR = ROOT / "data"
LEDGER_PATH = ROOT / "data" / "new_build" / "policy_lane_ledger.jsonl"

def _norm(s):
    import re
    v = str(s or "").strip().lower()
    v = v.replace("(aw)", "")
    # Strip country codes in parentheses like (GB), (IRE), (FR)
    v = re.sub(r"\([a-z]{2,3}\)", "", v)
    return v.replace(" ", "").strip()

def _nb_to_min(t):
    if not t: return -1
    if "T" in str(t):
        # Extract HH:MM from ISO
        import re
        m = re.search(r"T(\d{2}):(\d{2})", str(t))
        if m: return int(m.group(1)) * 60 + int(m.group(2))
    return -1

def _sl_to_min(t):
    if not t: return -1
    parts = str(t).split(".")
    h = int(parts[0]) if parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if 1 <= h <= 9: h += 12
    return h * 60 + m

def build_ledger_for_date(target_date: str):
    date_und = target_date.replace("-", "_")
    report_path = REPORT_DIR / f"two_lane_readiness_{date_und}.json"
    results_path = RESULTS_DIR / f"results_{date_und}.json"
    
    if not report_path.exists():
        print(f"  [SKIP] Readiness report not found: {report_path}")
        return []
    if not results_path.exists():
        print(f"  [SKIP] Results not found: {results_path}")
        return []
        
    print(f"Processing {target_date}...")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw_results = json.loads(results_path.read_text(encoding="utf-8"))
    results_list = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
    
    # 1. Index results by race_id and (course, min_time)
    results_by_id = {str(r.get("race_id")): r for r in results_list}
    results_by_ct = {(_norm(r.get("course")), _sl_to_min(r.get("off"))): r for r in results_list}
    
    DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}
    
    entries = []
    
    for sc in report.get("race_day_scorecards", []):
        race_id = str(sc.get("race_id"))
        course = sc.get("course")
        off_time_iso = sc.get("off_time")
        min_time = _nb_to_min(off_time_iso)
        
        # Determine Top Pick (Lane B is our anchor for policy)
        if not sc.get("lane_b_top3"): continue
        top_pick = sc["lane_b_top3"][0]
        horse_name = top_pick["horse"]
        lane = sc.get("top_pick_lane", "NO_EDGE")
        
        # 2. Reconcile race
        res = results_by_id.get(race_id)
        if not res:
            res = results_by_ct.get((_norm(course), min_time))
            
        if not res:
            # Try +/- 1-2 mins for slight variations
            for offset in [-2, -1, 1, 2]:
                res = results_by_ct.get((_norm(course), min_time + offset))
                if res: break
                
        if not res:
            print(f"    [WARN] No result for {course} @ {min_time} min ({race_id})")
            continue
            
        # 3. Reconcile horse
        runners = res.get("full_runners", res.get("runners", []))
        horse_res = None
        for r in runners:
            # Match by name normalized
            res_name_norm = _norm(r.get("horse"))
            pred_name_norm = _norm(horse_name)
            if res_name_norm == pred_name_norm:
                horse_res = r
                break
                
        outcome = "UNKNOWN"
        confidence = "LOW"
        sp = None
        
        if horse_res:
            pos_raw = str(horse_res.get("position", "")).strip().upper()
            if pos_raw in DNF_POSITIONS:
                outcome = "NR"
            elif pos_raw == "1":
                outcome = "WIN"
            elif pos_raw in ("2", "3"):
                outcome = "PLACE"
            else:
                outcome = "MISS"
            sp = horse_res.get("sp_dec", horse_res.get("sp"))
            confidence = "HIGH"
        else:
            # If race found but horse not in (likely lightweight) finishers
            positions = [str(r.get("position")) for r in runners]
            if "1" in positions and "2" in positions:
                outcome = "MISS"
                confidence = "MEDIUM_ABSENCE"
                print(f"    [INFO] Horse {horse_name} absent from finishers for {course} -> assumed MISS")
            else:
                print(f"    [WARN] Horse {horse_name} not found and results incomplete for {course}")
                continue
            
        entry = {
            "date": target_date,
            "race_id": race_id,
            "course": course,
            "off": off_time_iso,
            "horse": horse_name,
            "lane": lane,
            "outcome": outcome,
            "outcome_confidence": confidence,
            "vp": top_pick.get("prob"),
            "sp": sp,
            "generated_at": datetime.now(UTC).isoformat()
        }
        entries.append(entry)
        
    return entries

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--backfill", action="store_true", help="Scan all reports")
    args = parser.parse_args()
    
    all_entries = []
    
    if args.backfill:
        files = sorted(list(REPORT_DIR.glob("two_lane_readiness_20*.json")))
        for f in files:
            dt = f.name.replace("two_lane_readiness_", "").replace(".json", "").replace("_", "-")
            all_entries.extend(build_ledger_for_date(dt))
    elif args.date:
        all_entries.extend(build_ledger_for_date(args.date))
    else:
        all_entries.extend(build_ledger_for_date("2026-06-02"))
        
    if not all_entries:
        print("No new ledger entries found.")
        return
        
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        for e in all_entries:
            f.write(json.dumps(e) + "\n")
            
    print(f"\nAdded {len(all_entries)} entries to {LEDGER_PATH}")
    
    df = pd.DataFrame(all_entries)
    if not df.empty:
        print("\n--- Batch Summary ---")
        summary = df.groupby('lane')['outcome'].value_counts().unstack(fill_value=0)
        for col in ["WIN", "PLACE", "MISS", "NR"]:
            if col not in summary.columns: summary[col] = 0
            
        summary['Total'] = summary['WIN'] + summary['PLACE'] + summary['MISS']
        summary['SR%'] = (summary['WIN'] / summary.Total.replace(0, 1) * 100).round(1)
        summary['Frame%'] = ((summary['WIN'] + summary['PLACE']) / summary.Total.replace(0, 1) * 100).round(1)
        print(summary[['Total', 'WIN', 'PLACE', 'SR%', 'Frame%']])

if __name__ == "__main__":
    main()
