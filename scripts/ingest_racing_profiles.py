"""
ingest_racing_profiles.py
--------------------------
Pulls jockeys, trainers, horses, and owners from The Racing API results history
and upserts everything into Supabase.

Standard plan endpoints used:
  GET /results?start_date=&end_date=&limit=&skip=
  GET /racecards/standard          (today's cards — runners + form)
  GET /courses                     (all courses)

Rate limit: 1 req/sec (free) or 5 req/sec (standard).
Script defaults to 1 req/sec to be safe. Override with --rate 5.

Usage:
  python scripts/ingest_racing_profiles.py --days 90
  python scripts/ingest_racing_profiles.py --days 180 --rate 5
  python scripts/ingest_racing_profiles.py --today-cards
"""

import argparse
import json
import logging
import os
import sys
import time
from base64 import b64encode
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Credentials ────────────────────────────────────────────────────────────────

RACING_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
RACING_USER = os.getenv("RACING_API_USERNAME", "cHHxKCt4ePK3TpFrWNq3sax6")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "D2Zlg9VcD4Sjbjcb7pMzpwwy")

SB_URL = os.getenv("SUPABASE_URL", "https://ltbsxbvfsxtnharjvqcm.supabase.co")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ4ODM2OSwiZXhwIjoyMDc5MDY0MzY5fQ.MmQiC3kt6UJ0e2BQ6k32oWbSNbWmv2U0G9E6l6k2C18")

# ── Racing API helpers ──────────────────────────────────────────────────────────

_auth = "Basic " + b64encode(f"{RACING_USER}:{RACING_PASS}".encode()).decode()


def _racing_get(path: str, params: dict | None = None) -> dict:
    url = f"{RACING_BASE}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={
        "Authorization": _auth,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    })
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        log.error("Racing API HTTP %s on %s — %s", e.code, url, body[:200])
        if e.code == 429:
            log.warning("Rate limited — sleeping 10s")
            time.sleep(10)
        return {"error": e.code, "detail": body}
    except URLError as e:
        log.error("Network error: %s", e.reason)
        return {"error": "network", "detail": str(e.reason)}


# ── Supabase helpers ────────────────────────────────────────────────────────────

_sb_headers = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def _sb_upsert(table: str, rows: list[dict]) -> bool:
    if not rows:
        return True
    url = f"{SB_URL}/rest/v1/{table}"
    payload = json.dumps(rows).encode()
    req = Request(url, data=payload, headers=_sb_headers, method="POST")
    try:
        with urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except HTTPError as e:
        log.error("Supabase upsert failed on %s: %s — %s", table, e.code, e.read().decode()[:300])
        return False
    except URLError as e:
        log.error("Supabase network error: %s", e.reason)
        return False


def _sb_delete_today_runners(today_str: str):
    """Remove today's runner rows before re-inserting to avoid unique constraint errors."""
    # First get today's race_ids
    url = f"{SB_URL}/rest/v1/racing_today_cards?select=race_id&date=eq.{today_str}"
    req = Request(url, headers={**_sb_headers, "Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=30) as r:
            cards = json.loads(r.read().decode())
        race_ids = [c["race_id"] for c in cards]
        if not race_ids:
            return
        race_ids_str = ",".join(race_ids)
        del_url = f"{SB_URL}/rest/v1/racing_today_runners?race_id=in.({race_ids_str})"
        del_req = Request(del_url, headers=_sb_headers, method="DELETE")
        with urlopen(del_req, timeout=30):
            pass
    except Exception as e:
        log.warning("Could not clear today's runners: %s", e)


def _sb_upsert_batch(table: str, rows: list[dict], batch_size: int = 500) -> int:
    written = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        if _sb_upsert(table, chunk):
            written += len(chunk)
        else:
            log.error("Batch %d failed for %s", i // batch_size, table)
    return written


# ── Main ingestion logic ────────────────────────────────────────────────────────

def fetch_results_range(start: date, end: date, rate: float = 1.0) -> list[dict]:
    """Pull all results between start and end dates, respecting rate limit."""
    all_results = []
    limit = 50
    skip = 0
    delay = 1.0 / rate

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    log.info("Fetching results %s → %s", start_str, end_str)

    while True:
        data = _racing_get("results", {
            "start_date": start_str,
            "end_date": end_str,
            "limit": limit,
            "skip": skip,
        })
        time.sleep(delay)

        if "error" in data:
            log.error("Stopping results fetch — error: %s", data)
            break

        batch = data.get("results", [])
        total = data.get("total", 0)

        if not batch:
            break

        all_results.extend(batch)
        skip += len(batch)
        log.info("  Fetched %d / %d results", len(all_results), total)

        if skip >= total:
            break

    return all_results


def extract_profiles(results: list[dict]) -> tuple[dict, dict, dict, dict]:
    """Extract unique jockeys, trainers, horses, owners from results."""
    jockeys: dict[str, dict] = {}
    trainers: dict[str, dict] = {}
    horses: dict[str, dict] = {}
    owners: dict[str, dict] = {}

    for race in results:
        race_meta = {
            "course": race.get("course", ""),
            "region": race.get("region", ""),
            "date": race.get("date", ""),
            "type": race.get("type", ""),
            "going": race.get("going", ""),
            "distance": race.get("dist", ""),
        }

        for r in race.get("runners", []):
            pos = r.get("position", "")
            is_win = pos == "1"
            is_placed = pos in ("1", "2", "3")

            # Jockey
            jid = r.get("jockey_id", "")
            jname = r.get("jockey", "")
            if jid and jid not in ("", "jky_0"):
                if jid not in jockeys:
                    jockeys[jid] = {
                        "id": jid,
                        "name": jname,
                        "runs": 0, "wins": 0, "places": 0,
                        "regions": set(),
                        "courses": set(),
                        "last_seen": "",
                    }
                j = jockeys[jid]
                j["runs"] += 1
                if is_win: j["wins"] += 1
                if is_placed: j["places"] += 1
                j["regions"].add(race_meta["region"])
                j["courses"].add(race_meta["course"])
                if race_meta["date"] > j["last_seen"]:
                    j["last_seen"] = race_meta["date"]

            # Trainer
            tid = r.get("trainer_id", "")
            tname = r.get("trainer", "")
            if tid and tid not in ("", "trn_0"):
                if tid not in trainers:
                    trainers[tid] = {
                        "id": tid,
                        "name": tname,
                        "runs": 0, "wins": 0, "places": 0,
                        "regions": set(),
                        "courses": set(),
                        "last_seen": "",
                    }
                t = trainers[tid]
                t["runs"] += 1
                if is_win: t["wins"] += 1
                if is_placed: t["places"] += 1
                t["regions"].add(race_meta["region"])
                t["courses"].add(race_meta["course"])
                if race_meta["date"] > t["last_seen"]:
                    t["last_seen"] = race_meta["date"]

            # Horse
            hid = r.get("horse_id", "")
            hname = r.get("horse", "")
            if hid:
                if hid not in horses:
                    horses[hid] = {
                        "id": hid,
                        "name": hname,
                        "age": r.get("age", ""),
                        "sex": r.get("sex", ""),
                        "sire": r.get("sire", ""),
                        "sire_id": r.get("sire_id", ""),
                        "dam": r.get("dam", ""),
                        "dam_id": r.get("dam_id", ""),
                        "trainer_id": tid,
                        "trainer": tname,
                        "runs": 0, "wins": 0, "places": 0,
                        "last_seen": "",
                        "last_or": None,
                        "last_rpr": None,
                    }
                h = horses[hid]
                h["runs"] += 1
                if is_win: h["wins"] += 1
                if is_placed: h["places"] += 1
                if race_meta["date"] > h.get("last_seen", ""):
                    h["last_seen"] = race_meta["date"]
                    h["trainer_id"] = tid
                    h["trainer"] = tname
                    or_val = r.get("or", "")
                    rpr_val = r.get("rpr", "")
                    if or_val and or_val not in ("–", ""):
                        try: h["last_or"] = int(or_val)
                        except: pass
                    if rpr_val and rpr_val not in ("–", ""):
                        try: h["last_rpr"] = int(rpr_val)
                        except: pass

            # Owner
            oid = r.get("owner_id", "")
            oname = r.get("owner", "")
            if oid:
                if oid not in owners:
                    owners[oid] = {"id": oid, "name": oname, "runs": 0, "wins": 0}
                owners[oid]["runs"] += 1
                if is_win: owners[oid]["wins"] += 1

    return jockeys, trainers, horses, owners


def extract_horse_runs(results: list[dict]) -> list[dict]:
    """Extract one row per horse per race from results — the raw run ledger."""
    rows = []
    for race in results:
        race_date = race.get("date", "")
        course = race.get("course", "")
        course_id = race.get("course_id", "")
        region = race.get("region", "")
        race_name = race.get("race_name", "")
        race_type = race.get("type", "")
        distance = race.get("dist", "")
        distance_f = race.get("dist_f", "") or race.get("distance_f", "")
        going = race.get("going", "")
        race_class = race.get("class", "") or race.get("race_class", "")
        pattern = race.get("pattern", "")
        race_id = race.get("race_id", "")

        for r in race.get("runners", []):
            hid = r.get("horse_id", "")
            if not hid:
                continue

            pos_raw = str(r.get("position", "")).strip()
            pos_int = None
            try:
                pos_int = int(pos_raw)
            except (ValueError, TypeError):
                pass

            def _int_field(val):
                if val is None: return None
                s = str(val).strip()
                if s in ("", "–", "-", "N/A"): return None
                try: return int(float(s))
                except: return None

            def _float_field(val):
                if val is None: return None
                s = str(val).strip()
                if s in ("", "–", "-", "N/A"): return None
                try: return float(s)
                except: return None

            try:
                dist_f_val = float(str(distance_f).replace("f","").strip()) if distance_f else None
            except:
                dist_f_val = None

            rows.append({
                "horse_id":      hid,
                "horse":         r.get("horse", ""),
                "race_id":       race_id,
                "run_date":      race_date,
                "course":        course,
                "course_id":     course_id,
                "region":        region,
                "race_name":     race_name,
                "race_type":     race_type,
                "distance":      distance,
                "distance_f":    dist_f_val,
                "going":         going,
                "race_class":    race_class,
                "pattern":       pattern,
                "position":      pos_raw if pos_raw else None,
                "position_int":  pos_int,
                "official_rating": _int_field(r.get("or")),
                "rpr":           _int_field(r.get("rpr")),
                "tsr":           _int_field(r.get("tsr")),
                "sp":            r.get("sp", "") or None,
                "sp_dec":        _float_field(r.get("sp_dec")),
                "btn":           _float_field(r.get("btn")),
                "weight":        r.get("weight", "") or None,
                "weight_lbs":    _int_field(r.get("weight_lbs")),
                "headgear":      r.get("headgear", "") or None,
                "jockey_id":     r.get("jockey_id", "") or None,
                "jockey":        r.get("jockey", "") or None,
                "trainer_id":    r.get("trainer_id", "") or None,
                "trainer":       r.get("trainer", "") or None,
                "owner_id":      r.get("owner_id", "") or None,
                "owner":         r.get("owner", "") or None,
                "prize":         _float_field(r.get("prize")),
            })
    return rows


def _serialise(d: dict) -> dict:
    """Convert sets to sorted lists for JSON serialisation."""
    out = {}
    for k, v in d.items():
        if isinstance(v, set):
            out[k] = sorted(v)
        else:
            out[k] = v
    return out


def ingest_courses(rate: float = 1.0):
    log.info("Fetching all courses...")
    data = _racing_get("courses")
    time.sleep(1.0 / rate)
    courses = data.get("courses", [])
    if not courses:
        log.warning("No courses returned")
        return

    rows = [
        {
            "id": c["id"],
            "name": c["course"],
            "region_code": c.get("region_code", ""),
            "region": c.get("region", ""),
        }
        for c in courses
    ]
    written = _sb_upsert_batch("racing_courses", rows)
    log.info("Courses: %d upserted", written)


def ingest_today_cards(rate: float = 1.0):
    log.info("Fetching today's standard racecards...")
    data = _racing_get("racecards/standard")
    time.sleep(1.0 / rate)
    cards = data.get("racecards", [])
    if not cards:
        log.warning("No racecards returned")
        return

    race_rows = []
    runner_rows = []

    for race in cards:
        race_rows.append({
            "race_id": race["race_id"],
            "date": race.get("date", ""),
            "course": race.get("course", ""),
            "course_id": race.get("course_id", ""),
            "off_time": race.get("off_time", ""),
            "off_dt": race.get("off_dt", ""),
            "race_name": race.get("race_name", ""),
            "distance": race.get("distance", ""),
            "race_class": race.get("race_class", ""),
            "type": race.get("type", ""),
            "going": race.get("going", ""),
            "region": race.get("region", ""),
            "pattern": race.get("pattern", ""),
            "age_band": race.get("age_band", ""),
            "sex_restriction": race.get("sex_restriction", ""),
            "field_size": len(race.get("runners", [])),
        })

        for r in race.get("runners", []):
            runner_rows.append({
                "race_id": race["race_id"],
                "horse_id": r.get("horse_id", ""),
                "horse": r.get("horse", ""),
                "number": r.get("number"),
                "draw": r.get("draw"),
                "age": r.get("age", ""),
                "sex": r.get("sex", ""),
                "weight": r.get("weight", ""),
                "headgear": r.get("headgear", ""),
                "jockey_id": r.get("jockey_id", ""),
                "jockey": r.get("jockey", ""),
                "jockey_claim": r.get("jockey_claim_lbs"),
                "trainer_id": r.get("trainer_id", ""),
                "trainer": r.get("trainer", ""),
                "owner_id": r.get("owner_id", ""),
                "owner": r.get("owner", ""),
                "sire": r.get("sire", ""),
                "dam": r.get("dam", ""),
                "form": r.get("form", ""),
                "official_rating": r.get("ofr") or r.get("or"),
                "rpr": r.get("rpr"),
                "ts": r.get("ts"),
                "lbs_carried": r.get("weight_lbs"),
                "silk_url": r.get("silk_url", ""),
            })

    # Clear today's runners before re-inserting to avoid unique constraint errors
    today_str = date.today().isoformat()
    _sb_delete_today_runners(today_str)
    r1 = _sb_upsert_batch("racing_today_cards", race_rows)
    r2 = _sb_upsert_batch("racing_today_runners", runner_rows)
    log.info("Today's cards: %d races, %d runners upserted", r1, r2)


# ── Entry point ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest Racing API data into Supabase")
    parser.add_argument("--days", type=int, default=90, help="Days of results history to pull (default: 90)")
    parser.add_argument("--start-date", type=str, default="", help="Explicit start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end-date", type=str, default="", help="Explicit end date YYYY-MM-DD (default: today)")
    parser.add_argument("--rate", type=float, default=1.0, help="Requests per second (default: 1.0)")
    parser.add_argument("--today-cards", action="store_true", help="Also ingest today's racecards")
    parser.add_argument("--courses-only", action="store_true", help="Only sync courses table")
    args = parser.parse_args()

    if args.courses_only:
        ingest_courses(args.rate)
        return

    # Courses
    ingest_courses(args.rate)

    # Results history → profiles
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=args.days)

    results = fetch_results_range(start_date, end_date, args.rate)
    log.info("Total results fetched: %d races", len(results))

    if not results:
        log.error("No results — check credentials or date range")
        sys.exit(1)

    jockeys, trainers, horses, owners = extract_profiles(results)
    log.info("Profiles extracted: %d jockeys, %d trainers, %d horses, %d owners",
             len(jockeys), len(trainers), len(horses), len(owners))

    # Individual run ledger
    run_rows = extract_horse_runs(results)
    log.info("Horse runs extracted: %d rows", len(run_rows))
    written = _sb_upsert_batch("racing_horse_runs", run_rows)
    log.info("Horse runs upserted: %d", written)

    # Upsert jockeys
    jockey_rows = []
    for j in jockeys.values():
        s = _serialise(j)
        win_pct = round(s["wins"] / s["runs"] * 100, 1) if s["runs"] else 0
        place_pct = round(s["places"] / s["runs"] * 100, 1) if s["runs"] else 0
        jockey_rows.append({
            "id": s["id"],
            "name": s["name"],
            "runs": s["runs"],
            "wins": s["wins"],
            "places": s["places"],
            "win_pct": win_pct,
            "place_pct": place_pct,
            "regions": s["regions"],
            "courses": s["courses"],
            "last_seen": s["last_seen"] or None,
            "updated_at": datetime.utcnow().isoformat(),
        })
    written = _sb_upsert_batch("racing_jockeys", jockey_rows)
    log.info("Jockeys upserted: %d", written)

    # Upsert trainers
    trainer_rows = []
    for t in trainers.values():
        s = _serialise(t)
        win_pct = round(s["wins"] / s["runs"] * 100, 1) if s["runs"] else 0
        place_pct = round(s["places"] / s["runs"] * 100, 1) if s["runs"] else 0
        trainer_rows.append({
            "id": s["id"],
            "name": s["name"],
            "runs": s["runs"],
            "wins": s["wins"],
            "places": s["places"],
            "win_pct": win_pct,
            "place_pct": place_pct,
            "regions": s["regions"],
            "courses": s["courses"],
            "last_seen": s["last_seen"] or None,
            "updated_at": datetime.utcnow().isoformat(),
        })
    written = _sb_upsert_batch("racing_trainers", trainer_rows)
    log.info("Trainers upserted: %d", written)

    # Upsert horses
    horse_rows = []
    for h in horses.values():
        s = _serialise(h)
        win_pct = round(s["wins"] / s["runs"] * 100, 1) if s["runs"] else 0
        horse_rows.append({
            "id": s["id"],
            "name": s["name"],
            "age": s.get("age", ""),
            "sex": s.get("sex", ""),
            "sire": s.get("sire", ""),
            "sire_id": s.get("sire_id", ""),
            "dam": s.get("dam", ""),
            "dam_id": s.get("dam_id", ""),
            "trainer_id": s.get("trainer_id", ""),
            "trainer": s.get("trainer", ""),
            "runs": s["runs"],
            "wins": s["wins"],
            "places": s["places"],
            "win_pct": win_pct,
            "last_seen": s.get("last_seen") or None,
            "last_or": s.get("last_or"),
            "last_rpr": s.get("last_rpr"),
            "updated_at": datetime.utcnow().isoformat(),
        })
    written = _sb_upsert_batch("racing_horses", horse_rows)
    log.info("Horses upserted: %d", written)

    # Upsert owners
    owner_rows = [
        {
            "id": o["id"],
            "name": o["name"],
            "runs": o["runs"],
            "wins": o["wins"],
            "win_pct": round(o["wins"] / o["runs"] * 100, 1) if o["runs"] else 0,
            "updated_at": datetime.utcnow().isoformat(),
        }
        for o in owners.values()
    ]
    written = _sb_upsert_batch("racing_owners", owner_rows)
    log.info("Owners upserted: %d", written)

    # Today's cards
    if args.today_cards:
        ingest_today_cards(args.rate)

    log.info("Done.")


if __name__ == "__main__":
    main()
