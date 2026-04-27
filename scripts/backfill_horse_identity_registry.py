"""
VÉLØ Identity Registry Backfill: Populate racing_horses from public.raceform
File: scripts/backfill_horse_identity_registry.py
-------------------------------------------------------------------------
Phase 2 Hardened: Keyset Pagination (ID Cursor) for Large-Scale Ingestion.
"""

import os
import sys
import re
import json
import hashlib
import argparse
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from supabase import create_client, Client

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.model_manager import get_model_manager

# ---- Configuration ----
IDENTITY_VERSION = "RACEFORM_ID_V1"
CURSOR_FILE = ROOT / "data" / "identity_scan_cursor.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("identity_backfill")

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)

def normalize_name(name: str) -> str:
    if not name: return ""
    name = str(name).strip().upper()
    name = re.sub(r"\s+", " ", name)
    return name

def generate_deterministic_id(norm_name: str) -> str:
    hash_digest = hashlib.sha256(norm_name.encode()).hexdigest()[:12]
    return f"hrs_rf_{hash_digest}"

def load_cursor() -> int:
    if CURSOR_FILE.exists():
        with open(CURSOR_FILE, "r") as f:
            return json.load(f).get("last_id", 0)
    return 0

def save_cursor(last_id: int):
    os.makedirs(CURSOR_FILE.parent, exist_ok=True)
    with open(CURSOR_FILE, "w") as f:
        json.dump({"last_id": last_id, "updated_at": datetime.now().isoformat()}, f)

def run_identity_task(args):
    sb = get_sb_client()
    
    # 1. Fetch Existing Production Registry for Deduplication
    LOG.info("Loading existing production horse registry...")
    # Process in chunks if registry is large
    prod_horses_count = 0
    exact_map = set()
    norm_map = defaultdict(set)
    
    offset = 0
    while True:
        res = sb.table("racing_horses").select("id, name").range(offset, offset + 999).execute()
        if not res.data: break
        for h in res.data:
            exact_map.add(h["name"].strip().upper())
            norm_map[normalize_name(h["name"])].add(h["id"])
            prod_horses_count += 1
        offset += len(res.data)
        if offset % 10000 == 0: LOG.info(f"  Loaded {offset:,} production horses...")

    # 2. Keyset Pagination Scan
    start_id = args.resume_from if args.resume_from is not None else load_cursor()
    LOG.info(f"Starting scan from raceform.id > {start_id}...")
    
    unique_horses = {} 
    total_rows_scanned = 0
    last_processed_id = start_id
    chunk_size = 1000
    
    try:
        while True:
            res = sb.table("raceform") \
                .select("id, horse, date") \
                .gt("id", last_processed_id) \
                .order("id", desc=False) \
                .limit(chunk_size) \
                .execute()
            
            if not res.data: break
            
            for r in res.data:
                total_rows_scanned += 1
                last_processed_id = r["id"]
                source_name = r["horse"]
                if not source_name: continue
                norm = normalize_name(source_name)
                date_val = r["date"]
                
                if norm not in unique_horses:
                    unique_horses[norm] = {"source_name": source_name, "first_seen": date_val, "last_seen": date_val, "count": 1}
                else:
                    h = unique_horses[norm]
                    h["count"] += 1
                    if date_val and (not h["first_seen"] or date_val < h["first_seen"]): h["first_seen"] = date_val
                    if date_val and (not h["last_seen"] or date_val > h["last_seen"]): h["last_seen"] = date_val
            
            if total_rows_scanned % 10000 == 0:
                LOG.info(f"  Scanned {total_rows_scanned:,} rows... Current ID: {last_processed_id}")
            if args.limit_rows and total_rows_scanned >= args.limit_rows: break
    except Exception as e:
        LOG.error(f"Scan interrupted: {e}")
    finally:
        if not args.dry_run:
            save_cursor(last_processed_id)

    # 3. Filter and Prepare
    proposed_inserts = []
    stats = Counter()
    
    for norm_name, h_info in unique_horses.items():
        source_name = h_info["source_name"]
        if source_name.strip().upper() in exact_map:
            stats["matched_exact"] += 1; continue
        if len(norm_map.get(norm_name, set())) >= 1:
            stats["matched_normalized"] += 1; continue
            
        new_id = generate_deterministic_id(norm_name)
        proposed_inserts.append({
            "id": new_id, "name": source_name, "runs": h_info["count"],
            "last_seen": h_info["last_seen"], "updated_at": datetime.now().isoformat()
        })
        stats["new_identities"] += 1

    # 4. Execution
    if args.dry_run:
        print("\n" + "="*60)
        print("VÉLØ IDENTITY REGISTRY DRY-RUN (KEYSET)")
        print("="*60)
        print(f"Pagination Method: Keyset (GT ID)")
        print(f"Start ID:          {start_id}")
        print(f"End ID:            {last_processed_id}")
        print(f"Rows Scanned:      {total_rows_scanned:,}")
        print(f"Unique Found:      {len(unique_horses):,}")
        print(f"Proposed Inserts:  {len(proposed_inserts):,}")
        print("="*60)
    else:
        LOG.info(f"PERFORMING REAL INSERT: {len(proposed_inserts):,} horses...")
        for i in range(0, len(proposed_inserts), 500):
            batch = proposed_inserts[i:i+500]
            # UPSERT to prevent primary key violations on partial resumes
            sb.table("racing_horses").upsert(batch).execute()
            if (i // 500) % 10 == 0: LOG.info(f"  Processed {i + len(batch):,} rows...")
        LOG.info(f"Final Count in Registry: {prod_horses_count + len(proposed_inserts):,}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-rows", type=int, default=None)
    parser.add_argument("--resume-from", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_identity_task(args)
