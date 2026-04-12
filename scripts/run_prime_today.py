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
import urllib.error
from urllib.parse import urlencode
from datetime import datetime, timedelta
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


def tg(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print(f"  [TG SKIP — no token/chat]: {text[:80]}")
        return False
    try:
        body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                print(f"  [TG FAIL — HTTP {resp.status}]: {text[:60]}")
                return False
        return True
    except urllib.error.HTTPError as e:
        print(f"  [TG FAIL — HTTP {e.code} {e.reason}]: {text[:60]}")
        return False
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
#             OR  (longshot > 0.35 AND sp_dec >= 10)  (SP-gated outsider pressure)
#             OR  macro_chaos_mode == True
#
#   NOTE: gap=0.000 alone does NOT trigger X if place >= 0.40.
#         That becomes D-NO BET or C-WATCH depending on prob/place.
#
# A-STRIKE : prob >= 0.32  AND  gap >= 0.08  AND  place >= 0.52
#             AND  conf != 'low'  AND  trap != 'high'
#
# B-PLAYABLE: prob >= 0.15  AND  gap >= 0.03  AND  conf != 'low'
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


def _apply_archetype(
    top: dict,
    preds: list[dict],
    tier: str,
    sec_prob: float,
) -> None:
    """
    Classify race archetype and store result on top dict.

    Runs after TIE v3 gate so it can see the final tier.
    Stores archetype fields directly on top so they persist with the verdict
    and appear in build_decision_card.
    """
    try:
        from src.intelligence.race_archetypes import RaceArchetypeClassifier
        prob       = float(top.get("velo_prime_prob") or 0)
        separation = prob - float(sec_prob or 0)
        archetype  = RaceArchetypeClassifier().classify(top, preds, tier, separation)
        top.update(archetype.to_dict())
    except Exception as e:
        import logging
        logging.getLogger("velo.run_prime").warning("Archetype classification failed: %s", e)


def _apply_tie_v3_gate(
    top: dict,
    tier: str,
    reasons: list[str],
    preds: list[dict],
) -> tuple[str, list[str]]:
    """
    Apply TIE v3 conviction gate after synthesize_decision().

    Signal counts are pre-computed in score_race_velo_prime() where live
    doctrine features (days_since_run, sp_rank, trainer_timing_score etc.)
    are available. This function applies the policy decisions now that
    current_tier is known.

    Upgrade path : top pick tie_gate_signal_count >= MIN_SIGNALS_FOR_UPGRADE
                   AND tier in (C, D) → promote to B or C
    EW path      : any runner with signal_count >= MIN_SIGNALS_FOR_EW_FLAG
                   AND SP > LONGSHOT_SP_THRESHOLD AND not fav → annotate

    Does NOT alter velo_prime_prob or ensemble ranking.
    """
    try:
        from src.intelligence.tie_v3_gate import (
            MIN_SIGNALS_FOR_UPGRADE,
            MIN_SIGNALS_FOR_EW_FLAG,
            LONGSHOT_SP_THRESHOLD,
        )

        # ── Upgrade path — top pick only ──────────────────────────────────────
        n       = top.get("tie_gate_signal_count", 0)
        signals = top.get("tie_gate_signals", [])
        sp_top  = float(top.get("sp_dec") or 0)
        is_fav  = bool(top.get("is_fav"))

        top["tie_gate_fires"]        = False
        top["tie_gate_tier_upgrade"] = None
        top["tie_gate_ew_flag"]      = False

        if n >= MIN_SIGNALS_FOR_UPGRADE and tier in ("C", "D"):
            upgraded = "B" if tier == "C" else "C"
            top["tie_gate_fires"]        = True
            top["tie_gate_tier_upgrade"] = upgraded
            reasons.append(
                f"TIE v3: {n} intent signals → upgrade {tier}→{upgraded} "
                f"[{', '.join(signals)}]"
            )
            tier = upgraded

        # ── EW path — top pick ────────────────────────────────────────────────
        if (n >= MIN_SIGNALS_FOR_EW_FLAG
                and sp_top > LONGSHOT_SP_THRESHOLD
                and not is_fav):
            top["tie_gate_fires"]   = True
            top["tie_gate_ew_flag"] = True
            if not top.get("tie_gate_tier_upgrade"):
                reasons.append(
                    f"TIE v3 EW: {n} signals + SP {sp_top:.1f} → each-way angle"
                )

        # ── EW scan — rest of field (observability only, no tier change) ──────
        for runner in preds[1:]:
            rn  = runner.get("tie_gate_signal_count", 0)
            rsp = float(runner.get("sp_dec") or 0)
            rfav = bool(runner.get("is_fav"))
            runner["tie_gate_fires"]   = False
            runner["tie_gate_ew_flag"] = (
                rn >= MIN_SIGNALS_FOR_EW_FLAG
                and rsp > LONGSHOT_SP_THRESHOLD
                and not rfav
            )
            if runner["tie_gate_ew_flag"]:
                runner["tie_gate_fires"] = True

    except Exception as e:
        import logging
        logging.getLogger("velo.run_prime").warning("TIE v3 gate policy failed: %s", e)

    return tier, reasons


def synthesize_decision(top: dict, second_prob: float, field_size: int = 0) -> tuple[str, list[str]]:
    """
    Returns (tier, reasons) where tier is A/B/C/D/X.
    Uses full available signal stack from velo_prime_v1 output.

    Parameters
    ----------
    top : dict
        Highest-ranked runner from score_race_velo_prime output.
    second_prob : float
        velo_prime_prob of the second-ranked runner (0.0 if no second runner).
    field_size : int
        Number of runners in the race (len(preds)).  Required to guard against
        single-runner races where gap == prob, making every gap threshold trivial.
    """
    prob      = float(top.get("velo_prime_prob") or 0)
    place     = float(top.get("place_prob") or 0)
    longshot  = float(top.get("longshot_prob") or 0)
    sp_dec    = float(top.get("sp_dec") or 0)
    improve   = float(top.get("improvement_score") or 0)
    mkt_dec   = top.get("market_deception_score")
    release   = float(top.get("release_day_prob") or 0)
    # macro_chaos_mode may be None (failed) or bool (known). Treat None as unknown → force chaos.
    _chaos_raw = top.get("macro_chaos_mode")
    chaos_m   = bool(_chaos_raw) if _chaos_raw is not None else True
    trap      = (top.get("favourite_trap_risk") or "normal").lower()
    conf      = (top.get("confidence_level") or "low").lower()
    gap       = prob - second_prob

    # ── Pre-condition blockers ────────────────────────────────────────────────
    # These two checks run before any tier logic and force X-CHAOS hard.

    # 1. Single-runner race: gap == prob is mathematically guaranteed —
    #    every A/B gap threshold becomes trivially true. Model has no real signal.
    if field_size == 1:
        return "X", [f"single-runner race (field_size=1) — gap is meaningless, no model signal"]

    # 2. Horse state tagging failed: doctrine signals (days_since_run, trainer timing,
    #    etc.) are absent. A/B decisions require horse state to be valid.
    if top.get("horse_state_failed"):
        return "X", ["horse state tagging failed — required signals absent, cannot evaluate tier"]

    # confidence_level is assigned pre-normalization in the ensemble, then the field
    # normalization step raises the top horse's prob without updating the label.
    # Recompute from the already-normalized prob so A/B gates see the real signal.
    # Boundary set at 0.15 to match the B-PLAYABLE win prob floor.
    eff_conf = "high" if prob >= 0.45 else "normal" if prob >= 0.15 else "low"

    # Longshot gate: only meaningful when horse is genuinely a longshot (SP >= 10).
    # The specialist longshot model scores all runners but was trained on SP >= 10 data.
    # Without the SP guard, short-priced favourites with high longshot_score trigger X.
    longshot_trigger = longshot > 0.35 and sp_dec >= 10.0

    reasons = []

    # ── X-CHAOS ───────────────────────────────────────────────────────────────
    # Trigger X only when model is genuinely blind: flat field, no place floor,
    # outsider dominance (longshot SP-gated), or macro chaos.
    # gap=0 alone does NOT trigger X if place >= 0.40.
    #
    # Strong-signal escape: if the horse itself shows real edge (prob ≥ 0.18,
    # place ≥ 0.35), race-shape signals (tight gap, outsider pressure) should not
    # bury it in X-CHAOS. macro_chaos_mode is market-wide — it stays a hard block.
    strong_escape = prob >= 0.18 and place >= 0.35
    if (prob < 0.10
            or (gap < 0.015 and place < 0.40 and not strong_escape)
            or (longshot_trigger and not strong_escape)
            or chaos_m):
        if prob < 0.10:
            reasons.append(f"flat field — top prob {prob:.3f} below threshold")
        if gap < 0.015 and place < 0.40:
            reasons.append(f"no separation (gap {gap:.3f}) and weak place floor ({place:.3f})")
        if longshot_trigger:
            reasons.append(f"outsider pressure — longshot signal {longshot:.3f} (SP {sp_dec:.1f})")
        if chaos_m:
            reasons.append("macro chaos mode active")
        reasons.append("model cannot identify reliable leader")
        return "X", reasons

    # ── Core numbers always logged ─────────────────────────────────────────────
    reasons.append(f"win {prob:.3f} | gap {gap:.3f} | place {place:.3f}")

    # ── A-STRIKE ──────────────────────────────────────────────────────────────
    if (prob >= 0.32 and gap >= 0.08 and place >= 0.52
            and eff_conf not in ("low",) and trap != "high"):
        reasons.append(f"strong separation gap {gap:.3f}")
        reasons.append(f"place floor solid {place:.3f}")
        if improve > 0.20:
            reasons.append(f"form improvement signal {improve:.2f}")
        return "A", reasons

    # ── B-PLAYABLE ────────────────────────────────────────────────────────────
    b_place_ok = place >= 0.45
    b_gap_ok   = gap >= 0.08
    b_improve  = improve >= 0.18
    if (prob >= 0.15 and gap >= 0.03 and eff_conf not in ("low",)
            and (b_place_ok or b_gap_ok or b_improve)):
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
    arch = top.get("race_archetype")
    if arch:
        arch_conf  = (top.get("archetype_confidence") or "?")[0].upper()
        arch_style = top.get("archetype_bet_style") or ""
        trap_mark  = " ⚠ TRAP" if top.get("archetype_trap_flag") else ""
        lines.append(f"ARCHETYPE: [{arch}:{arch_conf}]{trap_mark}  {arch_style}")
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


# ── RPD-C evidence derivation ─────────────────────────────────────────────────

def _derive_rpd_evidence(runner: dict, race: dict) -> tuple[list, bool, bool]:
    """
    Derive RPD-C evidence codes from a normalized runner dict.
    Returns (evidence_codes, market_shortening, won_last_time).

    Evidence is derived conservatively — only from clearly available fields.
    Missing or ambiguous data defaults to H (Honest) via engine fallback.
    market_shortening is always False here (no intraday movement data available).
    """
    evidence = []

    # Form string — only digit characters
    form_raw = str(runner.get("form", "") or "")
    form_digits = [c for c in form_raw if c.isdigit()]

    # won_last_time: last meaningful figure is "1"
    won_last_time = bool(form_digits) and form_digits[-1] == "1"

    # no form reference: fewer than 2 runs on record → S evidence
    if len(form_digits) < 2:
        evidence.append("no_form_reference")

    # declining_positions: last 3 non-zero positions strictly worsening → E evidence
    if len(form_digits) >= 3:
        last3 = [int(d) for d in form_digits[-3:] if d != "0"]
        if len(last3) == 3 and last3[0] < last3[1] < last3[2]:
            evidence.append("declining_positions")

    # consistent_form: last 4 non-zero positions within a 2-position band → H evidence
    if len(form_digits) >= 4:
        last4 = [int(d) for d in form_digits[-4:] if d != "0"]
        if last4 and (max(last4) - min(last4)) <= 2:
            evidence.append("consistent_form")

    # Days since last run (if populated by normalizer)
    days = runner.get("days_since_last_run")
    if days is not None:
        try:
            days = int(days)
            if days >= 60:
                evidence.append("long_absence")      # P evidence
            elif days < 10:
                evidence.append("quick_turnaround")  # E evidence
        except (ValueError, TypeError):
            pass

    # Gear additions: visor, cheekpieces, tongue-tie, hood → T evidence
    gear = str(runner.get("gear", "") or "").lower()
    if any(kw in gear for kw in ["visor", "cheek", "tongue", "hood", "blinkers"]):
        evidence.append("gear_additions")

    # Market volatility: very long price (20+) → S evidence
    try:
        odds = float(runner.get("best_odds_decimal") or 0)
        if odds >= 20.0:
            evidence.append("market_volatility")
    except (ValueError, TypeError):
        pass

    return evidence, False, won_last_time


def _open_pipeline_run(db, date_str: str) -> str | None:
    """Open a pipeline_runs row.

    Age-gate cleanup: any running row for this service + date older than 24h is
    closed as FAIL before inserting the new row.  Rows newer than 24h abort the
    new run (prevents duplicate concurrent runs).
    """
    SERVICE = "velo-prime-scoring"
    AGE_GATE_HOURS = 24
    now = datetime.utcnow()

    try:
        # Find existing running rows scoped to this service + date
        try:
            existing = db.table("pipeline_runs").select(
                "id, started_at"
            ).eq("service_name", SERVICE).eq(
                "source_date", date_str
            ).eq("run_state", "running").execute()

            for row in (existing.data or []):
                try:
                    started = datetime.fromisoformat(row["started_at"].rstrip("Z"))
                except Exception:
                    started = now - timedelta(hours=AGE_GATE_HOURS + 1)  # treat as stale

                age_hours = (now - started).total_seconds() / 3600
                if age_hours >= AGE_GATE_HOURS:
                    # Stale — close as FAIL and allow new run
                    db.table("pipeline_runs").update({
                        "run_state":     "completed",
                        "status":        "FAIL",
                        "finished_at":   now.isoformat() + "Z",
                        "error_message": f"Closed by age gate ({age_hours:.1f}h stale): superseded by new run",
                    }).eq("id", row["id"]).execute()
                    print(f"  [pipeline_runs] age-gate closed stale run {row['id']} ({age_hours:.1f}h)")
                else:
                    # Recent running row — abort to prevent duplicate
                    print(f"  [pipeline_runs] run already running (id={row['id']}, age={age_hours:.1f}h). Aborting open.")
                    return None
        except Exception as e:
            print(f"  [pipeline_runs] stale-run cleanup failed (non-fatal): {e}")

        trigger_src = os.getenv("TRIGGER_SOURCE", "manual") or "manual"
        env_str = os.getenv("RAILWAY_ENVIRONMENT", "local")
        row = {
            "service_name":  SERVICE,
            "run_type":      "daily_scoring",
            "source_date":   date_str,
            "run_state":     "running",
            "status":        None,  # explicit NULL overrides DB DEFAULT 'in_progress'
            "trigger_source": trigger_src,
            "started_at":    now.isoformat() + "Z",
            "environment":   env_str,
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
            "run_state":         "completed",
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

    # ── PREFLIGHT GATE — must pass before anything else runs ─────────────────
    print("\nPREFLIGHT")
    print("-" * 40)
    from src.preflight import preflight_or_die
    pf_result = preflight_or_die(tg_fn=tg)   # exits with sys.exit(1) on FAIL
    print(f"  Status: {pf_result.status}")
    print("-" * 40)
    # ─────────────────────────────────────────────────────────────────────────

    from workers.racing_api_normalizer import normalize_race
    from app.services.velo_prime_service import (
        score_race_velo_prime, persist_race_predictions
    )
    from supabase import create_client as _sb_create
    from src.rpd import RPDv2Engine, RPDTag

    _sb_url = os.getenv("SUPABASE_URL", "")
    _sb_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
               or os.getenv("SUPABASE_SERVICE_KEY")
               or os.getenv("SUPABASE_ANON_KEY", ""))
    db = _sb_create(_sb_url, _sb_key) if _sb_url and _sb_key else None
    run_id = _open_pipeline_run(db, date_str) if db else None
    if not db:
        print("  pipeline_run: SKIPPED — no Supabase creds (monitoring blind this run) ⚠")
    elif not run_id:
        print("  pipeline_run: OPEN FAILED — monitoring blind for this run ⚠")
    else:
        print(f"  pipeline_run: {run_id}")

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

    # ── STEP 2b: UK/IRE jurisdiction filter ──────────────────────────────
    # Jurisdiction is resolved canonically by normalize_race() via _resolve_jurisdiction().
    # Raw API region "GB" → "uk", "IRE" → "ire", anything else → "other"/"unknown".
    # We score only UK and Irish racing. France/HK/US are out of scope for VÉLØ.
    pre_filter = len(normalized)
    normalized = [r for r in normalized if r.get("jurisdiction") in ("uk", "ire")]
    filtered_out = pre_filter - len(normalized)
    if filtered_out:
        print(f"  Jurisdiction filter: kept {len(normalized)} UK/IRE races, dropped {filtered_out} other/unknown")
    else:
        print(f"  Jurisdiction filter: {len(normalized)} UK/IRE races (no other jurisdictions in feed)")

    # ── STEP 3: Score through REAL PRIME path ─────────────────────────────────
    # scored entries: (race, preds, tier, reasons)
    print("\nSTEP 3: Score through score_race_velo_prime (velo_prime_v1)")

    # Sentient bridge — Phase 1 (audit only, no scoring change)
    _sentient_state = None
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        _g = SentientLoopbackEngine()
        _raw_state = _g.get_evolutionary_state()
        _source = "disk"
        # Detect if state was restored from Supabase (G logs this; we probe total_races_observed)
        if _raw_state.get("total_races_observed", 0) == 0:
            # Fresh default — may still be disk or supabase, mark as unknown
            _source = "unknown"
        _sentient_state = {**_raw_state, "_source": _source}
        print(
            f"  [sentient] G state loaded — source={_source} "
            f"races_observed={_raw_state.get('total_races_observed', 0)} "
            f"aggression={_raw_state.get('appetite_state', {}).get('aggression_level', '?')}"
        )
    except Exception as _g_err:
        print(f"  [sentient] G state load failed (non-fatal, scoring unaffected): {_g_err}")
        _sentient_state = None

    # RPD-C engine — passive metadata layer, does not alter scores or ranking
    _rpd_db = str(ROOT / "data" / "rpd_tags.db")
    rpd_engine = RPDv2Engine(db_path=_rpd_db)
    print(f"  RPD-C engine: ready (db={_rpd_db})")

    scored = []
    score_errors = []
    for race in normalized:
        cid = f"{race.get('course')} {race.get('off_time','?')}"
        try:
            preds = score_race_velo_prime(race, sentient_state=_sentient_state)
            if preds:
                # RPD-C tagging — passive metadata only, no score/rank mutation
                runner_map = {
                    r.get("horse_name", ""): r
                    for r in race.get("runners", [])
                }
                for pred in preds:
                    raw_runner = runner_map.get(pred.get("horse", ""), {})
                    rpd_evidence, rpd_mkt_short, rpd_won_last = _derive_rpd_evidence(
                        raw_runner, race
                    )
                    rpd_suggestion = rpd_engine.suggest_tag(
                        pred.get("horse", ""),
                        rpd_evidence,
                        market_shortening=rpd_mkt_short,
                        won_last_time=rpd_won_last,
                    )
                    pred["rpd_tag"]            = rpd_suggestion.suggested_tag.value
                    pred["rpd_confidence"]     = rpd_suggestion.confidence
                    pred["rpd_evidence_codes"] = rpd_evidence

                top       = preds[0]
                second    = preds[1] if len(preds) > 1 else {}
                sec_prob  = float(second.get("velo_prime_prob") or 0)
                tier, reasons = synthesize_decision(top, sec_prob, field_size=len(preds))
                tier, reasons = _apply_tie_v3_gate(top, tier, reasons, preds)
                _apply_archetype(top, preds, tier, sec_prob)
                _add_secondary_signals(top, reasons)
                scored.append((race, preds, tier, reasons))
                gate_note  = f" [TIE^{top.get('tie_gate_tier_upgrade','')}]" if top.get("tie_gate_tier_upgrade") else ""
                arch_note  = f" [{top.get('race_archetype','?')}:{(top.get('archetype_confidence') or '?')[0].upper()}]"
                print(f"  PASS  {cid:<30} top={top['horse']:<20} velo_prime_prob={top['velo_prime_prob']:.4f}  tier={tier}{gate_note}{arch_note}")
            else:
                score_errors.append((race, "no predictions returned"))
                print(f"  SKIP  {cid} — no predictions returned")
        except Exception as e:
            score_errors.append((race, str(e)))
            print(f"  FAIL  {cid} — {e}")

    print(f"\n  Scored: {len(scored)}  Errors: {len(score_errors)}")

    # ── STEP 4: Persist to Supabase ───────────────────────────────────────────
    print("\nSTEP 4: Persist to velo_verdicts")
    persist_ok = 0
    persist_fail = 0
    for race, preds, tier, _reasons in scored:
        if persist_race_predictions(race, preds, decision_tier=tier):
            persist_ok += 1
        else:
            persist_fail += 1
            print(f"  PERSIST FAIL: {race.get('race_id')} {race.get('course')}")

    print(f"  Verdicts: {persist_ok} OK / {persist_fail} FAIL / {len(scored)} total")

    # ── STEP 5: Build Telegram output ─────────────────────────────────────────
    print("\nSTEP 5: Send to Telegram")

    # A. Pre-flight report — reflects actual preflight result
    pf_lines = [f"  {c.name}: {'OK' if c.passed else c.detail}"
                for c in pf_result.checks]
    tg(
        f"VELO PRE-FLIGHT REPORT — {TODAY_DISPLAY}\n"
        f"repo:       elpresidentepiff/velo-oracle-prime\n"
        f"racecards:  {racecard_source}\n"
        + "\n".join(pf_lines) + "\n"
        f"STATUS:     {pf_result.status}"
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
    persist_status = "PASS" if (persist_fail == 0 and len(score_errors) == 0) else "FAIL"
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

    if persist_fail > 0 and persist_ok == 0:
        # Total failure — nothing persisted
        err_summary = f"{persist_fail} persist failures, {len(score_errors)} score errors"
        _close_pipeline_run(db, run_id, "FAIL", persist_ok, total_runners, err_summary)
        print(f"\nFAIL — 0/{len(normalized)} races in velo_verdicts")
        tg(
            f"VELO ALERT — FAIL — {TODAY_DISPLAY}\n"
            f"Persist failures: {persist_fail}\n"
            f"Score errors:     {len(score_errors)}\n"
            f"Races in DB:      0 / {len(normalized)}\n"
            f"Status:           FAIL — investigate immediately"
        )
        if score_errors:
            for race, err in score_errors[:5]:
                print(f"  SCORE ERROR: {race.get('course')} {race.get('off_time')} — {err[:100]}")
        sys.exit(1)
    elif persist_fail > 0:
        # Partial run — some persisted, some failed → DEGRADED
        err_summary = f"{persist_fail} persist failures, {len(score_errors)} score errors"
        _close_pipeline_run(db, run_id, "DEGRADED", persist_ok, total_runners, err_summary)
        print(f"\nDEGRADED — {persist_ok}/{len(normalized)} races in velo_verdicts ({persist_fail} failed)")
        tg(
            f"VELO ALERT — DEGRADED — {TODAY_DISPLAY}\n"
            f"Persist failures: {persist_fail}\n"
            f"Score errors:     {len(score_errors)}\n"
            f"Races in DB:      {persist_ok} / {len(normalized)}\n"
            f"Status:           DEGRADED — partial truth only"
        )
        if score_errors:
            for race, err in score_errors[:5]:
                print(f"  SCORE ERROR: {race.get('course')} {race.get('off_time')} — {err[:100]}")
        sys.exit(1)
    else:
        _close_pipeline_run(db, run_id, "PASS", persist_ok, total_runners)
        print(f"\nPASS — {persist_ok}/{len(normalized)} races in velo_verdicts")
        sys.exit(0)


if __name__ == "__main__":
    main()
