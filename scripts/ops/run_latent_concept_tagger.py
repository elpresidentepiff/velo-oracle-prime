#!/usr/bin/env python3
"""
# OBSERVATION ONLY — DO NOT IMPORT INTO velo_prime_service.py OR run_prime_today.py
# State classification enters scoring only after 30+ closed-outcome validation per state.
# Hard rule: docs/engineering/VELO_PROBABILITY_AND_STATE_ENGINE_V1.md

Latent Concept Learning Tagger (Read-Only)
Assigns advanced multi-variate concept tags to runners based on passport and state history.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
FEED_DIR = DATA_DIR / "new_build" / "current_cards"
MARKOV_DIR = DATA_DIR / "markov"
LATENT_DIR = DATA_DIR / "latent"
LATENT_DIR.mkdir(parents=True, exist_ok=True)

def _norm(s):
    if not s: return ""
    import re
    v = str(s).strip().lower().replace("(aw)", "").replace("aw", "")
    return re.sub(r"[^a-z]", "", v).strip()

def tag_concepts(pp, v_info, markov_state):
    """
    Evaluates all defined latent concepts for a single runner.
    """
    if not pp:
        return [], "LOW", ["insufficient_passport_data"]

    concepts = []
    evidence_list = []

    days = pp.get("days_since_last_run")
    or_change = pp.get("or_change_last3")
    sp_traj = str(pp.get("sp_trajectory") or "").upper()
    jock = bool(pp.get("jockey_continuity"))
    class_mov = str(pp.get("class_movement") or "").upper()
    runs = pp.get("career_runs", 0)
    
    impr = v_info.get("improvement_score", 0.0)
    mds = v_info.get("market_deception_score", 0.0)

    # 1. MARK_READY_WITH_CONNECTION_INTENT
    # or_change_last3 flat (<=1) AND jockey_continuity=True AND days_since_last 30–60 AND class_moved_down=True
    if or_change is not None and or_change <= 1:
        if jock:
            if days is not None and 30 <= days <= 60:
                if class_mov == "DOWN":
                    concepts.append("MARK_READY_WITH_CONNECTION_INTENT")
                    evidence_list.append("or_flat+jockey_retained+days_30_60+class_down")

    # 2. DRIFT_TRAP
    # pp_avg_sp_last5 declining (tightening/shortening) AND improvement_score<0.20 AND mds<0.10
    # Note: "declining" here means SP is getting smaller (tightening market).
    if sp_traj == "TIGHTENING" or sp_traj == "SHORTENING":
        if impr < 0.20 and mds < 0.10:
            concepts.append("DRIFT_TRAP")
            evidence_list.append("market_shortening+low_impr+low_mds")

    # 3. CASH_RUN_CANDIDATE
    # Markov state=SETUP_RUN in previous run (we only have today's state easily, 
    # but the prompt says: check prior state if stored. We don't have historical Markov states yet,
    # so we will approximate using today's raw setup signals or leave it requiring historical state.)
    # Given the strict brief: "Markov state=SETUP_RUN in previous run AND current days_since_last 14–28 AND jockey_continuity=True"
    # For now, if we can't look up the previous state, this might rarely fire. We will rely on the 
    # pp.get("setup_run_candidate") which is a passport flag from previous runs.
    prev_setup = bool(pp.get("setup_run_candidate"))
    if prev_setup and jock:
        if days is not None and 14 <= days <= 28:
            concepts.append("CASH_RUN_CANDIDATE")
            evidence_list.append("prev_setup+days_14_28+jockey_retained")

    # 4. CONCEALED_FORM_SIGNAL
    # place_rate>0.40 AND win_rate<0.10 AND layoff_flag active
    place_rate = float(pp.get("place_rate") or 0.0)
    win_rate = float(pp.get("win_rate") or 0.0)
    layoff = str(pp.get("layoff_flag") or "").upper() == "ACTIVE"
    if place_rate > 0.40 and win_rate < 0.10 and layoff:
        concepts.append("CONCEALED_FORM_SIGNAL")
        evidence_list.append("high_place_low_win+layoff_active")

    # 5. BOUNCE_WARNING
    # career_runs>20 AND days_since_last<10 AND class_moved_up=True
    if runs > 20:
        if days is not None and days < 10:
            if class_mov == "UP":
                concepts.append("BOUNCE_WARNING")
                evidence_list.append("runs_gt_20+days_lt_10+class_up")

    conf = "HIGH" if len(concepts) > 0 else "LOW"
    if not concepts:
        evidence_list = ["no_concept_matched"]

    return concepts, conf, evidence_list

def run_latent_tagger(target_date: str):
    date_und = target_date.replace("-", "_")
    feed_path = FEED_DIR / "current_card_passport_feed_latest.jsonl"
    markov_path = MARKOV_DIR / f"markov_state_card_{date_und}.jsonl"
    verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_und}.json"

    if not feed_path.exists():
        print(f"Error: Passport feed not found at {feed_path}")
        return

    # Load verdicts to augment missing intelligence (MDS, Impr, Tier)
    v_map = {}
    tier_a_horses = set()
    if verdicts_path.exists():
        verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
        for v in verdicts:
            r_id = str(v.get("race_id"))
            tier = v.get("tier")
            for r in v.get("full_analysis", []):
                h_norm = _norm(r.get("horse"))
                v_map[f"{r_id}:{h_norm}"] = r
                if tier == "A":
                    tier_a_horses.add(f"{r_id}:{h_norm}")
            top = v.get("top")
            if top:
                h_norm = _norm(top.get("horse"))
                v_map[f"{r_id}:{h_norm}"] = top
                if tier == "A":
                    tier_a_horses.add(f"{r_id}:{h_norm}")

    # Load Markov states
    m_map = {}
    if markov_path.exists():
        for line in markov_path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            mr = json.loads(line)
            m_map[f"{mr.get('race_id')}:{_norm(mr.get('horse'))}"] = mr.get("state", "UNKNOWN")

    records = []
    all_concepts = []
    
    for line in feed_path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        
        rd = row.get("race_date", "")[:10]
        if rd and rd != target_date:
            continue

        race_id = str(row.get("race_id"))
        horse = row.get("horse", "")
        h_norm = _norm(horse)
        
        pp = row.get("passport_summary") or {}
        v_info = v_map.get(f"{race_id}:{h_norm}") or {}
        m_state = m_map.get(f"{race_id}:{h_norm}", "UNKNOWN")
        
        concepts, conf, ev = tag_concepts(pp, v_info, m_state)
        
        records.append({
            "race_id": race_id,
            "course": row.get("course"),
            "off": row.get("off_time"),
            "horse": horse,
            "concepts": concepts,
            "confidence": conf,
            "evidence": ev,
            "is_tier_a": f"{race_id}:{h_norm}" in tier_a_horses
        })
        all_concepts.extend(concepts)

    if not records:
        print(f"No runners matched target date {target_date} in feed.")
        return

    # 1. Write JSONL
    out_jsonl = LATENT_DIR / f"latent_concepts_{date_und}.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
            
    # 2. Summary
    tagged_count = sum(1 for r in records if r["concepts"])
    
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_date": target_date,
        "total_runners": len(records),
        "tagged_runners": tagged_count,
        "concept_frequencies": dict(Counter(all_concepts))
    }
    
    out_json = LATENT_DIR / f"latent_summary_{date_und}.json"
    out_json.write_text(json.dumps(summary, indent=2))
    
    # 3. Markdown Report (Tier A Focus)
    tier_a_records = [r for r in records if r["is_tier_a"]]
    
    md_lines = [
        f"# Latent Concept Operator Card",
        f"**Date:** {target_date}",
        f"**Total Runners Tagged:** {tagged_count} / {len(records)}",
        "",
        "## Tier A Concept Context",
        "| Course | Time | Horse | Concepts | Evidence |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    
    if not tier_a_records:
        md_lines.append("| - | - | *No Tier A runners found* | - | - |")
    else:
        for r in sorted(tier_a_records, key=lambda x: (x.get("course", ""), x.get("off", ""))):
            conc_str = ", ".join(r["concepts"]) if r["concepts"] else "-"
            ev_str = ", ".join(r["evidence"]) if r["evidence"] and r["evidence"] != ["no_concept_matched"] else "-"
            off = str(r.get("off", ""))
            if "T" in off: off = off.split("T")[1][:5]
            md_lines.append(f"| {r.get('course')} | {off} | **{r.get('horse')}** | `{conc_str}` | {ev_str} |")
            
    md_lines.extend([
        "",
        "## Global Concept Frequencies",
        "| Concept | Count |",
        "| :--- | :--- |"
    ])
    for c, count in sorted(summary["concept_frequencies"].items(), key=lambda x: x[1], reverse=True):
        md_lines.append(f"| {c} | {count} |")
        
    out_md = LATENT_DIR / f"latent_concepts_{date_und}.md"
    out_md.write_text("\n".join(md_lines))
    
    print(f"Latent Concept tagging complete for {target_date}")
    print(f"  Runners tagged: {tagged_count}")
    for c, count in summary["concept_frequencies"].items():
        print(f"    {c}: {count}")
    print(f"  Saved to: {LATENT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_latent_tagger(args.date)
