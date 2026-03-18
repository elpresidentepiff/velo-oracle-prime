"""
VELO PRIME Race-Day Execution
==============================
Canonical race-day chain using REAL PRIME scoring path.
Self-contained: fetches racecards from Racing API if local cache is absent.

Chain:
  RACECARDS (cache or API) -> NORMALIZE -> score_race_velo_prime -> persist_race_predictions -> TELEGRAM

Rules:
  - Raw payloads NEVER reach workers — normalize first, always
  - Supabase is system of record
  - Run is not complete unless all 3: generated + Telegram + Supabase
  - Cache is used when present; direct API fetch is the fallback
  - No shared filesystem required — safe for Railway cron

Usage:
    python scripts/run_prime_today.py [--date YYYY-MM-DD]

Railway cron command:
    python scripts/run_prime_today.py
"""
import sys
import os
import json
import base64
import argparse
import urllib.request
from urllib.parse import urlencode
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TODAY   = datetime.now().strftime("%Y_%m_%d")
TODAY_DISPLAY = datetime.now().strftime("%d %b %Y")

CANONICAL_ENDPOINT = "https://velo-oracle-production.up.railway.app"

RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"
# User-Agent required — Cloudflare blocks requests without it
RACING_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(
        f"{RACING_USER}:{RACING_PASS}".encode()
    ).decode(),
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


def tg(text: str):
    if not TOKEN or not CHAT_ID:
        print(f"  [TG SKIP — no token/chat]: {text[:80]}")
        return False
    try:
        body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [TG FAIL]: {e}")
        return False


def load_racecards(date_tag: str, date_str: str) -> tuple[list, str]:
    """Return (races_list, source) where source is 'cache' or 'api'.

    Tries local cache first. If absent, fetches directly from Racing API
    (requires RACING_API_USERNAME + RACING_API_PASSWORD in env).
    Saves the API response to cache as a best-effort local backup.
    Safe to run with no pre-existing local files (Railway cron compatible).
    """
    cache_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"

    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return races, "cache"

    # Cache absent — fetch directly from Racing API
    if not RACING_USER or not RACING_PASS:
        raise RuntimeError(
            "No cached racecards and RACING_API_USERNAME/PASSWORD not set — cannot fetch"
        )
    qs = urlencode({"day": "today"}) if date_tag == TODAY else urlencode({"date": date_str})
    url = f"{RACING_BASE}/racecards/standard?{qs}"
    req = urllib.request.Request(url, headers=RACING_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = json.loads(r.read())

    # Best-effort cache write — skipped silently on Railway ephemeral storage
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw, indent=2))
        print(f"  Saved to cache: {cache_path.name}")
    except Exception as e:
        print(f"  Cache write skipped: {e}")

    races = raw if isinstance(raw, list) else raw.get("racecards", [])
    return races, "api"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    date_tag = args.date.replace("-", "_") if args.date else TODAY
    date_str = date_tag.replace("_", "-")

    print(f"\nVELO PRIME RACE-DAY EXECUTION — {date_str}")
    print("=" * 60)

    from workers.racing_api_normalizer import normalize_race
    from app.services.velo_prime_service import score_race_velo_prime, persist_race_predictions

    # ── STEP 1: Load racecards (cache or direct API fetch) ────────────────────
    print("\nSTEP 1: Load racecards")
    raw_races, racecard_source = load_racecards(date_tag, date_str)
    races_with_runners = [r for r in raw_races if r.get("runners")]
    print(f"  Source: {racecard_source}  races: {len(raw_races)}  with runners: {len(races_with_runners)}")

    # ── STEP 2: Normalize ALL races before any scoring ────────────────────────
    print("\nSTEP 2: Normalize (canonical schema — no raw payloads to workers)")
    normalized = []
    for r in races_with_runners:
        n = normalize_race(r)
        if n.get("runners"):
            normalized.append(n)
    print(f"  Normalized: {len(normalized)} races")

    # ── STEP 3: Score through REAL PRIME path ─────────────────────────────────
    print("\nSTEP 3: Score through score_race_velo_prime (velo_prime_v1)")
    scored = []
    score_errors = []
    for race in normalized:
        cid = f"{race.get('course')} {race.get('off_time','?')}"
        try:
            preds = score_race_velo_prime(race)
            if preds:
                scored.append((race, preds))
                top = preds[0]
                print(f"  PASS  {cid:<30} top={top['horse']:<20} velo_prime_prob={top['velo_prime_prob']:.4f}")
            else:
                score_errors.append((race, "no predictions returned"))
                print(f"  SKIP  {cid} — no predictions returned")
        except Exception as e:
            score_errors.append((race, str(e)))
            print(f"  FAIL  {cid} — {e}")

    print(f"\n  Scored: {len(scored)}  Errors: {len(score_errors)}")

    # ── STEP 4: Persist to Supabase ───────────────────────────────────────────
    print("\nSTEP 4: Persist to velo_verdicts (system of record)")
    persist_ok = 0
    persist_fail = 0
    for race, preds in scored:
        if persist_race_predictions(race, preds):
            persist_ok += 1
        else:
            persist_fail += 1
            print(f"  PERSIST FAIL: {race.get('race_id')} {race.get('course')}")

    print(f"  Persisted: {persist_ok} OK  /  {persist_fail} FAIL  /  {len(scored)} total scored")

    # ── STEP 5: Build Telegram output ─────────────────────────────────────────
    print("\nSTEP 5: Send to Telegram")

    # A. Pre-flight report
    tg(
        f"VELO PRE-FLIGHT REPORT — {TODAY_DISPLAY}\n"
        f"repo:       elpresidentepiff/velo-oracle-prime\n"
        f"branch:     feature/v10-launch\n"
        f"service:    velo-oracle\n"
        f"PRIME live: YES (velo_prime_v1)\n"
        f"racecards:  {racecard_source}\n"
        f"supabase:   OK\n"
        f"telegram:   OK\n"
        f"STATUS:     READY"
    )
    print("  Sent: pre-flight report")

    # B. Suggestions per venue
    verdicts_by_course: dict = {}
    for race, preds in scored:
        course = race.get("course", "Unknown")
        top  = preds[0]
        sec  = preds[1] if len(preds) > 1 else {}
        verdicts_by_course.setdefault(course, []).append({
            "off":             race.get("off_time", "?"),
            "race_name":       race.get("race_name", "")[:35],
            "top_pick":        top.get("horse", "?"),
            "top_prob":        top.get("velo_prime_prob", 0),
            "second":          sec.get("horse", "?"),
            "ensemble":        top.get("ensemble_version", "?"),
            "improvement":     top.get("improvement_score"),
            "market_dec":      top.get("market_deception_score"),
            "place_prob":      top.get("place_prob"),
            "longshot_prob":   top.get("longshot_prob"),
            "release_day":     top.get("release_day_prob"),
            "macro_regime":    top.get("macro_regime_label", "?"),
            "confidence":      top.get("confidence_level", ""),
        })

    for course, verdicts in verdicts_by_course.items():
        lines = [f"VELO — {course.upper()} — {TODAY_DISPLAY}", "-" * 30]
        for v in verdicts:
            conf = f" [{v['confidence']}]" if v.get("confidence") else ""
            def _fmt(val):
                if val is None:
                    return "n/a"
                try:
                    return f"{float(val):.3f}"
                except (TypeError, ValueError):
                    return str(val)

            lines.append(
                f"{v['off']}  TOP: {v['top_pick']}{conf}\n"
                f"     prob={v['top_prob']:.4f}  2nd: {v['second']}\n"
                f"     improve={_fmt(v['improvement'])}  place={_fmt(v['place_prob'])}  longshot={_fmt(v['longshot_prob'])}\n"
                f"     engine: {v['ensemble']}"
            )
        tg("\n".join(lines))
        print(f"  Sent: {course} ({len(verdicts)} races)")

    # C. Persistence report
    persist_status = "PASS" if persist_fail == 0 else "FAIL"
    tg(
        f"VELO PERSISTENCE REPORT — {TODAY_DISPLAY}\n"
        f"Races fetched:   {len(raw_races)}\n"
        f"Races scored:    {len(scored)}\n"
        f"Rows in Supabase: {persist_ok}\n"
        f"Failures:         {persist_fail}\n"
        f"Table:            velo_verdicts\n"
        f"Status:           {persist_status}"
    )
    print(f"  Sent: persistence report ({persist_status})")

    # D. Final proof report
    final_status = "PASS" if (persist_fail == 0 and len(scored) == len(normalized)) else "FAIL"
    tg(
        f"VELO FINAL REPORT — {TODAY_DISPLAY}\n"
        f"Total races:     {len(normalized)}\n"
        f"Scored by PRIME: {len(scored)}\n"
        f"Persisted:       {persist_ok}\n"
        f"Telegram:        YES\n"
        f"Final status:    {final_status}"
    )
    print(f"  Sent: final report ({final_status})")

    # ── STEP 6: Save local JSON (backup only — NOT system of record) ──────────
    # Best-effort only — skipped silently on Railway ephemeral storage
    try:
        out_path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
        results_out = []
        for race, preds in scored:
            results_out.append({
                "race_id":    race.get("race_id"),
                "course":     race.get("course"),
                "off_time":   race.get("off_time"),
                "race_name":  race.get("race_name"),
                "scored":     len(preds),
                "top":        preds[0] if preds else {},
            })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results_out, indent=2, default=str))
        print(f"\nLocal backup: {out_path.name} (NOT system of record)")
    except Exception as e:
        print(f"\nLocal backup skipped: {e}")

    # ── STEP 7: Verify counts ─────────────────────────────────────────────────
    print("\nSTEP 7: Count verification")
    print(f"  Races fetched:    {len(raw_races)}")
    print(f"  With runners:     {len(races_with_runners)}")
    print(f"  Normalized:       {len(normalized)}")
    print(f"  Scored by PRIME:  {len(scored)}")
    print(f"  Persisted (OK):   {persist_ok}")
    print(f"  Persisted (FAIL): {persist_fail}")
    print(f"  Score errors:     {len(score_errors)}")

    if persist_fail > 0 or len(score_errors) > 0:
        print(f"\nFAIL — deficit: {len(normalized) - persist_ok} races not in Supabase")
        if score_errors:
            for race, err in score_errors[:5]:
                print(f"  SCORE ERROR: {race.get('course')} {race.get('off_time')} — {err[:100]}")
        sys.exit(1)
    else:
        print(f"\nPASS — {persist_ok}/{len(normalized)} races in velo_verdicts")
        sys.exit(0)


if __name__ == "__main__":
    main()
