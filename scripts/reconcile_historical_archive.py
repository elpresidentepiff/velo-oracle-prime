"""
VÉLØ Archive Bridge: Discovery & Reconciliation
File: scripts/reconcile_historical_archive.py
-----------------------------------------------
Hardened Phase 6: Unique Race Deduplication & Scaled Discovery.
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

# ---- Configuration ----
BRIDGE_VERSION = "RACEFORM_BRIDGE_V1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("archive_bridge")

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)

def normalize_sp(sp_str: str) -> Optional[float]:
    if not sp_str or sp_str == "–": return None
    try:
        if '/' in sp_str:
            num, den = sp_str.split('/')
            return (float(num) / float(den)) + 1.0
        return float(sp_str)
    except: return None

def normalize_distance(dist_str: str) -> Optional[int]:
    if not dist_str: return None
    try:
        total = 0.0
        m = re.search(r'(\d+)m', str(dist_str))
        if m: total += float(m.group(1)) * 8
        f = re.search(r'(\d+)f', str(dist_str))
        if f: total += float(f.group(1))
        if total == 0 and str(dist_str).replace('.','').isdigit():
            total = float(dist_str)
        return int(round(total)) if total > 0 else None
    except: return None

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

def run_bridge_task(args):
    sb = get_sb_client()
    target_clean = args.limit_races
    
    # 1. Skip Existing
    ex_res = sb.table("race_results").select("race_id").execute()
    existing_rids = {str(r["race_id"]) for r in ex_res.data}
    
    # 2. Registry Cache
    LOG.info("Loading horse registry...")
    name_map = defaultdict(set)
    h_offset = 0
    while True:
        h_res = sb.table("racing_horses").select("id, name").range(h_offset, h_offset + 999).execute()
        if not h_res.data: break
        for h in h_res.data:
            name_map[clean_horse_name(h["name"])].add(h["id"])
        h_offset += len(h_res.data)
        if h_offset % 50000 == 0: LOG.info(f"  Loaded {h_offset:,} horses...")

    # 3. Discovery Loop
    LOG.info(f"Discovery Mode: Finding {target_clean} clean races from offset {args.offset}...")
    clean_races_batch = []
    clean_results_batch = []
    clean_runners_batch = []
    rejections = Counter()
    
    offset = args.offset
    chunk_size = 1000
    rows_scanned = 0
    
    while len(clean_races_batch) < target_clean:
        res = sb.table("raceform").select("*").range(offset, offset + chunk_size - 1).execute()
        if not res.data: break
        
        # Group by race
        current_batch_map = defaultdict(list)
        for row in res.data:
            current_batch_map[str(row["race_id"])].append(row)
        
        for rid, r_list in current_batch_map.items():
            if rid in existing_rids:
                rejections["duplicate_existing"] += 1; continue
                
            sample = r_list[0]
            valid_race, race_runners = True, []
            winner_count = 0
            
            for rr in r_list:
                norm_name = clean_horse_name(rr["horse"])
                matches = name_map.get(norm_name, set())
                
                if len(matches) == 1:
                    hid = list(matches)[0]
                    pos_int, is_winner = normalize_pos(rr["pos"])
                    sp_val = normalize_sp(rr["sp"])
                    if pos_int is None or sp_val is None:
                        valid_race = False; rejections["malformed_data"] += 1; break
                    if is_winner: winner_count += 1
                    race_runners.append({
                        "race_id": rid, "horse_id": hid, "position": pos_int,
                        "is_winner": is_winner, "sp_dec": sp_val
                    })
                elif len(matches) > 1:
                    valid_race = False; rejections["ambiguous_horse"] += 1; break
                else:
                    valid_race = False; rejections["unmatched_horse"] += 1; break
            
            if valid_race:
                if winner_count != 1:
                    rejections["winner_parity_fail"] += 1
                elif len(r_list) < 2:
                    rejections["one_horse_race"] += 1
                else:
                    # ACCEPTED
                    clean_races_batch.append({
                        "race_id": rid, "course": sample.get("course"),
                        "date": sample.get("date"), "time": sample.get("off") or "00:00",
                        "going": sample.get("going"), "class": sample.get("class_raw"),
                        "distance_f": normalize_distance(sample.get("dist")), "race_name": sample.get("race_name")
                    })
                    clean_results_batch.append({"race_id": rid, "reconciled_at": datetime.now().isoformat()})
                    clean_runners_batch.extend(race_runners)
            
            if len(clean_races_batch) >= target_clean: break
            
        rows_scanned += len(res.data)
        offset += chunk_size
        if rows_scanned % 10000 == 0:
            LOG.info(f"  Scanned: {rows_scanned:,} | Clean Found: {len(clean_races_batch)}")
        
        if rows_scanned > args.max_scan: break

    # 4. Write Execution
    if args.dry_run:
        print(f"\nDRY-RUN: Eligible={len(clean_races_batch)}")
    else:
        # Final Dedupe protection (Dictionary comprehension keys by ID)
        final_races = list({r["race_id"]: r for r in clean_races_batch}.values())
        final_results = list({r["race_id"]: r for r in clean_results_batch}.values())
        
        LOG.info(f"STARTING REAL BRIDGE: {len(final_races)} races...")
        if final_races: sb.table("races").upsert(final_races).execute()
        if final_results: sb.table("race_results").upsert(final_results).execute()

        if clean_runners_batch: 
            # Final Runner Dedupe (Composite key: race_id + horse_id)
            unique_runners = {}
            for r in clean_runners_batch:
                key = (r["race_id"], r["horse_id"])
                unique_runners[key] = r
            
            final_runners = list(unique_runners.values())
            LOG.info(f"Writing {len(final_runners)} unique runners...")
            
            for j in range(0, len(final_runners), 500):
                sb.table("runner_results").upsert(final_runners[j:j+500], on_conflict="race_id,horse_id").execute()
        LOG.info("Bridge complete.")