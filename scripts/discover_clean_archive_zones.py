"""
VÉLØ Clean Race Index: Identify High-Fidelity Archive Zones
File: scripts/discover_clean_archive_zones.py
-----------------------------------------------------------
Scans the archive to identify course/date clusters with high data quality.
"""

import os
import sys
import re
import json
import argparse
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from supabase import create_client, Client

# ---- Project imports ----
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("discovery_index")

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)

def normalize_sp(sp_str: str) -> bool:
    if not sp_str or sp_str == "–": return False
    try:
        if '/' in sp_str:
            num, den = sp_str.split('/')
            _ = (float(num) / float(den)) + 1.0
        else:
            _ = float(sp_str)
        return True
    except: return False

def normalize_pos(pos_str: str) -> Tuple[Optional[int], bool]:
    if not pos_str: return None, False
    try:
        clean_pos = re.sub(r"[^\d]", "", str(pos_str))
        if not clean_pos: return None, False
        pos_int = int(clean_pos)
        return pos_int, pos_int == 1
    except: return None, False

def clean_horse_name(name: str) -> str:
    if not name: return ""
    name = re.sub(r"\([A-Z]+\)$", "", str(name)).strip()
    return name.upper()

def run_discovery(args):
    sb = get_sb_client()
    
    # 1. Load Registry for matching
    LOG.info("Loading horse registry for discovery...")
    name_map = {} # normalized_name -> count of IDs
    h_offset = 0
    while True:
        h_res = sb.table("racing_horses").select("id, name").range(h_offset, h_offset + 999).execute()
        if not h_res.data: break
        for h in h_res.data:
            norm = clean_horse_name(h["name"])
            name_map[norm] = name_map.get(norm, 0) + 1
        h_offset += len(h_res.data)
        if h_offset % 20000 == 0: LOG.info(f"  Loaded {h_offset:,} horses...")

    # 2. Keyed Pagination Scan
    LOG.info(f"Scanning archive from offset {args.offset} (Limit: {args.max_scan})...")
    
    # zones: (course, year_month) -> {stats}
    zones = defaultdict(lambda: {
        "rows": 0, "candidates": set(), "clean_races": set(), 
        "rejections": Counter(), "dates": set()
    })
    
    offset = args.offset
    chunk_size = 1000
    rows_scanned = 0
    
    while rows_scanned < args.max_scan:
        res = sb.table("raceform").select("*").range(offset, offset + chunk_size - 1).execute()
        if not res.data: break
        
        # Group by race for validation
        race_map = defaultdict(list)
        for row in res.data:
            race_map[str(row["race_id"])].append(row)
            
        for rid, r_list in race_map.items():
            sample = r_list[0]
            course = sample.get("course", "UNKNOWN")
            date_val = sample.get("date", "2000-01-01")
            year_month = date_val[:7] # YYYY-MM
            
            zone_key = (course, year_month)
            z = zones[zone_key]
            z["rows"] += len(r_list)
            z["candidates"].add(rid)
            z["dates"].add(date_val)
            
            # Fidelity Filter
            valid_race = True
            winner_count = 0
            for rr in r_list:
                norm_name = clean_horse_name(rr["horse"])
                match_count = name_map.get(norm_name, 0)
                
                if match_count == 1:
                    pos_int, is_winner = normalize_pos(rr["pos"])
                    if pos_int is None or not normalize_sp(rr["sp"]):
                        valid_race = False; z["rejections"]["malformed_data"] += 1; break
                    if is_winner: winner_count += 1
                elif match_count > 1:
                    valid_race = False; z["rejections"]["ambiguous_horse"] += 1; break
                else:
                    valid_race = False; z["rejections"]["unmatched_horse"] += 1; break
            
            if valid_race:
                if winner_count != 1:
                    z["rejections"]["winner_parity_fail"] += 1
                elif len(r_list) < 2:
                    z["rejections"]["one_horse_race"] += 1
                else:
                    z["clean_races"].add(rid)
                    
        rows_scanned += len(res.data)
        offset += len(res.data)
        if rows_scanned % 10000 == 0:
            LOG.info(f"  Scanned {rows_scanned:,} rows...")

    # 3. Compile Report
    zone_report = []
    for (course, ym), data in zones.items():
        cand_count = len(data["candidates"])
        clean_count = len(data["clean_races"])
        rate = (clean_count / cand_count * 100) if cand_count > 0 else 0
        
        zone_report.append({
            "course": course,
            "year_month": ym,
            "rows": data["rows"],
            "candidates": cand_count,
            "clean": clean_count,
            "clean_rate": rate,
            "rejections": dict(data["rejections"]),
            "date_range": f"{min(data['dates'])} to {max(data['dates'])}"
        })

    # Sort by clean rate then volume
    zone_report.sort(key=lambda x: (x["clean_rate"], x["clean"]), reverse=True)

    print("\n" + "="*80)
    print(f"{'VÉLØ CLEAN RACE INDEX: TOP DENSE ZONES':^80}")
    print("="*80)
    print(f"{'ZONE (COURSE | YM)':<35} | {'CANDS':>6} | {'CLEAN':>6} | {'RATE %':>8}")
    print("-"*80)
    
    for z in zone_report[:20]:
        print(f"{z['course'][:25] + ' | ' + z['year_month']:<35} | {z['candidates']:>6} | {z['clean']:>6} | {z['clean_rate']:>7.2f}%")

    print("\n" + "="*80)
    # Global aggregates for audit
    global_rejections = Counter()
    for z in zone_report: global_rejections.update(z["rejections"])
    
    print(f"A. Total Rows Scanned:     {rows_scanned:,}")
    print(f"B. Total Clean Races:      {sum(z['clean'] for z in zone_report)}")
    print(f"C. Global Rejection Breakdown:")
    for k, v in global_rejections.items():
        print(f"   - {k:<20}: {v}")
    print("="*80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-scan", type=int, default=100000)
    parser.add_argument("--offset", type=int, default=101000) # Resume after last bridge
    args = parser.parse_args()
    run_discovery(args)
