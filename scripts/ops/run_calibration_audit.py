#!/usr/bin/env python3
"""
Logistic / Benter Calibration Baseline
Computes calibration metrics (Brier score, Decile curve, OR baseline) for Old VELO's velo_prime_prob.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
SIGMA_RESULTS_DIR = DATA_DIR / "sigma_results"
CALIB_DIR = DATA_DIR / "calibration"
CALIB_DIR.mkdir(parents=True, exist_ok=True)

def _norm(s):
    if not s: return ""
    import re
    v = str(s).strip().lower().replace("(aw)", "").replace("aw", "")
    v = re.sub(r"\([a-z]{2,3}\)", "", v)
    return re.sub(r"[^a-z]", "", v).strip()

def run_calibration_audit(days_back: int = 30):
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y_%m_%d")
    
    sigma_files = sorted([f for f in SIGMA_RESULTS_DIR.glob("sigma_results_*.json") if f.name >= f"sigma_results_{cutoff_date}.json"])
    
    if not sigma_files:
        print("No sigma results found in the specified timeframe.")
        return

    records = []
    race_stats = []

    for sf in sigma_files:
        date_str = sf.name.replace("sigma_results_", "").replace(".json", "")
        verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_str}.json"
        results_path = DATA_DIR / f"results_{date_str}.json"
        
        if not verdicts_path.exists() or not results_path.exists():
            continue

        try:
            verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
            raw_results = json.loads(results_path.read_text(encoding="utf-8"))
            results_list = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
        except:
            continue

        # Index verdicts
        v_map = {}
        for v in verdicts:
            v_off = str(v.get("off_time", "")).replace(":", ".")
            v_map[(_norm(v.get("course")), v_off)] = v

        for race in results_list:
            course_norm = _norm(race.get("course"))
            off = str(race.get("off", ""))
            
            v = v_map.get((course_norm, off))
            if not v:
                try:
                    h, m = map(int, off.split("."))
                    for delta in [-2, -1, 1, 2]:
                        t = h * 60 + m + delta
                        off_alt = f"{t // 60}.{t % 60:02d}"
                        if (course_norm, off_alt) in v_map:
                            v = v_map[(course_norm, off_alt)]
                            break
                except: pass
                if not v: continue

            winner = ""
            for rnr in race.get("runners", []):
                if str(rnr.get("position")) == "1":
                    winner = _norm(rnr.get("horse"))
                    break
            
            if not winner: continue

            runners_analysis = v.get("full_analysis", [])
            if not runners_analysis:
                top = v.get("top")
                if top: runners_analysis = [top]
            
            if not runners_analysis: continue
            
            # 1. OR Baseline Check
            highest_or = -1
            top_or_horse = ""
            velo_top_pick = _norm(v.get("top", {}).get("horse", ""))
            
            for r in runners_analysis:
                h_norm = _norm(r.get("horse"))
                is_win = 1 if h_norm == winner else 0
                vp = float(r.get("velo_prime_prob", 0))
                
                # Check OR
                or_val = r.get("official_rating")
                try:
                    or_val = float(or_val) if or_val is not None else -1
                except:
                    or_val = -1
                    
                if or_val > highest_or:
                    highest_or = or_val
                    top_or_horse = h_norm
                
                records.append({
                    "race_id": race.get("race_id"),
                    "horse": h_norm,
                    "vp": vp,
                    "won": is_win,
                    "field_size": len(runners_analysis)
                })
                
            race_stats.append({
                "race_id": race.get("race_id"),
                "velo_won": 1 if velo_top_pick == winner else 0,
                "or_won": 1 if top_or_horse == winner else 0
            })

    if not records:
        print("No matched records for calibration.")
        return

    df = pd.DataFrame(records)
    r_df = pd.DataFrame(race_stats)

    # 1. Calibration Curve (Deciles)
    # Define bins 0.0-0.1, 0.1-0.2...
    bins = np.arange(0, 1.1, 0.1)
    df['vp_bucket'] = pd.cut(df['vp'], bins=bins, right=False)
    
    calib = df.groupby('vp_bucket', observed=True).agg(
        n_races=('won', 'count'),
        observed_win_rate=('won', 'mean'),
        predicted_vp_mean=('vp', 'mean')
    ).reset_index()
    
    # 2. Brier Score
    df['brier_loss'] = (df['vp'] - df['won']) ** 2
    brier_score = df['brier_loss'].mean()
    
    # Naive baseline Brier (1/field_size)
    df['naive_prob'] = 1.0 / df['field_size']
    df['naive_brier_loss'] = (df['naive_prob'] - df['won']) ** 2
    naive_brier_score = df['naive_brier_loss'].mean()

    # 3. OR Baseline Comparison
    velo_sr = r_df['velo_won'].mean()
    or_sr = r_df['or_won'].mean()

    # 4. Overconfidence Flag
    high_vp_df = df[df['vp'] >= 0.70]
    overconfident = False
    if len(high_vp_df) > 0 and high_vp_df['won'].mean() < 0.25:
        overconfident = True

    # Assemble output
    calib_list = []
    for _, r in calib.iterrows():
        b = r['vp_bucket']
        calib_list.append({
            "bucket": f"{b.left:.1f}-{b.right:.1f}",
            "n": int(r['n_races']),
            "observed_win_rate": round(r['observed_win_rate'], 4) if pd.notnull(r['observed_win_rate']) else 0.0,
            "predicted_vp_mean": round(r['predicted_vp_mean'], 4) if pd.notnull(r['predicted_vp_mean']) else 0.0
        })

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days_back": days_back,
        "total_races_evaluated": len(r_df),
        "total_runners_evaluated": len(df),
        "brier_score_velo": round(brier_score, 4),
        "brier_score_naive": round(naive_brier_score, 4),
        "brier_skill_score": round(1 - (brier_score / naive_brier_score), 4) if naive_brier_score else 0,
        "baseline_comparison": {
            "velo_top_pick_sr": round(velo_sr, 4),
            "highest_or_sr": round(or_sr, 4)
        },
        "overconfidence_flag": "OVERCONFIDENT" if overconfident else "CALIBRATED",
        "calibration_curve": calib_list
    }

    # Write JSON
    out_json = CALIB_DIR / "calibration_audit_latest.json"
    out_json.write_text(json.dumps(summary, indent=2))

    # Write Markdown
    md_lines = [
        "# Logistic Calibration Baseline",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Sample:** Last {days_back} days ({len(r_df)} races, {len(df)} runners)",
        "",
        "## 1. Top-Line Metrics",
        f"- **VÉLØ Brier Score:** `{summary['brier_score_velo']:.4f}` (vs Naive: `{summary['brier_score_naive']:.4f}`)",
        f"- **Brier Skill Score:** `{summary['brier_skill_score']:+.4f}` *(Higher is better)*",
        f"- **VÉLØ Top Pick SR:** {summary['baseline_comparison']['velo_top_pick_sr']:.1%}",
        f"- **Highest OR Top Pick SR:** {summary['baseline_comparison']['highest_or_sr']:.1%}",
        f"- **High-VP Status (VP>0.70):** `{summary['overconfidence_flag']}`",
        "",
        "## 2. Decile Calibration Curve",
        "| VP Bucket | N Runners | Predicted VP (Mean) | Observed Win Rate | Delta |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for c in calib_list:
        delta = c['observed_win_rate'] - c['predicted_vp_mean']
        md_lines.append(
            f"| {c['bucket']} | {c['n']} | {c['predicted_vp_mean']:.1%} | {c['observed_win_rate']:.1%} | {delta:+.1%} |"
        )

    out_md = CALIB_DIR / "calibration_audit_latest.md"
    out_md.write_text("\n".join(md_lines))

    print(f"Calibration audit complete. Evaluated {len(r_df)} races.")
    print(f"  VÉLØ SR: {velo_sr:.1%} | Highest OR SR: {or_sr:.1%}")
    print(f"  Saved to {CALIB_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Days back to scan")
    args = parser.parse_args()
    run_calibration_audit(args.days)
