#!/usr/bin/env python3
"""
# OBSERVATION ONLY — DO NOT IMPORT INTO velo_prime_service.py OR run_prime_today.py
# State classification enters scoring only after 30+ closed-outcome validation per state.
# Hard rule: docs/engineering/VELO_PROBABILITY_AND_STATE_ENGINE_V1.md

Agentic RAG Evidence Layer (Read-Only)
Assembles a structured evidence dossier for each Tier A runner by pulling from local sources.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
FEED_DIR = DATA_DIR / "new_build" / "current_cards"
MARKOV_DIR = DATA_DIR / "markov"
LATENT_DIR = DATA_DIR / "latent"
SIGMA_MEM_DIR = DATA_DIR / "sigma_memory"
ELO_DIR = DATA_DIR / "sidecar_elo"
RAG_DIR = DATA_DIR / "rag"

RAG_DIR.mkdir(parents=True, exist_ok=True)

def _norm(s):
    if not s: return ""
    import re
    v = str(s).strip().lower().replace("(aw)", "").replace("aw", "")
    return re.sub(r"[^a-z]", "", v).strip()

def build_rag_verdict(vp, markov, concepts, sidecars, elo_best_sidecar):
    """
    Synthesize a one-sentence plain-English verdict. Max 25 words.
    Strongest signals first, warnings second.
    """
    signals = []
    warnings = []
    
    if sidecars.get("mds", 0) > 0.5:
        signals.append("MDS strong")
    if sidecars.get("improvement_score", 0) > 0.3:
        signals.append("High improvement")
    if sidecars.get("place_prob", 0) > 0.8:
        signals.append("Elite place confidence")
        
    if vp > 0.6:
        base = "STRONG"
    elif vp > 0.4:
        base = "SOLID"
    else:
        base = "MARGINAL"
        
    if markov and markov != "UNKNOWN":
        signals.append(f"Markov: {markov}")
        
    if concepts:
        warnings.append(f"Tags: {','.join(concepts)}")
        
    sentence = f"{base} — "
    if signals:
        sentence += ", ".join(signals) + ". "
    else:
        sentence += f"VP {vp:.3f}. "
        
    if warnings:
        sentence += "Warnings: " + " ".join(warnings) + "."
    else:
        sentence += "No latent warnings."
        
    # Check length
    words = sentence.split()
    if len(words) > 25:
        return " ".join(words[:25]) + "..."
    return sentence.strip()

def run_agentic_rag(target_date: str):
    date_und = target_date.replace("-", "_")
    
    # Paths
    verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_und}.json"
    feed_path = FEED_DIR / "current_card_passport_feed_latest.jsonl"
    markov_path = MARKOV_DIR / f"markov_state_card_{date_und}.jsonl"
    latent_path = LATENT_DIR / f"latent_concepts_{date_und}.jsonl"
    sigma_mem_path = SIGMA_MEM_DIR / "sigma_memory_summary.json"
    elo_path = ELO_DIR / "sidecar_elo_latest.json"

    if not verdicts_path.exists():
        print(f"Error: Verdicts file not found at {verdicts_path}")
        return

    # 1. Load Tier A runners
    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    tier_a_races = []
    for v in verdicts:
        if v.get("tier") == "A":
            tier_a_races.append(v)
            
    if not tier_a_races:
        print(f"No Tier A runners found for {target_date}.")
        return

    # 2. Load context sources
    # Passport
    passports = {}
    if feed_path.exists():
        for line in feed_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                h_norm = _norm(row.get("horse"))
                rid = str(row.get("race_id"))
                passports[f"{rid}:{h_norm}"] = row.get("passport_summary", {})

    # Markov
    markov_states = {}
    if markov_path.exists():
        for line in markov_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                mr = json.loads(line)
                h_norm = _norm(mr.get("horse"))
                rid = str(mr.get("race_id"))
                markov_states[f"{rid}:{h_norm}"] = mr.get("state", "UNKNOWN")

    # Latent
    latent_concepts = {}
    if latent_path.exists():
        for line in latent_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lr = json.loads(line)
                h_norm = _norm(lr.get("horse"))
                rid = str(lr.get("race_id"))
                latent_concepts[f"{rid}:{h_norm}"] = lr.get("concepts", [])

    # Sigma Memory Context
    sigma_context = {"dominant_miss_type": "UNKNOWN", "historical_sr_tier_a": 0.401} # 0.401 from system state provided
    if sigma_mem_path.exists():
        try:
            sm = json.loads(sigma_mem_path.read_text(encoding="utf-8"))
            counts = sm.get("miss_type_counts", {})
            if counts:
                dominant = max(counts, key=counts.get)
                sigma_context["dominant_miss_type"] = dominant
            # Using hardcoded 0.401 for now as historical_sr_tier_a is tracked outside of sigma_memory_summary.
        except: pass

    # Elo Context
    elo_context = {"best_sidecar_today": "UNKNOWN", "elo": 0}
    if elo_path.exists():
        try:
            elo_data = json.loads(elo_path.read_text(encoding="utf-8"))
            rankings = elo_data.get("rankings", [])
            if rankings:
                best = rankings[0]
                elo_context = {"best_sidecar_today": best.get("sidecar"), "elo": best.get("elo")}
        except: pass

    dossiers = []

    # 3. Assemble
    for v in tier_a_races:
        rid = str(v.get("race_id"))
        top = v.get("top") or {}
        horse = top.get("horse", "UNKNOWN")
        course = v.get("course", "UNKNOWN")
        off = v.get("off_time", "UNKNOWN")
        vp = top.get("velo_prime_prob", 0.0)
        h_norm = _norm(horse)
        key = f"{rid}:{h_norm}"
        
        pp = passports.get(key, {})
        pp_ev = {
            "career_runs": pp.get("career_runs"),
            "win_rate": pp.get("win_rate"),
            "place_rate": pp.get("place_rate"),
            "or_change_last3": pp.get("or_change_last3"),
            "days_since_last": pp.get("days_since_last_run"),
            "class_movement": pp.get("class_movement"),
            "pp_best_ts_last6": pp.get("pp_best_ts_last6")
        }
        
        m_state = markov_states.get(key, "UNKNOWN")
        concepts = latent_concepts.get(key, [])
        
        sidecars = {
            "improvement_score": top.get("improvement_score", 0.0),
            "mds": top.get("market_deception_score", 0.0),
            "place_prob": top.get("place_prob", 0.0)
        }
        
        rag_verdict = build_rag_verdict(vp, m_state, concepts, sidecars, elo_context.get("best_sidecar_today"))

        dossier = {
            "horse": horse,
            "race": f"{course} {off}",
            "vp": vp,
            "tier": "A",
            "passport_evidence": pp_ev,
            "markov_state": m_state,
            "latent_concepts": concepts,
            "sidecar_signals": sidecars,
            "elo_context": elo_context,
            "sigma_context": sigma_context,
            "rag_verdict": rag_verdict
        }
        dossiers.append(dossier)

    # 4. Output JSON
    out_json = RAG_DIR / f"rag_dossier_{date_und}.json"
    out_json.write_text(json.dumps(dossiers, indent=2))
    
    # 5. Output Markdown
    md_lines = [
        f"# Agentic RAG Evidence Dossier",
        f"**Date:** {target_date}",
        f"**Tier A Runners:** {len(dossiers)}",
        ""
    ]
    
    for d in dossiers:
        md_lines.extend([
            f"## {d['horse']} | {d['race']} (VP: {d['vp']:.3f})",
            f"**Verdict:** {d['rag_verdict']}",
            "",
            f"- **Markov State:** `{d['markov_state']}`",
            f"- **Latent Concepts:** `{', '.join(d['latent_concepts']) if d['latent_concepts'] else 'None'}`",
            f"- **Sidecars:** MDS: {d['sidecar_signals']['mds']:.3f} | Impr: {d['sidecar_signals']['improvement_score']:.3f} | Place: {d['sidecar_signals']['place_prob']:.3f}",
            f"- **Profile:** Runs: {d['passport_evidence']['career_runs']} | Days Off: {d['passport_evidence']['days_since_last']} | OR Change: {d['passport_evidence']['or_change_last3']}",
            ""
        ])
        
    out_md = RAG_DIR / f"rag_dossier_{date_und}.md"
    out_md.write_text("\n".join(md_lines))
    
    print(f"RAG Dossier built for {target_date}")
    print(f"  Tier A Runners processed: {len(dossiers)}")
    print(f"  Saved to: {RAG_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_agentic_rag(args.date)
