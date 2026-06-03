"""
Mid-Price Leakage Deep Dive (Broad Search v2)
Audit across results and verdicts to understand why VELO misses in the 3.0-8.5 SP zone.
"""
import json
import os
from pathlib import Path
import pandas as pd
import re

ROOT = Path(".")
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "data" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def norm(s):
    if not s: return ""
    import re
    v = str(s).strip().lower()
    v = v.replace("(aw)", "").replace("aw", "")
    v = re.sub(r"\([a-z]{2,3}\)", "", v)
    return re.sub(r"[^a-z]", "", v).strip()

def run_audit():
    result_files = sorted(DATA_DIR.glob("results_2026_*.json"))
    print(f"Total result files found: {len(result_files)}")
    
    audit_records = []
    total_midprice_races = 0
    total_midprice_wins = 0

    for rf in result_files:
        # Expected: results_2026_MM_DD.json
        date_str = rf.name.replace("results_", "").replace(".json", "")
        # Try both variants: underscore and hyphen
        verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_str}.json"
        if not verdicts_path.exists():
            date_hyphen = date_str.replace("_", "-")
            verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_hyphen}.json"
        
        if not verdicts_path.exists():
            continue
            
        print(f"Auditing {date_str}...")
        
        try:
            raw_results = json.loads(rf.read_text(encoding="utf-8"))
            results_list = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
            verdicts_list = json.loads(verdicts_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Error reading files for {date_str}: {e}")
            continue
            
        verdicts_map = {}
        for v in verdicts_list:
            v_off = str(v.get("off_time", "")).replace(":", ".")
            verdicts_map[(norm(v.get("course")), v_off)] = v

        for race in results_list:
            course_norm = norm(race.get("course"))
            off = str(race.get("off", ""))
            
            winner_name = ""
            sp = 0.0
            for rnr in race.get("runners", []):
                if str(rnr.get("position")) == "1":
                    winner_name = rnr.get("horse")
                    sp = float(rnr.get("sp_dec") or rnr.get("sp") or 0)
                    break
            
            if not winner_name or not (3.0 <= sp <= 8.5):
                continue
            
            total_midprice_races += 1
            
            v = verdicts_map.get((course_norm, off))
            if not v:
                try:
                    h, m = map(int, off.split("."))
                    for delta in [-2, -1, 1, 2]:
                        t = h * 60 + m + delta
                        off_alt = f"{t // 60}.{t % 60:02d}"
                        if (course_norm, off_alt) in verdicts_map:
                            v = verdicts_map[(course_norm, off_alt)]
                            break
                except: pass
                if not v: continue

            top_pick = v.get("top") or {}
            is_win = norm(top_pick.get("horse")) == norm(winner_name)
            
            if is_win:
                total_midprice_wins += 1
                continue
            
            runners = v.get("full_analysis", [])
            winner_verdict = None
            winner_rank = 99
            for i, r in enumerate(runners):
                if norm(r.get("horse")) == norm(winner_name):
                    winner_verdict = r
                    winner_rank = i + 1
                    break
            
            if not winner_verdict:
                if norm(top_pick.get("horse")) == norm(winner_name):
                    winner_verdict = top_pick
                    winner_rank = 1

            audit_records.append({
                "date": date_str.replace("_", "-"),
                "course": race.get("course"),
                "off": off,
                "winner": winner_name,
                "winner_sp": sp,
                "top_pick": top_pick.get("horse"),
                "top_pick_vp": top_pick.get("velo_prime_prob"),
                "winner_rank": winner_rank,
                "winner_vp": winner_verdict.get("velo_prime_prob") if winner_verdict else 0,
                "winner_impr": winner_verdict.get("improvement_score") if winner_verdict else 0,
                "winner_mds": winner_verdict.get("market_deception_score") if winner_verdict else 0,
                "winner_place": winner_verdict.get("place_prob") if winner_verdict else 0,
                "winner_flags": winner_verdict.get("verdict_flags", []) if winner_verdict else [],
                "invisible": winner_verdict is None
            })

    print(f"Audit processing complete. Total mid-price misses found: {len(audit_records)}")

    if not audit_records:
        return

    df = pd.DataFrame(audit_records)
    summary = {
        "total_midprice_races": total_midprice_races,
        "total_midprice_wins": total_midprice_wins,
        "total_midprice_misses": len(df),
        "midprice_sr": round(total_midprice_wins / total_midprice_races, 4) if total_midprice_races else 0,
        "rank_distribution": df["winner_rank"].value_counts().sort_index().to_dict(),
        "visibility": {
            "top_3": len(df[df["winner_rank"] <= 3]),
            "top_5": len(df[df["winner_rank"] <= 5]),
            "invisible": len(df[df["invisible"]])
        },
        "sidecar_catch": {
            "impr_gt_03": len(df[df["winner_impr"] > 0.30]),
            "mds_gt_03": len(df[df["winner_mds"] > 0.30]),
            "place_gt_05": len(df[df["winner_place"] > 0.50])
        },
        "top_pick_vp_avg": round(df["top_pick_vp"].mean(), 4)
    }

    out_json = OUTPUT_DIR / "midprice_leakage_audit_latest.json"
    out_json.write_text(json.dumps({"summary": summary, "records": audit_records}, indent=2))
    
    md = f"""# Mid-Price Leakage Audit (SP 3.0-8.5)
Generated: {pd.Timestamp.now()}
Total Mid-Price Races: {total_midprice_races}
Mid-Price Wins: {total_midprice_wins} ({summary['midprice_sr']:.1%})
Mid-Price Misses: {len(df)}

## 1. Visibility (Where is the winner when we miss?)
| Category | Count | % of Misses |
| :--- | :--- | :--- |
| **Truly Invisible** | {summary['visibility']['invisible']} | {summary['visibility']['invisible']/len(df):.1%} |
| **Visible (Rank 2-3)** | {summary['visibility']['top_3'] - summary['visibility']['invisible']} | {(summary['visibility']['top_3'] - summary['visibility']['invisible'])/len(df):.1%} |
| **Visible (Rank 4-5)** | {summary['visibility']['top_5'] - summary['visibility']['top_3']} | {(summary['visibility']['top_5'] - summary['visibility']['top_3'])/len(df):.1%} |
| **Visible (Rank 6+)** | {len(df) - summary['visibility']['top_5']} | {(len(df) - summary['visibility']['top_5'])/len(df):.1%} |

## 2. Sidecar Signal Check (Did we nearly have them?)
| Signal | Caught Winner | % of Misses |
| :--- | :--- | :--- |
| **Improvement > 0.30** | {summary['sidecar_catch']['impr_gt_03']} | {summary['sidecar_catch']['impr_gt_03']/len(df):.1%} |
| **MDS > 0.30** | {summary['sidecar_catch']['mds_gt_03']} | {summary['sidecar_catch']['mds_gt_03']/len(df):.1%} |
| **Place Prob > 0.50** | {summary['sidecar_catch']['place_gt_05']} | {summary['sidecar_catch']['place_gt_05']/len(df):.1%} |

## 3. Top Picks in these races
- Average Top Pick VP: {summary['top_pick_vp_avg']}
- Winner Rank distribution: {summary['rank_distribution']}
"""
    (OUTPUT_DIR / "midprice_leakage_audit_latest.md").write_text(md)
    print(f"Audit complete. Results in {OUTPUT_DIR}")

if __name__ == "__main__":
    run_audit()
