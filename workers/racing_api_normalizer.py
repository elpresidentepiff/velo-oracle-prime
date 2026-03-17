"""
Racing API Normalizer
=====================
Single canonical bridge from raw Racing API Standard payloads into VÉLØ.

ALL downstream agents and the orchestrator consume ONLY the output of these
functions. No agent should parse raw Racing API fields directly.

Canonical runner schema keys (all downstream code depends on these):
  horse_name        str
  horse_id          str
  official_rating   float   (0 = unrated/unknown)
  or                float   (alias of official_rating)
  rpr               float
  ts                float
  trainer_name      str
  trainer_id        str
  jockey_name       str
  jockey_id         str
  best_odds_decimal float   (0 = not available)
  odds_available_flag bool
  spotlight         str
  comment           str
  age               str
  sex               str
  weight_lbs        int
  draw              int
  form_figures      str     (e.g. "31202", "0PF")
  trainer_14_days   dict    (raw, preserved for connections agent)
  _raw              dict    (original raw runner, preserved for debugging)
"""
from __future__ import annotations

from typing import Any


# ──────────────────────────────────────────────
# Scalar helpers
# ──────────────────────────────────────────────

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert any value to float. Treats '-', '', None as default."""
    if val is None:
        return default
    s = str(val).strip()
    if s in ("-", "", "N/A", "n/a"):
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    return int(_safe_float(val, default))


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
    # Ratings — API returns strings like "120", "-", or absent
    or_rating  = _safe_float(raw.get("ofr") or raw.get("or") or raw.get("official_rating"))
    rpr        = _safe_float(raw.get("rpr"))
    ts         = _safe_float(raw.get("ts"))

    # Odds
    raw_odds = raw.get("odds")
    best_odds = _best_decimal(raw_odds) if isinstance(raw_odds, list) else _safe_float(raw_odds)

    return {
        # Identity
        "horse_name":          _safe_str(raw.get("horse")),
        "horse_id":            _safe_str(raw.get("horse_id")),

        # Ratings (all float, 0 = unrated)
        "official_rating":     or_rating,
        "or":                  or_rating,
        "rpr":                 rpr,
        "ts":                  ts,

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
        "region":      _safe_str(raw.get("region")),
        "jumps":       raw.get("jumps"),
        "runners":     normalized_runners,
        "_raw":        raw,
    }
