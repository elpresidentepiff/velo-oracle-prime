"""
HFS Signal Path Audit
File: scripts/audit_hfs_signal_path.py
------------------------------------
Forensic signal trace for Block 001 HFS rows.
Checks why mpi and chaos_bloom are flat/null.
"""

import os
import sys
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from supabase import create_client, Client

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime
from app.services.model_manager import get_model_manager

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("signal_audit")

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)

def run_audit():
    sb = get_sb_client()
    manifest_path = ROOT / "data" / "bridge_manifest_oasis_block_001.json"
    
    if not manifest_path.exists():
        LOG.error(f"Manifest not found: {manifest_path}")
        return

    with open(manifest_path, "r") as f:
        race_ids = json.load(f)

    LOG.info(f"Auditing {len(race_ids)} races from manifest...")

    # Fetch HFS rows for these races
    hfs_res = sb.table("historical_feature_store").select("*").in_("race_id", race_ids).execute()
    hfs_rows = hfs_res.data
    LOG.info(f"Found {len(hfs_rows)} HFS rows.")

    # Fetch raw results for comparison
    rr_res = sb.table("runner_results").select("*").in_("race_id", race_ids).execute()
    rr_rows = rr_res.data
    rr_map = {(str(r["race_id"]), str(r["horse_id"])): r for r in rr_rows}

    # Samples for tracing
    sample_races = race_ids[:5]
    
    trace_results = []

    for rid in sample_races:
        # Fetch race meta
        race_meta = sb.table("races").select("*").eq("race_id", rid).single().execute().data
        # Fetch runners
        runners = [r for r in rr_rows if str(r["race_id"]) == str(rid)]
        
        # Build normalized race object for reconstructor
        norm_runners = []
        for r in runners:
            norm_runners.append({
                "horse_id": r["horse_id"],
                "horse_name": next((h["horse_name"] for h in hfs_rows if h["horse_id"] == r["horse_id"]), "Unknown"),
                "sp": r["sp_dec"],
                "odds": r["sp_dec"],
                "is_winner": r["is_winner"],
                "position": r["position"],
                "pdf_intel": {}
            })
            
        nrace = {
            "race_id": rid,
            "course": race_meta.get("course"),
            "going": race_meta.get("going"),
            "race_class": race_meta.get("class"),
            "distance_f": race_meta.get("distance_f"),
            "runners": norm_runners
        }

        # TRACE: Call score_race_velo_prime
        preds = score_race_velo_prime(nrace, sentient_state=None)
        
        for p in preds:
            hid = p.get("horse_id")
            hfs_row = next((h for h in hfs_rows if str(h["race_id"]) == str(rid) and h["horse_id"] == hid), {})
            
            trace_results.append({
                "race_id": rid,
                "horse_id": hid,
                "sp_dec": p.get("sp_dec"),
                "implied_prob": 1.0 / p["sp_dec"] if p.get("sp_dec") else None,
                "mpi": hfs_row.get("mpi"),
                "chaos_bloom": hfs_row.get("chaos_bloom"),
                "pred_keys": list(p.keys()),
                "hfs_payload_keys": list(hfs_row.keys()) if hfs_row else []
            })

    # Global Stats
    mpi_values = [h["mpi"] for h in hfs_rows if h["mpi"] is not None]
    chaos_values = [h["chaos_bloom"] for h in hfs_rows if h["chaos_bloom"] is not None]
    
    print("\n" + "="*60)
    print("HFS SIGNAL PATH AUDIT: BLOCK 001")
    print("="*60)
    print(f"HFS Rows:          {len(hfs_rows)}")
    print(f"MPI Nulls:         {len(hfs_rows) - len(mpi_values)}")
    print(f"Chaos Nulls:       {len(hfs_rows) - len(chaos_values)}")
    
    if mpi_values:
        print(f"MPI Range:         {min(mpi_values)} -> {max(mpi_values)}")
        print(f"MPI Variance:      {np.var(mpi_values):.6f}")
    else:
        print("MPI Range:         None -> None")
        
    if chaos_values:
        print(f"Chaos Range:       {min(chaos_values)} -> {max(chaos_values)}")
        print(f"Chaos Variance:    {np.var(chaos_values):.6f}")
    else:
        print("Chaos Range:       None -> None")

    print("\nTRACING SAMPLE RUNNER PAYLOADS:")
    for t in trace_results[:10]:
        print(f"RID: {t['race_id']} | HID: {t['horse_id']} | SP: {t['sp_dec']} | MPI: {t['mpi']} | BLOOM: {t['chaos_bloom']}")
        print(f"  Prediction Keys: {t['pred_keys']}")
    print("="*60)

if __name__ == "__main__":
    run_audit()
