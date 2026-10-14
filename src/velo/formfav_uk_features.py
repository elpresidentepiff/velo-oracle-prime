"""UK/IRE FormFav shadow feature extraction for VÉLØ.

This module deliberately does NOT alter VÉLØ Prime probabilities.
It converts FormFav enrichment packets into source-aware, auditable features
that can be backtested and ablated against the existing UK model stack.

Design rules:
- Racing API / canonical VÉLØ fields remain primary truth.
- FormFav-derived values retain provenance and sample sizes.
- Strike rates are shrunk toward conservative priors before modelling.
- Missingness is explicit; missing data is never converted into a positive signal.
- FormFav predictions and badges are meta-evidence, not core training targets.
"""
from __future__ import annotations

import math
import re
import unicodedata
from copy import deepcopy
from typing import Any

FEATURE_SCHEMA_VERSION = "FORMFAV_UK_SHADOW_V1"

_STYLE_KEYS = ("L", "P", "M", "B", "X")
_PACE_KEYS = ("SLOW", "MODERATE", "FAST", "VERY_FAST")
_CLASS_TRENDS = ("rising", "stable", "dropping")
_CLASS_ASSESSMENTS = ("comfort_zone", "slight_rise", "big_rise", "slight_drop", "big_drop")

# Conservative priors. These are not betting claims; they prevent tiny samples
# such as 1/1 from masquerading as stable 100% signals.
_WIN_PRIOR = 0.12
_PLACE_PRIOR = 0.34
_PRIOR_STRENGTH = 8.0


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _clamp(v: float | None, lo: float = 0.0, hi: float = 1.0) -> float | None:
    if v is None:
        return None
    return min(max(v, lo), hi)


def _norm_name(v: Any) -> str:
    s = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _rate01(v: Any) -> float | None:
    f = _safe_float(v)
    if f is None:
        return None
    # FormFav examples have historically appeared in both 0-1 and 0-100
    # presentation contexts. Normalise defensively and preserve raw payload.
    if f > 1.0:
        f /= 100.0
    return _clamp(f)


def _stat_block(stats: dict[str, Any], key: str) -> dict[str, Any] | None:
    block = stats.get(key)
    return block if isinstance(block, dict) else None


def _smoothed_stat(block: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
    if not block:
        return {
            f"{prefix}_present": 0.0,
            f"{prefix}_starts": 0.0,
            f"{prefix}_win_rate_raw": None,
            f"{prefix}_place_rate_raw": None,
            f"{prefix}_win_rate_smoothed": None,
            f"{prefix}_place_rate_smoothed": None,
        }

    starts = max(_safe_float(block.get("starts")) or 0.0, 0.0)
    wins = max(_safe_float(block.get("wins")) or 0.0, 0.0)
    places = max(_safe_float(block.get("places")) or 0.0, 0.0)

    raw_win = _rate01(block.get("winPercent"))
    raw_place = _rate01(block.get("placePercent"))

    if starts > 0:
        # Prefer count-derived rates when counts are coherent.
        raw_win = _clamp(wins / starts) if wins <= starts else raw_win
        raw_place = _clamp(places / starts) if places <= starts else raw_place
        smooth_win = (wins + _WIN_PRIOR * _PRIOR_STRENGTH) / (starts + _PRIOR_STRENGTH)
        smooth_place = (places + _PLACE_PRIOR * _PRIOR_STRENGTH) / (starts + _PRIOR_STRENGTH)
    else:
        smooth_win = None
        smooth_place = None

    return {
        f"{prefix}_present": 1.0,
        f"{prefix}_starts": starts,
        f"{prefix}_win_rate_raw": raw_win,
        f"{prefix}_place_rate_raw": raw_place,
        f"{prefix}_win_rate_smoothed": _clamp(smooth_win),
        f"{prefix}_place_rate_smoothed": _clamp(smooth_place),
    }


def _recent_form_features(form: Any, last20: Any) -> dict[str, Any]:
    raw = str(last20 or form or "").upper()
    chars = list(raw)
    finishes: list[int] = []
    for ch in chars:
        if ch.isdigit():
            finishes.append(10 if ch == "0" else int(ch))

    # FormFav documents the most recent result last.
    last5 = finishes[-5:]
    last3 = finishes[-3:]

    def rate(values: list[int], cutoff: int) -> float | None:
        if not values:
            return None
        return sum(1 for x in values if x <= cutoff) / len(values)

    last_finish = last5[-1] if last5 else None
    return {
        "ff_form_present": 1.0 if raw else 0.0,
        "ff_form_observed_runs": float(len(finishes)),
        "ff_recent_win_rate_3": rate(last3, 1),
        "ff_recent_place_rate_3": rate(last3, 3),
        "ff_recent_win_rate_5": rate(last5, 1),
        "ff_recent_place_rate_5": rate(last5, 3),
        "ff_last_finish": float(last_finish) if last_finish is not None else None,
        "ff_spell_marker": 1.0 if "X" in raw else 0.0,
        "ff_recent_nonfinish_or_10plus": (
            sum(1 for x in last5 if x >= 10) / len(last5) if last5 else None
        ),
    }


def _condition_block(stats: dict[str, Any], condition: Any) -> dict[str, Any] | None:
    direct = stats.get("condition")
    if isinstance(direct, dict) and "starts" in direct:
        return direct

    by_cond = stats.get("conditions")
    if not isinstance(by_cond, dict):
        return None

    s = str(condition or "").lower()
    candidates = []
    if "heavy" in s:
        candidates = ["heavy"]
    elif "soft" in s:
        candidates = ["soft"]
    elif "good" in s:
        candidates = ["good"]
    elif "firm" in s:
        candidates = ["firm"]
    elif any(x in s for x in ("standard", "synthetic", "polytrack", "tapeta", "aw")):
        candidates = ["synthetic"]

    for k in candidates:
        if isinstance(by_cond.get(k), dict):
            return by_cond[k]
    return None


def _bias_for_barrier(track_bias: dict[str, Any] | None, barrier: Any) -> dict[str, Any] | None:
    if not isinstance(track_bias, dict):
        return None
    b = _safe_float(barrier)
    if b is None:
        return None
    b = int(round(b))
    for row in track_bias.get("barrierStats") or []:
        if not isinstance(row, dict):
            continue
        try:
            if int(row.get("barrierNumber")) == b:
                return row
        except (TypeError, ValueError):
            continue
    return None


def _pace_fit_hint(style: str, scenario: str) -> float:
    """Transparent shadow heuristic, not a trained model input."""
    style = style.upper()
    scenario = scenario.upper()
    if scenario == "SLOW":
        return {"L": 1.0, "P": 0.6, "M": -0.2, "B": -0.6}.get(style, 0.0)
    if scenario == "MODERATE":
        return {"L": 0.5, "P": 0.5, "M": 0.1, "B": -0.2}.get(style, 0.0)
    if scenario == "FAST":
        return {"L": -0.3, "P": 0.0, "M": 0.5, "B": 0.5}.get(style, 0.0)
    if scenario == "VERY_FAST":
        return {"L": -0.7, "P": -0.3, "M": 0.5, "B": 1.0}.get(style, 0.0)
    return 0.0


def _derived_pace_shape(runners: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive an auditable race-level pace shape from FormFav speed maps.

    This is a transparent shadow heuristic, not provider truth and not a model
    input.  At least two runners and 40% field coverage are required.
    """
    styles: list[str] = []
    high_speed = 0
    for runner in runners:
        ff = runner.get("_formfav") if isinstance(runner.get("_formfav"), dict) else {}
        speed_map = ff.get("speedMap") if isinstance(ff.get("speedMap"), dict) else {}
        if not speed_map:
            continue
        style = str(speed_map.get("runningStyle") or "X").upper()
        styles.append(style if style in _STYLE_KEYS else "X")
        speed = _safe_float(speed_map.get("earlySpeedIndex"))
        if speed is not None and speed >= 7.0:
            high_speed += 1

    field_size = len(runners)
    covered = len(styles)
    coverage = covered / max(field_size, 1)
    leaders = styles.count("L")
    pressers = styles.count("P")
    pressure = (2.0 * leaders + pressers) / max(covered, 1)
    scenario = None
    if covered >= 2 and coverage >= 0.40:
        if leaders >= 3 or pressure >= 0.90:
            scenario = "VERY_FAST"
        elif leaders >= 2 or pressure >= 0.55:
            scenario = "FAST"
        elif leaders == 0 and pressure <= 0.20:
            scenario = "SLOW"
        else:
            scenario = "MODERATE"
    return {
        "scenario": scenario,
        "source": "speed_map_derived" if scenario else "missing",
        "covered_runners": covered,
        "field_size": field_size,
        "coverage": round(coverage, 4),
        "leader_count": leaders,
        "presser_count": pressers,
        "high_speed_count": high_speed,
        "pressure_score": round(pressure, 4) if covered else None,
    }


def build_formfav_uk_shadow_features(race: dict[str, Any], runner: dict[str, Any]) -> dict[str, Any]:
    ff_race = race.get("_formfav") if isinstance(race.get("_formfav"), dict) else {}
    ff = runner.get("_formfav") if isinstance(runner.get("_formfav"), dict) else {}

    out: dict[str, Any] = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "source": "formfav",
        "jurisdiction": str(ff_race.get("country") or race.get("country") or race.get("region") or "").lower(),
        "race_id": race.get("race_id"),
        "horse_name": runner.get("horse_name") or runner.get("horse"),
        "ff_raw_attached": 1.0 if ff else 0.0,
    }

    # Identity and cross-source checks.
    canonical_name = runner.get("horse_name") or runner.get("horse")
    ff_name = ff.get("name")
    identity_match = bool(ff_name and _norm_name(canonical_name) == _norm_name(ff_name))
    out["ff_identity_name_match"] = 1.0 if identity_match else 0.0

    canonical_draw = _safe_float(runner.get("draw"))
    ff_barrier = _safe_float(ff.get("barrier"))
    draw_conflict = (
        canonical_draw is not None and ff_barrier is not None and int(round(canonical_draw)) != int(round(ff_barrier))
    )
    out["ff_draw_conflict"] = 1.0 if draw_conflict else 0.0

    # Pace / speed map.
    sm = ff.get("speedMap") if isinstance(ff.get("speedMap"), dict) else {}
    style = str(sm.get("runningStyle") or "X").upper()
    if style not in _STYLE_KEYS:
        style = "X"
    esi = _safe_float(sm.get("earlySpeedIndex"))
    settling = _safe_float(sm.get("settlingPosition"))
    field_size = max(len(race.get("runners") or []), 1)
    out["ff_speedmap_present"] = 1.0 if sm else 0.0
    out["ff_early_speed_index"] = esi
    out["ff_early_speed_norm"] = _clamp(esi / 10.0) if esi is not None else None
    out["ff_settling_position"] = settling
    out["ff_settling_pct"] = _clamp((settling - 1.0) / max(field_size - 1, 1)) if settling is not None else None
    for key in _STYLE_KEYS:
        out[f"ff_style_{key.lower()}"] = 1.0 if style == key else 0.0

    provider_pace = str(ff_race.get("paceScenario") or "").upper()
    derived_pace = str(ff_race.get("paceScenarioDerived") or "").upper()
    pace = provider_pace if provider_pace in _PACE_KEYS else derived_pace
    out["ff_pace_scenario_present"] = 1.0 if pace in _PACE_KEYS else 0.0
    out["ff_pace_scenario_provider"] = 1.0 if provider_pace in _PACE_KEYS else 0.0
    out["ff_pace_scenario_derived"] = (
        1.0 if provider_pace not in _PACE_KEYS and derived_pace in _PACE_KEYS else 0.0
    )
    for key in _PACE_KEYS:
        out[f"ff_pace_{key.lower()}"] = 1.0 if pace == key else 0.0
    out["ff_pace_shape_fit_hint"] = _pace_fit_hint(style, pace)

    # Form map: recent form + context strike rates with shrinkage and denominators.
    out.update(_recent_form_features(ff.get("form"), ff.get("last20Starts")))
    stats = ff.get("stats") if isinstance(ff.get("stats"), dict) else {}
    for key, prefix in (
        ("overall", "ff_overall"),
        ("track", "ff_track"),
        ("distance", "ff_distance"),
        ("trackDistance", "ff_track_distance"),
        ("firstUp", "ff_first_up"),
        ("secondUp", "ff_second_up"),
    ):
        out.update(_smoothed_stat(_stat_block(stats, key), prefix))
    out.update(_smoothed_stat(_condition_block(stats, ff_race.get("condition") or race.get("going")), "ff_condition"))

    # Class map.
    cp = ff.get("classProfile") if isinstance(ff.get("classProfile"), dict) else {}
    cf = ff.get("raceClassFit") if isinstance(ff.get("raceClassFit"), dict) else {}
    out["ff_class_profile_present"] = 1.0 if cp else 0.0
    out["ff_class_current"] = _safe_float(cp.get("currentRating"))
    out["ff_class_peak"] = _safe_float(cp.get("peakRating"))
    out["ff_class_highest_win"] = _safe_float(cp.get("highestClassWon"))
    out["ff_class_optimal_min"] = _safe_float(cp.get("optimalRangeMin"))
    out["ff_class_optimal_max"] = _safe_float(cp.get("optimalRangeMax"))
    trend = str(cp.get("trend") or "").lower()
    for key in _CLASS_TRENDS:
        out[f"ff_class_trend_{key}"] = 1.0 if trend == key else 0.0

    out["ff_class_fit_present"] = 1.0 if cf else 0.0
    out["ff_race_class_rating"] = _safe_float(cf.get("raceClassRating"))
    out["ff_class_difference"] = _safe_float(cf.get("classDifference"))
    out["ff_within_optimal_class"] = 1.0 if cf.get("withinOptimalRange") is True else 0.0
    assessment = str(cf.get("assessment") or "").lower()
    for key in _CLASS_ASSESSMENTS:
        out[f"ff_class_{key}"] = 1.0 if assessment == key else 0.0

    # Track / barrier map.
    track_bias = ff_race.get("trackBias") if isinstance(ff_race.get("trackBias"), dict) else None
    barrier_bias = _bias_for_barrier(track_bias, ff.get("barrier") or runner.get("draw"))
    out["ff_track_bias_present"] = 1.0 if barrier_bias else 0.0
    out["ff_track_bias_strength"] = {
        "none": 0.0, "mild": 0.33, "moderate": 0.66, "strong": 1.0
    }.get(str((track_bias or {}).get("biasStrength") or "").lower())
    out["ff_barrier_bias_starts"] = _safe_float((barrier_bias or {}).get("totalStarts")) or 0.0
    out["ff_barrier_advantage_raw"] = _safe_float((barrier_bias or {}).get("advantage"))
    out.update(_smoothed_stat(barrier_bias, "ff_barrier_bias"))

    # Decorators are derived summaries of data already present. Keep only
    # diagnostic counts to avoid double-counting the same fact in a future model.
    decorators = ff.get("decorators") if isinstance(ff.get("decorators"), list) else []
    pos = neg = neutral = 0
    for badge in decorators:
        if not isinstance(badge, dict):
            continue
        sentiment = str(badge.get("sentiment") or "")
        if sentiment == "+":
            pos += 1
        elif sentiment == "-":
            neg += 1
        else:
            neutral += 1
    out["ff_badge_positive_count"] = float(pos)
    out["ff_badge_negative_count"] = float(neg)
    out["ff_badge_neutral_count"] = float(neutral)

    # Quality gate. This is intentionally strict because the US test proved
    # provider-derived history can be incomplete or misidentified.
    blocks = [
        identity_match,
        bool(sm),
        bool(cp),
        bool(stats.get("overall")),
        bool(ff.get("form") or ff.get("last20Starts")),
        not draw_conflict,
    ]
    quality = sum(1.0 for x in blocks if x) / len(blocks)
    if not identity_match:
        quality *= 0.25
    if draw_conflict:
        quality *= 0.6
    out["ff_quality_score"] = round(quality, 4)
    out["ff_quality_tier"] = "HIGH" if quality >= 0.83 else "MEDIUM" if quality >= 0.60 else "LOW"
    out["ff_training_eligible"] = 1.0 if identity_match and not draw_conflict and quality >= 0.60 else 0.0

    return out


def build_race_shadow_packet(race: dict[str, Any]) -> dict[str, Any]:
    """Return one auditable race packet with race-shape summaries and runner features."""
    runners = race.get("runners") or []
    pace_shape = _derived_pace_shape(runners)
    effective_race = race
    provider_pace = str((race.get("_formfav") or {}).get("paceScenario") or "").upper()
    if provider_pace not in _PACE_KEYS and pace_shape["scenario"]:
        effective_race = deepcopy(race)
        effective_race.setdefault("_formfav", {})["paceScenarioDerived"] = pace_shape["scenario"]
    rows = [build_formfav_uk_shadow_features(effective_race, r) for r in runners]

    speed_rows = [r for r in rows if r.get("ff_speedmap_present") == 1.0]
    leaders = sum(1 for r in speed_rows if r.get("ff_style_l") == 1.0)
    pressers = sum(1 for r in speed_rows if r.get("ff_style_p") == 1.0)
    high_speed = sum(1 for r in speed_rows if (r.get("ff_early_speed_index") or 0.0) >= 7.0)

    quality_scores = [float(r["ff_quality_score"]) for r in rows if r.get("ff_quality_score") is not None]
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "race_id": race.get("race_id"),
        "course": race.get("course"),
        "off_time": race.get("off_time"),
        "race_name": race.get("race_name"),
        "going": race.get("going"),
        "race_class": race.get("race_class"),
        "distance": race.get("distance") or race.get("distance_f"),
        "formfav_pace_scenario": (
            provider_pace if provider_pace in _PACE_KEYS else pace_shape["scenario"]
        ),
        "pace_scenario_source": (
            "formfav_provider" if provider_pace in _PACE_KEYS else pace_shape["source"]
        ),
        "pace_pressure_score": pace_shape["pressure_score"],
        "pace_leader_count": leaders,
        "pace_presser_count": pressers,
        "pace_high_speed_count": high_speed,
        "speedmap_coverage": round(len(speed_rows) / max(len(rows), 1), 4),
        "mean_quality_score": round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 0.0,
        "training_eligible_runners": sum(1 for r in rows if r.get("ff_training_eligible") == 1.0),
        "runner_count": len(rows),
        "runners": rows,
    }
