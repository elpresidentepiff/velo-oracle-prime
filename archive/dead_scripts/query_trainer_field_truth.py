"""
query_trainer_field_truth.py
------------------------------
Retrospective truth queries for trainer_campaign_profile extended fields.

Uses racing_horse_runs (79K rows with real outcomes) as the truth ledger.
Joins trainer_campaign_profile extended fields to ask:

  Q1. MARK_READY proxy: does win_rate_mark_ready predict actual MARK_READY outcomes?
  Q2. CLASS_DROP: does trainer win_rate_class_drop predict actual drops?
  Q3. First-time headgear: does trainer headgear rate predict headgear-intro runs?
  Q4. Top-course: trainer at home venue vs elsewhere
  Q5. Going split: going-matched vs going-mismatched RPDC candidates
  Q6. Release run: do trainer release patterns actually hold in the data?

All stats are derived from racing_horse_runs (180 days). Trainer profiles
from trainer_campaign_profile are joined on trainer_id.

Usage:
  python scripts/query_trainer_field_truth.py
  python scripts/query_trainer_field_truth.py --min-runs 10
  python scripts/query_trainer_field_truth.py --threshold 18.0
"""

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import date, timedelta
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_QUERY_TRAINER_FIELD_TRUTH"
SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""

_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Accept": "application/json"}


def _require_legacy_override() -> None:
    if os.getenv(LEGACY_EXECUTION_ENV) == "1":
        return
    raise SystemExit(
        "Legacy script is quarantined and blocked by default. "
        f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
    )


def _get_all(path: str) -> list[dict]:
    rows, limit, offset = [], 1000, 0
    while True:
        sep = "&" if "?" in path else "?"
        url = f"{SB_URL}/rest/v1/{path}{sep}limit={limit}&offset={offset}"
        req = Request(url, headers=_h)
        try:
            with urlopen(req, timeout=30) as r:
                batch = json.loads(r.read().decode())
        except Exception as e:
            log.error("GET failed: %s", e)
            break
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def _pct(wins: int, runs: int) -> str:
    if not runs:
        return "  —  "
    return f"{wins / runs * 100:5.1f}%"


def _bar(wins: int, runs: int, width: int = 20) -> str:
    if not runs:
        return ""
    filled = int(wins / runs * 100 / (100 / width))
    return "█" * min(filled, width)


def _header(title: str):
    print(f"\n{'='*68}")
    print(f"  {title}")
    print(f"{'='*68}")


def _row(label: str, wins: int, runs: int, note: str = ""):
    if runs == 0:
        print(f"  {label:<38}  —  (no data)")
        return
    print(f"  {label:<38} {wins:>4}W/{runs:>5}R  {_pct(wins, runs)}  {_bar(wins, runs, 15)}  {note}")


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _going_bucket(going: str) -> str:
    g = (going or "").lower()
    if "standard" in g or "all weather" in g or "tapeta" in g or "polytrack" in g:
        return "aw"
    if "firm" in g or "good" in g:
        return "good_firm"
    if "soft" in g or "heavy" in g or "yielding" in g:
        return "soft_plus"
    return "other"


def _class_int(race_class) -> int | None:
    if not race_class:
        return None
    import re
    m = re.search(r"\d+", str(race_class))
    return int(m.group()) if m else None


def main():
    parser = argparse.ArgumentParser(description="Retrospective truth queries: trainer extended fields")
    parser.add_argument("--days",      type=int,   default=180,   help="Lookback window days (default: 180)")
    parser.add_argument("--min-runs",  type=int,   default=10,    help="Min runs per cohort to report (default: 10)")
    parser.add_argument("--threshold", type=float, default=15.0,  help="Trainer field split threshold %% (default: 15.0)")
    args = parser.parse_args()

    today = date.today()
    cutoff = (today - timedelta(days=args.days)).isoformat()
    min_n = args.min_runs
    thr = args.threshold

    # ── Load data ─────────────────────────────────────────────────────────────
    log.info("Loading racing_horse_runs (last %d days)...", args.days)
    runs = _get_all(
        f"racing_horse_runs?select=horse_id,trainer_id,run_date,position,position_int,"
        f"official_rating,going,course,race_class,headgear,jockey_id"
        f"&run_date=gte.{cutoff}&order=horse_id.asc,run_date.asc"
    )
    log.info("  %d run rows loaded", len(runs))

    if not runs:
        print(f"No runs found after {cutoff}.")
        return

    log.info("Loading trainer_campaign_profile (extended fields)...")
    trainer_rows = _get_all(
        "trainer_campaign_profile?select=trainer_id,trainer,win_rate_mark_ready,"
        "win_rate_class_drop,win_rate_first_time_headgear,win_rate_going_good_firm,"
        "win_rate_going_soft_plus,win_rate_going_aw,top_courses,release_style,"
        "win_rate_run1,win_rate_run2,win_rate_run3,win_rate_180d"
    )
    tp: dict[str, dict] = {t["trainer_id"]: t for t in trainer_rows}
    log.info("  %d trainer profiles loaded", len(tp))

    # ── Per-horse sequences for campaign + mark calculations ──────────────────
    log.info("Building per-horse sequences...")
    by_horse: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_horse[r["horse_id"]].append(r)
    for hrs in by_horse.values():
        hrs.sort(key=lambda x: x.get("run_date") or "")

    def is_win(r) -> bool:
        pos = str(r.get("position") or "").strip()
        return pos == "1"

    def is_place(r) -> bool:
        pos = str(r.get("position") or "").strip()
        return pos in ("1", "2", "3")

    def get_campaign_run(horse_id: str, run_date: str) -> int:
        hrs = by_horse.get(horse_id, [])
        idx = next((i for i, r in enumerate(hrs) if r.get("run_date") == run_date), None)
        if idx is None:
            return 1
        run_no = 1
        for i in range(idx, 0, -1):
            curr = hrs[i].get("run_date") or ""
            prev = hrs[i-1].get("run_date") or ""
            if curr and prev:
                try:
                    gap = (date.fromisoformat(curr) - date.fromisoformat(prev)).days
                    if gap >= 30:
                        break
                    run_no += 1
                except:
                    break
        return run_no

    def get_last_winning_or_before(horse_id: str, run_date: str) -> int | None:
        hrs = by_horse.get(horse_id, [])
        for h in reversed(hrs):
            if (h.get("run_date") or "") < run_date and is_win(h):
                return _safe_int(h.get("official_rating"))
        return None

    def get_prev_class(horse_id: str, run_date: str):
        hrs = by_horse.get(horse_id, [])
        for h in reversed(hrs):
            if (h.get("run_date") or "") < run_date:
                return _class_int(h.get("race_class"))
        return None

    def get_prev_headgear(horse_id: str, run_date: str) -> str | None:
        hrs = by_horse.get(horse_id, [])
        for h in reversed(hrs):
            if (h.get("run_date") or "") < run_date:
                return h.get("headgear") or None
        return None

    def all_prior_headgear(horse_id: str, run_date: str) -> set:
        hrs = by_horse.get(horse_id, [])
        seen = set()
        for h in hrs:
            if (h.get("run_date") or "") >= run_date:
                break
            gear = h.get("headgear") or ""
            if gear:
                seen.add(gear)
        return seen

    # Baseline: all runs in window
    total_wins = sum(1 for r in runs if is_win(r))
    total_places = sum(1 for r in runs if is_place(r))

    # ── Q1: MARK_READY proxy ──────────────────────────────────────────────────
    _header("Q1: MARK_READY — trainer win_rate_mark_ready splits actual outcomes")

    mark_ready_runs = []
    mark_ready_strong = []
    mark_ready_weak = []
    mark_ready_nodata = []

    for r in runs:
        hid = r["horse_id"]
        rdate = r.get("run_date") or ""
        cor = _safe_int(r.get("official_rating"))
        if cor is None:
            continue
        lwo = get_last_winning_or_before(hid, rdate)
        if lwo is None:
            continue
        if cor > lwo:  # above last winning OR — not mark ready
            continue
        # At or below last winning OR — mark ready proxy
        mark_ready_runs.append(r)
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        wmr = t.get("win_rate_mark_ready")
        if wmr is None:
            mark_ready_nodata.append(r)
        elif wmr >= thr:
            mark_ready_strong.append(r)
        else:
            mark_ready_weak.append(r)

    _row("Baseline (all runs)", total_wins, len(runs))
    _row("MARK_READY proxy (all)", sum(is_win(r) for r in mark_ready_runs), len(mark_ready_runs))
    if len(mark_ready_strong) >= min_n:
        _row(f"  + trainer mark_ready >= {thr}%",
             sum(is_win(r) for r in mark_ready_strong), len(mark_ready_strong), "<- amplifier?")
    if len(mark_ready_weak) >= min_n:
        _row(f"  + trainer mark_ready <  {thr}%",
             sum(is_win(r) for r in mark_ready_weak), len(mark_ready_weak))
    if len(mark_ready_nodata) >= min_n:
        _row("  + trainer mark_ready no data",
             sum(is_win(r) for r in mark_ready_nodata), len(mark_ready_nodata))

    # ── Q2: Class drop ────────────────────────────────────────────────────────
    _header("Q2: CLASS_DROP — trainer class-drop strike rate vs actual drops")

    class_drop_runs = []
    class_drop_strong = []
    class_drop_weak = []

    for r in runs:
        hid = r["horse_id"]
        rdate = r.get("run_date") or ""
        this_class = _class_int(r.get("race_class"))
        prev_class = get_prev_class(hid, rdate)
        if this_class is None or prev_class is None:
            continue
        if this_class <= prev_class:  # not a class drop (higher number = lower class)
            continue
        class_drop_runs.append(r)
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        wcd = t.get("win_rate_class_drop")
        if wcd is not None and wcd >= thr:
            class_drop_strong.append(r)
        elif wcd is not None:
            class_drop_weak.append(r)

    _row("Class drop (all)", sum(is_win(r) for r in class_drop_runs), len(class_drop_runs))
    if len(class_drop_strong) >= min_n:
        _row(f"  + trainer class_drop >= {thr}%",
             sum(is_win(r) for r in class_drop_strong), len(class_drop_strong), "<- amplifier?")
    if len(class_drop_weak) >= min_n:
        _row(f"  + trainer class_drop <  {thr}%",
             sum(is_win(r) for r in class_drop_weak), len(class_drop_weak))

    # ── Q3: First-time headgear ───────────────────────────────────────────────
    _header("Q3: FIRST-TIME HEADGEAR — trainer headgear rate vs actual headgear debuts")

    hg_debut_runs = []
    hg_strong = []
    hg_weak = []

    for r in runs:
        hid = r["horse_id"]
        rdate = r.get("run_date") or ""
        gear = r.get("headgear") or ""
        if not gear:
            continue
        prior_gear = all_prior_headgear(hid, rdate)
        if gear in prior_gear:
            continue  # worn before — not a debut
        hg_debut_runs.append(r)
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        whg = t.get("win_rate_first_time_headgear")
        if whg is not None and whg >= thr:
            hg_strong.append(r)
        elif whg is not None:
            hg_weak.append(r)

    _row("Headgear debut (all)", sum(is_win(r) for r in hg_debut_runs), len(hg_debut_runs))
    if len(hg_strong) >= min_n:
        _row(f"  + trainer headgear_rate >= {thr}%",
             sum(is_win(r) for r in hg_strong), len(hg_strong), "<- high headgear trainer")
    if len(hg_weak) >= min_n:
        _row(f"  + trainer headgear_rate <  {thr}%",
             sum(is_win(r) for r in hg_weak), len(hg_weak))

    # ── Q4: Top-course trainer at home venue ──────────────────────────────────
    _header("Q4: TOP-COURSE TRAINER — at home venue vs elsewhere")

    at_home = []
    away = []

    for r in runs:
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        top_courses = t.get("top_courses") or []
        course = r.get("course", "") or ""
        if not top_courses:
            continue
        if course in top_courses:
            at_home.append(r)
        else:
            away.append(r)

    _row("Baseline (all runs)", total_wins, len(runs))
    if len(at_home) >= min_n:
        _row("Trainer at top-course venue", sum(is_win(r) for r in at_home), len(at_home), "<- home advantage?")
    if len(away) >= min_n:
        _row("Trainer away from top venues", sum(is_win(r) for r in away), len(away))

    # ── Q5: Going-matched vs going-mismatched ─────────────────────────────────
    _header("Q5: GOING MATCH — trainer on their strong going vs weak going")

    going_match = []
    going_mismatch = []

    for r in runs:
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        gb = _going_bucket(r.get("going", ""))

        # Find trainer's best and worst going rates
        rates = {
            "good_firm":  t.get("win_rate_going_good_firm"),
            "soft_plus":  t.get("win_rate_going_soft_plus"),
            "aw":         t.get("win_rate_going_aw"),
        }
        valid = {k: v for k, v in rates.items() if v is not None}
        if not valid or gb not in valid:
            continue

        best_going = max(valid, key=valid.get)
        if gb == best_going:
            going_match.append(r)
        else:
            going_mismatch.append(r)

    if len(going_match) >= min_n:
        _row("On trainer's best going", sum(is_win(r) for r in going_match), len(going_match), "<- hypothesis")
    if len(going_mismatch) >= min_n:
        _row("On trainer's weaker going", sum(is_win(r) for r in going_mismatch), len(going_mismatch))

    # ── Q6: Release run patterns ──────────────────────────────────────────────
    _header("Q6: RELEASE RUN — actual win rates by trainer preferred run number")

    # Split: runs on trainer's declared preferred_release_run_no vs other run numbers
    on_release = []
    off_release = []
    by_run_no: dict[int, list] = defaultdict(list)

    for r in runs:
        tid = r.get("trainer_id", "")
        t = tp.get(tid, {})
        preferred = t.get("preferred_release_run_no") or t.get("win_rate_run1") and 1
        if not preferred:
            continue
        rn = get_campaign_run(r["horse_id"], r.get("run_date") or "")
        by_run_no[rn].append(r)
        if rn == preferred:
            on_release.append(r)
        else:
            off_release.append(r)

    _row("Baseline (all runs)", total_wins, len(runs))
    for rn in sorted(by_run_no.keys()):
        cohort = by_run_no[rn]
        if len(cohort) >= min_n:
            _row(f"Campaign run {rn}",
                 sum(is_win(r) for r in cohort), len(cohort))
    if len(on_release) >= min_n:
        print()
        _row("On trainer's preferred release run",
             sum(is_win(r) for r in on_release), len(on_release), "<- signal run")
    if len(off_release) >= min_n:
        _row("Other campaign runs",
             sum(is_win(r) for r in off_release), len(off_release))

    # ── Summary ───────────────────────────────────────────────────────────────
    _header("SUMMARY")
    print(f"  Window       : last {args.days} days (from {cutoff})")
    print(f"  Total runs   : {len(runs):,}")
    print(f"  Baseline W%  : {_pct(total_wins, len(runs))}")
    print(f"  Baseline P%  : {_pct(total_places, len(runs))}")
    print(f"  Min cohort   : {min_n}")
    print(f"  Threshold    : {thr}%")
    print()
    print("  Findings to checkpoint at W1 (2026-04-18):")
    print("  — Which trainer fields amplify tag win rate above baseline?")
    print("  — Which fields are noise (no delta vs baseline)?")
    print("  — Flag any field where STRONG cohort < WEAK cohort (inverse signal).")
    print()


if __name__ == "__main__":
    _require_legacy_override()
    main()
