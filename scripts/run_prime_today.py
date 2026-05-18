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

import argparse
import base64
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.runtime_env import (  # noqa: E402
    load_optional_env_file,
    resolve_runtime_environment,
    resolve_supabase_service_key,
    resolve_supabase_url,
    utc_now,
)
from runtime_truth_support import append_telegram_event, get_commit_sha  # noqa: E402

log = logging.getLogger("velo.run_prime")

from src.velo.racing_api_shadow_enrichment import (  # noqa: E402
    append_to_forward_ledger,
    compute_shadow_enrichment,
    load_enrichment_caches,
)

_ENRICHMENT_CACHES = None  # loaded once in _bootstrap_runtime
_SHADOW_LEDGER_PATH = ROOT / "data" / "racing_api_shadow_forward_ledger.csv"

TODAY = datetime.now().strftime("%Y_%m_%d")
TODAY_DISPLAY = datetime.now().strftime("%d %b %Y")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_TG_DATE = ""
_TG_SERVICE = "velo-prime-scoring"
_TG_NOTIFY_ENABLED = True

CANONICAL_ENDPOINT = "https://velo-oracle-production.up.railway.app"

RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"


# User-Agent required — Cloudflare blocks requests without it
def _racing_headers() -> dict[str, str]:
    racing_user = os.getenv("RACING_API_USERNAME", "")
    racing_pass = os.getenv("RACING_API_PASSWORD", "")
    return {
        "Authorization": "Basic " + base64.b64encode(f"{racing_user}:{racing_pass}".encode()).decode(),
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }


def _legacy_tg(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print(f"  [TG SKIP — no token/chat]: {text[:80]}")
        return False
    try:
        body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=body, headers={"Content-Type": "application/json"}
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


def tg(text: str, label: str = "generic") -> bool:
    preview = text.splitlines()[0] if text else ""
    sent = _legacy_tg(text)
    if _TG_DATE:
        append_telegram_event(
            date_str=_TG_DATE,
            service=_TG_SERVICE,
            event_type=label,
            sent=sent,
            notify_enabled=bool(TOKEN and CHAT_ID) and _TG_NOTIFY_ENABLED,
            message_preview=preview,
            error=None if sent else ("NO_TOKEN_OR_CHAT" if not TOKEN or not CHAT_ID else "SEND_FAILED"),
        )
    return sent


@dataclass
class RunPrimeOptions:
    date: str | None = None
    dry_run: bool = False
    notify: bool = True
    env_file: str | None = None


@dataclass
class RunPrimeResult:
    status: str
    exit_code: int
    date_str: str
    racecard_source: str = "unknown"
    races_fetched: int = 0
    races_normalized: int = 0
    races_scored: int = 0
    persist_ok: int = 0
    persist_fail: int = 0
    score_errors: int = 0
    notifications_enabled: bool = True
    persistence_enabled: bool = True


@dataclass
class PipelineRunOpenResult:
    run_id: str | None = None
    blocked_reason: str | None = None
    error: str | None = None


def _bootstrap_runtime(env_file: str | None = None, notify: bool = True) -> None:
    global TOKEN, CHAT_ID, RACING_USER, RACING_PASS, RACING_HEADERS, _SB_URL, _SB_KEY, _SB_HDRS, _ENRICHMENT_CACHES

    load_optional_env_file(env_file or ROOT / ".env")
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") if notify else ""
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") if notify else ""
    RACING_USER = os.getenv("RACING_API_USERNAME", "")
    RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
    RACING_HEADERS = {
        "Authorization": "Basic " + base64.b64encode(f"{RACING_USER}:{RACING_PASS}".encode()).decode(),
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    _SB_URL = resolve_supabase_url()
    _SB_KEY = resolve_supabase_service_key()
    _SB_HDRS = {
        "apikey": _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Accept": "application/json",
    }
    _ENRICHMENT_CACHES = load_enrichment_caches(_SB_URL, _SB_KEY)


def _load_rp_profile_as_racecards(date_str: str) -> list[dict]:
    """
    Build synthetic racecard list from the RP runner profile parquet.

    Fallback B in the racecard priority chain:
      A. cached racecard JSON  →  B. this function  →  C. live Racing API

    Produces minimal race dicts compatible with normalize_race() +
    score_race_velo_prime(). VP scores reflect RP-profile features only —
    no live market data, no Racing API enrichment. All races scored as "uk"
    jurisdiction (RP data is UK/IRE only; "GB" region passes both bands).

    Returns an empty list if no rows exist for date_str.
    Raises FileNotFoundError if the profile parquet is absent entirely.
    """
    import math

    import pandas as pd

    profile_path = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
    if not profile_path.exists():
        raise FileNotFoundError(f"RP profile not found: {profile_path}")

    rp = pd.read_parquet(profile_path)
    rp_today = rp[rp["race_date"].astype(str) == date_str].copy()
    if rp_today.empty:
        return []

    def _v(val):
        """Coerce pandas scalar to Python native, mapping NaN/NaT to None."""
        if val is None:
            return None
        try:
            if isinstance(val, float) and math.isnan(val):
                return None
        except Exception:
            pass
        return val

    races: list[dict] = []
    for race_id, group in rp_today.groupby("race_id"):
        first = group.iloc[0]

        runners = []
        for _, row in group.iterrows():
            last_run_raw = row.get("days_since_run")
            last_run = str(int(last_run_raw)) if pd.notna(last_run_raw) else None
            # Synthetic horse_id: RP profile has no Racing API horse_id (None).
            # Generate a stable derived ID so persist_race_predictions does not reject.
            # Use _norm_horse_name() to strip spaces/punctuation — must match the
            # normalisation used by scrape_results_atr.py and sigma's result lookup.
            # Bug introduced 1dc8d5b: used .lower() only, preserving spaces → mismatch.
            raw_hid = _v(row.get("horse_id"))
            if not raw_hid:
                horse_norm_val = _norm_horse_name(row.get("horse_norm") or row.get("horse") or "")
                raw_hid = f"RP_{horse_norm_val}" if horse_norm_val else None
            runners.append({
                "horse":      _v(row.get("horse")),
                "horse_id":   raw_hid,
                "ofr":        _v(row.get("current_or")),
                "rpr":        _v(row.get("current_rpr")),
                "ts":         _v(row.get("current_ts")),
                "trainer":    _v(row.get("trainer")),
                "trainer_id": _v(row.get("trainer_id")),
                "jockey":     _v(row.get("jockey")),
                "jockey_id":  _v(row.get("jockey_id")),
                "age":        _v(row.get("age")),
                "form":       _v(row.get("form_figures")),
                "draw":       _v(row.get("stall")),
                "headgear":   _v(row.get("headgear")),
                "last_run":   last_run,
                "spotlight":  _v(row.get("horse_comment")),
            })

        course = str(first.get("course") or "")
        races.append({
            "race_id":            str(race_id),
            "course":             course,
            "course_id":          course,
            "date":               date_str,
            "off_time":           str(first.get("off_time") or ""),
            "race_name":          str(first.get("race_info") or ""),
            "distance":           str(first.get("dist_text") or ""),
            "race_class":         str(first.get("class_band") or ""),
            "region":             "GB",
            "field_size":         len(runners),
            "runners":            runners,
            "_rp_profile_source": True,
        })

    return races


def load_racecards(date_tag: str, date_str: str) -> tuple[list, str]:
    """Return (races_list, source) where source is 'cache', 'rp_profile', or 'api'.

    Priority order:
      A. Local cache  (data/racecards_{date_tag}_standard.json)
      B. RP runner profile  (data/features/rp_runner_profile_latest.parquet)
         — produces partial VP scores; no live market data
      C. Live Racing API  (requires RACING_API_USERNAME + RACING_API_PASSWORD)

    The Racing API is only contacted when A and B are both unavailable.
    Saves the API response to cache as a best-effort local backup.
    """
    # A: local cache
    cache_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return races, "cache"

    # B: RP runner profile fallback
    try:
        rp_races = _load_rp_profile_as_racecards(date_str)
        if rp_races:
            print(f"  RP profile fallback: {len(rp_races)} synthetic racecards for {date_str}")
            return rp_races, "rp_profile"
        print(f"  RP profile fallback: no rows for {date_str} — proceeding to live API")
    except Exception as _rp_err:
        print(f"  RP profile fallback unavailable: {_rp_err}")

    # C: live Racing API
    if not RACING_USER or not RACING_PASS:
        raise RuntimeError(
            "No cached racecards, RP profile unavailable for this date, "
            "and RACING_API_USERNAME/PASSWORD not set — cannot fetch"
        )
    from datetime import date as _date
    _today = str(_date.today())
    if date_str == _today:
        qs = urlencode({"day": "today"})
    elif date_str > _today:
        qs = ""  # free/standard returns next available race day when no date given
    else:
        qs = urlencode({"date": date_str})
    url = f"{RACING_BASE}/racecards/standard" + (f"?{qs}" if qs else "")
    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    _creds = base64.b64encode(f"{RACING_USER}:{RACING_PASS}".encode()).decode()
    _req_obj = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {_creds}",
            "Accept": "application/json",
            "User-Agent": "VeloPrime/1.0",
        },
    )
    with urllib.request.urlopen(_req_obj, context=_ctx, timeout=30) as _resp:
        raw = json.loads(_resp.read())

    # Best-effort cache write — skipped silently on Railway ephemeral storage
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw, indent=2))
        print(f"  Saved to cache: {cache_path.name}")
    except Exception as e:
        print(f"  Cache write skipped: {e}")

    races = raw if isinstance(raw, list) else raw.get("racecards", [])
    return races, "api"


def _emit_daily_truth_packet(target_date: str, *, repair_local_archive: bool) -> None:
    """Best-effort daily truth packet emission after scoring completes."""
    try:
        from velo_daily_run_truth_watchdog import write_report

        report = write_report(target_date, repair_local_archive=repair_local_archive)
        print(f"  Daily truth packet: {Path(report['json_path']).name}")
    except Exception as exc:
        print(f"  Daily truth packet skipped: {exc}")


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


def effective_confidence(prob: float) -> str:
    """
    Recompute confidence from the final normalized velo_prime_prob.
    Must stay in sync with the boundary used in synthesize_decision().
    This is the canonical post-normalization label — use this for storage
    and display, not the raw ensemble label.
    """
    if prob >= 0.45:
        return "high"
    if prob >= 0.15:
        return "normal"
    return "low"


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

        prob = float(top.get("velo_prime_prob") or 0)
        separation = prob - float(sec_prob or 0)
        archetype = RaceArchetypeClassifier().classify(top, preds, tier, separation)
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
    # ── PLOT UPGRADE LOGIC ──────────────────────────────────────────────────
    pdf_intel = top.get("pdf_intel", {})
    plot_score = float(pdf_intel.get("plot_conviction", 0.0))
    or_delta = float(pdf_intel.get("or_delta_to_best_win", 0.0))

    if plot_score >= 0.85:
        if tier == "B":
            tier = "A"
            reasons.append(f"PLOT_UPGRADE:ELITE({plot_score:.2f})")
        elif tier == "C":
            tier = "B"
            reasons.append(f"PLOT_UPGRADE:STRONG({plot_score:.2f})")
    elif plot_score >= 0.70 and or_delta < 0:
        if tier == "C":
            tier = "B"
            reasons.append(f"PLOT_UPGRADE:INTENT({plot_score:.2f}|OR:{or_delta})")
    try:
        from src.intelligence.tie_v3_gate import (
            LONGSHOT_SP_THRESHOLD,
            MIN_SIGNALS_FOR_EW_FLAG,
            MIN_SIGNALS_FOR_UPGRADE,
        )

        # ── Upgrade path — top pick only ──────────────────────────────────────
        n = top.get("tie_gate_signal_count", 0)
        signals = top.get("tie_gate_signals", [])
        sp_top = float(top.get("sp_dec") or 0)
        is_fav = bool(top.get("is_fav"))

        top["tie_gate_fires"] = False
        top["tie_gate_tier_upgrade"] = None
        top["tie_gate_ew_flag"] = False

        if n >= MIN_SIGNALS_FOR_UPGRADE and tier in ("C", "D"):
            upgraded = "B" if tier == "C" else "C"
            top["tie_gate_fires"] = True
            top["tie_gate_tier_upgrade"] = upgraded
            reasons.append(f"TIE v3: {n} intent signals → upgrade {tier}→{upgraded} [{', '.join(signals)}]")
            tier = upgraded

        # ── EW path — top pick ────────────────────────────────────────────────
        if n >= MIN_SIGNALS_FOR_EW_FLAG and sp_top > LONGSHOT_SP_THRESHOLD and not is_fav:
            top["tie_gate_fires"] = True
            top["tie_gate_ew_flag"] = True
            if not top.get("tie_gate_tier_upgrade"):
                reasons.append(f"TIE v3 EW: {n} signals + SP {sp_top:.1f} → each-way angle")

        # ── EW scan — rest of field (observability only, no tier change) ──────
        for runner in preds[1:]:
            rn = runner.get("tie_gate_signal_count", 0)
            rsp = float(runner.get("sp_dec") or 0)
            rfav = bool(runner.get("is_fav"))
            runner["tie_gate_fires"] = False
            runner["tie_gate_ew_flag"] = rn >= MIN_SIGNALS_FOR_EW_FLAG and rsp > LONGSHOT_SP_THRESHOLD and not rfav
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
    prob = float(top.get("velo_prime_prob") or 0)
    place = float(top.get("place_prob") or 0)
    longshot = float(top.get("longshot_prob") or 0)
    sp_dec = float(top.get("sp_dec") or 0)
    improve = float(top.get("improvement_score") or 0)
    # macro_chaos_mode may be None (failed) or bool (known). Treat None as unknown → force chaos.
    _chaos_raw = top.get("macro_chaos_mode")
    chaos_m = bool(_chaos_raw) if _chaos_raw is not None else True
    trap = (top.get("favourite_trap_risk") or "normal").lower()
    gap = prob - second_prob

    # ── Pre-condition blockers ────────────────────────────────────────────────
    # These two checks run before any tier logic and force X-CHAOS hard.

    # 1. Single-runner race: gap == prob is mathematically guaranteed —
    #    every A/B gap threshold becomes trivially true. Model has no real signal.
    if field_size == 1:
        return "X", ["single-runner race (field_size=1) — gap is meaningless, no model signal"]

    # 2. Horse state tagging failed: doctrine signals (days_since_run, trainer timing,
    #    etc.) are absent. A/B decisions require horse state to be valid.
    if top.get("horse_state_failed"):
        return "X", ["horse state tagging failed — required signals absent, cannot evaluate tier"]

    # confidence_level is assigned pre-normalization in the ensemble, then the field
    # normalization step raises the top horse's prob without updating the label.
    # Recompute from the already-normalized prob so A/B gates see the real signal.
    eff_conf = effective_confidence(prob)

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
    if (
        prob < 0.10
        or (gap < 0.015 and place < 0.40 and not strong_escape)
        or (longshot_trigger and not strong_escape)
        or chaos_m
    ):
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
    if prob >= 0.32 and gap >= 0.08 and place >= 0.52 and eff_conf not in ("low",) and trap != "high":
        reasons.append(f"strong separation gap {gap:.3f}")
        reasons.append(f"place floor solid {place:.3f}")
        if improve > 0.20:
            reasons.append(f"form improvement signal {improve:.2f}")
        return "A", reasons

    # ── B-PLAYABLE ────────────────────────────────────────────────────────────
    b_place_ok = place >= 0.45
    b_gap_ok = gap >= 0.08
    b_improve = improve >= 0.18
    if prob >= 0.15 and gap >= 0.03 and eff_conf not in ("low",) and (b_place_ok or b_gap_ok or b_improve):
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
            reasons.append("some win signal but not enough separation")
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
    trap = (top.get("favourite_trap_risk") or "normal").lower()
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


_SB_URL = resolve_supabase_url()
_SB_KEY = resolve_supabase_service_key()
_SB_HDRS = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Accept": "application/json",
}


def _attach_rpdc_from_row(top: dict, row: dict | None) -> None:
    """Attach RPDC tags to the top pick from an already loaded row."""
    if not row:
        _rpdc_defaults(top, status="no_data")
        return

    tags = row.get("rpdc_tags") or []
    top["rpdc_lookup_status"] = "attached"
    top["rpdc_lookup_detail"] = None
    top["rpdc_release_score"] = row.get("rpdc_release_score", 0)
    top["rpdc_cash_window_flag"] = bool(row.get("rpdc_cash_window_flag", False))
    top["rpdc_tag_count"] = int(row.get("rpdc_tag_count", 0))
    top["rpdc_tags"] = tags

    if "CASH_WINDOW" in tags:
        top["rpdc_primary_tag"] = "CASH_WINDOW"
    elif tags:
        top["rpdc_primary_tag"] = tags[0]
    else:
        top["rpdc_primary_tag"] = None


def _attach_rpdc(top: dict, race_id: str) -> None:
    """Look up RPDC tags for the top pick and attach as observability fields.
    Never raises — failures are explicit in rpdc_lookup_status."""
    horse_id = top.get("horse_id") or top.get("predicted_id", "")
    if not horse_id or not race_id or not _SB_URL:
        _rpdc_defaults(top, status="unavailable")
        return
    try:
        url = (
            f"{_SB_URL}/rest/v1/runner_release_candidates"
            f"?horse_id=eq.{horse_id}&race_id=eq.{race_id}&order=generated_at.desc&limit=2"
        )
        req = urllib.request.Request(url, headers=_SB_HDRS)
        with urllib.request.urlopen(req, timeout=5) as r:
            rows = json.loads(r.read().decode())
        if rows:
            row = rows[0]
            tags = row.get("rpdc_tags") or []
            if len(rows) > 1:
                top["rpdc_lookup_status"] = "ambiguous_latest"
                top["rpdc_lookup_detail"] = f"{len(rows)} rows matched; used newest by generated_at"
                log.warning(
                    "RPDC lookup ambiguous for race_id=%s horse_id=%s; using newest generated_at row", race_id, horse_id
                )
            else:
                top["rpdc_lookup_status"] = "attached"
                top["rpdc_lookup_detail"] = None
            top["rpdc_release_score"] = row.get("rpdc_release_score", 0)
            top["rpdc_cash_window_flag"] = bool(row.get("rpdc_cash_window_flag", False))
            top["rpdc_tag_count"] = int(row.get("rpdc_tag_count", 0))
            top["rpdc_tags"] = tags
            # Primary tag = first CASH_WINDOW if present, else highest-scored tag
            if "CASH_WINDOW" in tags:
                top["rpdc_primary_tag"] = "CASH_WINDOW"
            elif tags:
                top["rpdc_primary_tag"] = tags[0]
            else:
                top["rpdc_primary_tag"] = None
        else:
            _rpdc_defaults(top, status="no_data")
    except Exception as exc:
        log.warning("RPDC lookup failed for race_id=%s horse_id=%s: %s", race_id, horse_id, exc)
        _rpdc_defaults(top, status="lookup_failed", detail=str(exc))


def _rpdc_defaults(top: dict, *, status: str, detail: str | None = None) -> None:
    top.setdefault("rpdc_release_score", 0)
    top.setdefault("rpdc_cash_window_flag", False)
    top.setdefault("rpdc_tag_count", 0)
    top.setdefault("rpdc_primary_tag", None)
    top.setdefault("rpdc_tags", [])
    top["rpdc_lookup_status"] = status
    top["rpdc_lookup_detail"] = detail


def build_decision_card(race: dict, top: dict, second: dict, tier: str, reasons: list) -> str:
    course = race.get("course", "?").upper()
    off = race.get("off_time", "?")
    primary = top.get("horse", "?")
    contain = second.get("horse", "?") if second else "—"
    conf = top.get("confidence_level") or "low"
    action = TIER_ACTIONS[tier]
    label = TIER_LABELS[tier]
    prob = float(top.get("velo_prime_prob") or 0)
    gap = prob - float(second.get("velo_prime_prob") or 0)
    place = float(top.get("place_prob") or 0)

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
        arch_conf = (top.get("archetype_confidence") or "?")[0].upper()
        arch_style = top.get("archetype_bet_style") or ""
        trap_mark = " ⚠ TRAP" if top.get("archetype_trap_flag") else ""
        lines.append(f"ARCHETYPE: [{arch}:{arch_conf}]{trap_mark}  {arch_style}")
    return "\n".join(lines)


SIGNAL_STACK_EVIDENCE = {
    "VP30_TIER_A": {"icon": "✅", "n": 162, "sr": 40.1, "frame": 77.2, "status": "SHADOW_CANDIDATE"},
    "MDS_HIGH": {"icon": "🔥", "n": 31, "sr": 54.8, "frame": 96.8, "status": "SHADOW_CANDIDATE"},
    "IMPROVE_HIGH": {"icon": "📈", "n": 62, "sr": 43.5, "frame": 82.3, "status": "SHADOW_CANDIDATE"},
    "PLACE_PROB_HIGH": {"icon": "🟡", "n": 392, "sr": 31.6, "frame": 66.8, "status": "WATCHLIST"},
    "B_LOW_VP_SUPPRESS": {"icon": "⚠️", "n": 272, "sr": 16.9, "frame": 44.1, "status": "SUPPRESS_CANDIDATE"},
}
SIGNAL_STACK_OPERATOR_NOTE = "SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION"
VP_DRAG_NOTE = "⚠️ VP_020_030_DRAG — 18.0% SR | 47.8% frame"
MID_PRICE_NOTE = "🔬 MID_PRICE_ZONE_WATCH — SP 3.0–8.5 research zone | FORENSICS_ONLY"
SHORT_FAV_NOTE = "⚠️ SHORT_FAV_OVERRIDE_WATCH — SP<3.0 compressed market zone"


def _signal_stack_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm_horse_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def _resolve_signal_stack_runner(race: dict, top: dict) -> dict:
    runners = race.get("runners", []) or []
    top_horse_id = str(top.get("horse_id") or "")
    top_name = _norm_horse_name(top.get("horse") or "")

    for runner in runners:
        if top_horse_id and str(runner.get("horse_id") or "") == top_horse_id:
            return runner
    for runner in runners:
        runner_name = runner.get("horse_name") or runner.get("horse") or runner.get("name") or ""
        if top_name and _norm_horse_name(runner_name) == top_name:
            return runner
    return {}


def _resolve_signal_stack_odds(race: dict, top: dict) -> float | None:
    runner = _resolve_signal_stack_runner(race, top)
    for key in ("best_odds_decimal", "sp_dec", "odds_decimal"):
        val = _signal_stack_float(runner.get(key), 0.0)
        if val > 1.0:
            return val
    return None


def _signal_stack_badges_and_risks(race: dict, top: dict, tier: str) -> tuple[list[str], list[str]]:
    vp = _signal_stack_float(top.get("velo_prime_prob"), 0.0)
    mds = _signal_stack_float(top.get("market_deception_score"), 0.0)
    improve = _signal_stack_float(top.get("improvement_score"), 0.0)
    place_prob = _signal_stack_float(top.get("place_prob"), 0.0)
    odds = _resolve_signal_stack_odds(race, top)

    badges: list[str] = []
    risks: list[str] = []

    if vp >= 0.30 and tier == "A":
        badges.append("VP30_TIER_A")
    if mds > 0.50:
        badges.append("MDS_HIGH")
    if improve > 0.40:
        badges.append("IMPROVE_HIGH")
    if place_prob > 0.80:
        badges.append("PLACE_PROB_HIGH")
    if tier == "B" and vp < 0.30:
        badges.append("B_LOW_VP_SUPPRESS")

    if 0.20 <= vp < 0.30:
        risks.append(VP_DRAG_NOTE)
    if odds is not None and 3.0 <= odds <= 8.5:
        risks.append(MID_PRICE_NOTE)
    if odds is not None and odds < 3.0:
        risks.append(SHORT_FAV_NOTE)

    return badges, risks


def _render_signal_badge_line(badge_id: str) -> str:
    meta = SIGNAL_STACK_EVIDENCE[badge_id]
    return (
        f"{meta['icon']} {badge_id} — n={meta['n']} | SR={meta['sr']}% | "
        f"Frame={meta['frame']}% | {meta['status']}"
    )


def _build_place_signal_tg(scored: list, date_display: str) -> str:
    """Build a compact Telegram message for place signal operator visibility."""
    from collections import defaultdict
    from src.velo.place_signal_classifier import classify_from_verdict, PlaceSignal

    LABEL_ORDER = [
        "ELITE_PLACE_STACK",
        "STRONG_PLACE_STACK_PLUS",
        "STRONG_PLACE_STACK",
        "IMPROVE_PLACE_WATCH",
        "PLACE_SUPPORT_WATCH",
        "BASE_PLACE_TRUST",
    ]
    LABEL_SHORT = {
        "ELITE_PLACE_STACK":        "ELITE",
        "STRONG_PLACE_STACK_PLUS":  "STRONG+",
        "STRONG_PLACE_STACK":       "STRONG",
        "IMPROVE_PLACE_WATCH":      "IMPROVE_WATCH",
        "PLACE_SUPPORT_WATCH":      "PLACE_SUPPORT",
        "BASE_PLACE_TRUST":         "BASE_TRUST",
    }

    by_label: dict[str, list] = defaultdict(list)
    for race, preds, tier, _ in scored:
        if not preds:
            continue
        top = preds[0]
        sig = classify_from_verdict(top)
        if sig.place_stack_label not in LABEL_ORDER:
            continue
        course = (race.get("course") or "?").upper()
        off = race.get("off_time") or "?"
        vp = float(top.get("velo_prime_prob") or 0)
        mds = float(top.get("market_deception_score") or 0)
        badges = " ".join(f"[{b}]" for b in sig.badges)
        mpo = f" min{sig.min_place_odds:.2f}" if sig.min_place_odds else ""
        by_label[sig.place_stack_label].append(
            f"• {top.get('horse','?')} — {course} {off} | VP={vp:.3f} | MDS={mds:.3f}{mpo} | {badges}"
        )

    active_labels = [lbl for lbl in LABEL_ORDER if by_label.get(lbl)]
    if not active_labels:
        return ""

    lines = [
        f"PLACE SIGNALS — {date_display}",
        "LIVE OPERATOR VISIBILITY ONLY",
        "─" * 34,
    ]
    for lbl in active_labels:
        short = LABEL_SHORT[lbl]
        rows = by_label[lbl]
        lines.append(f"{short} ({len(rows)})")
        lines.extend(rows)
        lines.append("")

    lines += [
        "─" * 34,
        "STATUS: LIVE_OPERATOR_VISIBILITY_ONLY",
        "NO STAKING. NO BETFAIR. NO EXECUTION.",
    ]
    return "\n".join(lines)


def render_signal_attribution_panel(race: dict, top: dict, tier: str, compact: bool = False) -> str:
    vp = _signal_stack_float(top.get("velo_prime_prob"), 0.0)
    mds = _signal_stack_float(top.get("market_deception_score"), 0.0)
    improve = _signal_stack_float(top.get("improvement_score"), 0.0)
    place_prob = _signal_stack_float(top.get("place_prob"), 0.0)
    badges, risks = _signal_stack_badges_and_risks(race, top, tier)

    if compact:
        badge_text = " | ".join(badges) if badges else "none"
        risk_text = " | ".join(risks) if risks else "none"
        return (
            f"  SIGNAL STACK: VP {vp:.3f} | Tier {tier}\n"
            f"  badges {badge_text}\n"
            f"  sidecar MDS {mds:.3f} | IMP {improve:.3f} | PLACE {place_prob:.3f}\n"
            f"  risk {risk_text}\n"
            f"  {SIGNAL_STACK_OPERATOR_NOTE}"
        )

    lines = [
        "VÉLØ SIGNAL STACK",
        f"PICK:        {top.get('horse', '?')}",
        f"VP:          {vp:.3f}",
        f"TIER:        {tier}",
        "LANES:",
    ]
    if badges:
        for badge_id in badges:
            lines.append(_render_signal_badge_line(badge_id))
    else:
        lines.append("— no candidate-lane badge triggered")

    lines.extend(
        [
            "SIDECAR:",
            f"MDS:         {mds:.3f}",
            f"IMPROVE:     {improve:.3f}",
            f"PLACE:       {place_prob:.3f}",
            "RISK FLAGS:",
        ]
    )
    if risks:
        lines.extend(risks)
    else:
        lines.append("— none")
    lines.append(f"STATUS:      {SIGNAL_STACK_OPERATOR_NOTE}")
    return "\n".join(lines)


def build_governed_card(
    race: dict, top: dict, second: dict, tier: str, reasons: list[str], source: str, requested_date: str
) -> str:
    """
    Builds a high-fidelity decision card for Telegram.
    Includes source truth, anti-cache guards, and operational depth.
    """
    course = race.get("course", "?").upper()
    off = race.get("off_time", "?")
    actual_date = race.get("date", "?")

    # Anti-Cache Guard
    cache_warning = ""
    if requested_date != actual_date:
        cache_warning = "🚨 *CACHE MISMATCH / NON-LIVE* 🚨\n"

    # Operational Depth
    prob_gap = float(top.get("velo_prime_prob", 0)) - float(second.get("velo_prime_prob", 0))
    mds = top.get("market_deception_score", 0)
    assigned = top.get("assigned_product", "UNKNOWN")
    allowed = "YES" if top.get("execution_allowed") else "NO"
    signal_panel = render_signal_attribution_panel(race, top, tier)

    return f"""{cache_warning}🛡️ *{course} {off} | {assigned}*
──────────────────────────────────
PRIMARY:     {top.get("horse", "?")}
TIER:        {tier}
CONFIDENCE:  {top.get("confidence_level", "NORMAL").upper()}
PROB GAP:    {prob_gap:.4f}
MDS (DECOY): {mds:.4f}
EXECUTION:   {allowed}
{signal_panel}
REASONS:     {", ".join(reasons)}
SOURCE:      {source}
DATE:        {actual_date}
──────────────────────────────────
"""


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


def _derive_rpd_evidence(runner: dict, race: dict, runner_rpdc: dict = None) -> tuple[list, bool, bool]:
    """
    Derive RPD-C evidence codes from a normalized runner dict.
    Returns (evidence_codes, market_shortening, won_last_time).

    Evidence is derived conservatively — only from clearly available fields.
    Missing or ambiguous data defaults to H (Honest) via engine fallback.
    market_shortening is always False here (no intraday movement data available).
    """
    evidence = []
    runner_rpdc = runner_rpdc or {}

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

    # Form reversal detection (P2 fix)
    rpdc_tags = runner_rpdc.get("rpdc_tags") or []
    if "FORM_REVERSAL" in rpdc_tags:
        try:
            odds = float(runner.get("best_odds_decimal") or 0)
            if 3.0 <= odds <= 9.0:
                evidence.append("form_reversal")
        except Exception:
            pass

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
                evidence.append("long_absence")  # P evidence
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


def _open_pipeline_run(db, date_str: str) -> PipelineRunOpenResult:
    """Open a pipeline_runs row.

    Age-gate cleanup: any running row for this service + date older than 24h is
    closed as FAIL before inserting the new row.  Rows newer than 24h abort the
    new run (prevents duplicate concurrent runs).
    """
    SERVICE = "velo-prime-scoring"
    AGE_GATE_HOURS = 24
    now = utc_now()
    existing_run_id = os.getenv("PIPELINE_RUN_ID", "").strip()

    if existing_run_id:
        return PipelineRunOpenResult(run_id=existing_run_id)

    try:
        # Find existing running rows scoped to this service + date
        try:
            existing = (
                db.table("pipeline_runs")
                .select("id, started_at")
                .eq("service_name", SERVICE)
                .eq("source_date", date_str)
                .eq("run_state", "running")
                .execute()
            )

            for row in existing.data or []:
                try:
                    started = datetime.fromisoformat(row["started_at"].rstrip("Z"))
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=now.tzinfo)
                except Exception:
                    started = now - timedelta(hours=AGE_GATE_HOURS + 1)  # treat as stale

                age_hours = (now - started).total_seconds() / 3600
                if age_hours >= AGE_GATE_HOURS:
                    # Stale — close as FAIL and allow new run
                    db.table("pipeline_runs").update(
                        {
                            "run_state": "completed",
                            "status": "FAIL",
                            "finished_at": now.isoformat().replace("+00:00", "Z"),
                            "error_message": f"Closed by age gate ({age_hours:.1f}h stale): superseded by new run",
                        }
                    ).eq("id", row["id"]).execute()
                    print(f"  [pipeline_runs] age-gate closed stale run {row['id']} ({age_hours:.1f}h)")
                else:
                    # Recent running row — abort to prevent duplicate
                    print(
                        f"  [pipeline_runs] run already running (id={row['id']}, age={age_hours:.1f}h). Aborting open."
                    )
                    return PipelineRunOpenResult(
                        blocked_reason=f"run already running (id={row['id']}, age={age_hours:.1f}h)"
                    )
        except Exception as e:
            print(f"  [pipeline_runs] stale-run cleanup failed (non-fatal): {e}")

        trigger_src = os.getenv("TRIGGER_SOURCE", "manual") or "manual"
        env_str = resolve_runtime_environment()
        row = {
            "id": str(uuid.uuid4()),
            "service_name": SERVICE,
            "run_type": "daily_scoring",
            "source_date": date_str,
            "run_state": "running",
            "status": None,  # explicit NULL overrides DB DEFAULT 'in_progress'
            "trigger_source": trigger_src,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "environment": env_str,
            "commit_sha": get_commit_sha(),
        }
        resp = db.table("pipeline_runs").insert(row).execute()
        if resp.data:
            return PipelineRunOpenResult(run_id=resp.data[0]["id"])
        return PipelineRunOpenResult(error="pipeline_runs insert returned no data")
    except Exception as e:
        detail = str(e)
        print(f"  [pipeline_runs] open failed: {detail}")
        if "duplicate key" in detail.lower() or "unique" in detail.lower():
            return PipelineRunOpenResult(blocked_reason="run already running (db uniqueness guard)")
        return PipelineRunOpenResult(error=detail)


def _close_pipeline_run(db, run_id: str | None, status: str, races: int, runners: int, error: str | None = None):
    """Close a pipeline_runs row with final stats."""
    if not run_id:
        return
    try:
        patch = {
            "run_state": "completed",
            "status": status,
            "finished_at": utc_now().isoformat().replace("+00:00", "Z"),
            "races_processed": races,
            "runners_processed": runners,
            "commit_sha": get_commit_sha(),
        }
        if error:
            patch["error_message"] = error[:500]
        db.table("pipeline_runs").update(patch).eq("id", run_id).execute()
    except Exception as e:
        print(f"  [pipeline_runs] close failed (non-fatal): {e}")


def sb_get(path: str) -> list[dict]:
    """Helper to fetch from Supabase."""
    if not _SB_URL or not _SB_KEY:
        return []
    url = f"{_SB_URL}/rest/v1{path}"
    req = urllib.request.Request(url, headers=_SB_HDRS)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.warning("sb_get failed for %s: %s", path, e)
        return []


def _fetch_race_rpdc(race_id: str) -> dict[str, dict]:
    """Fetch RPDC data for all runners in a race."""
    rows = sb_get(f"/runner_release_candidates?race_id=eq.{race_id}")
    return {r["horse_id"]: r for r in rows}


def main():
    global _TG_DATE, _TG_NOTIFY_ENABLED
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()
    notify_enabled = not args.no_notify and not args.dry_run
    _bootstrap_runtime(env_file=args.env_file, notify=notify_enabled)
    date_tag = args.date.replace("-", "_") if args.date else TODAY
    date_str = date_tag.replace("_", "-")
    persistence_enabled = not args.dry_run
    _TG_DATE = date_str
    _TG_NOTIFY_ENABLED = notify_enabled

    print(f"\nVELO PRIME RACE-DAY EXECUTION — {date_str}")
    print("=" * 60)

    # ── PREFLIGHT GATE — must pass before anything else runs ─────────────────
    print("\nPREFLIGHT")
    print("-" * 40)
    from src.preflight import preflight_or_die

    pf_result = preflight_or_die(tg_fn=tg)  # exits with sys.exit(1) on FAIL
    print(f"  Status: {pf_result.status}")
    print("-" * 40)
    # ─────────────────────────────────────────────────────────────────────────

    from app.services.velo_prime_service import persist_race_predictions, score_race_velo_prime
    from src.rpd import RPDv2Engine
    from supabase import create_client as _sb_create
    from workers.racing_api_normalizer import normalize_race

    _sb_url = resolve_supabase_url()
    _sb_key = resolve_supabase_service_key()
    db = _sb_create(_sb_url, _sb_key) if _sb_url and _sb_key else None
    run_open = _open_pipeline_run(db, date_str) if (db and persistence_enabled) else None
    run_id = run_open.run_id if run_open else None
    os.environ["_ACTIVE_PIPELINE_RUN_ID"] = run_id or ""
    if not persistence_enabled:
        print("  pipeline_run: SKIPPED â€” dry-run mode (no persistence side effects)")
    elif not db:
        print("  pipeline_run: SKIPPED — no Supabase creds (monitoring blind this run) ⚠")
    elif run_open and run_open.blocked_reason:
        log.error("pipeline_run blocked: %s", run_open.blocked_reason)
        print(f"  pipeline_run: BLOCKED — {run_open.blocked_reason}")
        return RunPrimeResult(
            status="BLOCKED",
            exit_code=1,
            date_str=date_str,
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )
    elif run_open and run_open.error:
        log.error("pipeline_run open failed: %s", run_open.error)
        print(f"  pipeline_run: OPEN FAILED — {run_open.error} ⚠")
        return RunPrimeResult(
            status="FAIL",
            exit_code=1,
            date_str=date_str,
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )
    else:
        print(f"  pipeline_run: {run_id}")

    # ── STEP 1: Load racecards (cache or direct API fetch) ────────────────────
    print("\nSTEP 1: Load racecards")
    raw_races, racecard_source = load_racecards(date_tag, date_str)
    races_with_runners = [r for r in raw_races if r.get("runners")]

    # ── SOURCE TRUTH HEADER ───────────────────────────────────────────────────
    # Detect if loaded card is actually for the requested date
    loaded_dates = set()
    for r in raw_races:
        d = r.get("date") or r.get("race_date") or r.get("off_dt", "")[:10]
        if d:
            loaded_dates.add(d)
    loaded_date_str = ", ".join(sorted(loaded_dates)) if loaded_dates else "unknown"
    date_mismatch = loaded_dates and date_str not in loaded_dates
    is_live = racecard_source == "api"
    _source_labels = {"api": "LIVE_API", "cache": "CACHE", "rp_profile": "RP_PROFILE_FALLBACK"}
    live_label = _source_labels.get(racecard_source, racecard_source.upper())
    commit_sha = get_commit_sha()

    print(f"\n{'=' * 60}")
    print("  SOURCE TRUTH HEADER")
    print(f"  requested_date : {date_str}")
    print(f"  loaded_date(s) : {loaded_date_str}")
    print(f"  source         : {live_label} ({racecard_source})")
    print(f"  commit_sha     : {commit_sha}")
    print("  router_version : ProductRouter v1 (live-safe)")
    if date_mismatch:
        print(f"  WARNING: DATE MISMATCH — loaded card is NOT for {date_str}")
        print("  WARNING: This is a cache/stale fetch. Marking output NON-LIVE.")
    elif racecard_source == "rp_profile":
        print("  INFO: Source = RP_PROFILE_FALLBACK. VP scores partial (no live market data).")
    elif not is_live:
        print("  INFO: Source = CACHE. Card date matches request.")
    else:
        print("  OK: Source = LIVE API. Card date matches request.")
    print(f"{'=' * 60}\n")

    if date_mismatch and notify_enabled:
        print("  TELEGRAM SUPPRESSED — date mismatch, would send stale card as live")
        notify_enabled = False
        _TG_NOTIFY_ENABLED = False

    if date_mismatch and persistence_enabled:
        err_summary = f"DATE_MISMATCH_STALE_CARD loaded={loaded_date_str} requested={date_str}"
        print("  PERSISTENCE BLOCKED — stale card cannot be written as current-day truth")
        _close_pipeline_run(db, run_id, "FAIL", 0, 0, err_summary)
        _emit_daily_truth_packet(date_str, repair_local_archive=False)
        return RunPrimeResult(
            status="BLOCKED",
            exit_code=1,
            date_str=date_str,
            racecard_source=racecard_source,
            races_fetched=len(raw_races),
            races_normalized=0,
            races_scored=0,
            persist_ok=0,
            persist_fail=0,
            score_errors=0,
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )

    print(f"  Source: {racecard_source}  races: {len(raw_races)}  with runners: {len(races_with_runners)}")

    # ── STEP 2: Normalize ALL races before any scoring ────────────────────────
    print("\nSTEP 2: Normalize (canonical schema — no raw payloads to workers)")
    normalized = []
    fetch_time = datetime.now(UTC).isoformat()
    for r in races_with_runners:
        n = normalize_race(r)
        if n.get("runners"):
            n["fetch_timestamp"] = fetch_time
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
    from src.velo.product_router import ProductRouter

    router = ProductRouter()

    # Initialize Spotlight Engine
    from workers.spotlight_parser import extract_spotlight_signals

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

    # Pre-load all available PDF intelligence for today's tracks
    pdf_intel_cache = {}
    for race in normalized:
        course_code = (race.get("course_id") or race.get("course", "")).upper()
        if course_code in (
            "PONTEFRACT",
            "PON",
            "CATTERICK",
            "CAT",
            "LUDLOW",
            "LUD",
            "PERTH",
            "PER",
            "TAUNTON",
            "TAU",
            "GOWRAN PARK",
            "GOW",
        ):
            # Simple mapping for known tracks if course_id isn't reliable, though the file names use 3-letter codes like CAT
            # Try deriving 3-letter code from course name
            cc = course_code[:3]
        else:
            cc = course_code[:3]

        if cc not in pdf_intel_cache:
            pdf_path = ROOT / "data" / "racecard_merged" / f"racecard_{cc}_{date_str}.json"
            if pdf_path.exists():
                with open(pdf_path) as f:
                    pdf_intel_cache[cc] = json.load(f)
            else:
                pdf_intel_cache[cc] = None

    scored = []
    score_errors = []
    for race in normalized:
        cid = f"{race.get('course')} {race.get('off_time', '?')}"

        # Attach PDF Intel to normalized runners before scoring
        course_code = (race.get("course_id") or race.get("course", "")[:3]).upper()
        cc = course_code[:3]
        merged_data = pdf_intel_cache.get(cc)
        if merged_data:
            # We need to match race_time strictly or loosely. Usually off_time is "1.52" or "13:52".
            # The merged JSON uses "1.52".
            race_time_api = race.get("off_time", "")
            # Convert 13:52 to 1.52 if necessary, but API usually provides raw times or we can try loose match
            # For simplicity, we just iterate through all races in the JSON and match time strings roughly
            merged_horses = []
            for r_time, r_data in merged_data.get("races", {}).items():
                api_time_clean = race_time_api.replace(":", ".")
                # e.g., API: 13:52, JSON: 1.52
                if api_time_clean == r_time or api_time_clean.endswith(r_time):
                    merged_horses = r_data.get("horses", [])
                    break

                # Check 12-hour vs 24-hour
                try:
                    parts = api_time_clean.split(".")
                    if len(parts) == 2 and int(parts[0]) > 12:
                        hr_12 = str(int(parts[0]) - 12)
                        time_12 = f"{hr_12}.{parts[1]}"
                        if time_12 == r_time:
                            merged_horses = r_data.get("horses", [])
                            break
                except Exception:
                    pass

            for runner in race.get("runners", []):
                api_name = (runner.get("horse_name") or "").lower().strip()
                api_key = re.sub(r"[^a-z]", "", api_name)
                for h in merged_horses:
                    pdf_name = (h.get("horse_name") or "").lower().strip()
                    pdf_key = re.sub(r"[^a-z]", "", pdf_name)
                    if pdf_key == api_key or (len(pdf_key) > 4 and (pdf_key in api_key or api_key in pdf_key)):
                        runner["pdf_intel"] = h
                        break

        try:
            preds = score_race_velo_prime(race, sentient_state=_sentient_state)
            if preds:
                # Load RPDC data for this race to inform RPD-C tags
                race_rpdc = _fetch_race_rpdc(race.get("race_id", ""))

                # RPD-C tagging — passive metadata only, no score/rank mutation
                runner_map = {r.get("horse_name", ""): r for r in race.get("runners", [])}
                for pred in preds:
                    raw_runner = runner_map.get(pred.get("horse", ""), {})
                    horse_id = raw_runner.get("horse_id")
                    runner_rpdc = race_rpdc.get(horse_id, {})

                    # Spotlight Parsing
                    spot_text = raw_runner.get("spotlight", "")
                    if spot_text:
                        # Extract full 15-category signals using workers/spotlight_parser.py
                        # Required args: raw_text, horse_name, race_id, race_date
                        spot_record = extract_spotlight_signals(
                            spot_text,
                            horse_name=pred.get("horse"),
                            race_id=race.get("race_id", "unknown"),
                            race_date=date_str,
                        )
                        # Normalize sentiment (-2 to +2) to 0-1 score
                        pred["spotlight_score"] = (spot_record.get("sentiment_score", 0.0) + 2.0) / 4.0

                    # Gear and Wind signals from Racing API raw runner
                    pred["headgear_run"] = 1 if raw_runner.get("headgear_run") == "1" else 0
                    pred["wind_surgery_run"] = 1 if raw_runner.get("wind_surgery_run") == "1" else 0

                    rpd_evidence, rpd_mkt_short, rpd_won_last = _derive_rpd_evidence(
                        raw_runner, race, runner_rpdc=runner_rpdc
                    )
                    rpd_suggestion = rpd_engine.suggest_tag(
                        pred.get("horse", ""),
                        rpd_evidence,
                        market_shortening=rpd_mkt_short,
                        won_last_time=rpd_won_last,
                    )
                    pred["rpd_tag"] = rpd_suggestion.suggested_tag.value
                    pred["rpd_confidence"] = rpd_suggestion.confidence
                    pred["rpd_evidence_codes"] = rpd_evidence

                top = preds[0]
                second = preds[1] if len(preds) > 1 else {}
                sec_prob = float(second.get("velo_prime_prob") or 0)
                tier, reasons = synthesize_decision(top, sec_prob, field_size=len(preds))
                # Write effective confidence back onto top so persist sees it.
                # Raw label (pre-normalization) is preserved separately.
                top["confidence_level_raw"] = top.get("confidence_level")
                top["confidence_level_effective"] = effective_confidence(float(top.get("velo_prime_prob") or 0))
                # Shadow suspect cohort flag — A-tier with weak place support.
                # No gate change. Passive monitor only. Track for 30 days to build
                # enough sample to decide whether to tighten the A-gate conditionally.
                # Cohort: A-tier AND place_prob < 0.75 (win signal overpowering place).
                top["a_tier_weak_place_flag"] = tier == "A" and float(top.get("place_prob") or 0) < 0.75
                tier, reasons = _apply_tie_v3_gate(top, tier, reasons, preds)
                _apply_archetype(top, preds, tier, sec_prob)
                _add_secondary_signals(top, reasons)
                # Attach RPDC data to top pick (from pre-fetched race_rpdc)
                _attach_rpdc_from_row(top, race_rpdc.get(top.get("horse_id")))

                # ── GOVERNED EXECUTION ROUTER ────────────────────────────────
                top_raw_runner = runner_map.get(top.get("horse", ""), {})
                pdf_intel = top_raw_runner.get("pdf_intel", {})

                # ── v2 context fields for D/X intelligence layer ─────────────
                race_name = race.get("race_name") or ""
                is_handicap = "handicap" in race_name.lower() or "hcap" in race_name.lower()
                # Favourite SP = minimum sp_dec across all scored runners
                sp_vals = [float(p.get("sp_dec") or 0) for p in preds if p.get("sp_dec")]
                fav_sp = min((v for v in sp_vals if v > 0), default=0.0)

                route_data = {
                    "decision_tier": tier,
                    "confidence_level": top.get("confidence_level"),
                    "actual_winner_sp": top.get("sp_dec", 0.0),
                    "prob_gap": float(top.get("velo_prime_prob", 0)) - sec_prob,
                    "track": race.get("course"),
                    "top_horse_draw": top.get("draw"),
                    "market_deception_score": top.get("market_deception_score", 0),
                    "plot_conviction": pdf_intel.get("plot_conviction"),
                    "or_compression_score": pdf_intel.get("or_compression_score"),
                    "is_postdata_pick": pdf_intel.get("is_postdata_pick"),
                    "is_topspeed_pick": pdf_intel.get("is_topspeed_pick"),
                    # v2: D/X intelligence layer inputs
                    "field_size": race.get("scored") or len(preds),
                    "race_type": race.get("type", "?"),
                    "going": race.get("going", "?"),
                    "is_handicap": is_handicap,
                    "fav_sp": fav_sp,
                    "velo_prime_prob": float(top.get("velo_prime_prob", 0)),
                    "archetype": top.get("race_archetype", "?"),
                }
                governance = router.route_verdict(route_data)

                top["assigned_product"] = governance["assigned_product"]
                top["router_reasons"] = governance["router_reasons"]
                top["execution_allowed"] = governance["execution_allowed"]
                top["legacy_execution_allowed"] = governance.get("legacy_execution_allowed", governance["execution_allowed"])

                # ── Candidate Execution Router v1 (shadow) ─────────────────
                from app.services.model_manager import ModelManager as _MM
                _class_num = _MM._parse_class(race.get("race_class") or race.get("class"))
                candidate_data = {
                    "velo_prime_prob":    float(top.get("velo_prime_prob", 0)),
                    "field_size":         race.get("scored") or len(preds),
                    "archetype":          top.get("race_archetype", ""),
                    "going":              race.get("going", ""),
                    "macro_chaos_mode":   top.get("macro_chaos_mode", False),
                    "class_num":          _class_num,
                    "sp_decimal":         float(top.get("sp_dec") or 0),
                    "archetype_suppression": top.get("archetype_suppression", False),
                }
                candidate = router.candidate_route(candidate_data)
                top["candidate_execution_allowed"] = candidate["candidate_execution_allowed"]
                top["candidate_execution_reason"]  = candidate["candidate_execution_reason"]
                top["candidate_execution_lane"]    = candidate["candidate_execution_lane"]

                # ── Phase 5: Racing API Shadow Enrichment (forward-test only) ──
                # GOVERNANCE: shadow fields only — never alters velo_prime_prob,
                # tier, assigned_product, candidate_execution_allowed, or router.
                _shadow = compute_shadow_enrichment(
                    trainer_id=top_raw_runner.get("trainer_id"),
                    jockey_id=top_raw_runner.get("jockey_id"),
                    course_name=race.get("course"),
                    dist_f_raw=race.get("distance_f"),
                    caches=_ENRICHMENT_CACHES,
                )
                top.update(_shadow)
                try:
                    append_to_forward_ledger(str(_SHADOW_LEDGER_PATH), {
                        "date": date_str,
                        "race_id": race.get("race_id"),
                        "course": race.get("course"),
                        "off_time": race.get("off_time"),
                        "horse": top.get("horse"),
                        "horse_id": top.get("horse_id"),
                        "trainer_id": top_raw_runner.get("trainer_id"),
                        "jockey_id": top_raw_runner.get("jockey_id"),
                        "velo_prime_prob": top.get("velo_prime_prob"),
                        "tier": tier,
                        "candidate_execution_allowed": top.get("candidate_execution_allowed"),
                        "router_shadow_lane": top.get("candidate_execution_lane"),
                        "racing_api_connection_shadow_score": top.get("racing_api_connection_shadow_score"),
                        "racing_api_course_shadow_score": top.get("racing_api_course_shadow_score"),
                        "racing_api_distance_shadow_score": top.get("racing_api_distance_shadow_score"),
                        "racing_api_enrichment_shadow_score": top.get("racing_api_enrichment_shadow_score"),
                        "racing_api_connection_coverage": top.get("racing_api_connection_coverage"),
                        "racing_api_course_coverage": top.get("racing_api_course_coverage"),
                        "racing_api_distance_coverage": top.get("racing_api_distance_coverage"),
                        "racing_api_enrichment_coverage": top.get("racing_api_enrichment_coverage"),
                        "result_position": None,
                        "won": None,
                        "placed": None,
                        "sp_decimal": top.get("sp_dec"),
                        "profit_loss": None,
                        "shadow_version": top.get("racing_api_shadow_version"),
                        "leakage_status": top.get("racing_api_shadow_leakage_status"),
                    })
                except Exception as _ledger_exc:
                    log.warning("shadow ledger append failed: %s", _ledger_exc)

                if pdf_intel.get("plot_conviction"):
                    reasons.append(f"PDF_PLOT_CONVICTION:{pdf_intel['plot_conviction']:.2f}")

                scored.append((race, preds, tier, reasons))
                prob_gap_val = float(top.get("velo_prime_prob", 0)) - sec_prob
                gate_note = f" [TIE^{top.get('tie_gate_tier_upgrade', '')}]" if top.get("tie_gate_tier_upgrade") else ""
                arch_note = f" [{top.get('race_archetype', '?')}:{(top.get('archetype_confidence') or '?')[0].upper()}]"
                print(
                    f"  SCORED  {race.get('course', '?'):22s}  {race.get('off_time', '?'):5s}"
                    f"  race_id={race.get('race_id', '?')}\n"
                    f"          horse={top['horse']:<25s}  tier={tier}  conf={top.get('confidence_level', '?')}{gate_note}{arch_note}\n"
                    f"          prob={top.get('velo_prime_prob', 0):.4f}  gap={prob_gap_val:.4f}"
                    f"  mds={top.get('market_deception_score', 0):.4f}\n"
                    f"          product={top.get('assigned_product', '?'):15s}"
                    f"  exec={top.get('execution_allowed', '?')}"
                    f"  reasons={top.get('router_reasons', '?')}"
                )
            else:
                score_errors.append((race, "no predictions returned"))
                print(f"  SKIP  {cid} — no predictions returned")
        except Exception as e:
            score_errors.append((race, str(e)))
            print(f"  FAIL  {cid} — {e}")

    print(f"\n  Scored: {len(scored)}  Errors: {len(score_errors)}")

    # ── GOVERNED CARD SUMMARY ─────────────────────────────────────────────────
    from collections import Counter

    product_counts = Counter()
    for _race, preds, _t, _ in scored:
        top_pick = preds[0] if preds else {}
        product_counts[top_pick.get("assigned_product", "UNKNOWN")] += 1
    exec_total = sum(v for k, v in product_counts.items() if k in ("WIN_ONLY", "FRAME_ONLY", "EW_CANDIDATE"))
    print("\n  ── GOVERNED CARD SUMMARY ──────────────────────────────")
    print(f"  Scored:        {len(scored)}")
    for prod in ["WIN_ONLY", "FRAME_ONLY", "EW_CANDIDATE", "VISION_ONLY", "PASS", "UNKNOWN"]:
        n = product_counts.get(prod, 0)
        if n:
            exec_flag = " ← EXECUTION AUTHORIZED" if prod in ("WIN_ONLY", "FRAME_ONLY", "EW_CANDIDATE") else ""
            print(f"  {prod:<20s} {n:3d}{exec_flag}")
    print(f"  EXECUTION AUTHORIZED: {exec_total}")
    print("  ──────────────────────────────────────────────────────")

    # ── STEP 4: Persist to Supabase ───────────────────────────────────────────
    print("\nSTEP 4: Persist to velo_verdicts")
    persist_ok = 0
    persist_fail = 0
    persist_map = {}  # race_id -> bool (honesty gate)

    for race, preds, tier, _reasons in scored:
        rid = race.get("race_id")
        if not persistence_enabled:
            persist_ok += 1
            persist_map[rid] = True
            continue

        success = persist_race_predictions(race, preds, decision_tier=tier)
        persist_map[rid] = success

        if success:
            persist_ok += 1
        else:
            persist_fail += 1
            print(f"  PERSIST FAIL: {rid} {race.get('course')}")

    print(f"  Verdicts: {persist_ok} OK / {persist_fail} FAIL / {len(scored)} total")

    # ── STEP 5: Build Telegram output ─────────────────────────────────────────
    print("\nSTEP 5: Send to Telegram")

    # A. Pre-flight report — reflects actual preflight result
    pf_lines = [f"  {c.name}: {'OK' if c.passed else c.detail}" for c in pf_result.checks]
    tg(
        f"VELO PRE-FLIGHT REPORT — {TODAY_DISPLAY}\n"
        f"repo:       elpresidentepiff/velo-oracle-prime\n"
        f"racecards:  {racecard_source}\n" + "\n".join(pf_lines) + "\n"
        f"STATUS:     {pf_result.status}"
    )
    print("  Sent: pre-flight report")

    # A1. CASH RUNS — scan merged PDF data for postdata PLOT candidates
    # Criteria: postdata_score >= 0.70 AND trainer_form == 'strong_positive'
    #           AND or_compression_score > 0
    # Sent as a dedicated message BEFORE day posture so it's always the first
    # actionable signal the user sees — never buried in prediction output.
    cash_runs = []
    for cc, merged_data in pdf_intel_cache.items():
        if not merged_data:
            continue
        for r_time, r_data in merged_data.get("races", {}).items():
            for h in r_data.get("horses", []):
                ps = float(h.get("postdata_score") or 0)
                tf = str(h.get("trainer_form") or "")
                ors = float(h.get("or_compression_score") or 0)
                if ps >= 0.70 and tf == "strong_positive" and ors > 0:
                    cash_runs.append({
                        "venue": cc,
                        "time": r_time,
                        "name": h.get("horse_name", "?"),
                        "postdata_score": ps,
                        "or_compression_score": ors,
                        "trainer_form": tf,
                    })

    if cash_runs:
        lines = [f"CASH RUNS — {TODAY_DISPLAY}", "=" * 34]
        for cr in cash_runs:
            lines.append(
                f"{cr['venue'].upper()} {cr['time']}  {cr['name'].upper()}\n"
                f"  postdata={cr['postdata_score']:.2f}  OR_compress={cr['or_compression_score']:.2f}"
            )
        tg("\n".join(lines))
        print(f"  Sent: CASH RUNS ({len(cash_runs)} horses)")
    else:
        print("  Cash runs: none detected from PDF data (check PDFs ingested for today)")

    # B. Decision Synthesis Layer — bucket already computed in STEP 3
    buckets: dict = {"A": [], "B": [], "C": [], "D": [], "X": []}

    for race, preds, tier, reasons in scored:
        top = preds[0]
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
        f"SOURCE:     {racecard_source}\n"
        f"A-STRIKE:   {a_n}\n"
        f"B-PLAYABLE: {b_n}\n"
        f"C-WATCH:    {c_n}\n"
        f"D-NO BET:   {d_n}\n"
        f"X-CHAOS:    {x_n}\n"
        f"Total:      {len(scored)}\n"
        f"Overall:    {overall}"
    )
    print(f"  Sent: day posture  A={a_n} B={b_n} C={c_n} D={d_n} X={x_n}  [{overall}]")

    # A-STRIKE — individual governed card per race
    for race, top, second, reasons in buckets["A"]:
        rid = race.get("race_id")
        if persist_map.get(rid):
            card = build_governed_card(race, top, second, "A", reasons, racecard_source, date_str)
            tg(card)
            print(f"  Sent: A-STRIKE (Governed) — {race.get('course')} {race.get('off_time')}")
        else:
            tg(
                f"⚠ CRITICAL: PERSISTENCE FAILURE — A-STRIKE SUPPRESSED\nCourse: {race.get('course')} {race.get('off_time')}\nSignal exists but was not written to DB. Truth loop protected."
            )
            print(f"  SUPPRESSED: A-STRIKE — {race.get('course')} — persistence failed")

    # B-PLAYABLE — individual governed card per race
    for race, top, second, reasons in buckets["B"]:
        rid = race.get("race_id")
        if persist_map.get(rid):
            card = build_governed_card(race, top, second, "B", reasons, racecard_source, date_str)
            tg(card)
            print(f"  Sent: B-PLAYABLE (Governed) — {race.get('course')} {race.get('off_time')}")
        else:
            tg(
                f"⚠ WARNING: PERSISTENCE FAILURE — B-PLAYABLE SUPPRESSED\nCourse: {race.get('course')} {race.get('off_time')}\nSignal suppressed to protect truth loop."
            )
            print(f"  SUPPRESSED: B-PLAYABLE — {race.get('course')} — persistence failed")

    # C-WATCH — grouped brief list
    if buckets["C"]:
        lines = [f"C-WATCH LIST — {TODAY_DISPLAY}", "─" * 34]
        for race, top, second, reasons in buckets["C"]:
            course = race.get("course", "?").upper()
            off = race.get("off_time", "?")
            primary = top.get("horse", "?")
            prob = float(top.get("velo_prime_prob") or 0)
            place = float(top.get("place_prob") or 0)
            gap = prob - float(second.get("velo_prime_prob") or 0)
            r0 = reasons[1] if len(reasons) > 1 else reasons[0] if reasons else ""
            panel = render_signal_attribution_panel(race, top, "C", compact=True)
            lines.append(
                f"{course} {off}  {primary}\n"
                f"  prob {prob:.3f} | gap {gap:.3f} | place {place:.3f}\n"
                f"{panel}\n"
                f"  {r0}"
            )
        tg("\n".join(lines))
        print(f"  Sent: C-WATCH list ({c_n} races)")

    # PLACE SIGNALS — gated by VELO_ENABLE_PLACE_SIGNAL_TELEGRAM=1
    if os.getenv("VELO_ENABLE_PLACE_SIGNAL_TELEGRAM", "0") == "1":
        try:
            place_msg = _build_place_signal_tg(scored, TODAY_DISPLAY)
            if place_msg:
                tg(place_msg)
                print("  Sent: PLACE SIGNALS — LIVE OPERATOR VISIBILITY")
            else:
                print("  Place signals: no active stacks (ELITE through BASE_TRUST) — nothing sent")
        except Exception as _ps_err:
            print(f"  Place signals: skipped — {_ps_err}")
    else:
        print("  Place signals: DISABLED (set VELO_ENABLE_PLACE_SIGNAL_TELEGRAM=1 to enable)")

    # D / X — summary pass list
    pass_races = buckets["D"] + buckets["X"]
    if pass_races:
        lines = [f"D/X PASS LIST — {TODAY_DISPLAY}", "─" * 34]
        for tier_tag, bucket in (("D", buckets["D"]), ("X", buckets["X"])):
            for race, top, _second, reasons in bucket:
                course = race.get("course", "?").upper()
                off = race.get("off_time", "?")
                primary = top.get("horse", "?")
                r0 = reasons[0] if reasons else tier_tag
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
        f"Telegram:        {'YES' if notify_enabled else 'NO'}\n"
        f"Final status:    {final_status}"
    )
    print(f"  Sent: final report ({final_status})")

    # ── STEP 6: Save local JSON (backup only — NOT system of record) ──────────
    # Best-effort only — skipped silently on Railway ephemeral storage
    try:
        out_path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
        results_out = []
        for race, preds, tier, _reasons in scored:
            results_out.append(
                {
                    "race_id": race.get("race_id"),
                    "course": race.get("course"),
                    "off_time": race.get("off_time"),
                    "race_name": race.get("race_name"),
                    "scored": len(preds),
                    "tier": tier,
                    "top": preds[0] if preds else {},
                }
            )
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
        if persistence_enabled:
            _emit_daily_truth_packet(date_str, repair_local_archive=True)
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
        return RunPrimeResult(
            status="FAIL",
            exit_code=1,
            date_str=date_str,
            racecard_source=racecard_source,
            races_fetched=len(raw_races),
            races_normalized=len(normalized),
            races_scored=len(scored),
            persist_ok=persist_ok,
            persist_fail=persist_fail,
            score_errors=len(score_errors),
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )
    elif persist_fail > 0:
        # Partial run — some persisted, some failed → DEGRADED
        err_summary = f"{persist_fail} persist failures, {len(score_errors)} score errors"
        _close_pipeline_run(db, run_id, "DEGRADED", persist_ok, total_runners, err_summary)
        if persistence_enabled:
            _emit_daily_truth_packet(date_str, repair_local_archive=True)
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
        return RunPrimeResult(
            status="DEGRADED",
            exit_code=1,
            date_str=date_str,
            racecard_source=racecard_source,
            races_fetched=len(raw_races),
            races_normalized=len(normalized),
            races_scored=len(scored),
            persist_ok=persist_ok,
            persist_fail=persist_fail,
            score_errors=len(score_errors),
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )
    else:
        _close_pipeline_run(db, run_id, "PASS", persist_ok, total_runners)
        if persistence_enabled:
            _emit_daily_truth_packet(date_str, repair_local_archive=True)
        print(f"\nPASS — {persist_ok}/{len(normalized)} races in velo_verdicts")
        return RunPrimeResult(
            status="PASS",
            exit_code=0,
            date_str=date_str,
            racecard_source=racecard_source,
            races_fetched=len(raw_races),
            races_normalized=len(normalized),
            races_scored=len(scored),
            persist_ok=persist_ok,
            persist_fail=persist_fail,
            score_errors=len(score_errors),
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main().exit_code)
    except SystemExit:
        raise
    except Exception as exc:
        _sb_url = resolve_supabase_url()
        _sb_key = resolve_supabase_service_key()
        active_run_id = (os.getenv("_ACTIVE_PIPELINE_RUN_ID") or "").strip()
        if active_run_id and _sb_url and _sb_key:
            try:
                from supabase import create_client as _sb_create

                _db = _sb_create(_sb_url, _sb_key)
                _close_pipeline_run(_db, active_run_id, "FAIL", 0, 0, str(exc))
            except Exception:
                pass
        raise
