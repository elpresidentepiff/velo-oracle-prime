"""
Shadow Window Analysis — 100 most recent closed-loop races from velo_verdicts
Computes analog similarity signals and returns structured JSON summary.
"""
import sys
import os
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SHADOW_KEY = os.getenv("SHADOW_SUPABASE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

from supabase import create_client

def fetch_100_recent_closed_loop(sb):
    """Fetch 100 most recent races ordered by generated_at desc, deduplicated by race_id"""
    rows = sb.table("velo_verdicts") \
        .select("*") \
        .order("generated_at", desc=True) \
        .limit(200) \
        .execute()
    
    # Deduplicate by race_id, keeping first (most recent)
    seen = set()
    races = []
    for r in rows.data:
        rid = r.get("race_id")
        if rid and rid not in seen:
            seen.add(rid)
            races.append(r)
        if len(races) >= 100:
            break
    
    return races

def extract_race_fields(verdict):
    """Extract relevant fields from a verdict"""
    full_analysis = verdict.get("full_analysis") or []
    top3 = full_analysis[:3] if full_analysis else []
    
    return {
        "race_id": verdict.get("race_id"),
        "region": verdict.get("region"),
        "tier": verdict.get("tier"),
        "top_rank_horse_id": top3[0].get("horse_id") if len(top3) > 0 else None,
        "velo_prime_prob": top3[0].get("velo_prime_prob") if len(top3) > 0 else None,
        "improvement_score": verdict.get("improvement_score"),
        "market_deception_score": verdict.get("market_deception_score"),
        "macro_regime_label": verdict.get("macro_regime_label"),
        "favourite_trap_risk": verdict.get("favourite_trap_risk"),
        "top3_horse_ids": [h.get("horse_id") for h in top3],
        "verdict_status": verdict.get("verdict_status") or verdict.get("loop_status") or "unknown",
        "generated_at": verdict.get("generated_at"),
    }

def compute_spatial_coherence(races, window=10):
    """
    Check if top horse appears in similar positions in surrounding races.
    Spatial coherence: fraction of races where top horse is in top-3 of adjacent races.
    """
    agreements = []
    for i, race in enumerate(races):
        top_horse = race.get("top_rank_horse_id")
        if not top_horse:
            continue
        
        # Look at surrounding races
        start = max(0, i - window)
        end = min(len(races), i + window + 1)
        surrounding = races[start:i] + races[i+1:end]
        
        if not surrounding:
            continue
        
        # Count how many surrounding races have this horse in top-3
        count = sum(1 for r in surrounding if top_horse in r.get("top3_horse_ids", []))
        coherence_score = count / len(surrounding)
        
        agreements.append({
            "race_id": race["race_id"],
            "top_horse": top_horse,
            "spatial_coherence": round(coherence_score, 4),
            "neighbors_checked": len(surrounding),
            "neighbors_with_horse": count,
        })
    
    return agreements

def compute_analog_agreement(races):
    """
    Analog agreement score: fraction of races where top-3 horses overlap
    with prior window's top-3 distribution.
    """
    analog_agreements = []
    analog_disagreements = []
    window_size = 10
    
    for i in range(window_size, len(races)):
        current_race = races[i]
        prior_window = races[i-window_size:i]
        
        current_top3 = set(current_race.get("top3_horse_ids", []))
        prior_top3 = set()
        for pr in prior_window:
            prior_top3.update(pr.get("top3_horse_ids", []))
        
        overlap = current_top3 & prior_top3
        overlap_ratio = len(overlap) / 3.0 if current_top3 else 0
        
        entry = {
            "race_id": current_race["race_id"],
            "overlap_count": len(overlap),
            "overlap_ratio": round(overlap_ratio, 4),
            "overlap_horses": list(overlap),
            "prior_window_size": len(prior_window),
        }
        
        if overlap_ratio >= 0.5:
            analog_agreements.append(entry)
        else:
            analog_disagreements.append(entry)
    
    return analog_agreements, analog_disagreements

def compute_analog_agreement_score(races):
    """Overall analog agreement score for the window"""
    if len(races) < 11:
        return 0.0
    agreements, disagreements = compute_analog_agreement(races)
    total = len(agreements) + len(disagreements)
    if total == 0:
        return 0.0
    return round(len(agreements) / total, 4)

def compute_g_flags(races, g_state):
    """Extract G flags distribution across the window"""
    all_flags = defaultdict(int)
    flag_by_race = {}
    
    for race in races:
        verdict = race.get("_verdict", {})
        runner_list = verdict.get("full_analysis") or []
        if not runner_list:
            continue
            
        g_races = g_state.get("races_observed", 0)
        if g_races < 50:
            flag = "G_TOO_FEW_RACES"
        else:
            sent_tag = verdict.get("sentient_tag") or verdict.get("rpd_tag") or ""
            hdta_ae = verdict.get("hdta_ae") or 1.0
            dist_1st = verdict.get("hdta_dist_1st") or 999
            sentiment = verdict.get("sentient_modifier_applied") or 0.0
            macro_chaos = verdict.get("macro_chaos_mode") or False
            regime = verdict.get("macro_regime_label") or ""
            market_decep = verdict.get("market_deception_score") or 0.0
            
            flags = []
            if sent_tag in ("engine_dominance", "engine_supremacy"):
                flags.append("ENGINE_SUPREMACY")
            if sentiment > 0.15 and hdta_ae > 1.3:
                flags.append("VETP_ECHO")
            if dist_1st <= 3 and hdta_ae > 1.2:
                flags.append("DUAL_TRAP")
            if regime == "good-to-fast" and sentiment > 0.2:
                flags.append("ANGER_001")
            if macro_chaos and sentiment > 0.1:
                flags.append("ANGER_002")
            if market_decep > 0.6 and sentiment < 0.05:
                flags.append("EVIDENCE_WEAKNESS")
            
            flag = flags[0] if flags else "NEUTRAL"
        
        all_flags[flag] += 1
        flag_by_race[race["race_id"]] = flag
    
    return dict(all_flags), flag_by_race

def generate_top_suggestions(races, spatial_coherence_results):
    """Generate top suggestions based on patterns"""
    suggestions = []
    
    # Find horses with high spatial coherence
    horse_coherence = defaultdict(list)
    for sc in spatial_coherence_results:
        horse = sc.get("top_horse")
        if horse:
            horse_coherence[horse].append(sc["spatial_coherence"])
    
    high_coherence_horses = []
    for horse, scores in horse_coherence.items():
        avg = sum(scores) / len(scores) if scores else 0
        if avg >= 0.6:
            high_coherence_horses.append((horse, avg, len(scores)))
    
    high_coherence_horses.sort(key=lambda x: -x[1])
    
    for horse, avg, count in high_coherence_horses[:5]:
        suggestions.append({
            "type": "high_spatial_coherence",
            "horse_id": horse,
            "avg_coherence": round(avg, 4),
            "occurrences": count,
        })
    
    # Regime-based suggestions
    regime_counts = defaultdict(int)
    for race in races:
        regime = race.get("macro_regime_label")
        if regime:
            regime_counts[regime] += 1
    
    top_regimes = sorted(regime_counts.items(), key=lambda x: -x[1])[:3]
    for regime, count in top_regimes:
        suggestions.append({
            "type": "dominant_regime",
            "regime": regime,
            "count": count,
        })
    
    return suggestions

def main():
    print("=== Shadow Window Analysis ===")
    
    if not SUPABASE_URL or not SHADOW_KEY:
        print("ERROR: SUPABASE_URL or SHADOW_KEY not set")
        return
    
    sb = create_client(SUPABASE_URL, SHADOW_KEY)
    
    # Load G state
    g_rows = sb.table("learned_patterns") \
        .select("*") \
        .eq("pattern_type", "playbook_g_state") \
        .order("updated_at", desc=True) \
        .limit(1) \
        .execute()
    g_state = {}
    if g_rows.data:
        try:
            g_state = json.loads(g_rows.data[0].get("pattern_data", "{}"))
        except:
            g_state = {}
    
    # Fetch 100 most recent races
    print("Fetching 100 most recent closed-loop races...")
    raw_races = fetch_100_recent_closed_loop(sb)
    print(f"Fetched {len(raw_races)} races")
    
    # Extract fields
    races = []
    for r in raw_races:
        extracted = extract_race_fields(r)
        extracted["_verdict"] = r
        races.append(extracted)
    
    # Count by verdict status
    status_counts = defaultdict(int)
    for race in races:
        status_counts[race["verdict_status"]] += 1
    
    confirmed_count = status_counts.get("confirmed", 0) + status_counts.get("closed", 0)
    watch_count = status_counts.get("watch", 0)
    caution_count = status_counts.get("caution", 0) + status_counts.get("open", 0)
    
    # Compute analog signals
    spatial_coherence_results = compute_spatial_coherence(races)
    analog_agreements, analog_disagreements = compute_analog_agreement(races)
    analog_agreement_score = compute_analog_agreement_score(races)
    g_flags_dist, g_flags_by_race = compute_g_flags(races, g_state)
    top_suggestions = generate_top_suggestions(races, spatial_coherence_results)
    
    # Build summary
    summary = {
        "window": 100,
        "total_races": len(races),
        "confirmed_count": confirmed_count,
        "watch_count": watch_count,
        "caution_count": caution_count,
        "analog_agreement_score": analog_agreement_score,
        "analog_agreements": analog_agreements,
        "analog_disagreements": analog_disagreements,
        "g_flags": g_flags_dist,
        "top_suggestions": top_suggestions,
        "spatial_coherence_summary": {
            "avg": round(sum(sc["spatial_coherence"] for sc in spatial_coherence_results) / len(spatial_coherence_results), 4) if spatial_coherence_results else 0,
            "high_count": sum(1 for sc in spatial_coherence_results if sc["spatial_coherence"] >= 0.5),
        },
        "status_distribution": dict(status_counts),
    }
    
    print("\n=== JSON Summary ===")
    print(json.dumps(summary, indent=2))
    
    # Also save to file
    output_path = ROOT / "shadow_window_analysis.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {output_path}")

if __name__ == "__main__":
    main()
