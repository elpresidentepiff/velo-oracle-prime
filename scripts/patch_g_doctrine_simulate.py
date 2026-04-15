"""
Patch: G Doctrine Strength Simulation
=====================================
The enriched evolution fixed pain rules (horse IDs present) but doctrine
strengths remain frozen at 1.0 because _update_doctrine_strengths requires
doctrines_fired in the prediction dict — which sigma_audits never had.

This script simulates which doctrines should have fired for each enriched race,
then applies the EMA update directly to the doctrine strengths in state.

DOCTRINE SIMULATION RULES (reverse-engineered from race conditions):
  CHAOS_BLEED:       fires when winner_sp > 10 (market chaos signal)
  DRAW_SKEW:         fires when narrative_disruption > 65 (field distortion)
  ENGINE_SUPREMACY:  fires when correct (engine was right)
  GATEKEEPER:       fires when narrative_disruption > 70 (narrative trap)
  HOUSE_REVERSAL:    fires when winner_sp > 10 (market badly wrong)
  LAY_THE_STORY:    fires when narrative_disruption > 60 AND miss
  OVERLAY_ABSORPTION: fires when winner_sp > 8 AND miss
  PRESSURE_COLLAPSE: fires when narrative_disruption > 75 AND miss
  SARCOPHAGUS:      fires when narrative_disruption > 50 AND miss
  SHADOW_TRACKING:  fires when winner_sp > 6 AND miss
  TOP_4_ON_DANGER:  fires when winner was NOT top_rank_horse_id (danger)
  VETP_ECHO:        fires always (baseline echo)

Usage:
  PYTHONPATH=. python scripts/patch_g_doctrine_simulate.py
"""

import os
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import json, logging, urllib.request
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("patch_g_doctrine")

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_PATCH_G_DOCTRINE"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")


def _require_legacy_override() -> None:
    if os.getenv(LEGACY_EXECUTION_ENV) == "1":
        return
    raise SystemExit(
        "Legacy script is quarantined and blocked by default. "
        f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
    )


def db_get(path: str) -> list:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def _safe_float(val):
    try:
        v = float(val)
        return v if not __import__("math").isnan(v) else 0.0
    except (TypeError, ValueError):
        return 0.0


def simulate_doctrines_fired(race_data: dict, prediction: dict, actual_result: dict) -> list[str]:
    """
    Reverse-engineer which doctrines fired based on race conditions.
    Returns list of doctrine names that should have fired.
    """
    doctrines = []
    winner_sp = race_data.get("mpi", 0)  # MPI proxy is winner_sp proxy
    # Rebuild actual SP from actual_result
    winner_sp = actual_result.get("winner_profile", {}).get("sp", 0.0)
    narrative = race_data.get("narrative_disruption", 0)
    chaos = race_data.get("chaos_bloom", 0)
    winner_id = actual_result.get("winner", "")
    top_pick_id = prediction.get("power_anchor", "")
    correct = (winner_id == top_pick_id)

    miss = not correct

    # CHAOS_BLEED: high SP winner (market chaos)
    if winner_sp > 10:
        doctrines.append("CHAOS_BLEED")

    # DRAW_SKEW: narrative disruption
    if narrative > 65:
        doctrines.append("DRAW_SKEW")

    # ENGINE_SUPREMACY: engine was right
    if correct:
        doctrines.append("ENGINE_SUPREMACY")

    # GATEKEEPER: strong narrative trap
    if narrative > 70:
        doctrines.append("GATEKEEPER")

    # HOUSE_REVERSAL: market badly wrong
    if winner_sp > 10:
        doctrines.append("HOUSE_REVERSAL")

    # LAY_THE_STORY: narrative trap + miss
    if narrative > 60 and miss:
        doctrines.append("LAY_THE_STORY")

    # OVERLAY_ABSORPTION: high SP + miss
    if winner_sp > 8 and miss:
        doctrines.append("OVERLAY_ABSORPTION")

    # PRESSURE_COLLAPSE: strong narrative trap + miss
    if narrative > 75 and miss:
        doctrines.append("PRESSURE_COLLAPSE")

    # SARCOPHAGUS: narrative trap + miss
    if narrative > 50 and miss:
        doctrines.append("SARCOPHAGUS")

    # SHADOW_TRACKING: moderate-high SP + miss
    if winner_sp > 6 and miss:
        doctrines.append("SHADOW_TRACKING")

    # TOP_4_ON_DANGER: winner wasn't top pick
    if winner_id and top_pick_id and winner_id != top_pick_id:
        doctrines.append("TOP_4_ON_DANGER")

    # VETP_ECHO: always fires (baseline)
    doctrines.append("VETP_ECHO")

    return doctrines


def patch_state_doctrine_strengths(state_path: str):
    """
    Load enriched races from sigma_audits + velo_verdicts, simulate doctrine firing,
    apply EMA update to doctrine strengths, save updated state.
    """
    from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

    # Load current G state
    with open(state_path) as f:
        state = json.load(f)

    doctrine_strengths = dict(state.get("doctrine_strengths", {}))
    log.info("Starting doctrine simulation from base state: races=%d",
             state.get("total_races_observed", 0))
    log.info("Initial doctrine strengths (sample): %s",
             {k: v for k, v in list(doctrine_strengths.items())[:3]})

    # Fetch enriched races (all dates with winner data)
    sa_rows = db_get("sigma_audits?track=not.is.null&actual_winner_id=not.is.null&select=*&limit=600")
    sa_by_race = {r["race_id"]: r for r in sa_rows if r.get("race_id")}

    # Batch fetch velo_verdicts
    race_ids = list(sa_by_race.keys())
    vv_map = {}
    for i in range(0, len(race_ids), 50):
        batch = race_ids[i:i+50]
        ids_param = ",".join([f'"{rid}"' for rid in batch])
        try:
            vv_rows = db_get(f"velo_verdicts?race_id=in.({ids_param})&select=race_id,top_rank_horse_id,top_rank_score&limit={len(batch)}")
            for vv in vv_rows:
                vv_map[vv["race_id"]] = vv
        except Exception as e:
            log.warning("Batch error: %s", e)

    log.info("Fetched %d sigma_audit races, %d with velo_verdicts match", len(sa_by_race), len(vv_map))

    # Process each race
    updates = 0
    for race_id, sa in sa_by_race.items():
        vv = vv_map.get(race_id, {})
        winner_sp = _safe_float(sa.get("actual_winner_sp") or 0.0)
        winner_id = sa.get("actual_winner_id") or ""
        top_pick_id = vv.get("top_rank_horse_id") or ""
        correct = (winner_id == top_pick_id)

        # Build race_data proxy
        winner_sp_proxy = winner_sp
        if winner_sp_proxy > 10:
            mpi = 80
        elif winner_sp_proxy > 5:
            mpi = 50
        else:
            mpi = 20

        miss_reason = sa.get("miss_reason") or ""
        if miss_reason == "mid_priced_won":
            narrative = 80
        elif miss_reason == "market_decoy_followed":
            narrative = 65
        elif miss_reason in ("outsider_won", "outsider_hedge_omitted"):
            narrative = 70
        else:
            narrative = 30

        if winner_sp_proxy > 10:
            chaos = 75
        elif winner_sp_proxy > 6:
            chaos = 55
        elif winner_sp_proxy > 3:
            chaos = 35
        else:
            chaos = 20

        race_data = {
            "race_id": race_id,
            "story_anchor": top_pick_id or winner_id,
            "power_anchor": top_pick_id or winner_id,
            "mpi": mpi,
            "chaos_bloom": chaos,
            "narrative_disruption": narrative,
            "runners": [],
        }
        prediction = {
            "power_anchor": top_pick_id or winner_id,
            "confidence": _safe_float(vv.get("top_rank_score")) if vv else 0.0,
            "doctrines_fired": [],
        }
        actual_result = {
            "winner": winner_id,
            "favourite_won": correct,
            "winner_profile": {"sp": winner_sp, "miss_reason": miss_reason},
        }

        # Simulate doctrines
        doctrines_fired = simulate_doctrines_fired(race_data, prediction, actual_result)
        error_correct = 1.0 if correct else 0.0

        # Apply EMA update
        for doctrine in doctrines_fired:
            if doctrine in doctrine_strengths:
                current = doctrine_strengths[doctrine]
                doctrine_strengths[doctrine] = 0.9 * current + 0.1 * error_correct
                updates += 1

    log.info("Applied %d doctrine updates across all races", updates)

    # Update state
    state["doctrine_strengths"] = doctrine_strengths

    # Save
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    log.info("State saved to %s", state_path)

    # Print results
    log.info("")
    log.info("=" * 50)
    log.info("DOCTRINE STRENGTHS AFTER SIMULATION:")
    for k, v in sorted(doctrine_strengths.items()):
        mark = " ←" if v < 1.0 else ""
        log.info("  %-30s: %.4f%s", k, v, mark)

    # Also back up to Supabase
    try:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        payload = {
            "pattern_name": "SENTIENT_STATE_BACKUP",
            "description": f"Playbook G state after doctrine simulation: {state.get('total_races_observed')} races",
            "conditions": state,
            "occurrences": state.get("total_races_observed", 0),
            "successful_predictions": 0,
            "confidence_level": 1.0,
            "first_observed": now_naive,
            "last_observed": now_naive,
            "created_at": now_naive,
            "updated_at": now_naive,
            "is_active": True,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/learned_patterns?pattern_name=eq.SENTIENT_STATE_BACKUP",
            data=body,
            headers={
                "apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=30)
        log.info("Supabase backup updated")
    except Exception as e:
        log.warning("Supabase backup failed: %s", e)


if __name__ == "__main__":
    _require_legacy_override()
    state_path = ROOT / "data" / "sentient_state.json"
    patch_state_doctrine_strengths(str(state_path))
