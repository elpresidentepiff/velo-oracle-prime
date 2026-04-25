"""
repatch_rpdc_verdicts.py
-------------------------
Repatches velo_verdicts for a given date with RPDC data from runner_release_candidates.
Used when the RPDC pipeline runs AFTER scoring (or fails during scoring).

Usage:
    python scripts/repatch_rpdc_verdicts.py --date 2026-04-21
"""

import argparse
import json
import logging
import os
from datetime import date
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""

_sb_headers = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

def _sb_get(path: str) -> list[dict]:
    url = f"{SB_URL}/rest/v1/{path}"
    req = Request(url, headers={**_sb_headers, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.error("GET failed: %s — %s", path, e)
        return []

def _sb_patch(table: str, row_id: int, patch: dict) -> bool:
    url = f"{SB_URL}/rest/v1/{table}?id=eq.{row_id}"
    payload = json.dumps(patch).encode()
    req = Request(url, data=payload, headers=_sb_headers, method="PATCH")
    try:
        with urlopen(req, timeout=30) as r:
            return r.status in (200, 201, 204)
    except Exception as e:
        log.error("PATCH failed for id %d: %s", row_id, e)
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=date.today().isoformat())
    args = parser.parse_args()

    date_str = args.date
    log.info("Repatching velo_verdicts for %s", date_str)

    # 1. Load verdicts
    verdicts = _sb_get(
        f"velo_verdicts?select=id,race_id,top_rank_horse_id,generated_at"
        f"&generated_at=gte.{date_str}T00:00:00"
        f"&generated_at=lt.{date_str}T23:59:59"
    )
    log.info("Found %d verdicts", len(verdicts))

    # 2. Load RPDC candidates
    candidates = _sb_get(f"runner_release_candidates?run_date=eq.{date_str}")
    log.info("Found %d RPDC candidates", len(candidates))
    
    # Build lookup: (race_id, horse_id) -> candidate
    cand_map = {(c["race_id"], c["horse_id"]): c for c in candidates}

    # 3. Patch
    patched = 0
    for v in verdicts:
        race_id = v["race_id"]
        horse_id = v["top_rank_horse_id"]
        cand = cand_map.get((race_id, horse_id))
        
        if not cand:
            log.warning("  No RPDC candidate for %s / %s", race_id, horse_id)
            continue
            
        tags = cand.get("rpdc_tags") or []
        primary = None
        if cand.get("rpdc_cash_window_flag"):
            primary = "CASH_WINDOW"
        elif tags:
            primary = tags[0]
            
        patch = {
            "rpdc_release_score":    cand.get("rpdc_release_score", 0),
            "rpdc_cash_window_flag": bool(cand.get("rpdc_cash_window_flag", False)),
            "rpdc_tag_count":        int(cand.get("rpdc_tag_count", 0)),
            "rpdc_tags":             tags,
            "rpdc_primary_tag":      primary,
        }
        
        if _sb_patch("velo_verdicts", v["id"], patch):
            patched += 1
            log.info("  Patched %s / %s: %s (score=%.1f)", 
                     race_id, horse_id, primary, patch["rpdc_release_score"])

    log.info("Summary: %d / %d verdicts patched", patched, len(verdicts))

if __name__ == "__main__":
    main()
