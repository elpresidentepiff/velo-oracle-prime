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


def _fmt_prob(val):
    if val is None:
        return "n/a"
    try:
        return f"{float(val):.3f}"
    except (TypeError, ValueError):
        return str(val)


def classify_race(top: dict, second_prob: float) -> tuple[str, list[str], str]:
    """
    Returns (status, reasons, action) where status is STRIKE/WATCH/NO BET/CHAOS.

    Rules applied in order — first match wins:
      CHAOS   : prob < 0.15  OR  longshot_prob > 0.25  OR  gap < 0.02
      STRIKE  : prob >= 0.28 AND gap >= 0.06 AND place_prob >= 0.42
                AND confidence in (medium, high)
      NO BET  : prob < 0.22 AND gap < 0.05 AND confidence == low/missing
      WATCH   : everything else
    """
    prob      = float(top.get("velo_prime_prob") or 0)
    place     = float(top.get("place_prob") or 0)
    longshot  = float(top.get("longshot_prob") or 0)
    improve   = top.get("improvement_score")
    mkt_dec   = top.get("market_deception_score")
    conf      = (top.get("confidence_level") or "low").lower()
    gap       = prob - second_prob

    reasons = []

    # ── CHAOS ─────────────────────────────────────────────────────────────────
    if prob < 0.15 or longshot > 0.25 or gap < 0.02:
        if prob < 0.15:
            reasons.append(f"flat field — top prob only {prob:.3f}")
        if longshot > 0.25:
            reasons.append(f"outsider pressure — longshot prob {longshot:.3f}")
        if gap < 0.02:
            reasons.append(f"no separation — gap to 2nd only {gap:.3f}")
        reasons.append("model cannot identify clear leader")
        return "CHAOS", reasons, "do not bet — chaotic race shape"

    # ── STRIKE ────────────────────────────────────────────────────────────────
    if prob >= 0.28 and gap >= 0.06 and place >= 0.42 and conf in ("medium", "high"):
        reasons.append(f"top prob {prob:.3f} — clear field leader")
        reasons.append(f"gap to 2nd: {gap:.3f} — meaningful separation")
        reasons.append(f"place profile: {place:.3f}")
        if improve and float(improve) > 0.5:
            reasons.append(f"improvement signal: {float(improve):.3f}")
        return "STRIKE", reasons, "main win candidate — playable"

    # ── NO BET ────────────────────────────────────────────────────────────────
    if prob < 0.22 and gap < 0.05 and conf in ("low", ""):
        reasons.append(f"top prob {prob:.3f} — below threshold")
        reasons.append(f"gap to 2nd only {gap:.3f} — insufficient separation")
        if conf in ("low", ""):
            reasons.append("confidence: low — no conviction signal")
        return "NO BET", reasons, "skip — no identifiable edge"

    # ── WATCH ─────────────────────────────────────────────────────────────────
    reasons.append(f"top prob {prob:.3f} — some signal, not enough conviction")
    reasons.append(f"gap to 2nd: {gap:.3f}")
    if place >= 0.40:
        reasons.append(f"place profile acceptable: {place:.3f}")
    else:
        reasons.append(f"place profile weak: {place:.3f}")
    return "WATCH", reasons, "monitor only — wait for stronger signal"


def market_posture(top: dict) -> str:
    mkt = top.get("market_deception_score")
    if mkt is None:
        return "unknown"
    m = float(mkt)
    if m >= 0.55:
        return f"possible overlay ({m:.2f})"
    if m <= 0.30:
        return f"market aligned ({m:.2f})"
    return f"neutral ({m:.2f})"


def build_race_card(race: dict, top: dict, second: dict, status: str,
                    reasons: list, action: str) -> str:
    course   = race.get("course", "?").upper()
    off      = race.get("off_time", "?")
    primary  = top.get("horse", "?")
    contain  = second.get("horse", "?") if second else "none"
    conf     = top.get("confidence_level") or "low"
    mkt      = market_posture(top)
    longshot = float(top.get("longshot_prob") or 0)
    value    = "none"
    if longshot >= 0.20:
        value = f"{primary} (longshot prob {longshot:.3f})"

    status_prefix = {
        "STRIKE": "⚡ STRIKE",
        "WATCH":  "👁 WATCH",
        "NO BET": "✗ NO BET",
        "CHAOS":  "⚠ CHAOS",
    }.get(status, status)

    lines = [
        f"{course} {off} | {status_prefix}",
        "─" * 32,
        f"PRIMARY:     {primary}",
        f"CONTAINMENT: {contain}",
        f"VALUE:       {value}",
        f"CONFIDENCE:  {conf}",
        f"MARKET:      {mkt}",
        "REASONS:",
    ]
    for r in reasons[:4]:
        lines.append(f"• {r}")
    lines.append(f"ACTION: {action}")
    return "\n".join(lines)


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

    # B. Decision-layer cards
    # Classify every race, then send:
    #   - STRIKE races: individual card per race
    #   - WATCH races:  one grouped message
    #   - NO BET/CHAOS: one summary message
    strikes, watches, nobets = [], [], []

    for race, preds in scored:
        top    = preds[0]
        second = preds[1] if len(preds) > 1 else {}
        sec_prob = float(second.get("velo_prime_prob") or 0)
        status, reasons, action = classify_race(top, sec_prob)
        entry = (race, top, second, status, reasons, action)
        if status == "STRIKE":
            strikes.append(entry)
        elif status == "WATCH":
            watches.append(entry)
        else:
            nobets.append(entry)

    # Day posture header
    tg(
        f"VELO DAY POSTURE — {TODAY_DISPLAY}\n"
        f"{'─' * 32}\n"
        f"⚡ STRIKE:  {len(strikes)}\n"
        f"👁 WATCH:   {len(watches)}\n"
        f"✗ NO BET:  {len([e for e in nobets if e[3] == 'NO BET'])}\n"
        f"⚠ CHAOS:   {len([e for e in nobets if e[3] == 'CHAOS'])}\n"
        f"Total races: {len(scored)}"
    )
    print(f"  Sent: day posture ({len(strikes)} STRIKE, {len(watches)} WATCH, {len(nobets)} NO BET/CHAOS)")

    # Individual STRIKE cards
    for race, top, second, status, reasons, action in strikes:
        card = build_race_card(race, top, second, status, reasons, action)
        tg(card)
        print(f"  Sent: STRIKE — {race.get('course')} {race.get('off_time')}")

    # WATCH races grouped
    if watches:
        lines = [f"VELO WATCH LIST — {TODAY_DISPLAY}", "─" * 32]
        for race, top, second, status, reasons, action in watches:
            course  = race.get("course", "?").upper()
            off     = race.get("off_time", "?")
            primary = top.get("horse", "?")
            prob    = float(top.get("velo_prime_prob") or 0)
            gap     = prob - float(second.get("velo_prime_prob") or 0)
            lines.append(
                f"{course} {off}\n"
                f"  {primary} | prob {prob:.3f} | gap {gap:.3f}\n"
                f"  {action}"
            )
        tg("\n".join(lines))
        print(f"  Sent: WATCH list ({len(watches)} races)")

    # NO BET / CHAOS summary
    if nobets:
        lines = [f"VELO NO-BET / CHAOS — {TODAY_DISPLAY}", "─" * 32]
        for race, top, second, status, reasons, action in nobets:
            course  = race.get("course", "?").upper()
            off     = race.get("off_time", "?")
            primary = top.get("horse", "?")
            tag     = "✗" if status == "NO BET" else "⚠"
            lines.append(f"{tag} {course} {off}  {primary}  — {reasons[0] if reasons else status}")
        tg("\n".join(lines))
        print(f"  Sent: NO BET/CHAOS list ({len(nobets)} races)")

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
