"""
VÉLØ — Entity Bible Populator
==============================
Backfills horse_bible, trainer_bible, jockey_bible from:
  - velo_verdicts.full_analysis (per-runner scores)
  - velo_post_race_reviews (win/place/miss outcomes)
  - runner_race_facts (trainer_id, jockey_id per runner)

Run: python scripts/populate_entity_bibles.py
Also called as Step 7 from sigma loop when run_reviews is non-empty.
"""
import os
import sys
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.bible_populator")

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_ANON_KEY", ""))


def _safe_float(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def populate_bibles(db) -> dict:
    """
    Build horse/trainer/jockey bible rows from existing velo_verdicts data.
    Returns {"horses": n, "trainers": n, "jockeys": n}.
    """
    now = datetime.now(timezone.utc).isoformat()

    # ── Load verdicts + full_analysis ────────────────────────────────────────
    log.info("Loading velo_verdicts...")
    verdict_rows = (
        db.table("velo_verdicts")
        .select("race_id, top_rank_horse_id, top_rank_score, decision_tier, "
                "confidence_level, full_analysis, velo_prime_prob, place_prob, "
                "improvement_score, market_deception_score")
        .execute()
    )
    verdicts = verdict_rows.data
    log.info("  %d verdict rows loaded", len(verdicts))

    # ── Load sigma outcomes (race_id → outcome) ───────────────────────────────
    log.info("Loading sigma_audits outcomes...")
    audit_rows = (
        db.table("sigma_audits")
        .select("race_id, horse_id, outcome, decision_tier")
        .execute()
    )
    # horse outcome map: horse_id → list of outcomes
    horse_outcomes: dict = defaultdict(list)
    for a in audit_rows.data:
        if a.get("horse_id") and a.get("outcome"):
            horse_outcomes[a["horse_id"]].append(a["outcome"])

    # ── Load runner_race_facts for trainer/jockey mapping ────────────────────
    log.info("Loading runner_race_facts...")
    rrf_rows = (
        db.table("runner_race_facts")
        .select("race_id, horse_id, trainer_id, jockey_id")
        .execute()
    )
    # Map (race_id, horse_id) → {trainer_id, jockey_id}
    runner_map: dict = {}
    for r in rrf_rows.data:
        key = (r.get("race_id"), r.get("horse_id"))
        runner_map[key] = r
    log.info("  %d runner_race_facts loaded", len(runner_map))

    # Load name lookups from profiles tables
    tr_names: dict = {}
    jk_names: dict = {}
    h_names:  dict = {}
    try:
        for row in db.table("trainer_profiles").select("id, name").execute().data:
            tr_names[row["id"]] = row.get("name", "")
        for row in db.table("jockey_profiles").select("id, name").execute().data:
            jk_names[row["id"]] = row.get("name", "")
        for row in db.table("horse_profiles").select("id, name").execute().data:
            h_names[row["id"]] = row.get("name", "")
        log.info("  %d trainer / %d jockey / %d horse names loaded",
                 len(tr_names), len(jk_names), len(h_names))
    except Exception as e:
        log.warning("Profile name lookup failed (non-fatal): %s", e)

    # ── Accumulators ─────────────────────────────────────────────────────────
    horse_acc:   dict = defaultdict(lambda: {
        "name": None, "runs": 0, "top_picks": 0,
        "velo_probs": [], "place_probs": [], "improvement": [], "mkt_deception": [],
        "tiers": defaultdict(int), "last_date": None, "last_result": None,
    })
    trainer_acc: dict = defaultdict(lambda: {
        "name": None, "horses": set(), "top_picks": 0,
        "velo_probs": [], "last_date": None,
    })
    jockey_acc:  dict = defaultdict(lambda: {
        "name": None, "mounts": 0, "top_picks": 0,
        "velo_probs": [], "last_date": None,
    })

    for v in verdicts:
        race_id  = v.get("race_id", "")
        top_id   = v.get("top_rank_horse_id", "")
        tier     = v.get("decision_tier") or "?"
        full     = v.get("full_analysis") or []

        # full_analysis is stored as JSON array of runner score dicts
        if isinstance(full, str):
            try:
                full = json.loads(full)
            except Exception:
                full = []

        for runner in full:
            if isinstance(runner, str):
                try:
                    runner = json.loads(runner)
                except Exception:
                    continue
            if not isinstance(runner, dict):
                continue
            horse_id   = runner.get("horse_id") or runner.get("horse", "")
            horse_name = runner.get("horse", "")
            vp  = _safe_float(runner.get("velo_prime_prob"))
            pp  = _safe_float(runner.get("place_prob"))
            imp = _safe_float(runner.get("improvement_score"))
            mkt = _safe_float(runner.get("market_deception_score"))

            if not horse_id:
                continue

            ha = horse_acc[horse_id]
            ha["name"] = horse_name or ha["name"] or h_names.get(horse_id, "")
            ha["runs"] += 1
            if vp is not None: ha["velo_probs"].append(vp)
            if pp is not None: ha["place_probs"].append(pp)
            if imp is not None: ha["improvement"].append(imp)
            if mkt is not None: ha["mkt_deception"].append(mkt)

            if horse_id == top_id:
                ha["top_picks"] += 1
                ha["tiers"][tier] += 1
                ha["last_date"] = race_id  # use race_id as proxy; replace with date if available

            # Trainer / jockey lookup
            rrf = runner_map.get((race_id, horse_id))
            if rrf:
                tr_id   = rrf.get("trainer_id") or ""
                jk_id   = rrf.get("jockey_id") or ""

                if tr_id:
                    ta = trainer_acc[tr_id]
                    ta["name"] = ta["name"] or tr_names.get(tr_id, "")
                    ta["horses"].add(horse_id)
                    if horse_id == top_id:
                        ta["top_picks"] += 1
                        if vp is not None: ta["velo_probs"].append(vp)
                        ta["last_date"] = race_id

                if jk_id:
                    ja = jockey_acc[jk_id]
                    ja["name"] = ja["name"] or jk_names.get(jk_id, "")
                    ja["mounts"] += 1
                    if horse_id == top_id:
                        ja["top_picks"] += 1
                        if vp is not None: ja["velo_probs"].append(vp)
                        ja["last_date"] = race_id

    # ── Write horse_bible ─────────────────────────────────────────────────────
    log.info("Writing horse_bible (%d horses)...", len(horse_acc))
    h_written = 0
    for horse_id, ha in horse_acc.items():
        outcomes   = horse_outcomes.get(horse_id, [])
        wins       = outcomes.count("WIN")
        placed     = outcomes.count("PLACED")
        top_n      = ha["top_picks"]
        strike     = round(wins / top_n, 4) if top_n else None
        best_tier  = max(ha["tiers"], key=ha["tiers"].get) if ha["tiers"] else None
        last_res   = outcomes[-1] if outcomes else None

        db.table("horse_bible").upsert({
            "horse_id":                    horse_id,
            "horse_name":                  ha["name"],
            "runs_scored":                 ha["runs"],
            "top_pick_count":              top_n,
            "top_pick_wins":               wins,
            "top_pick_placed":             placed,
            "top_pick_strike_rate":        strike,
            "avg_velo_prime_prob":         _avg(ha["velo_probs"]),
            "avg_place_prob":              _avg(ha["place_probs"]),
            "avg_improvement_score":       _avg(ha["improvement"]),
            "avg_market_deception_score":  _avg(ha["mkt_deception"]),
            "best_decision_tier":          best_tier,
            "tier_distribution":           dict(ha["tiers"]),
            "last_result":                 last_res,
            "updated_at":                  now,
        }, on_conflict="horse_id").execute()
        h_written += 1

    log.info("  horse_bible: %d rows", h_written)

    # ── Write trainer_bible ───────────────────────────────────────────────────
    log.info("Writing trainer_bible (%d trainers)...", len(trainer_acc))
    t_written = 0
    for tr_id, ta in trainer_acc.items():
        if not tr_id:
            continue
        top_n = ta["top_picks"]
        db.table("trainer_bible").upsert({
            "trainer_id":          tr_id,
            "trainer_name":        ta["name"],
            "horses_scored":       len(ta["horses"]),
            "top_pick_count":      top_n,
            "avg_velo_prime_prob": _avg(ta["velo_probs"]),
            "updated_at":          now,
        }, on_conflict="trainer_id").execute()
        t_written += 1

    log.info("  trainer_bible: %d rows", t_written)

    # ── Write jockey_bible ────────────────────────────────────────────────────
    log.info("Writing jockey_bible (%d jockeys)...", len(jockey_acc))
    j_written = 0
    for jk_id, ja in jockey_acc.items():
        if not jk_id:
            continue
        db.table("jockey_bible").upsert({
            "jockey_id":           jk_id,
            "jockey_name":         ja["name"],
            "mounts_scored":       ja["mounts"],
            "top_pick_count":      ja["top_picks"],
            "avg_velo_prime_prob": _avg(ja["velo_probs"]),
            "updated_at":          now,
        }, on_conflict="jockey_id").execute()
        j_written += 1

    log.info("  jockey_bible: %d rows", j_written)

    return {"horses": h_written, "trainers": t_written, "jockeys": j_written}


def main():
    if not SUPA_URL or not SUPA_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    from supabase import create_client
    db = create_client(SUPA_URL, SUPA_KEY)
    log.info("=== VÉLØ Entity Bible Populator ===")
    counts = populate_bibles(db)
    log.info("Done: horses=%d trainers=%d jockeys=%d",
             counts["horses"], counts["trainers"], counts["jockeys"])


if __name__ == "__main__":
    main()
