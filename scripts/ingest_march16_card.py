"""
Ingest 2026-03-16 full racecard into Supabase races + runners tables.
Reads the cached Racing API JSON file from the Claude tool-results directory.
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY", "")
)

CARD_FILE = Path(
    r"C:\Users\puror\.claude\projects\C--Users-puror-velo-oracle-prime"
    r"\23cfd82a-1206-4945-8e5c-6558e66c0e10\tool-results"
    r"\mcp-the-racing-api-get_racecards_standard-1773610255103.txt"
)

TARGET_DATE = "2026-03-16"


def parse_prize(prize_str: str) -> int:
    """'£3,248' -> 3248"""
    try:
        return int(re.sub(r"[^\d]", "", str(prize_str or "0")) or 0)
    except ValueError:
        return 0


def parse_time(off_time: str) -> str:
    """'2:30' -> '14:30:00'  (all UK races, off_time is local, assume afternoon)"""
    if not off_time:
        return None
    parts = off_time.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        # Racing times before 10 are always PM in the UK for afternoon cards
        if h < 10:
            h += 12
        return f"{h:02d}:{m:02d}:00"
    except ValueError:
        return None


def safe_int(val) -> int:
    try:
        v = float(str(val).strip() or "0")
        return int(v)
    except (ValueError, TypeError):
        return 0


def best_odds(runner: dict) -> float:
    """Return lowest decimal odds (= most favoured) across all bookmakers."""
    decimals = []
    for o in runner.get("odds", []):
        try:
            v = float(o.get("decimal", 0) or 0)
            if v > 1.0:
                decimals.append(v)
        except (TypeError, ValueError):
            pass
    return min(decimals) if decimals else 10.0


def sp_rank(runners_in_race: list, horse_id: str) -> int:
    ranked = sorted(runners_in_race, key=lambda r: best_odds(r))
    for idx, r in enumerate(ranked, 1):
        if r.get("horse_id") == horse_id:
            return idx
    return len(runners_in_race)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set")
        sys.exit(1)

    if not CARD_FILE.exists():
        print(f"ERROR: Card file not found: {CARD_FILE}")
        sys.exit(1)

    print(f"Reading card file ({CARD_FILE.stat().st_size / 1024:.0f} KB)...")
    with open(CARD_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    racecards = data.get("racecards", [])
    target_races = [r for r in racecards if r.get("date") == TARGET_DATE]
    print(f"Found {len(target_races)} races for {TARGET_DATE}")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Check what's already loaded
    existing = sb.table("races").select("race_id").eq("date", TARGET_DATE).execute()
    existing_ids = {r["race_id"] for r in (existing.data or [])}
    print(f"Already in DB: {len(existing_ids)} races")

    races_inserted = 0
    runners_inserted = 0

    for rc in target_races:
        race_id = rc["race_id"]
        runners_in_race = rc.get("runners", [])
        field_size = len(runners_in_race)

        # ── Insert race ──────────────────────────────────────────────────────
        # Store enriched data + full raw blob
        race_row = {
            "race_id": race_id,
            "course": rc.get("course", ""),
            "date": rc.get("date"),
            "time": parse_time(rc.get("off_time", "")),
            "race_type": rc.get("type", ""),
            "distance_f": safe_int(rc.get("distance_f", 0)),
            "going": rc.get("going", ""),
            "class": rc.get("race_class", ""),
            "prize_money": parse_prize(rc.get("prize", "0")),
            "runners_count": field_size,
            "race_name": rc.get("race_name", ""),
            "join_key": f"{rc.get('course', '')}_{rc.get('date')}_{rc.get('off_time', '')}",
            "raw": {
                "course_id": rc.get("course_id"),
                "off_time": rc.get("off_time"),
                "off_dt": rc.get("off_dt"),
                "distance_round": rc.get("distance_round"),
                "distance": rc.get("distance"),
                "region": rc.get("region"),
                "pattern": rc.get("pattern"),
                "sex_restriction": rc.get("sex_restriction"),
                "age_band": rc.get("age_band"),
                "rating_band": rc.get("rating_band"),
                "surface": rc.get("surface"),
                "jumps": rc.get("jumps"),
                "going_detailed": rc.get("going_detailed"),
            },
        }

        try:
            if race_id in existing_ids:
                sb.table("races").update(race_row).eq("race_id", race_id).execute()
                action = "updated"
            else:
                sb.table("races").insert(race_row).execute()
                action = "inserted"
                races_inserted += 1
        except Exception as e:
            print(f"  ⚠️  Race {race_id} failed: {e}")
            continue

        # ── Insert runners ───────────────────────────────────────────────────
        # Remove any existing runners for this race to avoid duplicates on re-run
        sb.table("runners").delete().eq("race_id", race_id).execute()

        for runner in runners_in_race:
            horse_id = runner.get("horse_id", "")
            odds_dec = best_odds(runner)
            rank = sp_rank(runners_in_race, horse_id)

            runner_row = {
                "race_id": race_id,
                "horse_id": horse_id,
                "horse_name": runner.get("horse", ""),
                "draw": safe_int(runner.get("draw", 0)),
                "weight": runner.get("lbs", ""),
                "or_rating": safe_int(runner.get("ofr", 0)),
                "ts_rating": safe_int(runner.get("ts", 0)),
                "rpr": safe_int(runner.get("rpr", 0)),
                "trainer": runner.get("trainer", ""),
                "trainer_id": runner.get("trainer_id", ""),
                "jockey": runner.get("jockey", ""),
                "jockey_id": runner.get("jockey_id", ""),
                "age": safe_int(runner.get("age", 0)),
                "sex": runner.get("sex", ""),
                "headgear": runner.get("headgear", ""),
                "sire": runner.get("sire", ""),
                "sire_id": runner.get("sire_id", ""),
                "dam": runner.get("dam", ""),
                "dam_id": runner.get("dam_id", ""),
                "damsire": runner.get("damsire", ""),
                "damsire_id": runner.get("damsire_id", ""),
                "owner": runner.get("owner", ""),
                "owner_id": runner.get("owner_id", ""),
                "cloth_no": runner.get("number", ""),
                "form": runner.get("form", ""),
                "raw": {
                    "colour": runner.get("colour"),
                    "region": runner.get("region"),
                    "last_run": runner.get("last_run"),
                    "trainer_rtf": runner.get("trainer_rtf"),
                    "trainer_14_days": runner.get("trainer_14_days"),
                    "comment": runner.get("comment"),
                    "spotlight": runner.get("spotlight"),
                    "past_results_flags": runner.get("past_results_flags"),
                    "odds": odds_dec,
                    "sp_rank": rank,
                    "is_fav": 1 if rank == 1 else 0,
                    "quotes": runner.get("quotes", []),
                },
            }

            try:
                sb.table("runners").insert(runner_row).execute()
                runners_inserted += 1
            except Exception as e:
                print(f"    ⚠️  {runner.get('horse')} failed: {e}")

        print(
            f"  OK [{action}] {rc.get('course')} {rc.get('off_time')} "
            f"- {race_id} ({field_size} runners)"
        )

    print()
    print("=" * 60)
    print(f"Races inserted/updated : {races_inserted + len(existing_ids)}")
    print(f"Runners inserted       : {runners_inserted}")
    print("=" * 60)
    print(f"DONE - VELO is loaded for {TARGET_DATE}. Awaiting results.")


if __name__ == "__main__":
    main()
