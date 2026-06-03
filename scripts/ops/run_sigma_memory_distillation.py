#!/usr/bin/env python3
"""
Sigma Memory Distillation
Extracts structured learning records from daily closed races (Sigma results + Verdicts).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
SIGMA_RESULTS_DIR = DATA_DIR / "sigma_results"
NEW_BUILD_DIR = DATA_DIR / "new_build" / "reports"
MEMORY_DIR = DATA_DIR / "sigma_memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def norm(s):
    if not s: return ""
    v = str(s).strip().lower()
    v = v.replace("(aw)", "").replace("aw", "")
    v = re.sub(r"\([a-z]{2,3}\)", "", v)
    return re.sub(r"[^a-z]", "", v).strip()

def norm_time(t):
    if not t: return ""
    t = str(t).replace(":", ".")
    try:
        parts = t.split(".")
        h = int(parts[0])
        m = parts[1]
        if h <= 9: h += 12
        return f"{h}.{m}"
    except:
        return t

def get_sp_band(sp):
    if sp <= 3.0: return "SHORT"
    elif sp <= 8.5: return "MID"
    return "LONG"

def run_distillation(target_date: str):
    date_iso = target_date.replace("_", "-")
    date_und = target_date.replace("-", "_")

    # Load source files
    verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_und}.json"
    results_path = DATA_DIR / f"results_{date_und}.json"
    sigma_path = SIGMA_RESULTS_DIR / f"sigma_results_{date_und}.json"
    nb_path = NEW_BUILD_DIR / f"two_lane_readiness_{date_und}.json"

    if not verdicts_path.exists() or not results_path.exists() or not sigma_path.exists():
        print(f"Skipping distillation for {date_iso} - Missing source files (verdicts, results, or sigma).")
        return

    try:
        verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
        raw_results = json.loads(results_path.read_text(encoding="utf-8"))
        results = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
    except Exception as e:
        print(f"Error reading files for {date_iso}: {e}")
        return

    nb_data = {}
    if nb_path.exists():
        try:
            nb_payload = json.loads(nb_path.read_text(encoding="utf-8"))
            for sc in nb_payload.get("race_day_scorecards", []):
                rid = sc.get("race_id")
                if rid and sc.get("lane_b_top3"):
                    nb_data[rid] = sc["lane_b_top3"][0].get("horse")
        except: pass

    # Index verdicts by course/time
    verdicts_map = {}
    for v in verdicts:
        v_off = str(v.get("off_time", "")).replace(":", ".")
        verdicts_map[(norm(v.get("course")), v_off)] = v

    memory_records = []

    print(f"Loaded {len(results)} races from results and {len(verdicts_map)} races from verdicts.")
    print(f"Sample verdicts keys: {list(verdicts_map.keys())[:5]}")
    for race in results:
        course_norm = norm(race.get("course"))
        off = norm_time(str(race.get("off", "")))
        race_id = str(race.get("race_id", ""))

        winner_name = ""
        winner_sp = 0.0
        for rnr in race.get("runners", []):
            if str(rnr.get("position")) == "1":
                winner_name = rnr.get("horse")
                winner_sp = float(rnr.get("sp_dec") or rnr.get("sp") or 0)
                break
        
        if not winner_name: continue

        v = verdicts_map.get((course_norm, off))
        if not v:
            # Fallback time matching
            try:
                h, m = map(int, off.split("."))
                for delta in [-2, -1, 1, 2]:
                    t = h * 60 + m + delta
                    off_alt = f"{t // 60}.{t % 60:02d}"
                    if (course_norm, off_alt) in verdicts_map:
                        v = verdicts_map[(course_norm, off_alt)]
                        break
            except: pass
            if not v:
                print(f"No verdict match for {course_norm} {off}")
                continue

        top_pick = v.get("top") or {}
        velo_top_pick_name = top_pick.get("horse")
        velo_pick_vp = top_pick.get("velo_prime_prob", 0)
        
        is_win = norm(velo_top_pick_name) == norm(winner_name)
        
        sp_band = get_sp_band(winner_sp)
        
        if is_win:
            miss_type = "NONE"
        else:
            if sp_band == "SHORT": miss_type = "short-fav"
            elif sp_band == "MID": miss_type = "mid-price"
            else: miss_type = "outsider"

            # Check decoy
            if top_pick.get("market_deception_score", 0) < 0.10 and top_pick.get("improvement_score", 0) < 0.15 and not is_win:
                miss_type = "decoy followed"

        # Find winner in verdict
        runners = v.get("full_analysis", [])
        winner_verdict = None
        for r in runners:
            if norm(r.get("horse")) == norm(winner_name):
                winner_verdict = r
                break
        
        if not winner_verdict and norm(top_pick.get("horse")) == norm(winner_name):
            winner_verdict = top_pick

        w_vp = winner_verdict.get("velo_prime_prob", 0) if winner_verdict else 0
        w_impr = winner_verdict.get("improvement_score", 0) if winner_verdict else 0
        w_mds = winner_verdict.get("market_deception_score", 0) if winner_verdict else 0
        w_place = winner_verdict.get("place_prob", 0) if winner_verdict else 0

        # New Build agreement
        nb_top_pick = nb_data.get(race_id)
        nb_agreed = False
        if nb_top_pick:
            nb_agreed = norm(nb_top_pick) == norm(winner_name)

        # Doctrine Patch Candidate
        patch_candidate = False
        patch_reason = ""
        if not is_win and winner_verdict:
            if w_impr > 0.30 and w_mds > 0.30:
                patch_candidate = True
                patch_reason = "High multi-sidecar signal on winner"
            elif sp_band == "MID" and w_vp > 0.15:
                patch_candidate = True
                patch_reason = "Visible mid-price winner"

        record = {
            "race_id": race_id,
            "course": v.get("course"),
            "date": date_iso,
            "winner": winner_name,
            "winner_sp_band": sp_band,
            "miss_type": miss_type,
            "velo_top_pick": velo_top_pick_name,
            "velo_pick_vp": velo_pick_vp,
            "winner_vp_if_scored": w_vp,
            "improvement_score_winner": w_impr,
            "mds_winner": w_mds,
            "place_prob_winner": w_place,
            "new_build_agreed": nb_agreed,
            "doctrine_patch_candidate": patch_candidate,
            "patch_reason": patch_reason,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        memory_records.append(record)

    if not memory_records:
        print(f"No valid races evaluated for {date_iso}.")
        return

    out_jsonl = MEMORY_DIR / f"sigma_memory_{date_und}.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for rec in memory_records:
            f.write(json.dumps(rec) + "\n")
    print(f"Written {len(memory_records)} records to {out_jsonl.name}")

    _update_summary()

def _update_summary():
    all_records = []
    for jf in MEMORY_DIR.glob("sigma_memory_*.jsonl"):
        for line in jf.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            all_records.append(json.loads(line))
            
    if not all_records: return

    total_races = len(all_records)
    wins = sum(1 for r in all_records if r["miss_type"] == "NONE")
    
    miss_counts = Counter(r["miss_type"] for r in all_records if r["miss_type"] != "NONE")
    
    # SR by miss type (if we had picked them, what would SR be? Actually, SR is 0 for misses.)
    # The prompt asks for "sr_by_miss_type" which might mean distribution of misses.
    
    patch_candidates = [r for r in all_records if r["doctrine_patch_candidate"]]
    patch_reasons = Counter(r["patch_reason"] for r in patch_candidates)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_races": total_races,
        "total_wins": wins,
        "global_sr": round(wins / total_races, 4) if total_races else 0,
        "miss_type_counts": dict(miss_counts),
        "doctrine_patch_candidates_count": len(patch_candidates),
        "top_patch_reasons": dict(patch_reasons.most_common())
    }

    summary_path = MEMORY_DIR / "sigma_memory_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Updated memory summary: {summary_path.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_distillation(args.date)

if __name__ == "__main__":
    main()
