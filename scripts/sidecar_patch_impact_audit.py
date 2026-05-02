
import os
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# --- Ensemble Mirror Logic ---
WEIGHTS = {
    "sqpe_v17": 0.45,
    "market_deception_score": 0.10,
    "place_prob": 0.08,
    "longshot_score": 0.07,
    "improvement_score": 0.12,
    "release_window_score": 0.10,
    "comment_intel_score": 0.08,
}

@dataclass
class MockRunner:
    horse: str
    horse_id: str
    sqpe: float
    mds: float
    place: float
    ls: float
    imp: float
    rel: float
    comm: float
    sp_dec: float = 0.0
    is_fav: bool = False
    # Outputs
    vp_live: float = 0.0
    vp_design_a: float = 0.0
    vp_design_b: float = 0.0
    # Pre-norm outputs
    raw_live: float = 0.0
    raw_a: float = 0.0
    raw_b: float = 0.0

def predict_race_mock(runners: List[MockRunner]) -> None:
    full_denominator = sum(WEIGHTS.values())

    for r in runners:
        scores = {
            "sqpe_v17": r.sqpe, "market_deception_score": r.mds,
            "place_prob": r.place, "improvement_score": r.imp
        }
        if r.sp_dec >= 10.0: scores["longshot_score"] = r.ls

        # LIVE: include all
        live_scores = {**scores, "release_window_score": r.rel, "comment_intel_score": r.comm}
        live_den = sum(WEIGHTS[k] for k in live_scores)
        r.raw_live = sum(WEIGHTS[k] * live_scores[k] for k in live_scores) / live_den
        
        # A: Renormalized (smaller denominator)
        a_den = sum(WEIGHTS[k] for k in scores)
        r.raw_a = sum(WEIGHTS[k] * scores[k] for k in scores) / a_den
        
        # B: Fixed (full denominator)
        r.raw_b = sum(WEIGHTS[k] * scores[k] for k in scores) / full_denominator

    # Apply Normalization
    total_live = sum(r.raw_live for r in runners)
    total_a = sum(r.raw_a for r in runners)
    total_b = sum(r.raw_b for r in runners)
    
    for r in runners:
        if total_live > 0: r.vp_live = r.raw_live / total_live
        if total_a > 0: r.vp_design_a = r.raw_a / total_a
        if total_b > 0: r.vp_design_b = r.raw_b / total_b

def run_impact_audit(target_date: str):
    ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT / ".env")
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    print(f"Running Patch Impact Audit for {target_date}...")
    v_resp = sb.table("velo_verdicts").select("*").gte("generated_at", f"{target_date}T00:00:00").lt("generated_at", f"{target_date}T23:59:59").execute()
    if not v_resp.data: return
    s_resp = sb.table("sigma_audits").select("race_id,outcome,actual_winner_id,actual_winner_sp").eq("date", target_date).execute()
    results = {r["race_id"]: r for r in s_resp.data}

    comparison = []
    for v in v_resp.data:
        rid = v["race_id"]
        fa = v.get("full_analysis") or []
        if isinstance(fa, dict): fa = list(fa.values())
        if not fa: continue
        res = results.get(rid)
        
        runners = []
        for rd in fa:
            if not isinstance(rd, dict): continue
            runners.append(MockRunner(
                horse=rd.get("horse"), horse_id=rd.get("horse_id"),
                sqpe=float(rd.get("sqpe_v17_prob") or 0),
                mds=float(rd.get("market_deception_score") or 0),
                place=float(rd.get("place_prob") or 0),
                ls=float(rd.get("longshot_prob") or 0),
                imp=float(rd.get("improvement_score") or 0),
                rel=float(rd.get("release_day_prob") or 0),
                comm=float(rd.get("comment_intel_score") or 0),
                sp_dec=float(rd.get("sp_dec") or 0)
            ))
        if not runners: continue
        predict_race_mock(runners)
        
        top_live = sorted(runners, key=lambda x: x.vp_live, reverse=True)[0]
        top_a = sorted(runners, key=lambda x: x.vp_design_a, reverse=True)[0]
        top_b = sorted(runners, key=lambda x: x.vp_design_b, reverse=True)[0]
        
        comparison.append({
            "race_id": rid, "winner_id": res["actual_winner_id"] if res else None,
            "winner_sp": float(res["actual_winner_sp"]) if res and res["actual_winner_sp"] else 0,
            "live_id": top_live.horse_id, "live_vp": top_live.vp_live, "live_raw": top_live.raw_live,
            "a_id": top_a.horse_id, "a_vp": top_a.vp_design_a, "a_raw": top_a.raw_a,
            "b_id": top_b.horse_id, "b_vp": top_b.vp_design_b, "b_raw": top_b.raw_b
        })

    df = pd.DataFrame(comparison)
    report = []
    for mode in ["LIVE", "A", "B"]:
        pfx = mode.lower() if mode != "LIVE" else "live"
        n = len(df)
        wins = df[df[f"{pfx}_id"] == df["winner_id"]]
        sr = len(wins) / n * 100
        pnl = (wins["winner_sp"] - 1).sum() - (n - len(wins))
        roi = pnl / n * 100
        vp30 = df[df[f"{pfx}_vp"] >= 0.3]
        vp30_sr = len(vp30[vp30[f"{pfx}_id"] == vp30["winner_id"]]) / len(vp30) * 100 if len(vp30) else 0
        report.append({
            "Design": mode, "SR": f"{sr:.1f}%", "ROI": f"{roi:.1f}%",
            "VP30_n": len(vp30), "VP30_SR": f"{vp30_sr:.1f}%",
            "Changes": (df[f"{pfx}_id"] != df["live_id"]).sum() if mode != "LIVE" else 0,
            "Avg_VP": df[f"{pfx}_vp"].mean(),
            "Avg_Raw": df[f"{pfx}_raw"].mean()
        })
    print("\n=== SIDECAR PATCH IMPACT AUDIT REPORT ===")
    print(pd.DataFrame(report).to_string(index=False))
    print("\nInterpretation:")
    print(" - DESIGN A (Renormalized) removes weights from denominator.")
    print(" - DESIGN B (Fixed) keeps denominator, setting harmful weights to 0.")
    print(" - Normalized results (SR/ROI/VP30) will be identical if relative rankings are constant.")
    print(" - Raw Prob (Avg_Raw) shows the true scale impact.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    run_impact_audit(args.date)
