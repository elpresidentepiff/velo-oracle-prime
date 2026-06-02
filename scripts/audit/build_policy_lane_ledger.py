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

def build_ledger_for_date(target_date: str, force: bool = False):
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
    
    # ── Source Completeness Check ──────────────────────────────────────────
    if results_list and not force:
        avg_runners = sum(len(r.get("runners", [])) for r in results_list) / len(results_list)
        if avg_runners < 3.0:
            print(f"  [STOP] Result source for {target_date} appears incomplete (avg runners: {avg_runners:.1f}). Skipping.")
            return []

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
        
        if not sc.get("lane_b_top3"): continue
        top_pick = sc["lane_b_top3"][0]
        horse_name = top_pick["horse"]
        lane = sc.get("top_pick_lane", "NO_EDGE")
        
        res = results_by_id.get(race_id)
        if not res:
            res = results_by_ct.get((_norm(course), min_time))
        if not res:
            for offset in [-2, -1, 1, 2]:
                res = results_by_ct.get((_norm(course), min_time + offset))
                if res: break
        if not res:
            print(f"    [WARN] No result for {course} @ {min_time} min ({race_id})")
            continue
            
        runners = res.get("full_runners", res.get("runners", []))
        horse_res = None
        for r in runners:
            if _norm(r.get("horse")) == _norm(horse_name):
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
            positions = [str(r.get("position")) for r in runners]
            if "1" in positions and "2" in positions:
                outcome = "MISS"
                confidence = "MEDIUM_ABSENCE"
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

def print_summary(df, label):
    if df.empty:
        print(f"\n--- {label}: No Data ---")
        return
        
    print("\n" + "=" * 60)
    print(f"{label} SUMMARY")
    print("=" * 60)
    
    print("\n[Outcome Confidence Segmentation]")
    print(df.groupby('outcome_confidence').size().to_string())
    
    print("\n[Lane Performance - Valid Outcomes Only]")
    valid = df[
        (df['outcome'] != 'NR') & 
        (df['outcome_confidence'].isin(['HIGH', 'MEDIUM_ABSENCE']))
    ].copy()
    
    if not valid.empty:
        summary = valid.groupby('lane')['outcome'].value_counts().unstack(fill_value=0)
        for col in ["WIN", "PLACE", "MISS"]:
            if col not in summary.columns: summary[col] = 0
        
        summary['Total'] = summary['WIN'] + summary['PLACE'] + summary['MISS']
        summary['SR%'] = (summary['WIN'] / summary.Total.replace(0, 1) * 100).round(1)
        summary['Frame%'] = ((summary['WIN'] + summary['PLACE']) / summary.Total.replace(0, 1) * 100).round(1)
        print(summary[['Total', 'WIN', 'PLACE', 'SR%', 'Frame%']])
        
        if "GLOBAL" in label:
            print(f"\nProgress to n=150: {len(valid)} / 150 ({len(valid)/150:.1%})")
            print(f"Progress to HIGH n=50: {len(df[df['outcome_confidence'] == 'HIGH'])} / 50")
    else:
        print("No valid outcomes to report.")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--backfill", action="store_true", help="Scan all reports")
    parser.add_argument("--report-only", action="store_true", help="Don't add new entries")
    parser.add_argument("--force", action="store_true", help="Ignore source completeness check")
    args = parser.parse_args()
    
    if not args.report_only:
        all_entries = []
        if args.backfill:
            files = sorted(list(REPORT_DIR.glob("two_lane_readiness_20*.json")))
            for f in files:
                dt = f.name.replace("two_lane_readiness_", "").replace(".json", "").replace("_", "-")
                all_entries.extend(build_ledger_for_date(dt, force=args.force))
        elif args.date:
            all_entries.extend(build_ledger_for_date(args.date, force=args.force))
        else:
            all_entries.extend(build_ledger_for_date(datetime.now(UTC).strftime("%Y-%m-%d"), force=args.force))
            
        if all_entries:
            # Deduplicate before appending
            existing_ids = set()
            if LEDGER_PATH.exists():
                for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        existing_ids.add((json.loads(line)["race_id"], json.loads(line)["horse"]))
            
            new_rows = []
            for e in all_entries:
                if (e["race_id"], e["horse"]) not in existing_ids:
                    new_rows.append(e)
            
            if new_rows:
                with LEDGER_PATH.open("a", encoding="utf-8") as f:
                    for e in new_rows:
                        f.write(json.dumps(e) + "\n")
                print(f"\nAdded {len(new_rows)} new entries to {LEDGER_PATH}")
                # Print daily summary for the new rows
                print_summary(pd.DataFrame(new_rows), "DAILY BATCH")
            else:
                print("All processed entries already in ledger.")

    # Always print global summary
    if LEDGER_PATH.exists():
        all_rows = [json.loads(l) for l in LEDGER_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        print_summary(pd.DataFrame(all_rows), "GLOBAL CUMULATIVE")

if __name__ == "__main__":
    main()
