"""
VÉLØ HFS Signal Integrity Audit - Block 001
File: scripts/audit_hfs_signal_integrity_block001.py
---------------------------------------------------
Forensic audit of Block 001 signals and proxy implementation.
"""

import os
import sys
import json
import logging
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from supabase import create_client, Client

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("signal_audit")

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)

def calculate_entropy(probs: List[float]) -> float:
    """Standard Shannon Entropy for market distribution."""
    return -sum(p * math.log2(p) for p in probs if p > 0)

def archive_proxy_mpi(rank: int, field_size: int) -> float:
    """MPI Proxy: 100 at fav, decreasing to 0 at longshot."""
    if field_size <= 1: return 50.0
    return round(100.0 * (1.0 - (rank - 1) / (field_size - 1)), 4)

def archive_proxy_chaos(probs: List[float], going: str, field_size: int) -> float:
    """Chaos Bloom Proxy: Higher entropy + soft ground + large field = more chaos."""
    entropy = calculate_entropy(probs)
    # Normalize entropy to 0-100 (approx max entropy for 20 runners is ~4.3)
    ent_score = (entropy / 4.5) * 100
    
    g = str(going or "").upper()
    going_factor = 20 if any(x in g for x in ["SOFT", "HEAVY", "YIELDING"]) else 0
    size_factor = min(20, (field_size / 20) * 20)
    
    bloom = (ent_score * 0.6) + going_factor + size_factor
    return round(min(100.0, bloom), 4)

def run_audit():
    sb = get_sb_client()
    
    # Identify archive races (numeric IDs)
    res_ids = sb.table("historical_feature_store").select("race_id").limit(5000).execute()
    race_ids = sorted(list({r["race_id"] for r in res_ids.data if r["race_id"].isdigit()}))
    
    if not race_ids:
        LOG.error("No numeric archive races found in HFS.")
        return

    LOG.info(f"Auditing {len(race_ids)} archive races...")

    # 1. Fetch HFS and Raw Data
    hfs_res = sb.table("historical_feature_store").select("*").in_("race_id", race_ids).execute()
    hfs_rows = hfs_res.data
    
    print("\n" + "="*60)
    print("HFS SIGNAL INTEGRITY AUDIT: ARCHIVE")
    print("="*60)
    print(f"A. Archive Races Found:  {len(race_ids)}")
    print(f"B. HFS Rows Found:       {len(hfs_rows)}")
    
    mpi_vals = [r["mpi"] for r in hfs_rows if r["mpi"] is not None]
    chaos_vals = [r["chaos_bloom"] for r in hfs_rows if r["chaos_bloom"] is not None]
    
    print(f"C. MPI Null Count:       {len(hfs_rows) - len(mpi_vals)}")
    print(f"D. Chaos Null Count:     {len(hfs_rows) - len(chaos_vals)}")
    
    if mpi_vals:
        print(f"E. MPI Variance:         {np.var(mpi_vals):.4f}")
        print(f"F. MPI Min/Max:          {min(mpi_vals)} / {max(mpi_vals)}")
    
    if chaos_vals:
        print(f"G. Chaos Variance:       {np.var(chaos_vals):.4f}")
        print(f"H. Chaos Min/Max:        {min(chaos_vals)} / {max(chaos_vals)}")

    # Check for constant values (flatness)
    if len(set(mpi_vals)) == 1:
        print("ALERT: MPI IS FLAT (Constant Value)")
    if len(set(chaos_vals)) == 1:
        print("ALERT: CHAOS_BLOOM IS FLAT (Constant Value)")

    print("\nSAMPLE ROWS:")
    for r in hfs_rows[:10]:
        print(f"RID: {r['race_id']} | HID: {r['horse_id']} | MPI: {r['mpi']} | BLOOM: {r['chaos_bloom']}")
    print("="*60)

if __name__ == "__main__":
    run_audit()
