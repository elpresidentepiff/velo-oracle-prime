"""
VÉLØ — Playbook G Enriched Evolution
====================================
Enriches sigma_audit races with velo_verdicts prediction data,
then feeds enriched data to Playbook G.

ENRICHMENT PATH:
  sigma_audits (outcome) ←race_id→ velo_verdicts (prediction)

FIELDS JOINED FROM velo_verdicts:
  - top_rank_horse_id     (story_anchor / power_anchor in G)
  - top_rank_score       (prediction.confidence in G)
  - confidence_level
  - decision_tier

FIELDS FROM sigma_audits:
  - race_id, date
  - actual_winner_id
  - actual_winner_sp
  - outcome (WIN/PLACED/MISS)
  - miss_reason

PAIN RULE FIX:
  story_anchor now set from velo_verdicts.top_rank_horse_id (not from sigma_audit verdict_id).
  Fixes the "Avoid  when MPI > 70" bug from the previous run.

Usage:
    PYTHONPATH=. python scripts/evolve_playbook_g_from_sigma_audits.py --enriched

Deduplication: writes 'playbook_g_enriched_{date}' to learned_patterns.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Setup ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.g_enriched_evolution")

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_EVOLVE_PLAYBOOK_G"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")


def _require_legacy_override() -> None:
    if os.getenv(LEGACY_EXECUTION_ENV) == "1":
        return
    raise SystemExit(
        "Legacy script is quarantined and blocked by default. "
        f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
    )


def db_get(path: str, params: str = "") -> list:
    """Direct REST call — avoids Supabase Python client filter quirks."""
    url = f"{SUPABASE_URL}/rest/v1/{path}?{params}" if params else f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers={"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def _safe_float(val: Any) -> float:
    try:
        v = float(val)
        return v if not (__import__("math").isnan(v)) else 0.0
    except (TypeError, ValueError):
        return 0.0


def fetch_enriched_races(target_date: str) -> list[dict]:
    """
    Fetch sigma_audit races for a date, enriched with velo_verdicts prediction data.
    Returns enriched race dicts.
    """
    # Get sigma_audit races with winner data for this date
    sa_races = db_get(
        "sigma_audits",
        f"date=eq.{target_date}&track=not.is.null&actual_winner_id=not.is.null&select=*"
    )
    if not sa_races:
        return []

    # Get velo_verdicts for all race_ids in one batch
    race_ids = [r["race_id"] for r in sa_races if r.get("race_id")]
    if not race_ids:
        return []

    batch_size = 50
    vv_map = {}
    for i in range(0, len(race_ids), batch_size):
        batch = race_ids[i:i + batch_size]
        ids_param = ",".join([f'"{rid}"' for rid in batch])
        try:
            vv_rows = db_get(
                "velo_verdicts",
                f"race_id=in.({ids_param})&select=race_id,top_rank_horse_id,top_rank_score,confidence_level,decision_tier&limit={len(batch)}"
            )
            for vv in vv_rows:
                vv_map[vv["race_id"]] = vv
        except Exception as e:
            log.warning("velo_verdicts batch fetch failed: %s", e)

    enriched = []
    for sa in sa_races:
        race_id = sa.get("race_id")
        vv = vv_map.get(race_id, {})

        # Determine outcome
        outcome = sa.get("outcome") or "MISS"

        # MPI proxy from winner SP
        winner_sp = _safe_float(sa.get("actual_winner_sp") or 0.0)
        if winner_sp > 10:
            mpi = 80
        elif winner_sp > 5:
            mpi = 50
        else:
            mpi = 20

        # Chaos bloom from SP (high SP = upset = chaos)
        if winner_sp > 10:
            chaos_bloom = 75
        elif winner_sp > 6:
            chaos_bloom = 55
        elif winner_sp > 3:
            chaos_bloom = 35
        else:
            chaos_bloom = 20

        # Narrative disruption from miss reason
        miss_reason = sa.get("miss_reason") or ""
        if miss_reason == "mid_priced_won":
            narrative_disruption = 80
        elif miss_reason == "market_decoy_followed":
            narrative_disruption = 65
        elif miss_reason in ("outsider_won", "outsider_hedge_omitted"):
            narrative_disruption = 70
        else:
            narrative_disruption = 30

        # Build race_data — key fix: use velo_verdicts top_rank_horse_id as story_anchor
        story_anchor = vv.get("top_rank_horse_id") or sa.get("actual_winner_id") or ""
        power_anchor = story_anchor  # same as story when no divergence

        race_data = {
            "race_id": race_id,
            "story_anchor": story_anchor,
            "power_anchor": power_anchor,
            "mpi": mpi,
            "chaos_bloom": chaos_bloom,
            "narrative_disruption": narrative_disruption,
            "runners": [],
        }

        # Prediction from velo_verdicts (this is what G was missing)
        top_score = vv.get("top_rank_score")
        if top_score is None:
            top_score = 0.0

        prediction = {
            "power_anchor": story_anchor,
            "confidence": _safe_float(top_score),
            "doctrines_fired": [],
        }

        # Actual result
        actual_result = {
            "winner": sa.get("actual_winner_id") or "",
            "favourite_won": (outcome == "WIN"),
            "winner_profile": {
                "sp": winner_sp,
                "miss_reason": miss_reason,
            },
        }

        enriched.append({
            "race_id": race_id,
            "date": target_date,
            "outcome": outcome,
            "verdict_score": _safe_float(top_score),
            "confidence_level": vv.get("confidence_level") or "unknown",
            "decision_tier": vv.get("decision_tier") or "unknown",
            "actual_winner_id": sa.get("actual_winner_id"),
            "actual_winner_sp": winner_sp,
            "miss_reason": miss_reason,
            "race_data": race_data,
            "prediction": prediction,
            "actual_result": actual_result,
            "enriched": bool(story_anchor),  # True if we got velo_verdicts data
        })

    return enriched


def write_dedup_marker(target_date: str, fed_count: int, wins: int, enriched_count: int) -> None:
    """Write enriched dedup marker to learned_patterns."""
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    source_hash = hashlib.sha256(
        f"g_enriched:{target_date}:{fed_count}:{enriched_count}".encode()
    ).hexdigest()[:16]
    payload = {
        "pattern_name": f"playbook_g_enriched_{target_date}",
        "pattern_type": "system_marker",
        "description": (
            f"Playbook G ENRICHED evolution {target_date}: "
            f"{fed_count} races ({enriched_count} enriched with velo_verdicts), {wins} wins"
        ),
        "conditions": {
            "source_date": target_date,
            "fed_count": fed_count,
            "enriched_count": enriched_count,
            "wins_fed": wins,
            "source_hash": source_hash,
            "doctrine_family": "SENTIENT_LOOPBACK",
            "mutation_type": "observe_race_outcome_enriched",
            "source": "sigma_audits_plus_velo_verdicts",
        },
        "occurrences": fed_count,
        "successful_predictions": wins,
        "success_rate": round(wins / fed_count, 4) if fed_count else 0.0,
        "confidence_level": round(min(fed_count / 20, 1.0), 4),
        "first_observed": now_naive,
        "last_observed": now_naive,
        "created_at": now_naive,
        "updated_at": now_naive,
        "is_active": True,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/learned_patterns",
        data=body,
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        method="POST"
    )
    urllib.request.urlopen(req, timeout=30)


def evolve_g_for_date(target_date: str) -> dict:
    """Feed enriched sigma_audit races to Playbook G. Returns stats."""
    # Dedup check
    dedup_name = f"playbook_g_enriched_{target_date}"
    try:
        existing = db_get("learned_patterns", f"pattern_name=eq.{dedup_name}&select=id&limit=1")
        if existing:
            log.info("[%s] Already enriched for this date — skipping", target_date)
            return {"date": target_date, "fed": 0, "skipped": True}
    except Exception as e:
        log.warning("[%s] Dedup check failed: %s — proceeding", target_date, e)

    # Import Playbook G
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        engine = SentientLoopbackEngine()
    except Exception as e:
        log.error("SentientLoopbackEngine import failed: %s", e)
        return {"date": target_date, "fed": 0, "error": str(e)}

    # Fetch enriched races
    enriched_races = fetch_enriched_races(target_date)
    if not enriched_races:
        log.info("[%s] No sigma_audit races with winner data — skipping", target_date)
        return {"date": target_date, "fed": 0, "skipped": True}

    fed = 0
    wins = 0
    enriched_count = 0
    errors = 0

    for er in enriched_races:
        try:
            engine.observe_race_outcome(
                er["race_data"],
                er["prediction"],
                er["actual_result"]
            )
            fed += 1
            if er["outcome"] == "WIN":
                wins += 1
            if er["enriched"]:
                enriched_count += 1
        except Exception as e:
            log.warning("[%s] observe_race_outcome failed for %s: %s",
                       target_date, er.get("race_id"), e)
            errors += 1

    if fed > 0:
        try:
            engine._save_state()
            log.info("[%s] G state saved", target_date)
        except Exception as e:
            log.warning("[%s] G state save failed: %s", target_date, e)

        try:
            write_dedup_marker(target_date, fed, wins, enriched_count)
        except Exception as e:
            log.warning("[%s] Dedup marker write failed: %s", target_date, e)

    return {
        "date": target_date,
        "fed": fed,
        "wins": wins,
        "enriched": enriched_count,
        "errors": errors,
    }


def get_dates_with_winner_data() -> list[str]:
    """Get dates that have sigma_audit races with winner data."""
    rows = db_get(
        "sigma_audits",
        "track=not.is.null&actual_winner_id=not.is.null&select=date"
    )
    return sorted(set(r.get("date") for r in rows if r.get("date")))


def print_state_summary(engine):
    """Print G state summary."""
    state = engine.state
    log.info("")
    log.info("=" * 50)
    log.info("G STATE AFTER ENRICHED EVOLUTION:")
    log.info("  Races observed: %s", state.get("total_races_observed", "?"))
    log.info("  Version: %s", state.get("version", "?"))
    app = state.get("appetite_state", {})
    log.info("  Doctrine threshold: %s", app.get("doctrine_firing_threshold", "?"))
    log.info("  Aggression: %s", app.get("aggression_level", "?"))
    log.info("")
    log.info("  Doctrine strengths:")
    for k, v in sorted(state.get("doctrine_strengths", {}).items()):
        log.info("    %-30s: %.3f", k, v)
    log.info("")
    log.info("  Structural drift:")
    for k, v in sorted(state.get("structural_weights", state.get("structural_drift", {})).items()):
        log.info("    %-30s: %s", k, v)
    log.info("")
    log.info("  Emotion laws:")
    for cat in ["pain_rules", "anger_rules", "triumph_rules", "regret_rules"]:
        rules = state.get("emotion_laws", {}).get(cat, [])
        log.info("    %-20s: %d rules", cat, len(rules))
        if cat == "pain_rules" and rules:
            for r in rules[:3]:
                log.info("      Rule: %s", r.get("rule", "?"))
    log.info("")


def main():
    parser = argparse.ArgumentParser(description="Enriched G evolution from sigma_audits + velo_verdicts")
    parser.add_argument("--dates", help="Comma-separated YYYY-MM-DD dates")
    parser.add_argument("--all-dates", action="store_true", help="Process all dates with winner data")
    args = parser.parse_args()

    if args.all_dates:
        dates = get_dates_with_winner_data()
        log.info("Found %d dates with winner data in sigma_audits", len(dates))
    elif args.dates:
        dates = [d.strip() for d in args.dates.split(",")]
    else:
        log.error("Specify --dates or --all-dates")
        sys.exit(1)

    log.info("=" * 60)
    log.info("PLAYBOOK G ENRICHED EVOLUTION — %d dates", len(dates))
    log.info("Enrichment: sigma_audits + velo_verdicts (top_rank_horse_id + top_rank_score)")
    log.info("=" * 60)

    total_fed = 0
    total_wins = 0
    total_enriched = 0
    skipped = 0
    errors = 0

    for i, date in enumerate(dates):
        log.info("[%d/%d] Processing %s", i + 1, len(dates), date)
        result = evolve_g_for_date(date)
        if result.get("skipped"):
            skipped += 1
            log.info("  → Skipped (already done or no data)")
        elif "error" in result:
            errors += 1
            log.error("  → Error: %s", result["error"])
        else:
            total_fed += result["fed"]
            total_wins += result.get("wins", 0)
            total_enriched += result.get("enriched", 0)
            log.info("  → Fed %d races (%d enriched), %d wins",
                    result["fed"], result.get("enriched", 0), result.get("wins", 0))

    log.info("")
    log.info("=" * 60)
    log.info("ENRICHED EVOLUTION COMPLETE")
    log.info("  Dates processed: %d", len(dates))
    log.info("  Skipped (already done): %d", skipped)
    log.info("  Errors: %d", errors)
    log.info("  Total races fed to G: %d", total_fed)
    log.info("  Total enriched (with velo_verdicts): %d", total_enriched)
    log.info("  Total wins: %d", total_wins)
    log.info("=" * 60)

    # Print G state
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        engine = SentientLoopbackEngine()
        print_state_summary(engine)
    except Exception as e:
        log.warning("Could not print G state: %s", e)


if __name__ == "__main__":
    _require_legacy_override()
    main()
