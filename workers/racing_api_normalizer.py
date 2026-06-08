"""
Racing API Normalizer
=====================
Single canonical bridge from raw Racing API Standard payloads into VÉLØ.

ALL downstream agents and the orchestrator consume ONLY the output of these
functions. No agent should parse raw Racing API fields directly.

Canonical runner schema keys (all downstream code depends on these):
  horse_name          str
  horse_id            str
  official_rating     Optional[float]  — None when absent/unrated. NEVER 0.0 for missing.
  or                  Optional[float]  — alias of official_rating
  rpr                 Optional[float]  — None when absent. Racing Post Rating.
  ts                  Optional[float]  — None when absent. Topspeed.
  or_missing          bool             — True if official_rating is absent
  rpr_missing         bool             — True if rpr is absent
  ts_missing          bool             — True if ts is absent
  trainer_name        str
  trainer_id          str
  jockey_name         str
  jockey_id           str
  best_odds_decimal   float   (0 = not available)
  odds_available_flag bool
  spotlight           str
  comment             str
  age                 str
  sex                 str
  weight_lbs          int
  draw                int
  form_figures        str     (e.g. "31202", "0PF")
  trainer_14_days     dict    (raw, preserved for connections agent)
  _raw                dict    (original raw runner, preserved for debugging)

Canonical race schema keys (added):
  jurisdiction        str — closed set: "uk" | "ire" | "other" | "unknown"
                            derived from race region, never None

IMPORTANT — rating semantics:
  Missing official_rating / rpr / ts must stay None. Downstream scoring must
  use neutral handling (or_vs_field = 0.0) for missing runners, not synthesise
  a worst-in-field value. 0.0 is NOT a valid rating; it is fabricated data.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("velo.normalizer")


# ──────────────────────────────────────────────
# Scalar helpers
# ──────────────────────────────────────────────

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert any value to float. Treats '-', '', None as default.
    Use only for non-rating numeric fields (odds, weight, draw).
    For rating fields (OR, RPR, TS) use _parse_rating() instead."""
    if val is None:
        return default
    s = str(val).strip()
    if s in ("-", "", "N/A", "n/a"):
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _parse_rating(val: Any) -> Optional[float]:
    """
    Parse a rating field (official_rating / rpr / ts).

    Returns None — not 0.0 — for any absent, invalid, or zero value.
    Ratings of <= 0 are treated as absent: horses have OR >= 1 in practice.

    Never synthesises a fallback numeric. Caller decides what to do with None.
    """
    if val is None:
        return None
    s = str(val).strip()
    if s in ("-", "", "N/A", "n/a", "0"):
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any, default: int = 0) -> int:
    return int(_safe_float(val, default))


def _resolve_jurisdiction(region: Any) -> str:
    """
    Map raw Racing API region code to a canonical closed-set jurisdiction.

    Returns one of:
      "uk"      — GB races (region == "GB")
      "ire"     — Irish races (region == "IRE" or "IE")
      "other"   — any other non-empty region code
      "unknown" — absent or blank region

    Never returns None. Never leaks raw strings downstream.
    """
    if not region:
        return "unknown"
    r = str(region).strip().upper()
    if r == "GB":
        return "uk"
    if r in ("IRE", "IE"):
        return "ire"
    if r:
        return "other"
    return "unknown"


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val).strip()


def _best_decimal(odds_list: Any) -> float:
    """
    Standard API returns odds as a list of bookmaker dicts:
      [{"bookmaker": "Bet365", "decimal": "151", "fractional": "150/1", ...}, ...]

    Returns the LOWEST (shortest price = most favoured by best bookie) decimal,
    or 0.0 if none available.
    """
    if not isinstance(odds_list, list) or not odds_list:
        return 0.0
    decimals = []
    for o in odds_list:
        d = o.get("decimal", "")
        if d in ("SP", "-", "", None):
            continue
        try:
            decimals.append(float(d))
        except (ValueError, TypeError):
            continue
    return min(decimals) if decimals else 0.0


# ──────────────────────────────────────────────
# Runner normalizer
# ──────────────────────────────────────────────

def normalize_runner(raw: dict) -> dict:
    """
    Convert one raw Racing API Standard runner dict into the canonical
    internal runner schema consumed by all VÉLØ agents.

    Parameters
    ----------
    raw : dict
        One runner entry from the Racing API Standard racecard response.

    Returns
    -------
    dict
        Canonical runner dict. Agents must use these keys only.
    """
    # Ratings — use _parse_rating(): returns None for absent/invalid, never 0.0
    # API field name: "ofr" (standard), also aliased as "or" / "official_rating"
    or_rating  = _parse_rating(raw.get("ofr") or raw.get("or") or raw.get("official_rating"))
    rpr_rating = _parse_rating(raw.get("rpr"))
    ts_rating  = _parse_rating(raw.get("ts"))

    # Missingness flags — explicit, countable, loggable
    or_missing  = or_rating  is None
    rpr_missing = rpr_rating is None
    ts_missing  = ts_rating  is None

    horse_id = _safe_str(raw.get("horse_id"))
    if or_missing or rpr_missing or ts_missing:
        missing_fields = [f for f, m in [("or", or_missing), ("rpr", rpr_missing), ("ts", ts_missing)] if m]
        log.debug(
            "rating_missing horse_id=%s fields=%s raw_ofr=%r raw_rpr=%r raw_ts=%r",
            horse_id, missing_fields,
            raw.get("ofr"), raw.get("rpr"), raw.get("ts"),
        )

    # Odds
    raw_odds = raw.get("odds")
    best_odds = _best_decimal(raw_odds) if isinstance(raw_odds, list) else _safe_float(raw_odds)

    return {
        # Identity
        "horse_name":          _safe_str(raw.get("horse")),
        "horse_id":            horse_id,

        # Ratings — Optional[float]. None = genuinely absent. Never 0.0 for missing.
        "official_rating":     or_rating,
        "or":                  or_rating,
        "rpr":                 rpr_rating,
        "ts":                  ts_rating,

        # Explicit missingness flags — use these in feature builders, not "== 0" checks
        "or_missing":          or_missing,
        "rpr_missing":         rpr_missing,
        "ts_missing":          ts_missing,

        # Connections — canonical keys + backward-compat aliases
        "trainer_name":        _safe_str(raw.get("trainer")),
        "trainer":             _safe_str(raw.get("trainer")),   # alias for agents using old key
        "trainer_id":          _safe_str(raw.get("trainer_id")),
        "jockey_name":         _safe_str(raw.get("jockey")),
        "jockey":              _safe_str(raw.get("jockey")),    # alias for agents using old key
        "jockey_id":           _safe_str(raw.get("jockey_id")),
        "trainer_14_days":     raw.get("trainer_14_days") or {},

        # Market
        "best_odds_decimal":   best_odds,
        "odds_available_flag": best_odds > 0,

        # NLP / comments
        "spotlight":           _safe_str(raw.get("spotlight")),
        "comment":             _safe_str(raw.get("comment")),

        # Physical / race entry
        "age":                 _safe_str(raw.get("age")),
        "sex":                 _safe_str(raw.get("sex")),
        "weight_lbs":          _safe_int(raw.get("lbs")),
        "draw":                _safe_int(raw.get("draw")),
        "headgear":            _safe_str(raw.get("headgear")),
        "last_run":            _safe_str(raw.get("last_run")),

        # Form — agents expect 'form_figures'
        "form_figures":        _safe_str(raw.get("form")),
        "form":                _safe_str(raw.get("form")),   # backward compat

        # Keep original for debugging
        "_raw":                raw,
    }


# ──────────────────────────────────────────────
# Race normalizer
# ──────────────────────────────────────────────

def normalize_race(raw: dict) -> dict:
    """
    Convert one raw Racing API Standard race (racecard) dict into the canonical
    internal race schema consumed by all VÉLØ agents and the orchestrator.

    Runners inside the returned dict are already normalized via normalize_runner().

    Parameters
    ----------
    raw : dict
        One racecard entry from the Racing API Standard response.

    Returns
    -------
    dict
        Canonical race dict with normalized runners list.
    """
    raw_runners = raw.get("runners", [])
    normalized_runners = [normalize_runner(r) for r in raw_runners]

    return {
        "race_id":     _safe_str(raw.get("race_id")),
        "course":      _safe_str(raw.get("course")),
        "course_id":   _safe_str(raw.get("course_id")),
        "date":        _safe_str(raw.get("date")),
        "off_time":    _safe_str(raw.get("off_time")),
        "race_name":   _safe_str(raw.get("race_name")),
        "distance":    _safe_str(raw.get("distance")),
        "distance_f":  _safe_str(raw.get("distance_f")),
        "going":       _safe_str(raw.get("going")),
        "going_detailed": _safe_str(raw.get("going_detailed")),
        "surface":     _safe_str(raw.get("surface")),
        "type":        _safe_str(raw.get("type")),
        "race_class":  _safe_str(raw.get("race_class")),
        "age_band":    _safe_str(raw.get("age_band")),
        "rating_band": _safe_str(raw.get("rating_band")),
        "pattern":     _safe_str(raw.get("pattern")),
        "prize":       _safe_str(raw.get("prize")),
        "field_size":  _safe_int(raw.get("field_size")),
        "region":      _safe_str(raw.get("region")),        # raw API value, e.g. "GB"
        "jurisdiction": _resolve_jurisdiction(raw.get("region") or raw.get("country")),  # canonical: "uk"|"ire"|"other"|"unknown"
        "jumps":       raw.get("jumps"),
        "runners":     normalized_runners,
        "_raw":        raw,
    }
