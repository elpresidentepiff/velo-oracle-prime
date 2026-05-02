
import os
import json
import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from typing import List, Dict, Any

# Ensure policy registry is available
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.velo.weight_policy_registry import POLICIES, WeightPolicy

load_dotenv(ROOT / ".env")

def calculate_vp(runner: Dict, policy: WeightPolicy) -> float:
    """Calculate VP prob using a specific policy."""
    if not policy.weights: return 0.0
    
    score_sum = 0.0
    weight_sum = 0.0
    
    # Active weights
    for field, weight in policy.weights.items():
        val = runner.get(field) or 0.0
        score_sum += val * weight
        weight_sum += weight
        
    # Gated weights (e.g. longshot)
    for field, gate_cfg in policy.gated_weights.items():
        sp = runner.get("sp_dec") or 0.0
        # Simple gate parser for this runner object
        gate_condition = gate_cfg["gate"].replace("sp_dec", str(sp))
        if eval(gate_condition):
            val = runner.get(field) or 0.0
            score_sum += val * gate_cfg["weight"]
            weight_sum += gate_cfg["weight"]
            
    return score_sum / weight_sum if weight_sum > 0 else 0.0

def run_comparison(target_date: str):
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    print(f"Shadow Comparing Weight Policies for {target_date}...")
    
    # 1. Fetch verdicts for date
    # We need full_analysis to see all runners
    v_resp = sb.table("velo_verdicts").select("race_id,full_analysis,decision_tier").eq("date", target_date).execute()
    if not v_resp.data:
        # Fallback: check by generated_at
        v_resp = sb.table("velo_verdicts").select("race_id,full_analysis,decision_tier").gte("generated_at", target_date).lt("generated_at", target_date + "T23:59:59").execute()
        
    if not v_resp.data:
        print(f"No verdicts found for {target_date}.")
        return

    # 2. Fetch results from sigma_audits
    s_resp = sb.table("sigma_audits").select("race_id,outcome,actual_winner_id,actual_winner_sp").eq("date", target_date).execute()
    results_map = {r["race_id"]: r for r in s_resp.data}
    
    comparison_data = []
    
    for v in v_resp.data:
        race_id = v["race_id"]
        res = results_map.get(race_id)
        fa = v.get("full_analysis") or []
        if isinstance(fa, dict): fa = list(fa.values())
        if not fa: continue
        
        # Original (Live) Top Pick
        live_top = fa[0]
        
        # Score each policy
        lane_tops = {}
        for pname, policy in POLICIES.items():
            if pname == "PAPER_EXECUTION_POLICY": continue
            
            # Map runners to scored list
            scored_runners = []
            for rd in fa:
                if not isinstance(rd, dict): continue
                scored_runners.append({
                    **rd,
                    "policy_vp": calculate_vp(rd, policy)
                })
            
            scored_runners.sort(key=lambda x: x["policy_vp"], reverse=True)
            top = scored_runners[0]
            lane_tops[pname] = {
                "horse": top.get("horse"),
                "horse_id": top.get("horse_id"),
                "vp": top["policy_vp"]
            }

        # Record for this race
        row = {
            "race_id": race_id,
            "live_top": live_top.get("horse"),
            "live_id": live_top.get("horse_id"),
            "winner_id": res["actual_winner_id"] if res else None,
            "winner_sp": float(res["actual_winner_sp"]) if res and res["actual_winner_sp"] else None,
            "outcome": res["outcome"] if res else "UNKNOWN"
        }
        for pname, top in lane_tops.items():
            row[f"{pname}_top"] = top["horse"]
            row[f"{pname}_id"] = top["horse_id"]
            row[f"{pname}_vp"] = top["vp"]
            
        comparison_data.append(row)

    if not comparison_data:
        print("No matchable data processed.")
        return

    df = pd.DataFrame(comparison_data)
    
    # Summary Statistics
    summary = []
    for pname in POLICIES.keys():
        if pname == "PAPER_EXECUTION_POLICY": continue
        
        # Calculate SR/ROI for each lane
        n = len(df)
        changes = (df[f"{pname}_id"] != df["live_id"]).sum()
        
        wins = 0
        pnl = 0.0
        frames = 0
        
        for _, r in df.iterrows():
            is_win = r[f"{pname}_id"] == r["winner_id"]
            sp = r["winner_sp"] or 0.0
            
            if is_win:
                wins += 1
                pnl += (sp - 1.0)
                frames += 1
            # Note: frame detection requires more detailed result data (top 3/4)
            # which might not be in sigma_audits directly.
            
        sr = (wins / n) * 100 if n else 0
        roi = (pnl / n) * 100 if n else 0
        
        summary.append({
            "Policy": pname,
            "n": n,
            "SR": f"{sr:.1f}%",
            "ROI": f"{roi:.1f}%",
            "P&L": round(pnl, 2),
            "Changes vs Live": changes
        })
    
    summary_df = pd.DataFrame(summary)
    
    # Write artifacts
    output_md = ROOT / "data" / f"weight_policy_shadow_compare_{target_date.replace('-', '_')}.md"
    output_csv = ROOT / "data" / f"weight_policy_shadow_compare_{target_date.replace('-', '_')}.csv"
    
    summary_df.to_markdown(output_md, index=False)
    summary_df.to_csv(output_csv, index=False)
    
    print(f"\nComparison Complete. Artifacts written to data/")
    print(summary_df.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_comparison(args.date)
