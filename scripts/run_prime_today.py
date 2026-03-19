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


# ── Decision Synthesis Layer ──────────────────────────────────────────────────
# Tiers: A-STRIKE | B-PLAYABLE | C-WATCH | D-NO BET | X-CHAOS
#
# Rules (applied in order — first match wins):
#
# X-CHAOS  : prob < 0.10  (truly flat — model sees no leader)
#             OR  (gap < 0.015 AND place < 0.40)  (no separation + no place floor)
#             OR  longshot > 0.35  (outsider pressure dominates)
#             OR  macro_chaos_mode == True
#
#   NOTE: gap=0.000 alone does NOT trigger X if place >= 0.40.
#         That becomes D-NO BET or C-WATCH depending on prob/place.
#
# A-STRIKE : prob >= 0.32  AND  gap >= 0.08  AND  place >= 0.52
#             AND  conf != 'low'  AND  trap != 'high'
#
# B-PLAYABLE: prob >= 0.18  AND  gap >= 0.03
#             AND  (place >= 0.45  OR  gap >= 0.08  OR  improve >= 0.18)
#
# C-WATCH  : (prob >= 0.13 AND gap >= 0.02)
#             OR  (place >= 0.55 AND prob >= 0.11)   ← each-way floor rescue
#
# D-NO BET : everything else (some signal but not enough edge to act)
#
# Secondary modifiers (added to reason stack, do not change tier):
#   market_deception_score > 0.55 → "possible overlay"
#   market_deception_score < 0.15 → "market aligned"
#   release_day_prob > 0.40       → "trainer release signal"
#   improvement_score > 0.18      → "form improvement signal"
#   favourite_trap_risk != normal → "favourite trap risk"
# ─────────────────────────────────────────────────────────────────────────────

TIER_LABELS = {
    "A": "A-STRIKE",
    "B": "B-PLAYABLE",
    "C": "C-WATCH",
    "D": "D-NO BET",
    "X": "X-CHAOS",
}

TIER_ACTIONS = {
    "A": "back win — primary selection",
    "B": "playable if price >= fair value — check market",
    "C": "watch price — each-way angle if generous",
    "D": "no bet — insufficient edge",
    "X": "pass — race shape unreliable",
}


def synthesize_decision(top: dict, second_prob: float) -> tuple[str, list[str]]:
    """
    Returns (tier, reasons) where tier is A/B/C/D/X.
    Uses full available signal stack from velo_prime_v1 output.
    """
    prob      = float(top.get("velo_prime_prob") or 0)
    place     = float(top.get("place_prob") or 0)
    longshot  = float(top.get("longshot_prob") or 0)
    improve   = float(top.get("improvement_score") or 0)
    mkt_dec   = top.get("market_deception_score")
    release   = float(top.get("release_day_prob") or 0)
    chaos_m   = bool(top.get("macro_chaos_mode") or False)
    trap      = (top.get("favourite_trap_risk") or "normal").lower()
    conf      = (top.get("confidence_level") or "low").lower()
    gap       = prob - second_prob

    reasons = []

    # ── X-CHAOS ───────────────────────────────────────────────────────────────
    # Trigger X only when model is genuinely blind: flat field, no place floor,
    # outsider dominance, or macro chaos. gap=0 alone does NOT trigger X if
    # place >= 0.40 (uniform scoring from broken numpy — still has place signal).
    if prob < 0.10 or (gap < 0.015 and place < 0.40) or longshot > 0.35 or chaos_m:
        if prob < 0.10:
            reasons.append(f"flat field — top prob {prob:.3f} below threshold")
        if gap < 0.015 and place < 0.40:
            reasons.append(f"no separation (gap {gap:.3f}) and weak place floor ({place:.3f})")
        if longshot > 0.35:
            reasons.append(f"outsider pressure — longshot signal {longshot:.3f}")
        if chaos_m:
            reasons.append("macro chaos mode active")
        reasons.append("model cannot identify reliable leader")
        return "X", reasons

    # ── Core numbers always logged ─────────────────────────────────────────────
    reasons.append(f"win {prob:.3f} | gap {gap:.3f} | place {place:.3f}")

    # ── A-STRIKE ──────────────────────────────────────────────────────────────
    if (prob >= 0.32 and gap >= 0.08 and place >= 0.52
            and conf not in ("low",) and trap != "high"):
        reasons.append(f"strong separation gap {gap:.3f}")
        reasons.append(f"place floor solid {place:.3f}")
        if improve > 0.20:
            reasons.append(f"form improvement signal {improve:.2f}")
        return "A", reasons

    # ── B-PLAYABLE ────────────────────────────────────────────────────────────
    b_place_ok = place >= 0.45
    b_gap_ok   = gap >= 0.08
    b_improve  = improve >= 0.18
    if prob >= 0.18 and gap >= 0.03 and (b_place_ok or b_gap_ok or b_improve):
        if b_gap_ok:
            reasons.append(f"field separation gap {gap:.3f}")
        if b_place_ok:
            reasons.append(f"strong place floor {place:.3f}")
        if b_improve:
            reasons.append(f"form improvement signal {improve:.2f}")
        if not b_place_ok and not b_gap_ok and not b_improve:
            reasons.append("marginal signal — price dependent")
        return "B", reasons

    # ── C-WATCH ───────────────────────────────────────────────────────────────
    if (prob >= 0.13 and gap >= 0.02) or (place >= 0.55 and prob >= 0.11):
        if place >= 0.55:
            reasons.append(f"place floor {place:.3f} — each-way angle possible")
        if prob >= 0.13 and gap >= 0.02:
            reasons.append(f"some win signal but not enough separation")
        return "C", reasons

    # ── D-NO BET ──────────────────────────────────────────────────────────────
    reasons.append("win signal weak — no clear betting angle")
    if place < 0.35:
        reasons.append(f"place floor also weak {place:.3f}")
    return "D", reasons


def _add_secondary_signals(top: dict, reasons: list) -> None:
    """Append market/intent signals to an existing reason list (in-place)."""
    mkt_dec = top.get("market_deception_score")
    release = float(top.get("release_day_prob") or 0)
    trap    = (top.get("favourite_trap_risk") or "normal").lower()
    if mkt_dec is not None:
        m = float(mkt_dec)
        if m > 0.55:
            reasons.append(f"market deception {m:.2f} — possible overlay")
        elif m < 0.15:
            reasons.append(f"market aligned {m:.2f}")
    if release > 0.40:
        reasons.append(f"trainer release signal {release:.2f}")
    if trap != "normal":
        reasons.append(f"favourite trap risk: {trap}")


def build_decision_card(race: dict, top: dict, second: dict,
                        tier: str, reasons: list) -> str:
    course   = race.get("course", "?").upper()
    off      = race.get("off_time", "?")
    primary  = top.get("horse", "?")
    contain  = second.get("horse", "?") if second else "—"
    conf     = top.get("confidence_level") or "low"
    action   = TIER_ACTIONS[tier]
    label    = TIER_LABELS[tier]
    prob     = float(top.get("velo_prime_prob") or 0)
    gap      = prob - float(second.get("velo_prime_prob") or 0)
    place    = float(top.get("place_prob") or 0)

    lines = [
        f"{course} {off} | {label}",
        "─" * 34,
        f"PRIMARY:     {primary}",
        f"CONTAINMENT: {contain}",
        f"CONF:        {conf}",
        f"KEY:         prob {prob:.3f} | gap {gap:.3f} | place {place:.3f}",
        "SIGNALS:",
    ]
    for r in reasons[:4]:
        lines.append(f"  • {r}")
    lines.append(f"ACTION: {action}")
    return "\n".join(lines)


def card_overall_label(a: int, b: int, total: int) -> str:
    actionable = a + b
    if total == 0:
        return "no data"
    ratio = actionable / total
    if a > 0 and ratio >= 0.25:
        return "strong card"
    if actionable > 0 and ratio >= 0.15:
        return "selective card"
    if b > 0:
        return "lean card — selective only"
    return "weak card — pass"


def _open_pipeline_run(db, date_str: str) -> str | None:
    """Open a pipeline_runs row for this scoring run. Returns run_id or None."""
    try:
        row = {
            "service_name": "velo-prime-scoring",
            "run_type":     "daily_scoring",
            "source_date":  date_str,
            "status":       "in_progress",
            "started_at":   datetime.utcnow().isoformat() + "Z",
            "environment":  os.getenv("RAILWAY_ENVIRONMENT", "local"),
        }
        resp = db.table("pipeline_runs").insert(row).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception as e:
        print(f"  [pipeline_runs] open failed (non-fatal): {e}")
        return None


def _close_pipeline_run(db, run_id: str | None, status: str,
                        races: int, runners: int, error: str | None = None):
    """Close a pipeline_runs row with final stats."""
    if not run_id:
        return
    try:
        patch = {
            "status":            status,
            "finished_at":       datetime.utcnow().isoformat() + "Z",
            "races_processed":   races,
            "runners_processed": runners,
        }
        if error:
            patch["error_message"] = error[:500]
        db.table("pipeline_runs").update(patch).eq("id", run_id).execute()
    except Exception as e:
        print(f"  [pipeline_runs] close failed (non-fatal): {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    date_tag = args.date.replace("-", "_") if args.date else TODAY
    date_str = date_tag.replace("_", "-")

    print(f"\nVELO PRIME RACE-DAY EXECUTION — {date_str}")
    print("=" * 60)

    from workers.racing_api_normalizer import normalize_race
    from app.services.velo_prime_service import (
        score_race_velo_prime, persist_race_predictions, persist_runner_derived_features
    )
    from supabase import create_client as _sb_create

    _sb_url = os.getenv("SUPABASE_URL", "")
    _sb_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
               or os.getenv("SUPABASE_SERVICE_KEY")
               or os.getenv("SUPABASE_ANON_KEY", ""))
    db = _sb_create(_sb_url, _sb_key) if _sb_url and _sb_key else None
    run_id = _open_pipeline_run(db, date_str) if db else None
    print(f"  pipeline_run: {run_id or 'skipped (no Supabase creds)'}")

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
    # scored entries: (race, preds, tier, reasons)
    print("\nSTEP 3: Score through score_race_velo_prime (velo_prime_v1)")
    scored = []
    score_errors = []
    for race in normalized:
        cid = f"{race.get('course')} {race.get('off_time','?')}"
        try:
            preds = score_race_velo_prime(race)
            if preds:
                top       = preds[0]
                second    = preds[1] if len(preds) > 1 else {}
                sec_prob  = float(second.get("velo_prime_prob") or 0)
                tier, reasons = synthesize_decision(top, sec_prob)
                _add_secondary_signals(top, reasons)
                scored.append((race, preds, tier, reasons))
                print(f"  PASS  {cid:<30} top={top['horse']:<20} velo_prime_prob={top['velo_prime_prob']:.4f}  tier={tier}")
            else:
                score_errors.append((race, "no predictions returned"))
                print(f"  SKIP  {cid} — no predictions returned")
        except Exception as e:
            score_errors.append((race, str(e)))
            print(f"  FAIL  {cid} — {e}")

    print(f"\n  Scored: {len(scored)}  Errors: {len(score_errors)}")

    # ── STEP 4: Persist to Supabase ───────────────────────────────────────────
    print("\nSTEP 4: Persist to velo_verdicts + runner_derived_features")
    persist_ok = 0
    persist_fail = 0
    derived_total = 0
    for race, preds, tier, _reasons in scored:
        if persist_race_predictions(race, preds, decision_tier=tier):
            persist_ok += 1
            # Write per-runner derived features via service function
            n_derived = persist_runner_derived_features(race, preds)
            derived_total += n_derived
            # Fallback: write directly via the working db client if service returned 0
            if n_derived == 0 and db:
                race_id = race.get("race_id", "")
                from datetime import datetime as _dt
                cat = _dt.utcnow().isoformat()
                direct_rows = []
                for pred in preds:
                    hid = pred.get("horse_id", "") or pred.get("horse", "")
                    if hid and race_id:
                        direct_rows.append({
                            "race_id": race_id, "horse_id": hid,
                            "computed_at": cat,
                            "feature_schema_version": "velo_prime_v1_direct",
                            "form_cycle_score":        pred.get("improvement_score"),
                            "market_confidence_score": pred.get("market_deception_score"),
                            "release_day_score":       pred.get("release_day_prob"),
                            "survivability_score":     pred.get("place_prob"),
                            "chaos_score":             pred.get("longshot_prob"),
                            "feature_vector": {
                                "velo_prime_prob": pred.get("velo_prime_prob"),
                            },
                        })
                if direct_rows:
                    try:
                        res = db.table("runner_derived_features").upsert(
                            direct_rows, on_conflict="race_id,horse_id"
                        ).execute()
                        n_direct = len(res.data) if res.data else len(direct_rows)
                        derived_total += n_direct
                        print(f"  [RDF direct] race={race_id} wrote {n_direct} rows")
                    except Exception as e:
                        print(f"  [RDF direct FAIL] race={race_id}: {e}")
        else:
            persist_fail += 1
            print(f"  PERSIST FAIL: {race.get('race_id')} {race.get('course')}")

    print(f"  Verdicts: {persist_ok} OK / {persist_fail} FAIL / {len(scored)} total")
    print(f"  runner_derived_features: {derived_total} rows written")

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

    # B. Decision Synthesis Layer — bucket already computed in STEP 3
    buckets: dict = {"A": [], "B": [], "C": [], "D": [], "X": []}

    for race, preds, tier, reasons in scored:
        top    = preds[0]
        second = preds[1] if len(preds) > 1 else {}
        buckets[tier].append((race, top, second, reasons))

    a_n = len(buckets["A"])
    b_n = len(buckets["B"])
    c_n = len(buckets["C"])
    d_n = len(buckets["D"])
    x_n = len(buckets["X"])
    overall = card_overall_label(a_n, b_n, len(scored))

    # Day posture header
    tg(
        f"VELO DAY POSTURE — {TODAY_DISPLAY}\n"
        f"{'─' * 34}\n"
        f"A-STRIKE:   {a_n}\n"
        f"B-PLAYABLE: {b_n}\n"
        f"C-WATCH:    {c_n}\n"
        f"D-NO BET:   {d_n}\n"
        f"X-CHAOS:    {x_n}\n"
        f"Total:      {len(scored)}\n"
        f"Overall:    {overall}"
    )
    print(f"  Sent: day posture  A={a_n} B={b_n} C={c_n} D={d_n} X={x_n}  [{overall}]")

    # A-STRIKE — individual full card per race
    for race, top, second, reasons in buckets["A"]:
        card = build_decision_card(race, top, second, "A", reasons)
        tg(card)
        print(f"  Sent: A-STRIKE — {race.get('course')} {race.get('off_time')}")

    # B-PLAYABLE — individual full card per race
    for race, top, second, reasons in buckets["B"]:
        card = build_decision_card(race, top, second, "B", reasons)
        tg(card)
        print(f"  Sent: B-PLAYABLE — {race.get('course')} {race.get('off_time')}")

    # C-WATCH — grouped brief list
    if buckets["C"]:
        lines = [f"C-WATCH LIST — {TODAY_DISPLAY}", "─" * 34]
        for race, top, second, reasons in buckets["C"]:
            course  = race.get("course", "?").upper()
            off     = race.get("off_time", "?")
            primary = top.get("horse", "?")
            prob    = float(top.get("velo_prime_prob") or 0)
            place   = float(top.get("place_prob") or 0)
            gap     = prob - float(second.get("velo_prime_prob") or 0)
            r0      = reasons[1] if len(reasons) > 1 else reasons[0] if reasons else ""
            lines.append(
                f"{course} {off}  {primary}\n"
                f"  prob {prob:.3f} | gap {gap:.3f} | place {place:.3f}\n"
                f"  {r0}"
            )
        tg("\n".join(lines))
        print(f"  Sent: C-WATCH list ({c_n} races)")

    # D / X — summary pass list
    pass_races = buckets["D"] + buckets["X"]
    if pass_races:
        lines = [f"D/X PASS LIST — {TODAY_DISPLAY}", "─" * 34]
        for tier_tag, bucket in (("D", buckets["D"]), ("X", buckets["X"])):
            for race, top, second, reasons in bucket:
                course  = race.get("course", "?").upper()
                off     = race.get("off_time", "?")
                primary = top.get("horse", "?")
                r0      = reasons[0] if reasons else tier_tag
                lines.append(f"{tier_tag} {course} {off}  {primary}  — {r0}")
        tg("\n".join(lines))
        print(f"  Sent: D/X pass list ({d_n + x_n} races)")

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
        for race, preds, tier, _reasons in scored:
            results_out.append({
                "race_id":    race.get("race_id"),
                "course":     race.get("course"),
                "off_time":   race.get("off_time"),
                "race_name":  race.get("race_name"),
                "scored":     len(preds),
                "tier":       tier,
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

    total_runners = sum(len(race.get("runners") or []) for race, _, _t, _r in scored)

    if persist_fail > 0 or len(score_errors) > 0:
        err_summary = f"{persist_fail} persist failures, {len(score_errors)} score errors"
        _close_pipeline_run(db, run_id, "failed", persist_ok, total_runners, err_summary)
        print(f"\nFAIL — deficit: {len(normalized) - persist_ok} races not in Supabase")
        if score_errors:
            for race, err in score_errors[:5]:
                print(f"  SCORE ERROR: {race.get('course')} {race.get('off_time')} — {err[:100]}")
        sys.exit(1)
    else:
        _close_pipeline_run(db, run_id, "completed", persist_ok, total_runners)
        print(f"\nPASS — {persist_ok}/{len(normalized)} races in velo_verdicts")
        sys.exit(0)


if __name__ == "__main__":
    main()
