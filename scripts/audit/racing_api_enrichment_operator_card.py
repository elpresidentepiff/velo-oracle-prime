
"""
Racing API Enrichment Operator Card
===================================

Identifies a race day by race_id manifest (standard or merged JSON),
not by generated_at timestamp.

SHADOW OPERATOR ENRICHMENT ONLY.
No live weighting. No staking. No betting language.
"""

from __future__ import annotations

import argparse
import os
import sys
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from src.velo.race_metadata_resolver import RaceMetadataResolver
from src.velo.racing_api_stat_adapter import RacingAPIStatAdapter

load_dotenv(ROOT / ".env")


def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def load_verdicts_by_manifest(sb, date_str: str) -> tuple[list[dict], str]:
    """Load verdicts using race_ids from standard or merged card as manifest."""
    token = date_str.replace("-", "_")
    
    # Priority 1: Standard Card
    card_path = ROOT / "data" / f"racecards_{token}_standard.json"
    if card_path.exists():
        with open(card_path) as f:
            data = json.load(f)
            # Fix: use 'racecards' key
            race_ids = [r["race_id"] for r in data.get("racecards", []) if r.get("race_id")]
            if race_ids:
                return _fetch_verdicts(sb, race_ids), f"standard_card:{card_path.name}"

    # Priority 2: Merged Cards
    merged_ids = []
    merged_files = list(ROOT.glob(f"data/racecard_merged/*_{date_str}.json"))
    for mf in merged_files:
        with open(mf) as f:
            data = json.load(f)
            for time, race in data.get("races", {}).items():
                if race.get("race_id"):
                    merged_ids.append(race["race_id"])
    
    if merged_ids:
        return _fetch_verdicts(sb, merged_ids), f"merged_cards:{len(merged_files)} files"

    return [], "FAIL_NO_RACE_ID_MANIFEST"


def _fetch_verdicts(sb, race_ids: list[str]) -> list[dict]:
    """Retrieve verdicts from Supabase for a specific list of race_ids."""
    rows = (
        sb.table("velo_verdicts")
        .select("race_id,velo_prime_prob,decision_tier,full_analysis,generated_at")
        .in_("race_id", race_ids)
        .order("velo_prime_prob", desc=True)
        .execute()
        .data
    )
    
    if not rows:
        # Fallback to local file
        from pathlib import Path
        import json
        import datetime
        date_str = datetime.datetime.now().strftime("%Y-%m-%d") # Or any hack since date_str not passed
        # Hack to find the date from race_ids might be hard, so just try matching local files
        # Alternatively, we can just search data directory for verdicts
        
        # We can just search for the latest file or pass date_str, but _fetch_verdicts doesn't have it.
        # However we know the structure of the data dir. Let's just find any matching race_ids in local verdicts
        DATA = Path(__file__).resolve().parent.parent / "data"
        for vf in DATA.glob("velo_prime_verdicts_*.json"):
            try:
                with open(vf, "r") as f:
                    local_data = json.load(f)
                    vr = local_data.get("verdicts", local_data) if isinstance(local_data, dict) else local_data
                    if isinstance(vr, list):
                        # Filter by race_ids
                        matched = [v for v in vr if v.get("race_id") in race_ids]
                        if matched:
                            rows.extend(matched)
            except Exception:
                pass

    return rows


def build_card(date_str: str) -> None:
    sb = _sb()
    verdicts, source_info = load_verdicts_by_manifest(sb, date_str)
    
    if source_info == "FAIL_NO_RACE_ID_MANIFEST":
        print(f"CARD_STATUS = FAIL_NO_RACE_ID_MANIFEST for {date_str}")
        return
        
    if not verdicts:
        print(f"No verdicts found in Supabase for manifest: {source_info}")
        return

    print(f"Loading Racing API caches...")
    adapter = RacingAPIStatAdapter.from_supabase()
    
    verdict_map: dict[str, list] = {}
    for v in verdicts:
        # Extract top horse info
        top = v.get("top") or {}
        fa = v.get("full_analysis") or []
        if not top and fa:
            if isinstance(fa, dict):
                top = (fa.get("predictions") or [{}])[0]
                fa_list = fa.get("predictions") or []
            elif isinstance(fa, list):
                top = fa[0]
                fa_list = fa
        else:
            fa_list = [top] if top else []
            
        verdict_map[v["race_id"]] = fa_list

    unique_race_ids = list(verdict_map.keys())
    resolver = RaceMetadataResolver(date=date_str, sb_client=sb)
    meta_map = resolver.resolve_batch(unique_race_ids, verdict_map)

    print(f"RACING API ENRICHMENT OPERATOR CARD — {date_str}")
    print(f"MANIFEST SOURCE: {source_info}")
    print("STATUS: SHADOW OPERATOR ENRICHMENT ONLY")
    print("=" * 60)
    
    scanned = 0
    for v in verdicts:
        scanned += 1
        predictions = verdict_map.get(v["race_id"])
        if not predictions: continue
        top = predictions[0]
        meta = meta_map.get(v["race_id"])
        
        # Build mock race dict for adapter
        race_mock = {
            "course": meta.course if meta else None,
            "distance_f": top.get("distance_f") or top.get("dist_f")
        }
        
        # Enrich top horse
        try:
            stats = adapter.enrich_runner(top, race_mock)
        except Exception as e:
            stats = {"racing_api_stat_status": f"ERROR: {e}"}
        
        vp_val = float(v.get("velo_prime_prob") or v.get("vp") or 0)
        off_time = meta.off_time if meta and meta.off_time else "??:??"
        course = meta.course if meta and meta.course else "?"
        
        raw_horse = top.get("horse") or top.get("horse_name") or "?"
        horse = meta.get_horse_name(horse_id=top.get("horse_id", ""), raw_name=raw_horse) if meta else raw_horse
        
        gen_at = v.get("generated_at", "unknown")
        
        print(f"\n{off_time} {course:<12} | {horse:<20} | VP={vp_val:.3f} | [PROV: {gen_at[:19]}]")
        
        if stats.get("racing_api_stat_status") in ("COMPLETE", "PARTIAL"):
            # Fix: handle None values
            twp = (stats.get('trainer_course_win_pct') or 0) * 100
            jwp = (stats.get('jockey_course_win_pct') or 0) * 100
            tjw = (stats.get('trainer_jockey_win_pct') or 0) * 100
            
            print(f"  Trainer @ Course: {twp:>5.1f}% ({stats.get('trainer_course_sample', 0)} runs)")
            print(f"  Jockey @ Course:  {jwp:>5.1f}% ({stats.get('jockey_course_sample', 0)} runs)")
            print(f"  Connection (T/J): {tjw:>5.1f}% ({stats.get('trainer_jockey_sample', 0)} runs)")
        else:
            reason = stats.get("racing_api_stat_status", "MISSING")
            missing = ", ".join(stats.get("missing_ids_or_fields", []))
            print(f"  ({reason} | Missing: {missing})")

    print("\n" + "-" * 60)
    print(f"Scanned {scanned} runners.")
    print("CONFIRMATION: SHADOW ONLY. No live probability mutation.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Racing API enrichment card")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    build_card(args.date)


if __name__ == "__main__":
    main()
