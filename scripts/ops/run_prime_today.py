"""
VELO PRIME Race-Day Execution
==============================
Canonical race-day chain using REAL PRIME scoring path.
Self-contained: uses Racing Post 'One Truth' data from local cache or RP merged.

Chain:
  RACECARDS (cache or RP) -> NORMALIZE -> score_race_velo_prime -> persist_race_predictions -> TELEGRAM

Rules:
  - Raw payloads NEVER reach workers — normalize first, always
  - Supabase is system of record
  - Run is not complete unless all 3: generated + Telegram + Supabase
  - Cache is used when present; RP merged is the fallback
  - No shared filesystem required — safe for Railway cron

Usage:
    python scripts/run_prime_today.py [--date YYYY-MM-DD]

Railway cron command:
    python scripts/run_prime_today.py
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from app.core.runtime_env import (  # noqa: E402
    load_optional_env_file,
    resolve_runtime_environment,
    resolve_supabase_service_key,
    resolve_supabase_url,
    utc_now,
)
from runtime_truth_support import append_telegram_event, get_commit_sha  # noqa: E402

log = logging.getLogger("velo.run_prime")

_BHA_OR_DIFF_LOOKUP: dict[str, dict[str, int]] = {}  # {norm_name: {disc: diff}} loaded once
_BHA_PERF_LOOKUP: dict[str, list] = {}  # {norm_name: [(surf, fig|None), ...]} loaded once


class _RuntimeTimer:
    """Lightweight stage timer. No scoring logic dependency."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._stages: list[dict] = []
        self._last = self._t0

    def mark(self, stage: str, races: int = 0, runners: int = 0, notes: str = "") -> float:
        now = time.perf_counter()
        dur = round(now - self._last, 4)
        self._stages.append(
            {"stage": stage, "duration_sec": dur, "races": races, "runners": runners, "notes": notes}
        )
        self._last = now
        return dur

    def elapsed(self) -> float:
        return round(time.perf_counter() - self._t0, 4)

    def to_dict(
        self,
        *,
        date: str,
        commit_sha: str,
        source: str,
        race_timings: list[dict],
        spotlight_total: int,
        pdf_intel_total: int,
    ) -> dict:
        return {
            "date": date,
            "commit_sha": commit_sha,
            "source": source,
            "total_runtime_sec": self.elapsed(),
            "spotlight_runners_parsed": spotlight_total,
            "pdf_intel_runners_attached": pdf_intel_total,
            "stages": self._stages,
            "race_timings": race_timings,
        }

TODAY = datetime.now().strftime("%Y_%m_%d")
TODAY_DISPLAY = datetime.now().strftime("%d %b %Y")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_TG_DATE = ""
_TG_SERVICE = "velo-prime-scoring"
_TG_NOTIFY_ENABLED = True

CANONICAL_ENDPOINT = "https://velo-oracle-production.up.railway.app"


def _legacy_tg(text: str) -> bool:
    """Disable Telegram for containment."""
    print(f"[CONTAINMENT NO-OP] TG: {text[:60]}")
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
    global TOKEN, CHAT_ID, _SB_URL, _SB_KEY, _SB_HDRS, _BHA_OR_DIFF_LOOKUP, _BHA_PERF_LOOKUP

    load_optional_env_file(env_file or ROOT / ".env")
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") if notify else ""
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") if notify else ""
    _SB_URL = resolve_supabase_url()
    _SB_KEY = resolve_supabase_service_key()
    if not _SB_URL or not _SB_KEY:
        print("  ⚠ Supabase credentials missing. Persistent truth will be SKIPPED.")
        print("  ⚠ Fallback: Use the Supabase Dashboard directly to verify historical records or run with --dry-run.")
    _SB_HDRS = {
        "apikey": _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Accept": "application/json",
    }
    _BHA_OR_DIFF_LOOKUP = _load_bha_or_diff_lookup()
    _BHA_PERF_LOOKUP = _load_bha_perf_lookup()


from src.velo.racecard_loader import (
    load_racecards as _racecard_load,
)
# ── HARNESS: source truth enforcement + observability writer (Phase 2) ─────────
from src.velo.source_truth_enforcer import (
    SourceTruthBlockError as _SourceTruthBlockError,
    SourceTruthDegradedWarning as _SourceTruthDegradedWarning,
    enforce_source_truth as _enforce_source_truth,
)
from write_velo_run_observability import (
    build_observability_packet as _build_obs_packet,
    write_observability_packet as _write_obs_packet,
)


def load_racecards(date_tag: str, date_str: str, source: str | None = None) -> tuple[list, str]:
    """Delegate to src.velo.racecard_loader.load_racecards with runtime constants."""
    races, src_label = _racecard_load(
        date_tag=date_tag,
        date_str=date_str,
        data_root=ROOT / "data",
        source=source,
    )
    n_races = len(races)
    n_runners = sum(len(r.get("runners", [])) for r in races)
    if src_label == "rp_merged":
        print(f"  source: RP_MERGED ({n_races} races built from Racing Post HTML files, {n_runners} runners)")
    elif src_label == "cache":
        print(f"  source: CACHE ({n_races} races)")
    return races, src_label



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


def _load_bha_or_diff_lookup() -> dict[str, dict[str, int]]:
    """Load data/bha_or_diff_latest.csv into a normalised name→discipline→diff dict.

    BHA name format: 'HORSE NAME (IRE)' → normalised to 'horse name' (suffix stripped).
    Disciplines stored: flat, awt, chase, hurdle (match by race_type at lookup time).
    Returns empty dict silently if file absent — signal is optional enrichment.
    """
    import csv as _csv
    import re as _re

    _suffix_re = _re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    path = ROOT / "data" / "bha_or_diff_latest.csv"
    if not path.exists():
        log.warning("BHA OR diff file not found: %s — or_diff signal disabled", path)
        return {}

    lookup: dict[str, dict[str, int]] = {}
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for row in _csv.DictReader(fh):
                raw_name = (row.get("Name") or "").strip()
                norm = _suffix_re.sub("", raw_name).lower().strip()
                if not norm:
                    continue
                discs: dict[str, int] = {}
                for disc, col in (("flat", "Diff Flat"), ("awt", "Diff AWT"),
                                  ("chase", "Diff Chase"), ("hurdle", "Diff Hurdle")):
                    v = (row.get(col) or "").strip()
                    if v and v != "-":
                        try:
                            discs[disc] = int(v.replace("+", ""))
                        except ValueError:
                            pass
                if discs:
                    lookup[norm] = discs
        log.info("BHA OR diff lookup loaded: %d horses with rating changes", len(lookup))
    except Exception as exc:
        log.warning("BHA OR diff load failed: %s", exc)
    return lookup


def _attach_bha_or_diff(top: dict, race_type: str) -> None:
    """Attach BHA official rating diff to the top pick (observability badge only).

    Looks up top['horse'] in _BHA_OR_DIFF_LOOKUP by normalised name.
    Selects the discipline column matching race_type:
      Flat / flat / turf → flat diff
      AWT / aw / allweather → awt diff
      Chase / steeplechase → chase diff
      Hurdle / NHF / nhflat → hurdle diff
    Writes: bha_or_diff (int|None), bha_or_diff_flag ('RAISED'|'LOWERED'|None),
            bha_or_diff_magnitude (int|None).
    Never raises.
    """
    import re as _re

    if not _BHA_OR_DIFF_LOOKUP:
        top.setdefault("bha_or_diff", None)
        top.setdefault("bha_or_diff_flag", None)
        top.setdefault("bha_or_diff_magnitude", None)
        return

    _suffix_re = _re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    raw_name = (top.get("horse") or "").strip()
    norm = _suffix_re.sub("", raw_name).lower().strip()

    rt = (race_type or "").lower()
    if "chase" in rt or "steeplechase" in rt:
        disc = "chase"
    elif "hurdle" in rt or "nhf" in rt or "nh flat" in rt or "national hunt flat" in rt:
        disc = "hurdle"
    elif "aw" in rt or "allweather" in rt or "all-weather" in rt or "polytrack" in rt or "tapeta" in rt:
        disc = "awt"
    else:
        disc = "flat"

    horse_discs = _BHA_OR_DIFF_LOOKUP.get(norm)
    diff = None
    if horse_discs:
        diff = horse_discs.get(disc)
        # AWT races arrive as race_type='Flat'; fall back to awt diff if flat absent
        if diff is None and disc == "flat":
            diff = horse_discs.get("awt")

    top["bha_or_diff"] = diff
    top["bha_or_diff_flag"] = ("RAISED" if diff > 0 else "LOWERED") if diff is not None else None
    top["bha_or_diff_magnitude"] = abs(diff) if diff is not None else None


# ── BHA Performance Figures — surface trajectory ──────────────────────────────
_BHA_PERF_LOOKUP: dict[str, list[tuple[str, int | None]]] = {}  # {norm_name: [(surf, fig_or_None), ...]} latest-first


def _load_bha_perf_lookup() -> dict[str, list[tuple[str, int | None]]]:
    """Load data/bha_perf_figures_latest.csv into a name→[(surf,fig)...] dict.

    Figures are ordered latest-first (position 0 = most recent run).
    fig=None means 'x' (ran, no figure). Missing '-' entries are omitted.
    Returns empty dict silently if file absent.
    """
    import csv as _csv
    import re as _re

    _suffix_re = _re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    _fig_re = _re.compile(r"^([TAHSNM]):(.+)$")
    path = ROOT / "data" / "bha_perf_figures_latest.csv"
    if not path.exists():
        log.warning("BHA perf figures file not found: %s — surf_traj signal disabled", path)
        return {}

    lookup: dict[str, list[tuple[str, int | None]]] = {}
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            reader = _csv.DictReader(fh)
            cols = ["Latest", "2 runs ago", "3 runs ago", "4 runs ago", "5 runs ago", "6 runs ago"]
            for row in reader:
                raw_name = (row.get("Racehorse") or "").strip()
                norm = _suffix_re.sub("", raw_name).lower().strip()
                if not norm:
                    continue
                figs: list[tuple[str, int | None]] = []
                for col in cols:
                    cell = (row.get(col) or "").strip()
                    m = _fig_re.match(cell)
                    if not m:
                        continue  # '-' or empty — no run recorded here
                    surf, val = m.group(1), m.group(2)
                    if val == "x":
                        figs.append((surf, None))  # ran, no figure
                    else:
                        try:
                            figs.append((surf, int(val)))
                        except ValueError:
                            figs.append((surf, None))
                if figs:
                    lookup[norm] = figs
        log.info("BHA perf figures lookup loaded: %d horses", len(lookup))
    except Exception as exc:
        log.warning("BHA perf figures load failed: %s", exc)
    return lookup


def _surf_traj_slope(values: list[int]) -> float:
    """Linear regression slope over values ordered oldest→newest. Returns 0 if < 2 points."""
    n = len(values)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(values))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den if den else 0.0


def _attach_bha_perf_trajectory(top: dict, race_type: str) -> None:
    """Attach BHA surface trajectory badge to the top pick (observability only).

    Selects performance figures matching today's race surface:
      Chase / steeplechase → S figures
      Hurdle / NHF        → H figures (N fallback)
      Flat (turf or AWT)  → T figures preferred; falls back to A if T sparse
    Excludes zero figures (non-finishers). Requires >= 2 non-zero figures to compute slope.

    Writes: surf_traj_surface (str), surf_traj_n (int), surf_traj_latest_fig (int|None),
            surf_traj_slope (float|None), surf_traj_flag (str|None).
    Never raises.
    """
    import re as _re

    _defaults = {
        "surf_traj_surface": None,
        "surf_traj_n": 0,
        "surf_traj_latest_fig": None,
        "surf_traj_slope": None,
        "surf_traj_flag": "SPARSE",
    }

    if not _BHA_PERF_LOOKUP:
        top.update({k: v for k, v in _defaults.items() if k not in top})
        return

    _suffix_re = _re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    raw_name = (top.get("horse") or "").strip()
    norm = _suffix_re.sub("", raw_name).lower().strip()

    horse_figs = _BHA_PERF_LOOKUP.get(norm)
    if not horse_figs:
        top.update(_defaults)
        return

    rt = (race_type or "").lower()
    if "chase" in rt or "steeplechase" in rt:
        target_surfs = ["S"]
    elif "hurdle" in rt or "nhf" in rt or "nh flat" in rt or "national hunt flat" in rt:
        target_surfs = ["H", "N"]
    else:
        # Flat (turf or AWT): prefer whichever has more non-zero figures
        t_figs = [f for s, f in horse_figs if s == "T" and f is not None and f > 0]
        a_figs = [f for s, f in horse_figs if s == "A" and f is not None and f > 0]
        target_surfs = ["T", "A"] if len(t_figs) >= len(a_figs) else ["A", "T"]

    # Collect non-zero numeric figures on target surfaces, latest-first
    matched: list[tuple[str, int]] = []
    used_surf: str | None = None
    for surf in target_surfs:
        candidates = [(s, f) for s, f in horse_figs if s == surf and f is not None and f > 0]
        if candidates:
            matched = candidates
            used_surf = surf
            break

    if not matched:
        top.update(_defaults)
        return

    # latest_fig = first entry (position 0 = most recent)
    latest_fig = matched[0][1]
    nums = [f for _, f in matched]  # still latest-first
    nums_asc = list(reversed(nums))   # oldest-first for regression

    slope = _surf_traj_slope(nums_asc) if len(nums_asc) >= 2 else None

    if slope is None or len(nums_asc) < 2:
        flag = "SPARSE"
    elif slope > 5.0:
        flag = "ACCELERATING"
    elif slope > 2.0:
        flag = "PROGRESSIVE"
    elif slope >= -2.0:
        flag = "STABLE"
    elif slope >= -5.0:
        flag = "REGRESSING"
    else:
        flag = "DECLINING"

    top["surf_traj_surface"] = used_surf
    top["surf_traj_n"] = len(nums_asc)
    top["surf_traj_latest_fig"] = latest_fig
    top["surf_traj_slope"] = round(slope, 2) if slope is not None else None
    top["surf_traj_flag"] = flag


def _apply_bha_or_diff_to_rpdc(top: dict) -> None:
    """Post-attach BHA OR diff modifier for RPDC mark signals.

    Rules:
      BHA LOWERED ≥3pts + MARK_NEAR → add BHA_MARK_CONFIRMED, bump release_score +0.5
      BHA RAISED  ≥3pts + MARK_READY → add BHA_MARK_RAISED (suppressor evidence)
    Evidence-only — no gate change, no staking weight. Shadow signal.
    """
    flag = top.get("bha_or_diff_flag")
    magnitude = top.get("bha_or_diff_magnitude") or 0
    if not flag or magnitude < 3:
        return

    tags = list(top.get("rpdc_tags") or [])
    primary = top.get("rpdc_primary_tag") or ""

    if flag == "LOWERED" and "MARK_NEAR" in tags:
        if "BHA_MARK_CONFIRMED" not in tags:
            tags.append("BHA_MARK_CONFIRMED")
            top["rpdc_tags"] = tags
            top["rpdc_release_score"] = float(top.get("rpdc_release_score") or 0) + 0.5
            log.debug("BHA_MARK_CONFIRMED added for %s (lowered %dpts + MARK_NEAR)",
                      top.get("horse"), magnitude)

    elif flag == "RAISED" and "MARK_READY" in tags:
        if "BHA_MARK_RAISED" not in tags:
            tags.append("BHA_MARK_RAISED")
            top["rpdc_tags"] = tags
            log.debug("BHA_MARK_RAISED suppressor added for %s (raised %dpts + MARK_READY)",
                      top.get("horse"), magnitude)


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
                    # Recent running row — warn but allow override
                    print(
                        f"  [pipeline_runs] WARNING: run already running (id={row['id']}, age={age_hours:.1f}h). Proceeding anyway."
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
    if not rows:
        log.warning("RPDC zero-runner warning: No candidates found for race_id=%s", race_id)
    return {r["horse_id"]: r for r in rows}


# Day-level RPDC name-fallback map — loaded once per run, only when an exact
# race_id join comes back empty (the June 9 synthetic-ID bypass pattern).
# Deterministic unique-name matching only; ambiguity attaches nothing.
_DAY_RPDC_NAME_MAP: dict | None = None


def _get_day_rpdc_name_map(date_str: str) -> dict:
    global _DAY_RPDC_NAME_MAP
    if _DAY_RPDC_NAME_MAP is None:
        from src.velo.rpdc_attach import build_name_map

        rows = sb_get(f"/runner_release_candidates?run_date=eq.{date_str}&select=*")
        _DAY_RPDC_NAME_MAP = build_name_map(rows or [])
        log.warning(
            "RPDC name-fallback map loaded for %s: %d unique names "
            "(exact race_id join returned nothing — synthetic-ID card suspected)",
            date_str,
            len(_DAY_RPDC_NAME_MAP),
        )
    return _DAY_RPDC_NAME_MAP


def main():
    global _TG_DATE, _TG_NOTIFY_ENABLED
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--env-file", default=None)
    parser.add_argument(
        "--source",
        choices=["auto", "cache", "rp", "api"],
        default=None,
        help="Racecard source: auto (default, tries cache→rp→api), cache, rp, api",
    )
    args = parser.parse_args()
    notify_enabled = not args.no_notify and not args.dry_run
    _bootstrap_runtime(env_file=args.env_file, notify=notify_enabled)
    date_tag = args.date.replace("-", "_") if args.date else TODAY
    date_str = date_tag.replace("_", "-")
    _display_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b %Y")
    persistence_enabled = not args.dry_run
    _TG_DATE = date_str
    _TG_NOTIFY_ENABLED = notify_enabled

    print(f"\nVELO PRIME RACE-DAY EXECUTION — {date_str}")
    print("=" * 60)

    _timer = _RuntimeTimer()

    # ── PREFLIGHT GATE — must pass before anything else runs ─────────────────
    print("\nPREFLIGHT")
    print("-" * 40)
    from src.preflight import preflight_or_die

    pf_result = preflight_or_die(tg_fn=tg)  # exits with sys.exit(1) on FAIL
    print(f"  Status: {pf_result.status}")
    print("-" * 40)
    _timer.mark("preflight")
    # ─────────────────────────────────────────────────────────────────────────

    from app.services.velo_prime_service import persist_race_predictions, score_race_velo_prime
    from src.rpd import RPDv2Engine
    from src.velo.midprice_hunter import evaluate_and_log as _midprice_evaluate
    from src.velo.runner_snapshot_store import (
        build_run_id as _build_run_id,
        write_runner_snapshots as _write_runner_snapshots,
    )
    from src.velo.feature_audit import (
        detect_vp_flatline as _detect_vp_flatline,
        flatline_summary_for_run as _flatline_summary_for_run,
    )
    from src.velo.signal_stack import build_signal_stack_payload as _build_signal_stack
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
    raw_races, racecard_source = load_racecards(date_tag, date_str, source=args.source)
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
    live_label = {"api": "LIVE_API", "cache": "CACHE", "rp_merged": "RP_MERGED"}.get(racecard_source, racecard_source.upper())
    commit_sha = get_commit_sha()
    _snapshot_run_id = _build_run_id(date_tag, commit_sha)

    print(f"\n{'=' * 60}")
    print("  SOURCE TRUTH HEADER")
    print(f"  requested_date : {date_str}")
    print(f"  loaded_date(s) : {loaded_date_str}")
    print(f"  source         : {live_label} ({racecard_source})")
    print(f"  commit_sha     : {commit_sha}")
    print("  router_version : ProductRouter v1 (live-safe)")
    if date_mismatch:
        print(f"  ⚠ DATE MISMATCH — loaded card is NOT for {date_str}")
        print("  ⚠ This is a cache/stale fetch. Marking output NON-LIVE.")
    elif not is_live:
        print("  ℹ Source = CACHE. Card date matches request.")
    else:
        print("  ✓ Source = LIVE API. Card date matches request.")
    print(f"{'=' * 60}\n")

    if date_mismatch and notify_enabled:
        print("  TELEGRAM SUPPRESSED — date mismatch, would send stale card as live")
        notify_enabled = False
        _TG_NOTIFY_ENABLED = False

    # ── HARNESS GATE: Source Truth Enforcement ─────────────────────────────────
    # Translates loader label to canonical harness label.
    # SOURCE_UNKNOWN_BLOCK raises immediately — execution cannot continue.
    # RP_MERGED_DEGRADED continues with warning and records in observability.
    # This runs BEFORE normalization and BEFORE scoring. No scoring logic touched.
    print("\n  HARNESS: Source truth enforcement")
    import warnings as _warnings
    _source_truth_warnings: list[str] = []
    try:
        with _warnings.catch_warnings(record=True) as _caught_warnings:
            _warnings.simplefilter("always")
            _source_truth_result = _enforce_source_truth(
                racecard_source, races=raw_races, raise_on_block=True
            )
        for _w in _caught_warnings:
            if issubclass(_w.category, _SourceTruthDegradedWarning):
                _source_truth_warnings.append(str(_w.message))
                print(f"  [HARNESS WARN] {_w.message}")
    except _SourceTruthBlockError as _block_err:
        # Hard stop — write observability packet recording the block, then exit
        print(f"\n  [HARNESS BLOCK] SOURCE_UNKNOWN_BLOCK: {_block_err}")
        _obs_block = _build_obs_packet(
            date_str=date_str,
            source_truth="SOURCE_UNKNOWN_BLOCK",
            feature_health="BLOCKED",
            active_formula="BLOCKED_BEFORE_SCORING",
            excluded_live_components=[],
            race_scoring_coverage_pct=0.0,
            persistence_status="BLOCKED",
            supabase_write_attempt_success=False,
            decision_tier_status="BLOCKED",
            learning_gate="BLOCKED_SOURCE_UNKNOWN",
            next_safe_command="python scripts/ops/velo_session_start_check.py",
            races_processed=0,
            runners_processed=0,
            warnings=[str(_block_err)],
            gate_fires={"gate_source_unknown_block": True},
            extra={"git_commit_sha": commit_sha, "racecard_source_raw": racecard_source},
        )
        _write_obs_packet(_obs_block)
        return RunPrimeResult(
            status="BLOCKED",
            exit_code=1,
            date_str=date_str,
            racecard_source=racecard_source,
            notifications_enabled=notify_enabled,
            persistence_enabled=persistence_enabled,
        )
    _canonical_source = _source_truth_result.canonical_label
    print(f"  source_truth_canonical : {_canonical_source}")
    if _source_truth_result.degraded:
        print("  [HARNESS WARN] RP_MERGED_DEGRADED — feature degradation active, learning will be blocked")
    # ─────────────────────────────────────────────────────────────────────

    print(f"  Source: {racecard_source}  races: {len(raw_races)}  with runners: {len(races_with_runners)}")
    _timer.mark("racecard_load", races=len(raw_races))

    # ── RACECARD CACHE COMPLETENESS GATE ─────────────────────────────────────
    # Hard pre-scoring gate. If the loaded card is incomplete (stale cache,
    # wrong date, suspiciously low races/runners) the engine must not proceed.
    from src.velo.racecard_cache_gate import validate_racecard, print_gate_result
    _gate_result = validate_racecard(
        raw_races=raw_races,
        date_str=date_str,
        racecard_source=racecard_source,
        sb_url=_SB_URL,
        sb_key=_SB_KEY,
    )
    print_gate_result(_gate_result)
    
    # OVERRIDE: June 9 PDF Source Bypass
    if not _gate_result.passed and racecard_source == "rp_merged":
        print("  [OVERRIDE] Metadata gate failed for RP_MERGED, but PDF data verified. Proceeding with scoring.")
    elif not _gate_result.passed:
        print("BAD_RACECARD_CACHE_BLOCKED — engine halted before scoring.")
        print("Fix: delete or replace the stale cache file and re-run.")
        print(f"  Cache: data/racecards_{date_tag}_standard.json")
        sys.exit(1)
    # ── END GATE ──────────────────────────────────────────────────────────────

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
    _n_runners_total = sum(len(r.get("runners", [])) for r in normalized)
    _timer.mark("normalize", races=len(normalized), runners=_n_runners_total)

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

    # Pre-load all available RP-merged intelligence for today's tracks.
    pdf_intel_cache = {}
    for race in normalized:
        course_name = (race.get("course") or "").upper().replace(" ", "_")
        course_code = (race.get("course_id") or race.get("course", "")).upper()
        
        # Try finding a merged racecard file for this course
        cc = course_code[:3]
        found_path = None
        
        # Check standard prefix first
        pdf_path = ROOT / "data" / "racecard_merged" / f"racecard_{cc}_{date_str}.json"
        if pdf_path.exists():
            found_path = pdf_path
        else:
            # Try searching for course name in filenames
            candidates = list((ROOT / "data" / "racecard_merged").glob(f"racecard_*{course_name}*{date_str}.json"))
            if candidates:
                found_path = candidates[0]
                # Extract the code from the filename (e.g. racecard_HAPPY_VALLEY_2026-06-03.json -> HAPPY_VALLEY)
                # Filename is usually racecard_CODE_DATE.json
                parts = found_path.name.split("_")
                if len(parts) >= 3:
                    cc = "_".join(parts[1:-1])
        
        if found_path and cc not in pdf_intel_cache:
            with open(found_path) as f:
                pdf_intel_cache[cc] = json.load(f)
        elif cc not in pdf_intel_cache:
            pdf_intel_cache[cc] = None

    _pdf_courses_loaded = sum(1 for v in pdf_intel_cache.values() if v is not None)
    _timer.mark("pdf_intel_preload", races=_pdf_courses_loaded, notes=f"{_pdf_courses_loaded}/{len(pdf_intel_cache)} courses with RP-merged data")

    scored = []
    score_errors = []
    _race_timings: list[dict] = []
    _spotlight_total = 0
    _pdf_intel_attached_total = 0
    _flatlines: list[dict] = []
    for race in normalized:
        cid = f"{race.get('course')} {race.get('off_time', '?')}"

        # Attach RP-merged intelligence to normalized runners before scoring.
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

        _pdf_attached_this_race = sum(1 for r in race.get("runners", []) if r.get("pdf_intel"))
        _pdf_intel_attached_total += _pdf_attached_this_race

        _t_score_start = time.perf_counter()
        try:
            preds = score_race_velo_prime(race, sentient_state=_sentient_state)
            _t_score_vp = time.perf_counter() - _t_score_start
            if preds:
                # Load RPDC data for this race to inform RPD-C tags
                race_rpdc = _fetch_race_rpdc(race.get("race_id", ""))
                # Deterministic fallback (June 9 pattern): exact race_id join
                # empty -> resolve by run_date + unique normalized horse name.
                from src.velo.rpdc_attach import resolve_runner_rpdc

                _rpdc_name_map = _get_day_rpdc_name_map(date_str) if not race_rpdc else None

                # RPD-C tagging — passive metadata only, no score/rank mutation
                runner_map = {r.get("horse_name", ""): r for r in race.get("runners", [])}
                _spotlight_this_race = 0
                for pred in preds:
                    raw_runner = runner_map.get(pred.get("horse", ""), {})
                    horse_id = raw_runner.get("horse_id")
                    runner_rpdc, _runner_attach_method = resolve_runner_rpdc(
                        race_rpdc, _rpdc_name_map, horse_id, pred.get("horse", "")
                    )
                    runner_rpdc = runner_rpdc or {}

                    # Spotlight Parsing — NOTE: happens AFTER score_race_velo_prime,
                    # so spotlight_score cannot affect velo_prime_prob or rank order.
                    spot_text = raw_runner.get("spotlight", "")
                    if spot_text:
                        _spotlight_this_race += 1
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
                _spotlight_total += _spotlight_this_race

                # ── Flatline detector (Issue #85) ─────────────────────────────
                # Read-only post-scoring check — never alters velo_prime_prob,
                # rank order, tier, router lane, or execution.
                _flatline_info = _detect_vp_flatline(
                    race.get("race_id", ""),
                    preds,
                    racecard_source,
                )
                if _flatline_info:
                    _flatlines.append(_flatline_info)
                    log.warning(_flatline_info["warning"])

                # ── NDS Report-Only Wire-In ────────────────────────────────
                # REPORT_ONLY — never alters velo_prime_prob, tier, routing,
                # or execution. Attaches nds_* badge fields to each pred.
                try:
                    import pandas as _pd
                    from src.intelligence.nds import NDS as _NDS
                    _nds_engine = _NDS()
                    _runners_df = _pd.DataFrame([{
                        "sp_decimal": float(p.get("sp_dec") or 10.0),
                        "horse": p.get("horse", ""),
                        "date": date_str,
                        "course": race.get("course", ""),
                        "num": i + 1,
                    } for i, p in enumerate(preds)])
                    _hist_df = _pd.DataFrame()
                    _nds_results = _nds_engine.analyze_race(_runners_df, _hist_df)
                    _nds_by_horse = {r.horse_name: r for r in _nds_results}
                    for _p in preds:
                        _nr = _nds_by_horse.get(_p.get("horse", ""))
                        if _nr:
                            _p["nds_narrative"] = _nr.narrative_type.value
                            _p["nds_score"] = round(_nr.nds_score, 4)
                            _p["nds_disruption"] = _nr.disruption_strength.value
                            _p["nds_is_fade"] = _nr.is_fade_opportunity
                            _p["nds_overround_signal"] = round(_nr.overround_signal, 4)
                        else:
                            _p["nds_narrative"] = "none"
                            _p["nds_score"] = 0.0
                            _p["nds_disruption"] = "none"
                            _p["nds_is_fade"] = False
                            _p["nds_overround_signal"] = 0.0
                    _fade_flags = [_p.get("horse") for _p in preds if _p.get("nds_is_fade")]
                    if _fade_flags:
                        log.info("[NDS] FADE signals race=%s horses=%s", race.get("race_id"), _fade_flags)
                except Exception as _nds_err:
                    log.debug("[NDS] wire-in skipped: %s", _nds_err)
                    for _p in preds:
                        _p.setdefault("nds_narrative", "none")
                        _p.setdefault("nds_score", 0.0)
                        _p.setdefault("nds_is_fade", False)
                # ─────────────────────────────────────────────────────────

                # ── Intelligence Chains Report-Only Wire-In ───────────────
                # REPORT_ONLY — pace, narrative, market chains run for context.
                # Results stored as chain_* badge fields only.
                # Never alters velo_prime_prob, tier, routing, or execution.
                try:
                    import asyncio as _asyncio
                    from app.optim.async_scheduler import run_chains_parallel as _run_chains
                    _chain_result = _asyncio.run(
                        _run_chains(race, race.get("runners", []))
                    )
                    _pace_shape = (
                        _chain_result.get("pace", {})
                        .get("signals", {})
                        .get("race_shape", {})
                        .get("shape", "unknown")
                    )
                    _narrative_sig = (
                        _chain_result.get("narrative", {})
                        .get("signals", {})
                        .get("primary_narrative", {})
                        .get("narrative_type", "unknown")
                    )
                    _market_status = _chain_result.get("market", {}).get("status", "unknown")
                    for _p in preds:
                        _p["chain_pace_shape"] = _pace_shape
                        _p["chain_narrative"] = _narrative_sig
                        _p["chain_market_status"] = _market_status
                    log.info(
                        "[CHAINS] race=%s pace=%s narrative=%s market=%s",
                        race.get("race_id"), _pace_shape, _narrative_sig, _market_status,
                    )
                except Exception as _chain_err:
                    log.debug("[CHAINS] wire-in skipped: %s", _chain_err)
                    for _p in preds:
                        _p.setdefault("chain_pace_shape", "unavailable")
                        _p.setdefault("chain_narrative", "unavailable")
                        _p.setdefault("chain_market_status", "unavailable")
                # ─────────────────────────────────────────────────────────

                top = preds[0]
                second = preds[1] if len(preds) > 1 else {}
                sec_prob = float(second.get("velo_prime_prob") or 0)
                tier, reasons = synthesize_decision(top, sec_prob, field_size=len(preds))
                # Write effective confidence back onto top so persist sees it.
                # Raw label (pre-normalization) is preserved separately.
                top["confidence_level_raw"] = top.get("confidence_level")
                top["confidence_level_effective"] = effective_confidence(float(top.get("velo_prime_prob") or 0))
                top["rp_flatline_warning"] = _flatline_info.get("warning") if _flatline_info else None
                # Shadow suspect cohort flag — A-tier with weak place support.
                # No gate change. Passive monitor only. Track for 30 days to build
                # enough sample to decide whether to tighten the A-gate conditionally.
                # Cohort: A-tier AND place_prob < 0.75 (win signal overpowering place).
                top["a_tier_weak_place_flag"] = tier == "A" and float(top.get("place_prob") or 0) < 0.75
                tier, reasons = _apply_tie_v3_gate(top, tier, reasons, preds)
                _apply_archetype(top, preds, tier, sec_prob)
                _add_secondary_signals(top, reasons)
                # Attach RPDC data to top pick — exact race_id first, then the
                # deterministic name fallback; ambiguity attaches nothing.
                _top_row, _top_attach_method = resolve_runner_rpdc(
                    race_rpdc, _rpdc_name_map, top.get("horse_id"), top.get("horse")
                )
                _attach_rpdc_from_row(top, _top_row)
                top["rpdc_attach_method"] = _top_attach_method
                if _top_attach_method == "ambiguous_blocked":
                    top["rpdc_lookup_status"] = "ambiguous_blocked"
                # Attach BHA OR diff badge (evidence only — no scoring weight)
                _attach_bha_or_diff(top, race.get("type") or race.get("race_type") or "")
                # Attach BHA surface trajectory badge (evidence only — no scoring weight)
                _attach_bha_perf_trajectory(top, race.get("type") or race.get("race_type") or "")
                # Apply BHA OR diff modifier to RPDC mark tags (shadow signal — evidence only)
                _apply_bha_or_diff_to_rpdc(top)
                # Claiming race flag — adds OWNERSHIP_CHANGE badge (evidence only, shadow)
                _rt = (race.get("type") or race.get("race_type") or "").lower()
                if "claim" in _rt:
                    _tags = list(top.get("rpdc_tags") or [])
                    if "OWNERSHIP_CHANGE" not in _tags:
                        _tags.append("OWNERSHIP_CHANGE")
                        top["rpdc_tags"] = _tags
                        top["claiming_race"] = True
                        log.debug("OWNERSHIP_CHANGE badge added for %s (claiming race)", top.get("horse"))
                else:
                    top["claiming_race"] = False

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
                from app.services.sqpe_v17_service import _parse_class
                _class_num = _parse_class(race.get("race_class") or race.get("class"))
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

                # ── Signal Stack payload (Issue #84) ──────────────────────────
                # Display/persistence truth — no scoring or routing side effects.
                top["signal_stack"] = _build_signal_stack(
                    race=race,
                    top=top,
                    tier=tier,
                    sec_prob=sec_prob,
                    racecard_source=racecard_source,
                    route_data=route_data,
                )


                if pdf_intel.get("plot_conviction"):
                    reasons.append(f"PDF_PLOT_CONVICTION:{pdf_intel['plot_conviction']:.2f}")

                scored.append((race, preds, tier, reasons))

                # ── Mid-Price Hunter shadow evaluation ────────────────────
                # SHADOW ONLY — never alters velo_prime_prob, tier, routing,
                # or execution. Runs after score_race_velo_prime() returns.
                try:
                    _midprice_verdict = _midprice_evaluate(
                        race_id=race.get("race_id", ""),
                        race_date=date_str,
                        course=race.get("course", ""),
                        off_time=race.get("off_time", ""),
                        tier=tier,
                        top_pick=top.get("horse", ""),
                        top_vp=top.get("velo_prime_prob"),
                        top_mds=top.get("market_deception_score"),
                        top_improvement=top.get("improvement_score"),
                        top_place_prob=top.get("place_prob"),
                        field_size=len(preds),
                        class_num=race.get("class_num") or race.get("race_class"),
                        sp_dec=top.get("sp_dec"),
                    )
                    top["midprice_shadow_action"] = _midprice_verdict.get("shadow_action")
                    top["midprice_shadow_evidence"] = _midprice_verdict.get("evidence")
                    top["midprice_shadow_field_band"] = _midprice_verdict.get("field_band")
                    top["midprice_shadow_rule_version"] = _midprice_verdict.get("rule_version")
                except Exception as _mph_exc:
                    log.warning("midprice_hunter shadow eval failed: %s", _mph_exc)

                _n_runners_this_race = len(preds)
                _per_runner_avg_ms = round(_t_score_vp / _n_runners_this_race * 1000, 3) if _n_runners_this_race else 0.0
                _race_timings.append({
                    "race_id": race.get("race_id", ""),
                    "course": race.get("course", ""),
                    "off_time": race.get("off_time", ""),
                    "runners": _n_runners_this_race,
                    "score_race_velo_prime_sec": round(_t_score_vp, 4),
                    "per_runner_avg_ms": _per_runner_avg_ms,
                    "pdf_intel_attached_count": _pdf_attached_this_race,
                    "spotlight_parsed_count": _spotlight_this_race,
                })
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

    # ── Flatline summary (Issue #85) ──────────────────────────────────────────
    _flatline_summary = _flatline_summary_for_run(_flatlines, total_races=len(scored))
    if _flatlines:
        print(
            f"\n  RP_FEATURE_FLATLINE: {_flatline_summary['flatline_count']}/{_flatline_summary['total_races']} races "
            f"({_flatline_summary['flatline_pct']:.1%}) — "
            f"{_flatline_summary['fully_uniform_count']} fully uniform, "
            f"{_flatline_summary['majority_tied_count']} majority tied"
        )
        for _fl in _flatlines:
            print(f"    {_fl['race_id']}: {_fl['warning'][:100]}")
    else:
        print(f"\n  RP_FEATURE_FLATLINE: 0/{len(scored)} races — VP well-differentiated")

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

        success = persist_race_predictions(race, preds, decision_tier=tier, commit_sha=commit_sha)
        persist_map[rid] = success

        if success:
            persist_ok += 1
        else:
            persist_fail += 1
            print(f"  PERSIST FAIL: {rid} {race.get('course')}")

    print(f"  Verdicts: {persist_ok} OK / {persist_fail} FAIL / {len(scored)} total")
    _timer.mark("persist", races=persist_ok + persist_fail, runners=sum(len(p) for _, p, _, _ in scored))

    # ── Gate 2: Detect feature degradation ────────────────────────────────────
    # Check if any live-weighted component was excluded from the ensemble on >80%
    # of races. If so, build a banner to send at the top of Telegram output.
    _LIVE_GATE_WEIGHTS = {"sqpe_v17": 0.45, "improvement_score": 0.12, "market_deception_score": 0.10}
    _EXPECTED_DENOM = sum(_LIVE_GATE_WEIGHTS.values())  # 0.67
    _degraded_components: list[str] = []
    _feature_degraded_banner: str = ""
    if scored:
        _all_gate_tops = [preds[0] for _, preds, _, _ in scored if preds]
        _gate_tracked = [t for t in _all_gate_tops if t.get("active_components") is not None]
        if _gate_tracked:
            for _comp in ("improvement_score", "market_deception_score"):
                _excl = sum(1 for t in _gate_tracked if _comp not in (t.get("active_components") or []))
                if _excl / len(_gate_tracked) > 0.80:
                    _degraded_components.append(_comp)
        if _degraded_components:
            # Compute effective denominator from a sample top pick's active_components
            _sample_active = _all_gate_tops[0].get("active_components") or []
            _denom_used = round(sum(_LIVE_GATE_WEIGHTS.get(k, 0) for k in _sample_active), 2)
            _feature_degraded_banner = (
                f"⚠ VÉLØ FEATURE_DEGRADED — {_display_date}\n"
                f"{'─' * 34}\n"
                + "\n".join(f"  EXCLUDED: {c}" for c in _degraded_components) + "\n"
                + f"  Formula: {' + '.join(_sample_active)} only\n"
                + f"  Denominator used: {_denom_used} (expected: {_EXPECTED_DENOM})\n"
                + f"  VP confidence inflated. Rankings within each race unchanged.\n"
                + f"  B-tier: treat with reduced conviction.\n"
                + f"  Learning from today BLOCKED until reconciliation closes."
            )
            print(f"  FEATURE_DEGRADED detected: {_degraded_components}")

    # ── STEP 5: Build Telegram output ─────────────────────────────────────────
    print("\nSTEP 5: Send to Telegram")

    # A. Pre-flight report — reflects actual preflight result
    pf_lines = [f"  {c.name}: {'OK' if c.passed else c.detail}" for c in pf_result.checks]
    tg(
        f"VELO PRE-FLIGHT REPORT — {_display_date}\n"
        f"repo:       elpresidentepiff/velo-oracle-prime\n"
        f"racecards:  {racecard_source}\n" + "\n".join(pf_lines) + "\n"
        f"STATUS:     {pf_result.status}"
    )
    print("  Sent: pre-flight report")

    # A0a. FEATURE_DEGRADED_BANNER — sent immediately after pre-flight if degraded
    if _feature_degraded_banner and notify_enabled:
        tg(_feature_degraded_banner, label="FEATURE_DEGRADED_BANNER")
        print(f"  Sent: FEATURE_DEGRADED_BANNER ({', '.join(_degraded_components)})")

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
        lines = [f"CASH RUNS — {_display_date}", "=" * 34]
        for cr in cash_runs:
            lines.append(
                f"{cr['venue'].upper()} {cr['time']}  {cr['name'].upper()}\n"
                f"  postdata={cr['postdata_score']:.2f}  OR_compress={cr['or_compression_score']:.2f}"
            )
        tg("\n".join(lines))
        print(f"  Sent: CASH RUNS ({len(cash_runs)} horses)")
    else:
        print("  Cash runs: none detected from RP-merged data")

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
        f"VELO DAY POSTURE — {_display_date}\n"
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
        lines = [f"C-WATCH LIST — {_display_date}", "─" * 34]
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
            place_msg = _build_place_signal_tg(scored, _display_date)
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
        lines = [f"D/X PASS LIST — {_display_date}", "─" * 34]
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
        f"VELO PERSISTENCE REPORT — {_display_date}\n"
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
        f"VELO FINAL REPORT — {_display_date}\n"
        f"Total races:     {len(normalized)}\n"
        f"Scored by PRIME: {len(scored)}\n"
        f"Persisted:       {persist_ok}\n"
        f"Telegram:        {'YES' if notify_enabled else 'NO'}\n"
        f"Final status:    {final_status}"
    )
    print(f"  Sent: final report ({final_status})")
    _timer.mark("telegram")

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
                    "signal_stack": preds[0].get("signal_stack") if preds else None,
                }
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results_out, indent=2, default=str))
        print(f"\nLocal backup: {out_path.name} (NOT system of record)")
    except Exception as e:
        print(f"\nLocal backup skipped: {e}")
    _timer.mark("local_backup")

    # ── RUNNER SNAPSHOT STORE (Issue #80) ─────────────────────────────────────
    # STORAGE ONLY — never alters scoring, routing, or execution.
    # Batch write of all runners across all scored races.
    # Failure logs a warning and returns 0; never aborts the pipeline.
    try:
        _snapshot_n = _write_runner_snapshots(
            scored=scored,
            date_str=date_str,
            date_tag=date_tag,
            run_id=_snapshot_run_id,
            supabase_client=db if persistence_enabled else None,
        )
        print(f"\nRUNNER SNAPSHOTS: {_snapshot_n} rows → runner_snapshots_{date_tag}_{_snapshot_run_id}.jsonl")
    except Exception as _snap_exc:
        print(f"\nRunner snapshot write skipped: {_snap_exc}")
    _timer.mark("runner_snapshots", races=len(scored), runners=sum(len(p) for _, p, _, _ in scored))

    # ── TIMING AUDIT ──────────────────────────────────────────────────────────
    try:
        _timing_out = ROOT / "data" / "timing_audit" / f"runtime_timing_audit_{date_tag}.json"
        _timing_payload = _timer.to_dict(
            date=date_str,
            commit_sha=commit_sha,
            source=racecard_source,
            race_timings=_race_timings,
            spotlight_total=_spotlight_total,
            pdf_intel_total=_pdf_intel_attached_total,
        )
        _timing_payload["flatline_summary"] = _flatline_summary
        _timing_out.parent.mkdir(parents=True, exist_ok=True)
        _timing_out.write_text(json.dumps(_timing_payload, indent=2, default=str))
        print(f"\nTIMING AUDIT: {_timing_out.name}")
        print(f"  total_runtime_sec       : {_timing_payload['total_runtime_sec']:.3f}s")
        print(f"  spotlight_runners_parsed: {_timing_payload['spotlight_runners_parsed']}")
        print(f"  pdf_intel_attached      : {_timing_payload['pdf_intel_runners_attached']}")
        for _s in _timing_payload["stages"]:
            _note = f"  [{_s['notes']}]" if _s.get("notes") else ""
            print(f"  {_s['stage']:<22s}: {_s['duration_sec']:>8.3f}s  races={_s['races']}  runners={_s['runners']}{_note}")
    except Exception as _timing_exc:
        print(f"\nTiming audit write skipped: {_timing_exc}")

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

    # ── HARNESS: Observability packet builder (shared across all exit paths) ───────
    # Derives feature health from flatline summary. Writes on PASS, FAIL, and DEGRADED.
    # No scoring logic. No Supabase writes. Local artifact only.
    def _build_and_write_obs(final_status: str) -> None:
        """Build and write the observability packet for this run. Never raises."""
        try:
            _fl = _flatline_summary if "_flatline_summary" in dir() else {}
            _fl_pct = _fl.get("flatline_pct", 0.0) if _fl else 0.0
            if _fl_pct > 0.5:
                _fh = "DEGRADED_FLATLINE"
            elif _fl_pct > 0.2:
                _fh = "PARTIAL_FLATLINE"
            elif _source_truth_result.degraded:
                _fh = "DEGRADED_RP_MERGED"
            else:
                _fh = "HEALTHY"
            _obs_warnings = list(_source_truth_warnings)
            if _fl_pct > 0.2:
                _obs_warnings.append(
                    f"RP_FEATURE_FLATLINE: {_fl.get('flatline_count', 0)}/{_fl.get('total_races', 0)} races "
                    f"({_fl_pct:.1%}) — {_fl.get('fully_uniform_count', 0)} fully uniform"
                )
            if score_errors:
                _obs_warnings.append(f"{len(score_errors)} score error(s) in this run")
            _learning_gate = (
                "BLOCKED_DEGRADED_SOURCE" if _source_truth_result.degraded
                else ("BLOCKED_FAIL" if final_status == "FAIL" else "ELIGIBLE")
            )
            _obs = _build_obs_packet(
                date_str=date_str,
                source_truth=_canonical_source,
                feature_health=_fh,
                active_formula=f"sqpe_v17 | {_canonical_source}",
                excluded_live_components=[],
                race_scoring_coverage_pct=float(len(scored)) / max(len(normalized), 1) * 100,
                persistence_status="OK" if persist_ok > 0 else "FAIL",
                supabase_write_attempt_success=(persist_ok > 0 and persistence_enabled),
                decision_tier_status=final_status,
                learning_gate=_learning_gate,
                next_safe_command="python scripts/ops/velo_session_start_check.py",
                races_processed=len(scored),
                runners_processed=total_runners,
                warnings=_obs_warnings,
                gate_fires={
                    "gate_2_flatline_fires": _fl_pct > 0.5,
                    "gate_5_rpdc_warn_fires": len(scored) < len(normalized),
                    "gate_6_learning_blocked": _source_truth_result.degraded or final_status == "FAIL",
                    "gate_source_unknown_block": False,
                },
                extra={
                    "git_commit_sha": commit_sha,
                    "racecard_source_raw": racecard_source,
                    "persist_ok": persist_ok,
                    "persist_fail": persist_fail,
                    "score_errors": len(score_errors),
                    "flatline_summary": _fl,
                },
            )
            _write_obs_packet(_obs)
        except Exception as _obs_exc:
            print(f"  [HARNESS WARN] Observability packet write failed: {_obs_exc}")
    # ─────────────────────────────────────────────────────────────────────

    if persist_fail > 0 and persist_ok == 0:
        # Total failure — nothing persisted
        err_summary = f"{persist_fail} persist failures, {len(score_errors)} score errors"
        _close_pipeline_run(db, run_id, "FAIL", persist_ok, total_runners, err_summary)
        if persistence_enabled:
            _emit_daily_truth_packet(date_str, repair_local_archive=True)
        _build_and_write_obs("FAIL")  # HARNESS: mandatory observability on FAIL
        print(f"\nFAIL — 0/{len(normalized)} races in velo_verdicts")
        tg(
            f"VELO ALERT — FAIL — {_display_date}\n"
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
        _build_and_write_obs("DEGRADED")  # HARNESS: mandatory observability on DEGRADED
        print(f"\nDEGRADED — {persist_ok}/{len(normalized)} races in velo_verdicts ({persist_fail} failed)")
        tg(
            f"VELO ALERT — DEGRADED — {_display_date}\n"
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
        _build_and_write_obs("PASS")  # HARNESS: mandatory observability on PASS
        # ── Supabase Write-Proof Report ──────────────────────────────────────
        print(f"\nPASS — {persist_ok}/{len(normalized)} races in velo_verdicts")
        if persist_ok > 0:
            print(f"  SUPABASE WRITE-PROOF REPORT — {_display_date}")
            print(f"  {'-' * 45}")
            for rid, ok in persist_map.items():
                if ok:
                    print(f"  ✓ {rid}")
            print(f"  {'-' * 45}")
            print(f"  Total verified writes: {persist_ok}")

        # ── Auto-update: New Build card feed + two-lane score + dashboard ────
        import subprocess as _sp
        _py = sys.executable
        _date_tag = date_str.replace("-", "_")
        _rc_path = ROOT / "data" / f"racecards_{_date_tag}_standard.json"
        _nb_env = {**os.environ, "PYTHONPATH": str(ROOT)}

        # Step 1: New Build current card feed
        try:
            _nb_cmd = [_py, str(ROOT / "scripts/ops/new_build_current_card_feed.py"), "--execute"]
            if _rc_path.exists():
                _nb_cmd += ["--racecard-path", str(_rc_path)]
            _r = _sp.run(
                _nb_cmd,
                capture_output=True, text=True, cwd=str(ROOT), env=_nb_env,
            )
            if _r.returncode == 0:
                print("  New Build card feed: OK")
            else:
                print(f"  [WARN] New Build card feed failed (non-fatal): {_r.stderr[-200:]}")
        except Exception as _e:
            print(f"  [WARN] New Build card feed error (non-fatal): {_e}")

        # Step 2: New Build two-lane score
        try:
            _r = _sp.run(
                [_py, str(ROOT / "scripts/ops/new_build_two_lane_score.py"),
                 "--date", date_str, "--execute"],
                capture_output=True, text=True, cwd=str(ROOT), env=_nb_env,
            )
            if _r.returncode == 0:
                _nb_line = [l for l in _r.stdout.splitlines() if "Races scored" in l]
                print(f"  New Build two-lane: OK{(' — ' + _nb_line[0].strip()) if _nb_line else ''}")
            else:
                print(f"  [WARN] New Build two-lane failed (non-fatal): {_r.stderr[-200:]}")
        except Exception as _e:
            print(f"  [WARN] New Build two-lane error (non-fatal): {_e}")

        # Step 3: Publish dashboard
        try:
            from publish_daily_predictions_to_dashboard import publish as _publish_dashboard
            _dash = _publish_dashboard(date_str)
            print(f"  Dashboard: {_dash.get('races_found', 0)} races published → {_dash.get('destination_table_or_api', '')}")
        except Exception as _dash_err:
            print(f"  [WARN] Dashboard auto-publish failed (non-fatal): {_dash_err}")

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
        # ── HARNESS: best-effort observability on unhandled exception ─────────
        # This is an UNCONTROLLED exit path. We attempt to write an observability
        # packet but cannot guarantee it — the exception may have occurred before
        # date_str or commit_sha were resolved.
        # Classification: OBSERVABILITY_MANDATORY_ON_CONTROLLED_EXIT_PATHS
        # Controlled paths: PASS / FAIL / DEGRADED / BLOCKED
        # Uncontrolled path (here): best-effort only, no guarantee.
        try:
            from datetime import date as _exc_date
            _exc_date_str = _exc_date.today().isoformat()
            _exc_sha = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or "unknown")[:40]
            _obs_exc = _build_obs_packet(
                date_str=_exc_date_str,
                source_truth="SOURCE_UNKNOWN_BLOCK",
                feature_health="BLOCKED",
                active_formula="UNHANDLED_EXCEPTION",
                excluded_live_components=[],
                race_scoring_coverage_pct=0.0,
                persistence_status="FAIL",
                supabase_write_attempt_success=False,
                decision_tier_status="EXCEPTION",
                learning_gate="BLOCKED_EXCEPTION",
                next_safe_command="python scripts/ops/velo_session_start_check.py",
                warnings=[f"UNHANDLED_EXCEPTION: {type(exc).__name__}: {str(exc)[:200]}"],
                gate_fires={"gate_source_unknown_block": False},
                extra={"git_commit_sha": _exc_sha, "exception_type": type(exc).__name__},
            )
            _write_obs_packet(_obs_exc)
        except Exception as _obs_exc_err:
            # Observability write itself failed — print only, do not mask original
            print(f"  [HARNESS WARN] Exception-path observability write failed: {_obs_exc_err}")
        # ─────────────────────────────────────────────────────────────────────
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
