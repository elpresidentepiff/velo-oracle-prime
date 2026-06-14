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

def parse_sp_decimal(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return 0.0
    if text in {"evens", "evensf", "evs", "evsf", "even", "evenf"}:
        return 2.0
    cleaned = re.sub(r"[^0-9./]", "", text)
    try:
        if "/" in cleaned:
            num, den = cleaned.split("/", 1)
            return round(float(num) / float(den) + 1, 2)
        return float(cleaned)
    except Exception:
        return 0.0

def is_aw_course(course: str | None) -> bool:
    text = str(course or "").lower()
    return "(aw)" in text or " aw" in text or "all-weather" in text

def parse_position(value):
    text = str(value or "").strip().upper()
    if not text:
        return None
    match = re.match(r"^(\d+)", text)
    if match:
        return int(match.group(1))
    return None

def run_distillation(
    target_date: str,
    verdicts_path_arg: str | None = None,
    results_path_arg: str | None = None,
):
    date_iso = target_date.replace("_", "-")
    date_und = target_date.replace("-", "_")

    # Load source files
    verdicts_path = Path(verdicts_path_arg) if verdicts_path_arg else DATA_DIR / f"velo_prime_verdicts_{date_und}.json"
    results_path = Path(results_path_arg) if results_path_arg else DATA_DIR / f"results_{date_und}.json"
    sigma_path = SIGMA_RESULTS_DIR / f"sigma_results_{date_und}.json"
    nb_path = NEW_BUILD_DIR / f"two_lane_readiness_{date_und}.json"

    if not verdicts_path.exists() or not results_path.exists():
        print(f"Skipping distillation for {date_iso} - Missing source files (verdicts or results).")
        return
    sigma_available = sigma_path.exists()
    if not sigma_available:
        print(f"Sigma artifact missing for {date_iso}; distilling from supported RP verdict/results inputs.")

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

    # Index verdicts by race ID first, then course/time fallback.
    verdicts_by_id = {}
    verdicts_map = {}
    for v in verdicts:
        rid = str(v.get("race_id") or "")
        if rid:
            verdicts_by_id[rid] = v
        v_off = norm_time(str(v.get("off_time", "")).replace(":", "."))
        verdicts_map[(norm(v.get("course")), v_off)] = v

    memory_records = []

    print(f"Loaded {len(results)} races from results and {len(verdicts_map)} races from verdicts.")
    print(f"Sample verdicts keys: {list(verdicts_map.keys())[:5]}")
    for race in results:
        course_norm = norm(race.get("course"))
        off = norm_time(str(race.get("off", "")))
        race_id = str(race.get("race_id", ""))

        race_runners = race.get("runners") or race.get("full_runners") or []
        winner_name = race.get("winner_horse") or race.get("winner_name") or ""
        winner_sp = parse_sp_decimal(race.get("winner_sp"))
        for rnr in race_runners:
            if str(rnr.get("position")) == "1":
                winner_name = rnr.get("horse") or winner_name
                winner_sp = parse_sp_decimal(rnr.get("sp_dec") or rnr.get("sp") or winner_sp)
                break
        
        if not winner_name: continue

        v = verdicts_by_id.get(race_id) or verdicts_map.get((course_norm, off))
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
        top_pick_position = None
        top_pick_framed = False
        for rnr in race_runners:
            if norm(rnr.get("horse")) == norm(velo_top_pick_name):
                top_pick_position = parse_position(rnr.get("position"))
                top_pick_framed = bool(top_pick_position and top_pick_position <= 3)
                break
        
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

        # Top pick sidecar values
        top_impr = top_pick.get("improvement_score", 0)
        top_mds = top_pick.get("market_deception_score", 0)
        top_place = top_pick.get("place_prob", 0)
        top_nb_agreed = False
        if nb_top_pick:
            top_nb_agreed = norm(nb_top_pick) == norm(velo_top_pick_name)

        aw_tier_a_watch = str(v.get("tier") or "").upper() == "A" and is_aw_course(v.get("course"))
        aw_watch_outcome = None
        if aw_tier_a_watch:
            aw_watch_outcome = "WIN" if is_win else "FRAME" if top_pick_framed else "MISS"

        record = {
            "race_id": race_id,
            "course": v.get("course"),
            "date": date_iso,
            "winner": winner_name,
            "winner_sp_band": sp_band,
            "miss_type": miss_type,
            "velo_top_pick": velo_top_pick_name,
            "velo_pick_vp": velo_pick_vp,
            "top_pick_result_position": top_pick_position,
            "top_pick_framed": top_pick_framed,
            "winner_vp_if_scored": w_vp,
            "improvement_score_winner": w_impr,
            "mds_winner": w_mds,
            "place_prob_winner": w_place,
            "new_build_agreed": nb_agreed,
            "top_pick_improvement_score": top_impr,
            "top_pick_mds": top_mds,
            "top_pick_place_prob": top_place,
            "top_pick_new_build_agreed": top_nb_agreed,
            "doctrine_patch_candidate": patch_candidate,
            "patch_reason": patch_reason,
            "aw_tier_a_forward_watch": aw_tier_a_watch,
            "aw_tier_a_watch_pattern": "sidecar_tier=A|course_type=AW" if aw_tier_a_watch else None,
            "aw_tier_a_watch_status": "DOCTRINE_CANDIDATE_ONLY_FORWARD_VALIDATION" if aw_tier_a_watch else None,
            "aw_tier_a_watch_outcome": aw_watch_outcome,
            "aw_tier_a_live_velo_impact": False,
            "sigma_artifact_available": sigma_available,
            "distillation_source": "supported_rp_results",
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
    aw_watch_rows = [r for r in all_records if r.get("aw_tier_a_forward_watch")]
    aw_watch_outcomes = Counter(r.get("aw_tier_a_watch_outcome") or "UNKNOWN" for r in aw_watch_rows)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_races": total_races,
        "total_wins": wins,
        "global_sr": round(wins / total_races, 4) if total_races else 0,
        "miss_type_counts": dict(miss_counts),
        "doctrine_patch_candidates_count": len(patch_candidates),
        "top_patch_reasons": dict(patch_reasons.most_common()),
        "aw_tier_a_forward_watch": {
            "candidate_only": True,
            "live_velo_impact": False,
            "pattern": "sidecar_tier=A|course_type=AW",
            "n": len(aw_watch_rows),
            "outcome_counts": dict(aw_watch_outcomes),
            "status": "FORWARD_VALIDATION_ACCUMULATING",
        },
    }

    summary_path = MEMORY_DIR / "sigma_memory_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Updated memory summary: {summary_path.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--verdicts-file", default=None)
    parser.add_argument("--results-file", default=None)
    args = parser.parse_args()
    run_distillation(args.date, args.verdicts_file, args.results_file)

if __name__ == "__main__":
    main()
