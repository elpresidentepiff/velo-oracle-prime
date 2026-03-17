"""
Pull today's racecards and run VELO 5-agent orchestrator on each race.
Sends Telegram updates as verdicts come in.

Protocol (per VELO operating procedure):
  1. Load saved state / confirm API tier
  2. Pull standard racecards
  3. Normalize ALL runners through racing_api_normalizer
  4. Smoke test: one race
  5. Smoke test: one meeting
  6. Full card
  7. Save outputs + send Telegram

Usage: python scripts/run_todays_races.py [--date YYYY-MM-DD] [--smoke]
"""
import argparse
import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── imports ──────────────────────────────────────────────────────────────────
from workers.racing_api_normalizer import normalize_race
from app.services.velo_prime_service import persist_race_predictions

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RACING_USER = os.getenv("RACING_API_USERNAME")
RACING_PASS = os.getenv("RACING_API_PASSWORD")
RACING_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")

TODAY = datetime.now().strftime("%Y_%m_%d")
TODAY_DISPLAY = datetime.now().strftime("%d %b %Y")


# ── Telegram ──────────────────────────────────────────────────────────────────
def tg(text: str):
    if not TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text[:4096]},
            timeout=10,
        )
    except Exception:
        pass


# ── Fetch standard racecards ──────────────────────────────────────────────────
def fetch_standard_racecards(date_str: str | None = None) -> dict:
    """Fetch standard racecards. Caches to data/racecards_{date}_standard.json."""
    date_tag = date_str.replace("-", "_") if date_str else TODAY
    cache_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"

    if cache_path.exists():
        print(f"  [cache] Using {cache_path.name}")
        with open(cache_path) as f:
            return json.load(f)

    print("  [api] Fetching standard racecards...")
    params = {}
    if date_str:
        params["date"] = date_str
    r = requests.get(
        f"{RACING_BASE}/racecards/standard",
        auth=(RACING_USER, RACING_PASS),
        params=params,
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  [ERROR] Racing API returned {r.status_code}: {r.text[:200]}")
        sys.exit(1)
    data = r.json()
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  [api] Saved to {cache_path.name}")
    return data


# ── Build a rating-based fallback verdict ─────────────────────────────────────
def fallback_verdict(race: dict, idx: int) -> dict:
    """OR/RPR rating sort when orchestrator is unavailable or errors."""
    runners = race["runners"]
    rated = sorted(
        runners,
        key=lambda r: r["official_rating"] * 0.6 + r["rpr"] * 0.4,
        reverse=True,
    )
    top    = rated[0] if rated else {}
    second = rated[1] if len(rated) > 1 else {}
    score  = top.get("official_rating", 0) * 0.6 + top.get("rpr", 0) * 0.4
    return {
        "race_id":       race["race_id"],
        "course":        race["course"],
        "off":           race["off_time"],
        "race_name":     race["race_name"][:40],
        "type":          race["type"],
        "class":         race["race_class"],
        "runners":       len(runners),
        "top_pick":      top.get("horse_name", "?"),
        "top_pick_or":   top.get("official_rating", 0),
        "top_pick_rpr":  top.get("rpr", 0),
        "second":        second.get("horse_name", "?"),
        "jockey":        top.get("jockey_name", "?"),
        "trainer":       top.get("trainer_name", "?"),
        "score":         round(score, 1),
        "confidence_level": "",
        "method":        "OR/RPR fallback",
    }


# ── Analyse one race ──────────────────────────────────────────────────────────
def analyse_race(race: dict, orch, race_idx: int) -> dict:
    """
    Run orchestrator on one normalised race.
    Falls back to OR/RPR sort if orchestrator errors.
    Returns a verdict dict.
    """
    runners = race["runners"]
    course  = race["course"]
    off     = race["off_time"]
    rclass  = race["race_class"]
    rtype   = race["type"]
    name    = race["race_name"][:30]
    n       = len(runners)

    print(f"    {course:<25} {off}  {n:2d}r  {rclass:<8} {rtype:<12} {name}")

    if orch:
        try:
            verdicts_list = orch.analyze_race(race)
            if verdicts_list:
                top_v    = max(verdicts_list, key=lambda v: v.final_score)
                sorted_v = sorted(verdicts_list, key=lambda v: -v.final_score)
                return {
                    "race_id":          race["race_id"],
                    "course":           course,
                    "off":              off,
                    "race_name":        race["race_name"][:40],
                    "type":             rtype,
                    "class":            rclass,
                    "runners":          n,
                    "top_pick":         top_v.horse_name,
                    "score":            round(top_v.final_score, 2),
                    "confidence_level": getattr(top_v, "confidence_level", ""),
                    "action":           getattr(top_v, "action", ""),
                    "stake_pct":        getattr(top_v, "stake_percentage", 0),
                    "jockey":           getattr(top_v, "jockey", "?") or "?",
                    "trainer":          getattr(top_v, "trainer", "?") or "?",
                    "second":           sorted_v[1].horse_name if len(sorted_v) > 1 else "?",
                    "method":           "orchestrator",
                }
        except Exception as e:
            print(f"      [orchestrator error] {e}")

    return fallback_verdict(race, race_idx)


# ── Telegram output ───────────────────────────────────────────────────────────
def send_verdicts_by_course(results: list, verdicts_by_course: dict):
    tg(
        f"VELO RACECARDS -- {TODAY_DISPLAY}\n"
        f"{'='*30}\n"
        f"{len(results)} races analysed across {len(verdicts_by_course)} venues"
    )
    for course, verdicts in verdicts_by_course.items():
        lines = [f"VELO -- {course.upper()}\n{'-'*30}"]
        for v in verdicts:
            conf_raw = v.get("confidence_level", "") or v.get("confidence", "")
            conf     = f" [{conf_raw}]" if conf_raw else ""
            lines.append(
                f"{v.get('off','?')}  TOP: {v.get('top_pick','?')}{conf}\n"
                f"     2nd: {v.get('second','?')}\n"
                f"     J: {v.get('jockey','?')[:15]} / T: {v.get('trainer','?')[:15]}"
                f"  score={v.get('score',0)}"
            )
        tg("\n".join(lines))
        print(f"  Sent {course}: {len(verdicts)} verdicts")

    aw_races   = verdicts_by_course.get("Wolverhampton (AW)", [])
    jump_races = [v for c, vs in verdicts_by_course.items() for v in vs if "Wolverhampton" not in c]
    tg(
        f"VELO ANALYSIS COMPLETE -- {TODAY_DISPLAY}\n"
        f"Total races: {len(results)}\n"
        f"Jump: {len(jump_races)} | AW flat: {len(aw_races)}\n\n"
        f"SIGMA NOTE: AW Wolverhampton went 0/9 yesterday.\n"
        f"AW picks = research only until sigma shows positive calibration restored."
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--smoke", action="store_true", help="Smoke test only (1 race)")
    args = parser.parse_args()

    # ── STEP 1: Fetch + normalize ─────────────────────────────────────────────
    raw_data = fetch_standard_racecards(args.date)
    raw_races = raw_data.get("racecards", [])
    print(f"\nRaw races: {len(raw_races)}")

    # Normalize ALL races through the single normalization layer
    races = [normalize_race(r) for r in raw_races if r.get("runners")]
    print(f"Normalized races with runners: {len(races)}\n")

    # ── STEP 2: Load orchestrator ─────────────────────────────────────────────
    orch = None
    try:
        from app.engine.orchestrator import Orchestrator
        orch = Orchestrator()
        print("Orchestrator: OK\n")
    except Exception as e:
        print(f"Orchestrator load failed: {e}\nFalling back to OR/RPR rating sort.\n")

    # ── STEP 3: Smoke test — one race ─────────────────────────────────────────
    print("=== SMOKE TEST: one race ===")
    test_verdict = analyse_race(races[0], orch, 0)
    print(f"  Result: {test_verdict['top_pick']} score={test_verdict['score']} method={test_verdict['method']}")

    if test_verdict["top_pick"] == "?" or test_verdict["top_pick"] == "Unknown":
        print("\n[ABORT] Smoke test returned unknown horse. Fix normalization before continuing.")
        sys.exit(1)
    print("  PASS\n")

    if args.smoke:
        print("Smoke mode — stopping after first race.")
        print(json.dumps(test_verdict, indent=2))
        return

    # ── STEP 4: Smoke test — first meeting ────────────────────────────────────
    first_course = races[0]["course"]
    meeting_races = [r for r in races if r["course"] == first_course]
    print(f"=== SMOKE TEST: {first_course} ({len(meeting_races)} races) ===")
    meeting_errors = 0
    for r in meeting_races:
        v = analyse_race(r, orch, 0)
        if v["top_pick"] in ("?", "Unknown", ""):
            meeting_errors += 1
            print(f"  [WARN] {r['off_time']} — no valid pick")
    if meeting_errors > len(meeting_races) // 2:
        print(f"\n[ABORT] {meeting_errors}/{len(meeting_races)} meeting races returned invalid picks.")
        sys.exit(1)
    print(f"  PASS ({meeting_errors} warnings)\n")

    # ── STEP 5: Full card ─────────────────────────────────────────────────────
    print(f"=== FULL CARD: {len(races)} races ===")
    results = []
    verdicts_by_course: dict = {}
    persist_ok = 0
    persist_fail = 0
    for i, race in enumerate(races, 1):
        v = analyse_race(race, orch, i)
        results.append(v)
        verdicts_by_course.setdefault(v["course"], []).append(v)
        # Persist to Supabase immediately after each verdict — system of record
        try:
            from app.services.velo_prime_service import score_race_velo_prime
            prime_preds = score_race_velo_prime(race)
        except Exception as e:
            print(f"      [prime_score error] {race.get('race_id')}: {e}")
            prime_preds = []
        if prime_preds:
            if persist_race_predictions(race, prime_preds):
                persist_ok += 1
            else:
                persist_fail += 1
                print(f"      [persist FAIL] {race.get('race_id')}")
        else:
            # Fallback: persist orchestrator verdict as minimal row
            persist_fail += 1
            print(f"      [persist SKIP — no prime scores] {race.get('race_id')}")

    # ── STEP 6: Save ──────────────────────────────────────────────────────────
    date_tag  = args.date.replace("-", "_") if args.date else TODAY
    out_path  = ROOT / "data" / f"velo_verdicts_{date_tag}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {out_path.name}")
    print(f"Supabase persist: {persist_ok} OK / {persist_fail} FAIL / {len(races)} total")

    # ── STEP 7: Telegram ──────────────────────────────────────────────────────
    send_verdicts_by_course(results, verdicts_by_course)
    print("\nDone. All verdicts sent to Telegram.")

    # ── STEP 8: Persistence report to Telegram ────────────────────────────────
    persist_status = "PASS" if persist_fail == 0 else "FAIL"
    tg(
        f"VELO PERSISTENCE REPORT -- {TODAY_DISPLAY}\n"
        f"Races generated: {len(races)}\n"
        f"Rows written to Supabase: {persist_ok}\n"
        f"Failures: {persist_fail}\n"
        f"Table: velo_verdicts\n"
        f"Status: {persist_status}"
    )
    if persist_fail > 0:
        print(f"\n[WARNING] {persist_fail} races failed Supabase persistence.")
        print("Run: python scripts/post_run_persistence_check.py")

    # ── STEP 9: Post-run persistence check ────────────────────────────────────
    import subprocess
    check_date = args.date or datetime.now().strftime("%Y-%m-%d")
    print(f"\nRunning post-run persistence check for {check_date}...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "post_run_persistence_check.py"),
         "--date", check_date],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("[WARNING] Persistence check reported FAIL — review Supabase row counts.")


if __name__ == "__main__":
    main()
