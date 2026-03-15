#!/usr/bin/env python3.11
"""
VÉLØ Daily Pipeline — Autonomous Race Data Ingestion
=====================================================
Runs daily at 10:00am to:
1. Fetch all UK/Ireland racecards from the Racing API
2. Write races and runners to Supabase
3. Parse spotlight comments through the NLP parser
4. Write horse_comments flags to Supabase
5. Log pipeline run status

Usage:
    python3.11 workers/daily_pipeline.py [--date YYYY-MM-DD]

Environment variables required:
    RACING_API_USERNAME
    RACING_API_PASSWORD
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime, date
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("velo.daily_pipeline")

# ── Credentials ──────────────────────────────────────────────────────────────
RACING_API_USER = os.environ.get("RACING_API_USERNAME", "cHHxKCt4ePK3TpFrWNq3sax6")
RACING_API_PASS = os.environ.get("RACING_API_PASSWORD", "D2Zlg9VcD4Sjbjcb7pMzpwwy")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ltbsxbvfsxtnharjvqcm.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ4ODM2OSwiZXhwIjoyMDc5MDY0MzY5fQ.MmQiC3kt6UJ0e2BQ6k32oWbSNbWmv2U0G9E6l6k2C18")

SUPABASE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}

# ── Spotlight trigger phrases (inline — no import dependency) ─────────────────
NEGATIVE_PHRASES = [
    "needs to improve", "well held", "out of depth", "struggling",
    "pulled up", "unseated", "fell", "refused", "never dangerous",
    "tailed off", "weakened", "faded", "beaten a long way",
    "non-stayer", "stamina doubtful", "trip too far", "trip too short",
    "headstrong", "hard to predict", "quirky", "awkward",
    "market drifter", "drifted in market", "weak in market",
    "fitness doubts", "not fully fit", "needed the run",
    "wind operation", "breathing problem"
]

POSITIVE_PHRASES = [
    "eye-catching", "eye catching", "caught the eye", "unlucky",
    "hampered", "short of room", "checked", "squeezed out",
    "course specialist", "loves this track", "course and distance winner",
    "in form", "trainer in form", "yard in form", "yard firing",
    "top jockey booking", "booking of note", "significant jockey booking",
    "progressive", "open to improvement", "unexposed",
    "well handicapped", "off a good mark", "dropped in class",
    "class dropper", "step down in class"
]

STAMINA_DOUBT_PHRASES = [
    "non-stayer", "stamina doubtful", "trip too far", "may not stay",
    "likely non-stayer", "stamina suspect", "bred for shorter"
]

BEHAVIOUR_RISK_PHRASES = [
    "headstrong", "hard to predict", "quirky", "awkward at start",
    "refused", "bolted", "unseated", "erratic"
]


def parse_spotlight(text: str, horse_name: str, race_id: str, race_date: str) -> dict:
    """Parse a spotlight comment and return a horse_comments row."""
    if not text:
        return None

    text_lower = text.lower()

    # Sentiment scoring
    neg_hits = sum(1 for p in NEGATIVE_PHRASES if p in text_lower)
    pos_hits = sum(1 for p in POSITIVE_PHRASES if p in text_lower)
    sentiment = pos_hits - neg_hits

    # Boolean flags
    flags = {
        "flag_stamina_doubt": any(p in text_lower for p in STAMINA_DOUBT_PHRASES),
        "flag_behaviour_risk": any(p in text_lower for p in BEHAVIOUR_RISK_PHRASES),
        "flag_class_drop": any(p in text_lower for p in ["class dropper", "dropped in class", "step down in class"]),
        "flag_market_drifter": any(p in text_lower for p in ["market drifter", "drifted in market", "weak in market"]),
        "flag_eye_catching": any(p in text_lower for p in ["eye-catching", "eye catching", "caught the eye", "unlucky", "hampered"]),
        "flag_course_specialist": any(p in text_lower for p in ["course specialist", "loves this track", "course and distance"]),
        "flag_jockey_booking": any(p in text_lower for p in ["top jockey booking", "booking of note", "significant jockey booking"]),
        "flag_trainer_form": any(p in text_lower for p in ["trainer in form", "yard in form", "yard firing"]),
        "flag_fitness_doubt": any(p in text_lower for p in ["fitness doubts", "not fully fit", "needed the run"]),
        "flag_pace_concern": any(p in text_lower for p in ["headstrong", "hard to settle", "keen"]),
        "flag_weight_concern": any(p in text_lower for p in ["top weight", "burden", "big weight"]),
        "flag_draw_concern": any(p in text_lower for p in ["wide draw", "poor draw", "unfavourable draw"]),
        "flag_ground_concern": any(p in text_lower for p in ["ground concern", "unsuited by", "not handle"]),
        "flag_distance_concern": any(p in text_lower for p in ["trip too far", "trip too short", "may not stay", "bred for shorter"]),
        "flag_positive_mention": pos_hits > 0
    }

    return {
        "race_id": race_id,
        "horse_name": horse_name,
        "spotlight_text": text[:1000],
        "sentiment_score": sentiment,
        "race_date": race_date,
        **flags
    }


def safe_int(val):
    if val is None:
        return None
    try:
        return int(float(str(val).replace(',', '').strip()))
    except (ValueError, TypeError):
        return None


def clean_prize(val):
    if not val:
        return 0
    digits = ''.join(filter(str.isdigit, str(val)))
    return int(digits) if digits else 0


def run_pipeline(target_date: str = None):
    """Run the full daily ingestion pipeline."""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    log.info(f"=== VÉLØ Daily Pipeline starting for {target_date} ===")

    # ── Step 1: Fetch racecards ───────────────────────────────────────────────
    log.info("Fetching racecards from Racing API...")
    try:
        resp = requests.get(
            "https://api.theracingapi.com/v1/racecards/standard",
            auth=(RACING_API_USER, RACING_API_PASS),
            params={"day": "today"},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error(f"Racing API fetch failed: {e}")
        return {"status": "FAILED", "error": str(e)}

    racecards = data.get("racecards", [])
    uk_ire = [r for r in racecards if r.get("region", "").upper() in ["GB", "IRE"]]
    log.info(f"Total races: {len(racecards)} | UK/Ireland: {len(uk_ire)}")

    stats = {
        "date": target_date,
        "races_total": len(uk_ire),
        "races_ok": 0, "races_fail": 0,
        "runners_ok": 0, "runners_fail": 0,
        "spotlight_ok": 0, "spotlight_fail": 0
    }

    for race in uk_ire:
        race_id = race.get("race_id", "")
        distance_raw = race.get("distance_f", 0)
        distance_int = safe_int(float(str(distance_raw or 0)) * 10) if distance_raw else 0

        # ── Step 2: Insert race ───────────────────────────────────────────────
        race_row = {
            "race_id": race_id,
            "course": race.get("course", ""),
            "date": target_date,
            "time": race.get("off_time", ""),
            "race_type": race.get("type", ""),
            "distance_f": distance_int,
            "going": race.get("going", ""),
            "class": str(race.get("race_class", "") or ""),
            "prize_money": clean_prize(race.get("prize")),
            "runners_count": len(race.get("runners", []))
        }

        r = requests.post(f"{SUPABASE_URL}/rest/v1/races",
                          headers=SUPABASE_HEADERS, json=race_row)
        if r.status_code in [200, 201]:
            stats["races_ok"] += 1
        else:
            stats["races_fail"] += 1
            log.warning(f"Race insert failed [{r.status_code}] {race_id}: {r.text[:100]}")

        # ── Step 3: Insert runners + parse spotlight ──────────────────────────
        for runner in race.get("runners", []):
            horse_name = runner.get("horse", "")
            spotlight_text = runner.get("spotlight", "") or runner.get("comment", "")

            runner_row = {
                "race_id": race_id,
                "horse_name": horse_name,
                "draw": safe_int(runner.get("draw")),
                "weight": safe_int(runner.get("lbs")),
                "or_rating": safe_int(runner.get("ofr")),
                "ts_rating": safe_int(runner.get("ts")),
                "rpr": safe_int(runner.get("rpr")),
                "trainer": runner.get("trainer", ""),
                "jockey": runner.get("jockey", ""),
                "form": runner.get("form", ""),
                "rpd_tag": runner.get("run_style", ""),
                "rpd_evidence": spotlight_text[:500] if spotlight_text else ""
            }

            r2 = requests.post(f"{SUPABASE_URL}/rest/v1/runners",
                               headers=SUPABASE_HEADERS, json=runner_row)
            if r2.status_code in [200, 201]:
                stats["runners_ok"] += 1
            else:
                stats["runners_fail"] += 1

            # ── Step 4: Parse spotlight and write horse_comments ──────────────
            if spotlight_text:
                parsed = parse_spotlight(spotlight_text, horse_name, race_id, target_date)
                if parsed:
                    # Map to actual horse_comments schema (uses JSONB spotlight_flags)
                    flags_json = {k.replace('flag_', ''): v
                                  for k, v in parsed.items()
                                  if k.startswith('flag_')}
                    comment_row = {
                        "race_id": race_id,
                        "horse_name": horse_name,
                        "horse_id": runner.get("horse_id", ""),
                        "race_date": target_date,
                        "comment_raw": spotlight_text[:1000],
                        "spotlight_flags": flags_json
                    }
                    r3 = requests.post(f"{SUPABASE_URL}/rest/v1/horse_comments",
                                       headers=SUPABASE_HEADERS, json=comment_row)
                    if r3.status_code in [200, 201]:
                        stats["spotlight_ok"] += 1
                    else:
                        stats["spotlight_fail"] += 1
                        if stats["spotlight_fail"] <= 2:
                            log.warning(f"Spotlight fail [{r3.status_code}]: {r3.text[:100]}")

    log.info("=== PIPELINE COMPLETE ===")
    log.info(f"Races:     {stats['races_ok']} ok / {stats['races_fail']} failed")
    log.info(f"Runners:   {stats['runners_ok']} ok / {stats['runners_fail']} failed")
    log.info(f"Spotlight: {stats['spotlight_ok']} ok / {stats['spotlight_fail']} failed")

    return {"status": "OK", "stats": stats}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VÉLØ Daily Pipeline")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    result = run_pipeline(args.date)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "OK" else 1)
