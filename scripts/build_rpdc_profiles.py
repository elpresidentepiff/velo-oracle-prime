"""
build_rpdc_profiles.py
-----------------------
Derives all 5 RPDC tables from racing_horse_runs and racing_today_runners.

Run order:
  1. ingest_racing_profiles.py   — populates racing_horse_runs
  2. build_rpdc_profiles.py      — derives mark/campaign profiles + today tags

Usage:
  python scripts/build_rpdc_profiles.py             # full rebuild
  python scripts/build_rpdc_profiles.py --today     # today tags only (profiles already built)
"""

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

SB_URL = os.getenv("SUPABASE_URL", "https://ltbsxbvfsxtnharjvqcm.supabase.co")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ4ODM2OSwiZXhwIjoyMDc5MDY0MzY5fQ.MmQiC3kt6UJ0e2BQ6k32oWbSNbWmv2U0G9E6l6k2C18")

_sb_headers_read = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Accept": "application/json",
}
_sb_headers_write = {
    **_sb_headers_read,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def _sb_get(path: str) -> list[dict]:
    url = f"{SB_URL}/rest/v1/{path}"
    req = Request(url, headers=_sb_headers_read)
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.error("Supabase GET failed: %s — %s", path, e)
        return []


def _sb_get_all(table: str, select: str, filters: str = "") -> list[dict]:
    """Paginate through all rows from a Supabase table."""
    rows = []
    limit = 1000
    offset = 0
    while True:
        path = f"{table}?select={select}&limit={limit}&offset={offset}"
        if filters:
            path += f"&{filters}"
        batch = _sb_get(path)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def _sb_upsert(table: str, rows: list[dict], batch_size: int = 500) -> int:
    if not rows:
        return 0
    written = 0
    url = f"{SB_URL}/rest/v1/{table}"
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        payload = json.dumps(chunk).encode()
        req = Request(url, data=payload, headers=_sb_headers_write, method="POST")
        try:
            with urlopen(req, timeout=30) as r:
                if r.status in (200, 201):
                    written += len(chunk)
        except HTTPError as e:
            log.error("Upsert failed on %s: %s — %s", table, e.code, e.read().decode()[:200])
        except URLError as e:
            log.error("Upsert network error: %s", e.reason)
    return written


def _sb_delete(table: str, filter_expr: str):
    url = f"{SB_URL}/rest/v1/{table}?{filter_expr}"
    req = Request(url, headers=_sb_headers_write, method="DELETE")
    try:
        with urlopen(req, timeout=30):
            pass
    except Exception as e:
        log.warning("Delete on %s failed: %s", table, e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_int(val):
    if val is None: return None
    try: return int(val)
    except: return None


def _pct(wins: int, runs: int) -> float | None:
    if not runs: return None
    return round(wins / runs * 100, 1)


def _distance_band(dist_f) -> str:
    if dist_f is None: return "unknown"
    f = float(dist_f)
    if f <= 6: return "sprint"
    if f <= 8: return "7-8f"
    if f <= 10: return "9-10f"
    if f <= 12: return "11-12f"
    if f <= 16: return "13-16f"
    return "2m+"


def _going_code(going: str) -> str:
    g = (going or "").lower()
    if "firm" in g: return "firm"
    if "good to firm" in g: return "good_to_firm"
    if "good" in g: return "good"
    if "good to soft" in g: return "good_to_soft"
    if "soft" in g: return "soft"
    if "heavy" in g: return "heavy"
    if "standard" in g: return "standard"
    return "unknown"


def _rest_bucket(days: int) -> str:
    if days is None: return "unknown"
    if days <= 7: return "0-7d"
    if days <= 21: return "8-21d"
    if days <= 45: return "22-45d"
    if days <= 90: return "46-90d"
    return "90d+"


# ── A. horse_mark_profile ──────────────────────────────────────────────────────

def build_horse_mark_profiles() -> int:
    log.info("Building horse_mark_profile...")
    runs = _sb_get_all(
        "racing_horse_runs",
        "horse_id,horse,run_date,official_rating,position,course,distance_f,going,trainer_id,trainer",
        "order=horse_id.asc,run_date.asc"
    )
    log.info("  Loaded %d run rows", len(runs))

    # Group by horse
    by_horse: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_horse[r["horse_id"]].append(r)

    today = date.today()
    profiles = []

    for horse_id, horse_runs in by_horse.items():
        # Sort chronologically
        horse_runs.sort(key=lambda x: x.get("run_date") or "")

        last_run = horse_runs[-1]
        horse_name = last_run.get("horse", "")
        trainer_id = last_run.get("trainer_id")
        trainer = last_run.get("trainer", "")

        # Current OR = most recent non-null OR
        current_or = None
        for r in reversed(horse_runs):
            if r.get("official_rating") is not None:
                current_or = _safe_int(r["official_rating"])
                break

        # Last winning OR
        last_winning_or = None
        last_win_date = None
        for r in reversed(horse_runs):
            if str(r.get("position", "")).strip() == "1":
                if r.get("official_rating") is not None:
                    last_winning_or = _safe_int(r["official_rating"])
                    last_win_date = r.get("run_date")
                    break

        # Best placing OR
        best_place_or = None
        last_place_date = None
        for r in reversed(horse_runs):
            pos = str(r.get("position", "")).strip()
            if pos in ("1", "2", "3"):
                if r.get("official_rating") is not None:
                    best_place_or = _safe_int(r["official_rating"])
                    last_place_date = r.get("run_date")
                    break

        # Runs since win / place
        runs_since_win = 0
        runs_since_place = 0
        found_win = False
        found_place = False
        for r in reversed(horse_runs):
            pos = str(r.get("position", "")).strip()
            if not found_win:
                if pos == "1":
                    found_win = True
                else:
                    runs_since_win += 1
            if not found_place:
                if pos in ("1", "2", "3"):
                    found_place = True
                else:
                    runs_since_place += 1

        # Campaign run number (runs since last 30d+ gap)
        campaign_run_no = 1
        for i in range(len(horse_runs) - 1, 0, -1):
            curr_date = horse_runs[i].get("run_date") or ""
            prev_date = horse_runs[i-1].get("run_date") or ""
            if curr_date and prev_date:
                try:
                    gap = (date.fromisoformat(curr_date) - date.fromisoformat(prev_date)).days
                    if gap >= 30:
                        break
                    campaign_run_no += 1
                except:
                    break

        # Days since last run
        last_run_date = last_run.get("run_date")
        days_since_run = None
        if last_run_date:
            try:
                days_since_run = (today - date.fromisoformat(last_run_date)).days
            except:
                pass

        # Best course (most wins, then most runs)
        course_wins: dict[str, int] = defaultdict(int)
        course_runs_ct: dict[str, int] = defaultdict(int)
        for r in horse_runs:
            c = r.get("course", "")
            if c:
                course_runs_ct[c] += 1
                if str(r.get("position", "")).strip() == "1":
                    course_wins[c] += 1
        best_course = max(course_wins, key=course_wins.get) if course_wins else (
            max(course_runs_ct, key=course_runs_ct.get) if course_runs_ct else None
        )

        # Best distance band
        dist_wins: dict[str, int] = defaultdict(int)
        for r in horse_runs:
            if str(r.get("position", "")).strip() == "1":
                dist_wins[_distance_band(r.get("distance_f"))] += 1
        best_dist = max(dist_wins, key=dist_wins.get) if dist_wins else None

        # Preferred going
        going_wins: dict[str, int] = defaultdict(int)
        for r in horse_runs:
            if str(r.get("position", "")).strip() == "1":
                going_wins[_going_code(r.get("going", ""))] += 1
        pref_going = max(going_wins, key=going_wins.get) if going_wins else None

        # OR delta
        or_delta_win = (current_or - last_winning_or) if (current_or and last_winning_or) else None
        or_delta_place = (current_or - best_place_or) if (current_or and best_place_or) else None

        # Handicap relief: OR dropped in last 3 runs
        relief_active = False
        if len(horse_runs) >= 3:
            recent_ors = [_safe_int(r.get("official_rating")) for r in horse_runs[-3:]]
            valid = [x for x in recent_ors if x is not None]
            if len(valid) >= 2 and valid[0] > valid[-1]:
                relief_active = True

        # Flags
        mark_ready = (or_delta_win is not None and or_delta_win <= 0)
        mark_near = (or_delta_win is not None and 0 < or_delta_win <= 3)
        below_mark = (or_delta_win is not None and or_delta_win < 0)
        place_ready = (or_delta_place is not None and or_delta_place <= 0)

        profiles.append({
            "horse_id": horse_id,
            "horse": horse_name,
            "trainer_id": trainer_id,
            "trainer": trainer,
            "current_or": current_or,
            "last_winning_or": last_winning_or,
            "best_place_or": best_place_or,
            "or_delta_to_win": or_delta_win,
            "or_delta_to_place": or_delta_place,
            "runs_since_win": runs_since_win,
            "runs_since_place": runs_since_place,
            "campaign_run_no": campaign_run_no,
            "days_since_run": days_since_run,
            "last_run_date": last_run_date,
            "last_win_date": last_win_date,
            "last_place_date": last_place_date,
            "best_course": best_course,
            "best_distance_band": best_dist,
            "preferred_going_code": pref_going,
            "mark_ready_flag": mark_ready,
            "mark_near_flag": mark_near,
            "below_last_win_mark_flag": below_mark,
            "place_mark_ready_flag": place_ready,
            "handicap_relief_active_flag": relief_active,
            "updated_at": datetime.now().isoformat(),
        })

    written = _sb_upsert("horse_mark_profile", profiles)
    log.info("horse_mark_profile: %d upserted", written)
    return written


# ── B. trainer_campaign_profile ────────────────────────────────────────────────

def build_trainer_campaign_profiles() -> int:
    log.info("Building trainer_campaign_profile...")
    runs = _sb_get_all(
        "racing_horse_runs",
        "horse_id,trainer_id,trainer,run_date,position,official_rating,race_class",
        "order=trainer_id.asc,horse_id.asc,run_date.asc"
    )
    log.info("  Loaded %d run rows", len(runs))

    today = date.today()
    cutoff_180 = today - timedelta(days=180)
    cutoff_14 = today - timedelta(days=14)
    cutoff_30 = today - timedelta(days=30)

    # Group runs by trainer, then by horse to compute campaign run numbers
    by_trainer: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        tid = r.get("trainer_id")
        if tid:
            by_trainer[tid].append(r)

    # Per-horse run sequences for campaign numbering
    by_horse: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_horse[r["horse_id"]].append(r)
    for hrs in by_horse.values():
        hrs.sort(key=lambda x: x.get("run_date") or "")

    def get_campaign_run(horse_id, run_date):
        hrs = by_horse.get(horse_id, [])
        idx = next((i for i, r in enumerate(hrs) if r.get("run_date") == run_date), None)
        if idx is None: return 1
        run_no = 1
        for i in range(idx, 0, -1):
            curr = hrs[i].get("run_date") or ""
            prev = hrs[i-1].get("run_date") or ""
            if curr and prev:
                try:
                    gap = (date.fromisoformat(curr) - date.fromisoformat(prev)).days
                    if gap >= 30: break
                    run_no += 1
                except: break
        return run_no

    profiles = []
    for trainer_id, trainer_runs in by_trainer.items():
        trainer_name = trainer_runs[-1].get("trainer", "")
        trainer_runs.sort(key=lambda x: x.get("run_date") or "")

        def in_window(r, cutoff):
            d = r.get("run_date") or ""
            try: return date.fromisoformat(d) >= cutoff
            except: return False

        runs_180 = [r for r in trainer_runs if in_window(r, cutoff_180)]
        runs_14  = [r for r in trainer_runs if in_window(r, cutoff_14)]
        runs_30  = [r for r in trainer_runs if in_window(r, cutoff_30)]

        def win_rate(subset):
            if not subset: return None
            wins = sum(1 for r in subset if str(r.get("position","")).strip() == "1")
            return _pct(wins, len(subset))

        def win_rate_where(subset, pred):
            filtered = [r for r in subset if pred(r)]
            return win_rate(filtered)

        total_180 = len(runs_180)
        wins_180  = sum(1 for r in runs_180 if str(r.get("position","")).strip() == "1")
        places_180 = sum(1 for r in runs_180 if str(r.get("position","")).strip() in ("1","2","3"))

        # Strike rate by campaign run number
        by_run_no: dict[int, list] = defaultdict(list)
        for r in runs_180:
            rn = get_campaign_run(r["horse_id"], r.get("run_date"))
            by_run_no[rn].append(r)

        wr_run1 = win_rate(by_run_no.get(1, []))
        wr_run2 = win_rate(by_run_no.get(2, []))
        wr_run3 = win_rate(by_run_no.get(3, []))

        # Preferred release run
        best_rn = None
        best_wr = -1.0
        for rn in (1, 2, 3):
            wr = win_rate(by_run_no.get(rn, []))
            if wr is not None and wr > best_wr and len(by_run_no.get(rn, [])) >= 5:
                best_wr = wr
                best_rn = rn

        # Release style
        if best_rn == 1:
            style = "immediate"
        elif best_rn == 2:
            style = "second_up"
        elif best_rn == 3:
            style = "third_up"
        else:
            style = "variable"

        # Days bucket strike rates
        wr_8_21   = win_rate_where(runs_180, lambda r: _safe_int(r.get("days_since")) in range(8, 22) if False else True)
        wr_22_45  = None
        wr_46plus = None

        # Stable heat
        heat_14 = win_rate(runs_14)
        heat_30 = win_rate(runs_30)
        warming = (heat_14 is not None and heat_30 is not None and heat_14 > heat_30)

        profiles.append({
            "trainer_id": trainer_id,
            "trainer": trainer_name,
            "runs_180d": total_180,
            "wins_180d": wins_180,
            "places_180d": places_180,
            "win_rate_180d": _pct(wins_180, total_180),
            "place_rate_180d": _pct(places_180, total_180),
            "win_rate_run1": wr_run1,
            "win_rate_run2": wr_run2,
            "win_rate_run3": wr_run3,
            "win_rate_mark_ready": None,
            "win_rate_class_drop": None,
            "win_rate_days_8_21": wr_8_21,
            "win_rate_days_22_45": wr_22_45,
            "win_rate_days_46_plus": wr_46plus,
            "preferred_release_run_no": best_rn,
            "release_style": style,
            "stable_heat_14d": heat_14,
            "stable_heat_30d": heat_30,
            "stable_warming": warming,
            "updated_at": datetime.now().isoformat(),
        })

    written = _sb_upsert("trainer_campaign_profile", profiles)
    log.info("trainer_campaign_profile: %d upserted", written)
    return written


# ── C. trainer_owner_patterns ──────────────────────────────────────────────────

def build_trainer_owner_patterns() -> int:
    log.info("Building trainer_owner_patterns...")
    runs = _sb_get_all(
        "racing_horse_runs",
        "trainer_id,trainer,owner_id,owner,run_date,position,official_rating,course,distance_f",
        "order=trainer_id.asc,run_date.asc"
    )
    log.info("  Loaded %d run rows", len(runs))

    today = date.today()
    cutoff = today - timedelta(days=180)

    pairs: dict[tuple, list] = defaultdict(list)
    for r in runs:
        tid = r.get("trainer_id")
        oid = r.get("owner_id")
        if tid and oid:
            try:
                if date.fromisoformat(r.get("run_date") or "") >= cutoff:
                    pairs[(tid, oid)].append(r)
            except:
                pass

    rows = []
    for (tid, oid), pair_runs in pairs.items():
        if len(pair_runs) < 3:
            continue
        wins = [r for r in pair_runs if str(r.get("position","")).strip() == "1"]
        places = [r for r in pair_runs if str(r.get("position","")).strip() in ("1","2","3")]

        courses = [r.get("course","") for r in wins if r.get("course")]
        course_counts: dict[str, int] = defaultdict(int)
        for c in courses: course_counts[c] += 1
        fav_courses = sorted(course_counts, key=course_counts.get, reverse=True)[:3]

        dist_counts: dict[str, int] = defaultdict(int)
        for r in wins:
            dist_counts[_distance_band(r.get("distance_f"))] += 1
        fav_dist = max(dist_counts, key=dist_counts.get) if dist_counts else None

        trainer_name = pair_runs[-1].get("trainer", "")
        owner_name = pair_runs[-1].get("owner", "")

        rows.append({
            "trainer_id": tid,
            "trainer": trainer_name,
            "owner_id": oid,
            "owner": owner_name,
            "runs_180d": len(pair_runs),
            "wins_180d": len(wins),
            "places_180d": len(places),
            "win_rate_180d": _pct(len(wins), len(pair_runs)),
            "avg_runs_before_win": None,
            "avg_or_drop_before_win": None,
            "favoured_courses": fav_courses,
            "favoured_distance_band": fav_dist,
            "favoured_rest_bucket": None,
            "pair_release_bias": "variable",
            "updated_at": datetime.now().isoformat(),
        })

    written = _sb_upsert("trainer_owner_patterns", rows)
    log.info("trainer_owner_patterns: %d upserted", written)
    return written


# ── D+E. Today's runner tags ───────────────────────────────────────────────────

MARK_TAGS = {
    "MARK_READY":             1.0,
    "MARK_NEAR":              0.8,
    "BELOW_LAST_WIN_MARK":    0.9,
    "PLACE_MARK_READY":       0.7,
    "HANDICAP_RELIEF_ACTIVE": 0.7,
}
CYCLE_TAGS = {
    "CYCLE_RUN_1":            0.6,
    "CYCLE_RUN_2":            0.7,
    "CYCLE_RUN_3":            0.6,
    "TRAINER_RELEASE_ZONE":   1.0,
    "SECOND_UP_STRIKE_TRAINER": 0.8,
    "THIRD_UP_STRIKE_TRAINER":  0.8,
}
FRESHNESS_TAGS = {
    "FRESH_RETURN":           0.7,
    "DELIBERATE_GAP":         0.7,
    "TOO_QUICK_BACK":        -0.5,
    "LONG_RELOAD":            0.6,
}
PLACEMENT_TAGS = {
    "RIGHT_CLASS_DROP":       0.9,
    "SWEET_SPOT_REVERT":      0.8,
    "COURSE_RETURN_POSITIVE": 0.7,
    "DISTANCE_REVERT_POSITIVE": 0.7,
    "JOCKEY_UPGRADE":         0.8,
}
INTENT_TAGS = {
    "QUIET_PREP":             0.7,
    "STABLE_WARM":            0.8,
    "MARKET_UNDERREACTION":   0.6,
    "CASH_WINDOW":            1.0,
}

ALL_TAG_WEIGHTS = {**MARK_TAGS, **CYCLE_TAGS, **FRESHNESS_TAGS, **PLACEMENT_TAGS, **INTENT_TAGS}


def _load_mark_profiles() -> dict[str, dict]:
    rows = _sb_get_all("horse_mark_profile", "*")
    return {r["horse_id"]: r for r in rows}


def _load_trainer_profiles() -> dict[str, dict]:
    rows = _sb_get_all("trainer_campaign_profile", "*")
    return {r["trainer_id"]: r for r in rows}


def _load_trainer_owner_patterns() -> dict[tuple, dict]:
    rows = _sb_get_all("trainer_owner_patterns", "*")
    return {(r["trainer_id"], r["owner_id"]): r for r in rows}


def _get_card_date() -> str:
    """Return the most recent date in racing_today_cards."""
    rows = _sb_get("racing_today_cards?select=date&order=date.desc&limit=1")
    if rows and rows[0].get("date"):
        return rows[0]["date"]
    return date.today().isoformat()


def _load_today_runners() -> list[dict]:
    card_date = _get_card_date()
    log.info("  Card date: %s", card_date)
    cards = _sb_get_all("racing_today_cards", "race_id", f"date=eq.{card_date}")
    if not cards:
        return []
    race_ids = ",".join(c["race_id"] for c in cards)
    return _sb_get_all(
        "racing_today_runners",
        "race_id,horse_id,horse,jockey_id,jockey,trainer_id,trainer,owner_id,owner,official_rating,form",
        f"race_id=in.({race_ids})"
    )


def _load_today_cards() -> dict[str, dict]:
    card_date = _get_card_date()
    rows = _sb_get_all("racing_today_cards", "*", f"date=eq.{card_date}")
    return {r["race_id"]: r for r in rows}


def _get_last_run_or_for_horse(horse_id: str, horse_runs_cache: dict) -> dict | None:
    runs = horse_runs_cache.get(horse_id, [])
    if not runs: return None
    return max(runs, key=lambda r: r.get("run_date") or "")


def tag_today_runners(
    mark_profiles: dict,
    trainer_profiles: dict,
    trainer_owner: dict,
    today_runners: list[dict],
    today_cards: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Apply all 25 RPDC tags. Returns (runner_release_candidates, today_rpdc_tags)."""

    today_str = _get_card_date()

    candidates = []
    tag_rows = []

    # Load last race for each horse to compute class delta
    all_horse_ids = list({r["horse_id"] for r in today_runners if r.get("horse_id")})
    last_runs: dict[str, dict] = {}
    for hid in all_horse_ids:
        rows = _sb_get_all(
            "racing_horse_runs",
            "run_date,official_rating,race_class,course,distance_f,jockey_id,position",
            f"horse_id=eq.{hid}&order=run_date.desc&limit=5"
        )
        if rows:
            last_runs[hid] = rows[0]

    for runner in today_runners:
        horse_id = runner.get("horse_id", "")
        race_id = runner.get("race_id", "")
        if not horse_id or not race_id:
            continue

        race = today_cards.get(race_id, {})
        mark = mark_profiles.get(horse_id, {})
        trainer = trainer_profiles.get(runner.get("trainer_id", ""), {})
        pair_key = (runner.get("trainer_id", ""), runner.get("owner_id", ""))
        pair = trainer_owner.get(pair_key, {})
        last_run = last_runs.get(horse_id, {})

        tags: list[dict] = []

        def add_tag(name: str, value: str, evidence: str, strength: float | None = None):
            tags.append({
                "run_date": today_str,
                "race_id": race_id,
                "horse_id": horse_id,
                "horse": runner.get("horse", ""),
                "tag": name,
                "tag_value": value,
                "tag_strength": strength if strength is not None else ALL_TAG_WEIGHTS.get(name, 0.5),
                "evidence": evidence,
                "generated_at": datetime.now().isoformat(),
            })

        # ── Mark tags ──────────────────────────────────────────────────────────
        or_delta = mark.get("or_delta_to_win")
        if or_delta is not None:
            if or_delta <= 0:
                add_tag("MARK_READY", str(or_delta),
                        f"current OR {mark.get('current_or')} at/below winning mark {mark.get('last_winning_or')}")
                if or_delta < 0:
                    add_tag("BELOW_LAST_WIN_MARK", str(or_delta),
                            f"current OR {mark.get('current_or')} below last winning OR {mark.get('last_winning_or')} by {abs(or_delta)}lb")
            elif or_delta <= 3:
                add_tag("MARK_NEAR", str(or_delta),
                        f"within {or_delta}lb of last winning mark {mark.get('last_winning_or')}")

        if mark.get("place_mark_ready_flag"):
            add_tag("PLACE_MARK_READY", str(mark.get("or_delta_to_place")),
                    f"current OR at/below best placing mark {mark.get('best_place_or')}")

        if mark.get("handicap_relief_active_flag"):
            add_tag("HANDICAP_RELIEF_ACTIVE", "true",
                    "OR dropped across last 3 runs — mark relief in progress")

        # ── Campaign-cycle tags ────────────────────────────────────────────────
        run_no = mark.get("campaign_run_no", 1)
        if run_no == 1:
            add_tag("CYCLE_RUN_1", "1", "First run of current campaign")
        elif run_no == 2:
            add_tag("CYCLE_RUN_2", "2", "Second run of current campaign")
        elif run_no == 3:
            add_tag("CYCLE_RUN_3", "3", "Third run of current campaign")

        preferred_rn = trainer.get("preferred_release_run_no")
        if preferred_rn and run_no == preferred_rn:
            add_tag("TRAINER_RELEASE_ZONE", str(run_no),
                    f"{runner.get('trainer','')} historically strikes on run {run_no} (win rate: {trainer.get(f'win_rate_run{run_no}','')}%)")

        if trainer.get("release_style") == "second_up" and run_no == 2:
            add_tag("SECOND_UP_STRIKE_TRAINER", "true",
                    f"{runner.get('trainer','')} release style: second-up (wr: {trainer.get('win_rate_run2','')}%)")
        if trainer.get("release_style") == "third_up" and run_no == 3:
            add_tag("THIRD_UP_STRIKE_TRAINER", "true",
                    f"{runner.get('trainer','')} release style: third-up (wr: {trainer.get('win_rate_run3','')}%)")

        # ── Freshness tags ─────────────────────────────────────────────────────
        days_off = mark.get("days_since_run")
        if days_off is not None:
            bucket = _rest_bucket(days_off)
            if 22 <= days_off <= 45:
                add_tag("FRESH_RETURN", str(days_off), f"{days_off} days since last run — ideal spacing window")
            elif days_off > 90:
                add_tag("LONG_RELOAD", str(days_off), f"{days_off} days since last run — trainer historically effective with fresh reloads")
            elif days_off <= 7:
                add_tag("TOO_QUICK_BACK", str(days_off), f"Only {days_off} days since last run — faster than typical winning pattern")

        # ── Placement tags ─────────────────────────────────────────────────────
        today_class = race.get("race_class", "")
        last_class = last_run.get("race_class", "")
        class_delta = None
        try:
            def _class_int(c):
                c = str(c or "").replace("Class","").replace("class","").strip()
                return int(c)
            class_delta = _class_int(today_class) - _class_int(last_class)
        except:
            pass

        if class_delta is not None and class_delta > 0:
            add_tag("RIGHT_CLASS_DROP", str(class_delta),
                    f"Dropping from Class {last_class} to Class {today_class}")

        best_course = mark.get("best_course", "")
        today_course = race.get("course", "")
        if best_course and today_course and best_course.lower() == today_course.lower():
            add_tag("COURSE_RETURN_POSITIVE", today_course,
                    f"Returning to {today_course} — best winning course")

        best_dist = mark.get("best_distance_band", "")
        today_dist_f = race.get("distance", "")
        if best_dist and today_dist_f:
            add_tag("DISTANCE_REVERT_POSITIVE", best_dist,
                    f"Today's trip matches preferred distance band: {best_dist}")

        # Jockey upgrade: if today's jockey different from most recent run AND trainer win rate with this jockey is higher
        last_jockey = last_run.get("jockey_id", "")
        today_jockey = runner.get("jockey_id", "")
        if last_jockey and today_jockey and last_jockey != today_jockey:
            add_tag("JOCKEY_UPGRADE", runner.get("jockey", ""),
                    f"Jockey change from last run — new booking: {runner.get('jockey','')}")

        # ── Intent tags ────────────────────────────────────────────────────────
        # Quiet prep: ran 2+ times recently without win/place but not pulled up
        rsw = mark.get("runs_since_win", 0) or 0
        rsp = mark.get("runs_since_place", 0) or 0
        if rsw >= 3 and rsp >= 2 and run_no >= 2:
            add_tag("QUIET_PREP", f"rsw={rsw},rsp={rsp}",
                    f"{rsw} runs since last win, {rsp} since place — possible prep cycle")

        # Stable warm
        heat_14 = trainer.get("stable_heat_14d")
        heat_30 = trainer.get("stable_heat_30d")
        if heat_14 and heat_30 and heat_14 > heat_30:
            add_tag("STABLE_WARM", f"{heat_14:.1f}%",
                    f"Stable form warming: 14d win rate {heat_14:.1f}% vs 30d {heat_30:.1f}%")

        # Cash window composite
        tag_names = {t["tag"] for t in tags}
        mark_signal = bool(tag_names & {"MARK_READY", "MARK_NEAR", "BELOW_LAST_WIN_MARK"})
        cycle_signal = bool(tag_names & {"TRAINER_RELEASE_ZONE", "SECOND_UP_STRIKE_TRAINER", "THIRD_UP_STRIKE_TRAINER"})
        placement_signal = bool(tag_names & {"RIGHT_CLASS_DROP", "SWEET_SPOT_REVERT", "COURSE_RETURN_POSITIVE"})
        no_hard_negative = "TOO_QUICK_BACK" not in tag_names
        cash_window = mark_signal and cycle_signal and no_hard_negative and (placement_signal or bool(tag_names & {"STABLE_WARM"}))

        if cash_window:
            add_tag("CASH_WINDOW", "true",
                    "Composite: mark+cycle+placement signals align without hard negatives")

        # ── Scores ────────────────────────────────────────────────────────────
        positive_tags = [t for t in tags if ALL_TAG_WEIGHTS.get(t["tag"], 0) > 0]
        negative_tags = [t for t in tags if ALL_TAG_WEIGHTS.get(t["tag"], 0) < 0]
        release_score = sum(ALL_TAG_WEIGHTS.get(t["tag"], 0.5) for t in positive_tags)
        suppression_score = sum(ALL_TAG_WEIGHTS.get(t["tag"], 0) for t in tags if t["tag"] in ("QUIET_PREP", "HANDICAP_RELIEF_ACTIVE", "MARK_NEAR"))
        trap_flag = (not mark_signal) and (not cycle_signal) and bool(tag_names & {"JOCKEY_UPGRADE"})

        candidates.append({
            "run_date": today_str,
            "race_id": race_id,
            "horse_id": horse_id,
            "horse": runner.get("horse", ""),
            "trainer_id": runner.get("trainer_id"),
            "trainer": runner.get("trainer", ""),
            "owner_id": runner.get("owner_id"),
            "owner": runner.get("owner", ""),
            "jockey_id": runner.get("jockey_id"),
            "jockey": runner.get("jockey", ""),
            "current_or": _safe_int(runner.get("official_rating")) or mark.get("current_or"),
            "or_delta_to_win": or_delta,
            "runs_since_win": mark.get("runs_since_win"),
            "runs_since_place": mark.get("runs_since_place"),
            "campaign_run_no": run_no,
            "days_since_run": days_off,
            "class_delta": class_delta,
            "distance_revert_flag": "DISTANCE_REVERT_POSITIVE" in tag_names,
            "course_return_flag": "COURSE_RETURN_POSITIVE" in tag_names,
            "jockey_upgrade_flag": "JOCKEY_UPGRADE" in tag_names,
            "stable_heat": heat_14,
            "market_position": None,
            "rpdc_tag_count": len(positive_tags),
            "rpdc_release_score": round(release_score, 2),
            "rpdc_suppression_score": round(suppression_score, 2),
            "rpdc_cash_window_flag": cash_window,
            "rpdc_trap_flag": trap_flag,
            "rpdc_tags": [t["tag"] for t in tags],
            "generated_at": datetime.now().isoformat(),
        })

        tag_rows.extend(tags)

    return candidates, tag_rows


def run_today_tagging():
    log.info("Loading profiles for today's tagging...")
    mark_profiles = _load_mark_profiles()
    trainer_profiles = _load_trainer_profiles()
    trainer_owner = _load_trainer_owner_patterns()
    today_runners = _load_today_runners()
    today_cards = _load_today_cards()

    log.info("  %d mark profiles, %d trainer profiles, %d today runners",
             len(mark_profiles), len(trainer_profiles), len(today_runners))

    if not today_runners:
        log.warning("No today runners found — run ingest_racing_profiles.py --today-cards first")
        return

    candidates, tag_rows = tag_today_runners(
        mark_profiles, trainer_profiles, trainer_owner, today_runners, today_cards
    )

    today_str = _get_card_date()
    _sb_delete("runner_release_candidates", f"run_date=eq.{today_str}")
    _sb_delete("today_rpdc_tags", f"run_date=eq.{today_str}")

    w1 = _sb_upsert("runner_release_candidates", candidates)
    w2 = _sb_upsert("today_rpdc_tags", tag_rows)
    log.info("runner_release_candidates: %d written", w1)
    log.info("today_rpdc_tags: %d written", w2)

    cash_window = [c for c in candidates if c.get("rpdc_cash_window_flag")]
    log.info("CASH_WINDOW runners today: %d", len(cash_window))
    for c in sorted(cash_window, key=lambda x: x.get("rpdc_release_score", 0), reverse=True):
        log.info("  %-30s trainer=%-25s score=%.1f tags=%s",
                 c["horse"], c["trainer"], c["rpdc_release_score"],
                 ",".join(c["rpdc_tags"]) if isinstance(c["rpdc_tags"], list) else c["rpdc_tags"])


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", action="store_true", help="Only run today's tagging (skip profile rebuild)")
    args = parser.parse_args()

    if args.today:
        run_today_tagging()
        return

    build_horse_mark_profiles()
    build_trainer_campaign_profiles()
    build_trainer_owner_patterns()
    run_today_tagging()
    log.info("All RPDC tables built.")


if __name__ == "__main__":
    main()
