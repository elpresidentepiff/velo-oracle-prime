"""
VELO Verdict Generator
Runs the 5-agent Orchestrator on every race for a given date
and writes one velo_verdicts row per race.

Usage:
    python scripts/generate_verdicts.py --date 2026-03-16
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY", "")
)

logging.basicConfig(
    level=logging.WARNING,          # suppress agent debug spam
    format="%(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("velo.verdicts")
log.setLevel(logging.INFO)

ENGINE_VERSION = "v10.0-agent"
DOCTRINE_VERSION = "v17"
FEATURE_SCHEMA = "v17"


def load_races_for_date(sb, date_str: str) -> list:
    """Return list of (race_row, runners_list) for the given date."""
    races_resp = sb.table("races").select("*").eq("date", date_str).order("time").execute()
    races = races_resp.data or []
    if not races:
        log.warning("No races found for %s", date_str)
        return []

    results = []
    for race in races:
        rid = race["race_id"]
        runners_resp = (
            sb.table("runners").select("*").eq("race_id", rid).execute()
        )
        runners = runners_resp.data or []
        results.append((race, runners))

    log.info("Loaded %d races for %s", len(results), date_str)
    return results


def build_race_data(race: dict, runners: list) -> dict:
    """Convert DB rows into the dict format expected by Orchestrator."""
    raw_race = race.get("raw") or {}

    runner_list = []
    for r in runners:
        raw_r = r.get("raw") or {}
        runner_list.append({
            "horse_id":   r.get("horse_id", ""),
            "horse_name": r.get("horse_name", ""),
            "cloth_no":   r.get("cloth_no", ""),
            "trainer":    r.get("trainer", ""),
            "trainer_id": r.get("trainer_id", ""),
            "jockey":     r.get("jockey", ""),
            "jockey_id":  r.get("jockey_id", ""),
            "form":       r.get("form", ""),
            "or_rating":  r.get("or_rating"),
            "rpr":        r.get("rpr"),
            "ts":         r.get("ts_rating"),
            "age":        r.get("age"),
            "weight":     r.get("weight", ""),
            "draw":       r.get("draw"),
            "sire":       r.get("sire", ""),
            "dam":        r.get("dam", ""),
            "owner":      r.get("owner", ""),
            # odds stored in raw blob
            "odds":       raw_r.get("odds"),
            "sp_rank":    raw_r.get("sp_rank"),
            "is_fav":     raw_r.get("is_fav", 0),
            "comment":    raw_r.get("comment", ""),
            "spotlight":  raw_r.get("spotlight", ""),
            "trainer_14_days": raw_r.get("trainer_14_days", {}),
            "past_results_flags": raw_r.get("past_results_flags", []),
        })

    return {
        "race_id":   race["race_id"],
        "course":    race.get("course", ""),
        "date":      str(race.get("date", "")),
        "off_time":  str(race.get("time", "")),
        "race_name": race.get("race_name", ""),
        "distance":  raw_race.get("distance", ""),
        "distance_f": race.get("distance_f"),
        "going":     race.get("going", ""),
        "race_type": race.get("race_type", ""),
        "class":     race.get("class", ""),
        "surface":   raw_race.get("surface", "Turf"),
        "runners":   runner_list,
    }


def classify_confidence(top_score: float, back_count: int) -> str:
    if top_score >= 70 and back_count >= 1:
        return "HIGH"
    if top_score >= 55:
        return "MEDIUM"
    return "LOW"


def build_velo_verdict_row(race_data: dict, verdicts: list, latency_ms: int) -> dict:
    """Map Orchestrator output to one velo_verdicts row."""
    # Map horse_name -> horse_id for lookup
    name_to_id = {r["horse_name"]: r["horse_id"] for r in race_data["runners"]}

    selections = []
    quarantines = []
    full_analysis = []

    for v in verdicts:
        entry = {
            "horse_name": v.horse_name,
            "horse_id": name_to_id.get(v.horse_name, ""),
            "final_score": round(v.final_score, 2),
            "action": v.action,
            "stake_pct": v.stake_pct,
            "reason": v.reason,
            "agent_scores": v.agent_scores,
        }
        full_analysis.append(entry)

        if v.action == "BACK":
            selections.append({
                "horse_name": v.horse_name,
                "horse_id": name_to_id.get(v.horse_name, ""),
                "score": round(v.final_score, 2),
                "stake_pct": v.stake_pct,
                "reason": v.reason,
            })
        elif v.action == "LAY":
            quarantines.append({
                "horse_name": v.horse_name,
                "horse_id": name_to_id.get(v.horse_name, ""),
                "score": round(v.final_score, 2),
                "reason": v.reason,
            })

    # Top-ranked horse by final score
    top = max(verdicts, key=lambda v: v.final_score)
    top_horse_id = name_to_id.get(top.horse_name, top.horse_name)
    back_count = len(selections)
    confidence = classify_confidence(top.final_score, back_count)

    return {
        "race_id": race_data["race_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "doctrine_version": DOCTRINE_VERSION,
        "feature_schema_version": FEATURE_SCHEMA,
        "environment": "local",
        "generation_latency_ms": latency_ms,
        "selections": selections,
        "quarantines": quarantines,
        "full_analysis": full_analysis,
        "top_rank_horse_id": top_horse_id,
        "top_rank_score": round(top.final_score, 4),
        "confidence_level": confidence,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate VELO verdicts for a race date")
    parser.add_argument("--date", default="2026-03-16", help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Print verdicts without saving")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE credentials missing")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    from app.engine.orchestrator import Orchestrator
    orch = Orchestrator(SUPABASE_URL, SUPABASE_KEY)

    # Suppress Orchestrator's own DB writes (race_verdicts table may not exist)
    orch.client = None  # disable internal saves — we write to velo_verdicts ourselves

    races = load_races_for_date(sb, args.date)
    if not races:
        print(f"No races loaded for {args.date}. Exiting.")
        sys.exit(0)

    print(f"\nGenerating verdicts for {len(races)} races on {args.date}")
    print("=" * 60)

    backs_total = 0
    lays_total = 0
    high_conf = 0

    for race, runners in races:
        race_data = build_race_data(race, runners)
        course = race_data["course"]
        off_time = race_data["off_time"][:5] if race_data["off_time"] else "?"
        field_size = len(runners)

        t0 = time.time()
        try:
            verdicts = orch.analyze_race(race_data)
        except Exception as e:
            print(f"  ERROR {course} {off_time}: {e}")
            continue
        latency_ms = int((time.time() - t0) * 1000)

        verdict_row = build_velo_verdict_row(race_data, verdicts, latency_ms)

        backs = verdict_row["selections"]
        lays = verdict_row["quarantines"]
        backs_total += len(backs)
        lays_total += len(lays)
        if verdict_row["confidence_level"] == "HIGH":
            high_conf += 1

        # Print race summary
        top_name = next(
            (v.horse_name for v in verdicts if name_to_id_match(v.horse_name, verdict_row["top_rank_horse_id"], race_data)),
            verdict_row["top_rank_horse_id"]
        )
        print(
            f"  {course} {off_time} ({field_size}r) | "
            f"TOP: {top_name} [{verdict_row['top_rank_score']:.1f}] | "
            f"BACK:{len(backs)} LAY:{len(lays)} | "
            f"conf={verdict_row['confidence_level']} | {latency_ms}ms"
        )
        if backs:
            for b in backs:
                print(f"    >> BACK {b['horse_name']} @ {b['stake_pct']}% — {b['reason']}")

        if not args.dry_run:
            try:
                sb.table("velo_verdicts").upsert(
                    verdict_row, on_conflict="race_id"
                ).execute()
            except Exception as e:
                # upsert may fail if no unique constraint — try insert
                try:
                    # delete existing then insert
                    sb.table("velo_verdicts").delete().eq("race_id", race_data["race_id"]).execute()
                    sb.table("velo_verdicts").insert(verdict_row).execute()
                except Exception as e2:
                    print(f"    SAVE ERROR: {e2}")

    print()
    print("=" * 60)
    print(f"  Races processed : {len(races)}")
    print(f"  BACK selections : {backs_total}")
    print(f"  LAY selections  : {lays_total}")
    print(f"  HIGH confidence : {high_conf}")
    if not args.dry_run:
        print(f"  Written to      : velo_verdicts")
    print("=" * 60)
    print(f"DONE — VELO verdicts for {args.date} generated.")


def name_to_id_match(horse_name: str, horse_id: str, race_data: dict) -> bool:
    """True if this verdict is for the horse with given ID."""
    for r in race_data["runners"]:
        if r["horse_name"] == horse_name and r["horse_id"] == horse_id:
            return True
    return False


if __name__ == "__main__":
    main()
