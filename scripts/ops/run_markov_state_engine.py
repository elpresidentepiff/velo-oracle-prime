#!/usr/bin/env python3
"""
# OBSERVATION ONLY — DO NOT IMPORT INTO velo_prime_service.py OR run_prime_today.py
# State classification enters scoring only after 30+ closed-outcome validation per state.
# Hard rule: docs/engineering/VELO_PROBABILITY_AND_STATE_ENGINE_V1.md

Markov Hidden-State Engine (Read-Only)
Classifies runners on today's card into latent states based on passport history.
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
MARKOV_DIR.mkdir(parents=True, exist_ok=True)

def _norm(s):
    if not s: return ""
    import re
    v = str(s).strip().lower().replace("(aw)", "").replace("aw", "")
    return re.sub(r"[^a-z]", "", v).strip()

def classify_state(pp, v_info):
    """
    Evaluates all states and returns the one with the highest confidence/evidence.
    """
    if not pp:
        return "UNKNOWN", "LOW", ["insufficient_passport_data"]

    candidates = []

    days = pp.get("days_since_last_run")
    or_change = pp.get("or_change_last3")
    sp_traj = str(pp.get("sp_trajectory") or "").upper()
    jock = bool(pp.get("jockey_continuity"))
    class_mov = str(pp.get("class_movement") or "").upper()
    runs = pp.get("career_runs", 0)
    
    impr = v_info.get("improvement_score", 0.0)
    mds = v_info.get("market_deception_score", 0.0)

    # 1. MARKET_TRAP
    trap_ev = []
    if sp_traj == "TIGHTENING": trap_ev.append("market_tightening")
    if impr < 0.20: trap_ev.append("low_improvement")
    if mds < 0.10: trap_ev.append("low_mds")
    if len(trap_ev) >= 3:
        candidates.append(("MARKET_TRAP", "HIGH", trap_ev))
    elif len(trap_ev) == 2 and "market_tightening" in trap_ev:
        candidates.append(("MARKET_TRAP", "MED", trap_ev))

    # 2. BOUNCE_RISK
    bounce_ev = []
    if runs > 5: bounce_ev.append("experienced_campaigner")
    if days is not None and days < 10: bounce_ev.append("quick_turnaround")
    if class_mov == "UP": bounce_ev.append("class_up")
    if "quick_turnaround" in bounce_ev and "class_up" in bounce_ev:
        candidates.append(("BOUNCE_RISK", "HIGH", bounce_ev))

    # 3. CASH_RUN
    cash_ev = []
    if days is not None and 14 <= days <= 35: cash_ev.append("days_14_35")
    if sp_traj == "TIGHTENING": cash_ev.append("market_tightening")
    if jock: cash_ev.append("jockey_retained")
    if or_change is not None and or_change <= 0: cash_ev.append("or_protected")
    if len(cash_ev) >= 3:
        candidates.append(("CASH_RUN", "HIGH", cash_ev))
    elif len(cash_ev) == 2 and "market_tightening" in cash_ev:
        candidates.append(("CASH_RUN", "MED", cash_ev))

    # 4. SETUP_RUN
    setup_ev = []
    if days is not None and days > 45: setup_ev.append("days_gt_45")
    if or_change is not None and or_change <= 0: setup_ev.append("or_protected")
    if sp_traj == "DRIFTING": setup_ev.append("market_drift")
    if pp.get("setup_run_candidate"): setup_ev.append("trainer_patient_flag")
    if len(setup_ev) >= 3:
        candidates.append(("SETUP_RUN", "HIGH", setup_ev))
    elif len(setup_ev) >= 2 and ("days_gt_45" in setup_ev or "trainer_patient_flag" in setup_ev):
        candidates.append(("SETUP_RUN", "MED", setup_ev))

    # 5. MARK_RELEASE
    release_ev = []
    if or_change == 0: release_ev.append("or_frozen")
    if class_mov == "UP": release_ev.append("class_up")
    if len(release_ev) == 2:
        candidates.append(("MARK_RELEASE", "MED", release_ev))

    # 6. MARK_PROTECTION
    prot_ev = []
    if class_mov == "DOWN": prot_ev.append("class_down")
    if or_change == 0 and pp.get("win_rate_last3", 0) > 0: prot_ev.append("frozen_despite_win")
    if jock: prot_ev.append("jockey_retained")
    if "frozen_despite_win" in prot_ev or ("class_down" in prot_ev and "jockey_retained" in prot_ev):
        candidates.append(("MARK_PROTECTION", "MED", prot_ev))

    # 7. CONCEALED_FORM
    conc_ev = []
    if pp.get("place_rate", 0) > 0.30 and pp.get("win_rate", 0) < 0.10: conc_ev.append("high_place_low_win")
    if pp.get("layoff_flag") == "ACTIVE" or (days is not None and days > 60): conc_ev.append("layoff_active")
    if len(conc_ev) >= 2:
        candidates.append(("CONCEALED_FORM", "MED", conc_ev))

    if not candidates:
        return "UNKNOWN", "LOW", ["insufficient_signals"]

    # Precedence: Highest confidence first, then by priority index
    priority = {
        "MARKET_TRAP": 1,
        "BOUNCE_RISK": 2,
        "CASH_RUN": 3,
        "SETUP_RUN": 4,
        "MARK_RELEASE": 5,
        "MARK_PROTECTION": 6,
        "CONCEALED_FORM": 7
    }

    # Sort by confidence (HIGH > MED > LOW), then by priority (lower is better)
    conf_rank = {"HIGH": 0, "MED": 1, "LOW": 2}
    candidates.sort(key=lambda x: (conf_rank[x[1]], priority.get(x[0], 99)))

    best = candidates[0]
    return best[0], best[1], best[2]

def run_markov_engine(target_date: str):
    date_und = target_date.replace("-", "_")
    feed_path = FEED_DIR / "current_card_passport_feed_latest.jsonl"
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
            # Also check top
            top = v.get("top")
            if top:
                h_norm = _norm(top.get("horse"))
                v_map[f"{r_id}:{h_norm}"] = top
                if tier == "A":
                    tier_a_horses.add(f"{r_id}:{h_norm}")

    records = []
    
    for line in feed_path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        
        # Ensure it matches target date
        rd = row.get("race_date", "")[:10]
        if rd and rd != target_date:
            continue

        race_id = str(row.get("race_id"))
        horse = row.get("horse", "")
        h_norm = _norm(horse)
        
        pp = row.get("passport_summary") or {}
        v_info = v_map.get(f"{race_id}:{h_norm}") or {}
        
        state, conf, ev = classify_state(pp, v_info)
        
        records.append({
            "race_id": race_id,
            "course": row.get("course"),
            "off": row.get("off_time"),
            "horse": horse,
            "state": state,
            "confidence": conf,
            "evidence": ev,
            "is_tier_a": f"{race_id}:{h_norm}" in tier_a_horses
        })

    if not records:
        print(f"No runners matched target date {target_date} in feed.")
        return

    # 1. Write JSONL
    out_jsonl = MARKOV_DIR / f"markov_state_card_{date_und}.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
            
    # 2. Summary
    states = [r["state"] for r in records]
    high_conf = sum(1 for r in records if r["confidence"] == "HIGH")
    
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_date": target_date,
        "total_runners": len(records),
        "high_confidence_states": high_conf,
        "state_distribution": dict(Counter(states))
    }
    
    out_json = MARKOV_DIR / f"markov_state_summary_{date_und}.json"
    out_json.write_text(json.dumps(summary, indent=2))
    
    # 3. Markdown Report (Tier A Focus)
    tier_a_records = [r for r in records if r["is_tier_a"]]
    
    md_lines = [
        f"# Markov Hidden-State Operator Card",
        f"**Date:** {target_date}",
        f"**Total Runners Classified:** {len(records)}",
        f"**High Confidence States:** {high_conf}",
        "",
        "## Tier A State Context",
        "| Course | Time | Horse | State | Confidence | Evidence |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    if not tier_a_records:
        md_lines.append("| - | - | *No Tier A runners found* | - | - | - |")
    else:
        for r in sorted(tier_a_records, key=lambda x: (x.get("course", ""), x.get("off", ""))):
            ev_str = ", ".join(r["evidence"]) if r["evidence"] else "-"
            # Format time simply if ISO
            off = str(r.get("off", ""))
            if "T" in off: off = off.split("T")[1][:5]
            md_lines.append(f"| {r.get('course')} | {off} | **{r.get('horse')}** | `{r['state']}` | {r['confidence']} | {ev_str} |")
            
    md_lines.extend([
        "",
        "## Global State Distribution",
        "| State | Count |",
        "| :--- | :--- |"
    ])
    for s, c in sorted(summary["state_distribution"].items(), key=lambda x: x[1], reverse=True):
        md_lines.append(f"| {s} | {c} |")
        
    out_md = MARKOV_DIR / f"markov_state_card_{date_und}.md"
    out_md.write_text("\n".join(md_lines))
    
    print(f"Markov Engine classification complete for {target_date}")
    print(f"  Runners: {len(records)}")
    print(f"  High Confidence: {high_conf}")
    print(f"  Saved to: {MARKOV_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_markov_engine(args.date)
