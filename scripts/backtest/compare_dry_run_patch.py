
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

TARGET_DATE = "2026-05-01"


def _known_race_ids_for_date(date_str: str) -> list:
    """race_ids from the standard racecard cache for this date, if it exists.

    generated_at is write-time, not race-date -- scoring the evening before
    race day stamps generated_at under the wrong calendar day and silently
    zeroes out any date-range query. race_id reliably correlates to the
    actual race date, so prefer it when the cache is available.
    """
    path = ROOT / "data" / f"racecards_{date_str.replace('-', '_')}_standard.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    races = payload.get("racecards", []) if isinstance(payload, dict) else payload
    return [r["race_id"] for r in races if isinstance(r, dict) and r.get("race_id")]


def run_diff():
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    # 1. Fetch live persisted verdicts for TARGET_DATE
    known_race_ids = _known_race_ids_for_date(TARGET_DATE)
    v_resp = None
    if known_race_ids:
        v_resp = (
            sb.table("velo_verdicts")
            .select("race_id,full_analysis,decision_tier,velo_prime_prob")
            .in_("race_id", known_race_ids)
            .execute()
        )
    if not (v_resp and v_resp.data):
        v_resp = sb.table("velo_verdicts").select("race_id,full_analysis,decision_tier,velo_prime_prob").gte("generated_at", f"{TARGET_DATE}T00:00:00").lt("generated_at", f"{TARGET_DATE}T23:59:59").execute()

    if not v_resp.data:
        print("No persisted verdicts found for 2026-05-01.")
        return
        
    persisted = {}
    vp30_before = 0
    for v in v_resp.data:
        race_id = v["race_id"]
        fa = v.get("full_analysis") or []
        if isinstance(fa, dict): fa = list(fa.values())
        if not fa: continue
        
        top = fa[0]
        persisted[race_id] = {
            "horse": top.get("horse"),
            "prob": v.get("velo_prime_prob") or 0.0,
            "tier": v.get("decision_tier"),
            "sqpe": top.get("sqpe_v17_prob") or 0.0,
            "mds": top.get("market_deception_score") or 0.0,
            "place_prob": top.get("place_prob") or 0.0,
        }
        if (v.get("velo_prime_prob") or 0.0) >= 0.3:
            vp30_before += 1
            
    # 2. Parse dry-run log
    log_path = ROOT / "data" / "dry_run_05_01_after.log"
    if not log_path.exists():
        print(f"Log not found at {log_path}")
        return
        
    with open(log_path) as f:
        lines = f.readlines()
        
    # Example format:
    # SCORED  Ascot                   2:00   race_id=rac_11914682
    #         horse=Adaay Of Scarlett          tier=B  conf=low [Structure:H]
    #         prob=0.3512  gap=0.0319  mds=0.1330
    
    dry_run = {}
    current_race = None
    current_horse = None
    current_tier = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("SCORED"):
            parts = line.split("race_id=")
            if len(parts) > 1:
                current_race = parts[1].strip()
        elif line.startswith("horse=") and current_race:
            horse_part = line.split("horse=")[1].split("tier=")[0].strip()
            tier_part = line.split("tier=")[1].split()[0].strip()
            current_horse = horse_part
            current_tier = tier_part
        elif line.startswith("prob=") and current_race and current_horse:
            prob_part = line.split("prob=")[1].split()[0].strip()
            mds_part = line.split("mds=")[1].split()[0].strip() if "mds=" in line else "0"
            dry_run[current_race] = {
                "horse": current_horse,
                "prob": float(prob_part),
                "tier": current_tier,
                "mds": float(mds_part)
            }
            current_race = None
            
    # 3. Compare
    print(f"Comparing {len(persisted)} live vs {len(dry_run)} dry-run races...")
    
    top_changes = 0
    vp_changes = 0
    vp30_after = 0
    vp_deltas = []
    mds_changed = 0
    
    for r_id, p_data in persisted.items():
        d_data = dry_run.get(r_id)
        if not d_data:
            continue
            
        if d_data["horse"] != p_data["horse"]:
            top_changes += 1
            print(f"Top Change: {r_id} | Live: {p_data['horse']} -> Dry: {d_data['horse']}")
            
        if abs(d_data["prob"] - p_data["prob"]) > 0.0001:
            vp_changes += 1
            vp_deltas.append(d_data["prob"] - p_data["prob"])
            
        if d_data["prob"] >= 0.3:
            vp30_after += 1
            
        if abs(d_data["mds"] - p_data["mds"]) > 0.0001:
            mds_changed += 1
            
    print("\n=== PATCH DRY-RUN COMPARISON REPORT ===")
    print(f"Total Matches Scored: {len(dry_run)}")
    print(f"Top Selection Changes: {top_changes}")
    print(f"VP Prob Changes: {vp_changes}")
    avg_delta = sum(vp_deltas)/len(vp_deltas) if vp_deltas else 0
    print(f"Average VP Delta (when changed): {avg_delta:+.4f}")
    print(f"VP30 Membership: Before={vp30_before}, After={vp30_after} (Delta: {vp30_after - vp30_before:+d})")
    print(f"MDS/SQPE Stability: {'PASS' if mds_changed == 0 else 'FAIL'} (MDS changed in {mds_changed} races)")
    print("=======================================\n")

if __name__ == "__main__":
    run_diff()
