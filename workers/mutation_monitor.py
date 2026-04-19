import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import resolve_supabase_service_key, resolve_supabase_url
from app.services.velo_prime_service import score_race_velo_prime
from workers.racing_api_fetcher import RacingAPIFetcher
from workers.racing_api_normalizer import normalize_race

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("velo.mutation_monitor")

def check_for_mutations():
    """
    15-minute pre-race integrity check for A-STRIKE races.
    """
    sb_url = resolve_supabase_url()
    sb_key = resolve_supabase_service_key()
    if not sb_url or not sb_key:
        logger.error("Supabase credentials missing")
        return

    from supabase import create_client
    db = create_client(sb_url, sb_key)

    # 1. Find upcoming A-STRIKE races (within next 20 mins)
    now = datetime.now(timezone.utc)
    lookahead = now + timedelta(minutes=20)
    
    # We query velo_verdicts joined with races (manually here)
    # Target: decision_tier='A' and race time near now.
    try:
        verdicts = db.table("velo_verdicts").select(
            "race_id, top_rank_horse_id, predicted_field_size, decision_tier"
        ).eq("decision_tier", "A").execute()
    except Exception as e:
        logger.error(f"Failed to fetch verdicts: {e}")
        return

    fetcher = RacingAPIFetcher()
    
    for v in verdicts.data:
        rid = v["race_id"]
        
        # 2. Fetch fresh racecard
        try:
            raw_race = fetcher.fetch_racecard_for_race(rid)
            if not raw_race:
                continue
            
            fresh_race = normalize_race(raw_race)
            actual_size = len(fresh_race.get("runners", []))
            predicted_size = v["predicted_field_size"] or 0
            
            # 3. Check for Material Mutation
            mutation_detected = False
            reasons = []
            
            if actual_size != predicted_size:
                mutation_detected = True
                reasons.append(f"Field size changed ({predicted_size} → {actual_size})")
            
            # 4. Re-score to detect top-pick displacement
            if mutation_detected:
                preds = score_race_velo_prime(fresh_race)
                if preds:
                    new_top = preds[0]["horse_id"]
                    new_prob = preds[0]["velo_prime_prob"]
                    old_prob = v.get("top_rank_score", 0)
                    
                    if new_top != v["top_rank_horse_id"]:
                        reasons.append(f"CRITICAL: Top pick shifted ({v['top_rank_horse_id']} → {new_top})")
                    elif abs(new_prob - old_prob) > 0.05:
                        reasons.append(f"SIGNAL: Prob materially shifted ({old_prob:.2f} → {new_prob:.2f})")
                
                # 5. Alert only if material
                if reasons:
                    _send_mutation_alert(rid, reasons)
                else:
                    logger.info(f"Mutation detected for {rid} but not material — staying quiet.")
                
        except Exception as e:
            logger.error(f"Mutation check failed for {rid}: {e}")

def _send_mutation_alert(race_id: str, reasons: list[str]):
    # Logic to send Telegram alert
    msg = f"⚠ MUTATION ALERT — Race {race_id}\n" + "\n".join(f"• {r}" for r in reasons)
    logger.warning(msg)
    # (Implementation of tg() omitted here for brevity; uses standard TG logic)

if __name__ == "__main__":
    check_for_mutations()
