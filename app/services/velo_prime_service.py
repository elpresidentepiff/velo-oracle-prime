"""
VELO Prime Service
==================
Canonical wire-in layer: Standard API racecard → VELO_PRIME_prob

Calling contract:
  from app.services.velo_prime_service import score_race_velo_prime
  predictions = score_race_velo_prime(normalized_race)
  predictions = score_race_velo_prime(normalized_race, sentient_state=g_state)  # Phase 1+

'normalized_race' must be the output of workers.racing_api_normalizer.normalize_race().

Returns:
  list of dicts, sorted by velo_prime_prob desc, each containing:
    horse_name, horse_id, sqpe_v17_prob, velo_prime_prob,
    improvement_score, market_deception_score, release_day_prob,
    place_prob, longshot_prob, draw_bias_score, comment_intel_score,
    macro_regime_label, macro_chaos_mode, favourite_trap_risk,
    confidence_level, verdict_flags, ensemble_version
"""
from __future__ import annotations

import logging
import math
import os
import re
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
load_dotenv()

# from src.intelligence.track_context import get_track_context, resolve_draw_bias  # module not yet present — disabled until src/intelligence/track_context.py is added

log = logging.getLogger("velo.prime_service")

ENSEMBLE_VERSION = "velo_prime_v1"


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    try:
        v = float(val)
        return v if not math.isnan(v) else default
    except (TypeError, ValueError):
        return default


def _build_live_features(runner: dict, race: dict, field_or_vals: list[float],
                          field_rpr_vals: list[float]) -> dict:
    """
    Build the feature dict for SQPE v17 + specialist models from a canonical
    normalized runner + race.

    Rating fields (official_rating, rpr, ts) may be None — this is legitimate
    absence, not zero. When absent:
      - or_vs_field / rpr_vs_field are set to 0.0 (neutral, not worst-in-field)
      - or_missing / rpr_missing / ts_missing flags are set to 1.0
    Downstream models use these flags as explicit uncertainty signals.
    """
    # Ratings: None = genuinely absent. Do NOT coerce to 0.0 here.
    or_raw   = runner.get("official_rating")  # Optional[float]
    rpr_raw  = runner.get("rpr")              # Optional[float]
    ts_raw   = runner.get("ts")               # Optional[float]

    or_missing  = float(runner.get("or_missing",  or_raw  is None))
    rpr_missing = float(runner.get("rpr_missing", rpr_raw is None))
    ts_missing  = float(runner.get("ts_missing",  ts_raw  is None))

    odds     = _safe(runner.get("best_odds_decimal"))
    sp_dec   = odds if odds > 1.0 else 10.0
    log_sp   = math.log(max(sp_dec, 1.01))
    imp_prob = 1.0 / max(sp_dec, 1.01)

    # Field averages computed only from rated runners (those with real values).
    # field_or_vals / field_rpr_vals are pre-filtered to > 0 by caller.
    avg_or  = sum(field_or_vals)  / len(field_or_vals)  if field_or_vals  else 0.0
    avg_rpr = sum(field_rpr_vals) / len(field_rpr_vals) if field_rpr_vals else 0.0

    # vs_field: neutral (0.0) when the runner has no rating.
    # This avoids fabricating a negative penalty for unrated horses.
    if or_raw is not None:
        or_num      = float(or_raw)
        or_vs_field = or_num - avg_or
    else:
        or_num      = avg_or  # placeholder only — not used in model when or_missing=1
        or_vs_field = 0.0

    if rpr_raw is not None:
        rpr_num      = float(rpr_raw)
        rpr_vs_field = rpr_num - avg_rpr
    else:
        rpr_num      = avg_rpr  # placeholder only
        rpr_vs_field = 0.0

    ts_num = float(ts_raw) if ts_raw is not None else 0.0

    # Emit structured log for any fallback so incidence can be counted
    if or_missing or rpr_missing or ts_missing:
        missing = [f for f, v in [("or", or_missing), ("rpr", rpr_missing), ("ts", ts_missing)] if v]
        log.debug(
            "rating_fallback race=%s horse=%s missing=%s or_vs_field=neutral",
            race.get("race_id"), runner.get("horse_name"), missing,
        )

    # Total field size — use actual runner count, not rated-runner count
    field_size = max(len(race.get("runners", [])), 1)

    # Market rank (1 = shortest odds)
    all_odds = sorted([r.get("best_odds_decimal", 0) or 999 for r in race.get("runners", [])
                       if (r.get("best_odds_decimal") or 0) > 0])
    sp_rank = (all_odds.index(sp_dec) + 1) if sp_dec in all_odds else field_size
    is_fav  = 1.0 if sp_rank == 1 else 0.0

    # Race-level
    from app.services.model_manager import ModelManager
    dist_f    = ModelManager._parse_dist(race.get("distance_f") or race.get("distance"))
    going_code, is_aw = ModelManager._parse_going(race.get("going"))
    class_num = ModelManager._parse_class(race.get("race_class"))
    draw_num  = _safe(runner.get("draw"))
    draw_pct  = draw_num / field_size

    # Rating/market gap helpers for market_deception_model
    rating_mkt_gap = rpr_vs_field - (1.0 / max(sp_dec, 1.01)) * 100
    or_mkt_gap     = or_vs_field  - (1.0 / max(sp_dec, 1.01)) * 100

    feats = {
        # v16 base
        "sp_dec": sp_dec, "log_sp": log_sp, "implied_prob": imp_prob,
        "dist_f": dist_f, "going_code": going_code, "is_aw": float(is_aw),
        "class_num": class_num, "wgt_lbs": _safe(runner.get("weight_lbs"), 126.0),
        "or_num": or_num, "rpr_num": rpr_num, "ts_num": ts_num,
        "or_vs_field": or_vs_field, "rpr_vs_field": rpr_vs_field,
        "field_size": float(field_size), "draw_num": draw_num,
        "draw_pct": draw_pct, "age_num": _safe(runner.get("age")),
        "sp_rank": float(sp_rank), "is_fav": is_fav,
        # draw model extras
        "draw_going": going_code * draw_pct,
        "draw_dist":  dist_f    * draw_pct,
        "draw_aw":    float(is_aw) * draw_pct,
        "draw_class": class_num * draw_pct,
        "draw_size":  field_size * draw_pct,
        # market deception extras
        "rating_mkt_gap": rating_mkt_gap,
        "or_mkt_gap":     or_mkt_gap,
        # explicit missingness flags (1.0 = absent, 0.0 = present)
        # models can use these as uncertainty signals rather than inferring from zero
        "or_missing":  or_missing,
        "rpr_missing": rpr_missing,
        "ts_missing":  ts_missing,
    }
    # v17 doctrine features — filled with 0.0 / defaults when not pre-computed
    from app.services.v17_feature_extractor import DEFAULTS
    for k, v in DEFAULTS.items():
        feats.setdefault(k, v)

    return feats


# ── main entry point ──────────────────────────────────────────────────────────

def _apply_sentient_modifiers(results: list[dict], sentient_state: dict | None) -> list[dict]:
    """
    Phase 1 — AUDIT ONLY. No probability change. No ranking change.

    Injects sentient bridge audit fields into every runner result.
    These fields are machine-checkable proof that G state reached the scorer.

    Fields added to every runner:
        sentient_state_loaded     : bool
        sentient_state_source     : "disk" | "supabase" | "none"
        sentient_races_observed   : int
        sentient_aggression_level : float
        sentient_modifier_applied : False (always, Phase 1)
        sentient_modifier_mode    : "audit_only"
    """
    if sentient_state is None:
        audit = {
            "sentient_state_loaded":     False,
            "sentient_state_source":     "none",
            "sentient_races_observed":   0,
            "sentient_aggression_level": None,
            "sentient_modifier_applied": False,
            "sentient_modifier_mode":    "audit_only",
        }
        for row in results:
            row.update(audit)
        return results

    source = sentient_state.get("_source", "unknown")
    races_observed = sentient_state.get("total_races_observed", 0)
    appetite = sentient_state.get("appetite_state", {})
    aggression = appetite.get("aggression_level", None)

    audit = {
        "sentient_state_loaded":     True,
        "sentient_state_source":     source,
        "sentient_races_observed":   races_observed,
        "sentient_aggression_level": round(float(aggression), 4) if aggression is not None else None,
        "sentient_modifier_applied": False,
        "sentient_modifier_mode":    "audit_only",
    }

    log.info(
        "[sentient] bridge active — source=%s races_observed=%d aggression=%.3f mode=audit_only",
        source, races_observed, aggression if aggression is not None else -1.0,
    )

    for row in results:
        row.update(audit)

    return results


def score_race_velo_prime(race: dict, sentient_state: dict | None = None) -> list[dict]:
    """
    Score a full normalized race through:
      1. SQPE v17 (per runner)
      2. Specialist models (per runner)
      3. VeloPrimeEnsemble (full field re-normalization + macro)

    Parameters
    ----------
    race : dict
        Output of workers.racing_api_normalizer.normalize_race()

    Returns
    -------
    list[dict]  sorted by velo_prime_prob desc
    """
    from app.services.model_manager import get_model_manager
    from src.intelligence.specialist_models.loader import score_runner
    from src.intelligence.velo_prime_ensemble import VeloPrimeEnsemble
    from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race

    mm       = get_model_manager()
    ensemble = VeloPrimeEnsemble()
    runners  = race.get("runners", [])
    race_id  = race.get("race_id", "unknown")

    if not runners:
        return []

    # Pre-compute field OR/RPR arrays for relative features.
    # official_rating and rpr are Optional[float] from the normalizer.
    # Only include runners with a real rating — exclude None and any stray zeros.
    field_or  = [r["official_rating"] for r in runners
                 if r.get("official_rating") is not None and r["official_rating"] > 0]
    field_rpr = [r["rpr"] for r in runners
                 if r.get("rpr") is not None and r["rpr"] > 0]

    # Macro context — current year, race type
    race_date = race.get("date") or datetime.now().strftime("%Y-%m-%d")
    race_type = race.get("type", "").lower()
    code = "jump" if any(x in race_type for x in ["hurdle", "chase", "nh flat"]) else "flat"
    try:
        macro_ctx = get_macro_context_for_race(race_date, code)
    except Exception as e:
        log.warning("Macro context unavailable: %s", e)
        macro_ctx = None

    # Score each runner
    ensemble_inputs = []
    for runner in runners:
        horse_name = runner.get("horse_name", "Unknown")
        feats = _build_live_features(runner, race, field_or, field_rpr)

        # SQPE v17 — features={} triggers the runner/race path internally
        sqpe_prob = mm.predict_sqpe(features={}, runner=runner, race=race)

        # Specialist scores — graceful on missing features
        try:
            spec_scores = score_runner(feats)
        except Exception as e:
            log.warning("Specialist scoring failed for %s: %s", horse_name, e)
            spec_scores = {}

        sp_dec = feats["sp_dec"]
        ensemble_inputs.append({
            "horse":                   horse_name,
            "horse_id":                runner.get("horse_id", ""),
            "race_id":                 race_id,
            "sqpe_v17_prob":           sqpe_prob,
            "improvement_score":       spec_scores.get("improvement_score"),
            "release_window_score":    spec_scores.get("release_window_score"),
            "market_deception_score":  spec_scores.get("market_deception_score"),
            "place_prob":              spec_scores.get("place_prob"),
            "comment_intel_score":     spec_scores.get("comment_intelligence_score"),
            "longshot_score":          spec_scores.get("longshot_score"),
            "sp_dec":                  sp_dec,
            "is_fav":                  feats["is_fav"] == 1.0,
            # Rating missingness — forwarded to full_analysis for observability
            "or_missing":              bool(feats["or_missing"]),
            "rpr_missing":             bool(feats["rpr_missing"]),
            "ts_missing":              bool(feats["ts_missing"]),
        })

    # Run VeloPrimeEnsemble
    predictions = ensemble.predict_race(ensemble_inputs, macro_context=macro_ctx)

    # Flatten to dicts
    results = []
    for pred in predictions:
        row = pred.to_dict()
        # Rename keys to canonical output names
        row["release_day_prob"]   = row.pop("release_window_score", None)
        row["longshot_prob"]      = row.pop("longshot_score", None)
        row["macro_regime_label"] = row.pop("macro_regime", None)
        row["macro_chaos_mode"]   = (macro_ctx.chaos_mode if macro_ctx else False)
        row["favourite_trap_risk"]= (macro_ctx.favourite_trap_risk if macro_ctx else "normal")
        row["ensemble_version"]   = ENSEMBLE_VERSION
        # Add horse_id + rating missingness flags from ensemble_inputs lookup
        for ei in ensemble_inputs:
            if ei["horse"] == row["horse"]:
                row["horse_id"]   = ei["horse_id"]
                row["or_missing"] = ei["or_missing"]
                row["rpr_missing"]= ei["rpr_missing"]
                row["ts_missing"] = ei["ts_missing"]
                break
        results.append(row)

    # Phase 1 sentient bridge — audit only, no scoring change
    results = _apply_sentient_modifiers(results, sentient_state)

    return results


# ── Warehouse enrichment (passive, non-scoring) ───────────────────────────────

_DIST_LABEL_RE = re.compile(r'^(?:(\d+)m)?(?:(\d+)?(½)?f)?$', re.IGNORECASE)


def _dist_label_to_yards(label: str) -> int:
    """
    Convert a warehouse dist label to integer yards.
    Inverse of _dist_tenths_to_label. Returns 0 on failure.

    Examples:
        '5f'    -> 1100    '5½f'   -> 1210
        '7f'    -> 1540    '7½f'   -> 1650
        '1m'    -> 1760    '1m½f'  -> 1870
        '1m2f'  -> 2200    '1m2½f' -> 2310
        '2m4½f' -> 4510
    """
    if not label:
        return 0
    m = _DIST_LABEL_RE.match(label.strip().lower())
    if not m:
        return 0
    miles_s, furlongs_s, half = m.group(1), m.group(2), m.group(3)
    furlongs = (
        (int(miles_s) * 8 if miles_s else 0)
        + (int(furlongs_s) if furlongs_s else 0)
        + (0.5 if half else 0)
    )
    if furlongs == 0 and not miles_s:
        return 0
    return round(furlongs * 220)


def _dist_tenths_to_label(dist_f_tenths: float) -> str:
    """
    Convert races.distance_f (tenths-of-furlongs encoding, e.g. 70 = 7.0f) to
    the Racing API human-readable dist label used in trainer_distance_analysis.dist
    and horse_racecard_history.dist  (e.g. "7f", "1m", "1m2f", "1m½f").

    Only handles the tenths-of-furlongs range (50–360).
    Returns "" for values outside that range or on any error.

    Examples:
        50  -> "5f"      70  -> "7f"    75  -> "7½f"
        80  -> "1m"      85  -> "1m½f"  100 -> "1m2f"
        160 -> "2m"      195 -> "2m3½f" 240 -> "3m"
    """
    if not (50 <= dist_f_tenths <= 360):
        return ""
    f = dist_f_tenths / 10.0          # 70 -> 7.0, 85 -> 8.5
    miles     = int(f) // 8
    remaining = f - miles * 8         # furlongs after subtracting whole miles
    whole_f   = int(remaining)
    is_half   = abs(remaining - whole_f - 0.5) < 0.05

    if miles == 0:
        return f"{whole_f}½f" if is_half else f"{whole_f}f"
    else:
        if is_half:
            return f"{miles}m{whole_f}½f" if whole_f > 0 else f"{miles}m½f"
        elif whole_f > 0:
            return f"{miles}m{whole_f}f"
        else:
            return f"{miles}m"


def _enrich_full_analysis_from_warehouse(
    predictions: list[dict],
    race: dict,
    sb,
) -> list[dict]:
    """
    Passively inject warehouse features into each runner block.
    Never raises — any failure logs a warning and returns predictions unchanged.
    Scoring outputs and rankings are not touched.

    Injects per runner:
      From horse_racecard_history:
        horse_recent_runs_90d, horse_recent_avg_pos,
        horse_course_runs, horse_distance_runs, horse_avg_pos_all
      From trainer_course_analysis (course match):
        trainer_course_runners, trainer_course_1st,
        trainer_course_ae, trainer_course_win_pct
      From trainer_distance_analysis (dist match):
        trainer_dist_runners, trainer_dist_1st, trainer_dist_ae
    """
    try:
        race_course   = (race.get("course") or "").strip()

        # Canonical distance resolution.
        # API distance strings (e.g. "7f14y", "1m13y") include yard suffixes that
        # do not match warehouse labels ("7f", "1m").  Use distance_y (yards) derived
        # from distance_f (furlongs, already rounded to nearest ½f by the Racing API)
        # to generate the exact label stored in trainer_distance_analysis.dist and
        # horse_racecard_history.dist.
        #
        # distance_y is set by normalize_race() via _dist_f_to_yards(distance_f).
        # Fallback chain: race["distance_y"] -> distance_f*220 -> 0.
        race_dist_y: int = race.get("distance_y") or 0
        if not race_dist_y:
            _df = race.get("distance_f")
            if _df is not None:
                try:
                    race_dist_y = round(float(_df) * 220)
                except Exception:
                    pass

        # Derive canonical warehouse label from yards for trainer_distance_analysis query.
        # _dist_tenths_to_label takes tenths-of-furlongs: yards / 22 = tenths.
        if race_dist_y:
            race_dist = _dist_tenths_to_label(race_dist_y / 22)
        else:
            # Last resort: raw distance string (old behaviour — may miss on yard-suffixed strings)
            race_dist = (race.get("distance") or race.get("dist") or "").strip()

        race_date_str = race.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
        try:
            race_date = datetime.strptime(race_date_str[:10], "%Y-%m-%d").date()
        except Exception:
            race_date = datetime.utcnow().date()
        cutoff_90d = (race_date - timedelta(days=90)).isoformat()

        # Build horse_id -> normalized runner lookup for trainer_id resolution
        runner_map = {r.get("horse_id", ""): r for r in race.get("runners", [])}

        horse_ids = [p.get("horse_id", "") for p in predictions if p.get("horse_id")]
        if not horse_ids:
            return predictions

        # horse_id -> trainer_id mapping
        pred_trainer: dict[str, str | None] = {}
        trainer_ids: list[str] = []
        for p in predictions:
            hid = p.get("horse_id", "")
            tid = runner_map.get(hid, {}).get("trainer_id")
            pred_trainer[hid] = tid
            if tid and tid not in trainer_ids:
                trainer_ids.append(tid)

        # -- Query 1: horse_racecard_history (all history, batch by horse_ids) --
        hrh_data: dict[str, list[dict]] = {}
        try:
            result = (
                sb.table("horse_racecard_history")
                .select("horse_id,race_date,course,dist,position")
                .in_("horse_id", horse_ids)
                .execute()
            )
            for r in (result.data or []):
                hid = r["horse_id"]
                hrh_data.setdefault(hid, []).append(r)
        except Exception as e:
            log.warning("warehouse: horse_racecard_history fetch failed: %s", e)

        # -- Query 2: trainer_course_analysis (trainer_id IN list AND course match) --
        tca_data: dict[str, dict] = {}
        if trainer_ids and race_course:
            try:
                result = (
                    sb.table("trainer_course_analysis")
                    .select("trainer_id,runners,wins_1st,ae,win_pct")
                    .in_("trainer_id", trainer_ids)
                    .eq("course", race_course)
                    .execute()
                )
                for r in (result.data or []):
                    tca_data[r["trainer_id"]] = r
            except Exception as e:
                log.warning("warehouse: trainer_course_analysis fetch failed: %s", e)

        # -- Query 3: trainer_distance_analysis (trainer_id IN list AND dist match) --
        tda_data: dict[str, dict] = {}
        if trainer_ids and race_dist:
            try:
                result = (
                    sb.table("trainer_distance_analysis")
                    .select("trainer_id,runners,wins_1st,ae")
                    .in_("trainer_id", trainer_ids)
                    .eq("dist", race_dist)
                    .execute()
                )
                for r in (result.data or []):
                    tda_data[r["trainer_id"]] = r
            except Exception as e:
                log.warning("warehouse: trainer_distance_analysis fetch failed: %s", e)

        # -- Query 4: horse_distance_time_analysis (horse_id IN list AND dist label match) --
        # Primary match: exact dist label (e.g. "7f") — same canonical label resolved above.
        # Passive only. hdta_pl_1 is intentionally excluded.
        hdta_data: dict[str, dict] = {}
        if horse_ids and race_dist:
            try:
                result = (
                    sb.table("horse_distance_time_analysis")
                    .select("horse_id,runs,wins_1st,ae,win_pct")
                    .in_("horse_id", horse_ids)
                    .eq("dist", race_dist)
                    .execute()
                )
                for r in (result.data or []):
                    hdta_data[r["horse_id"]] = r
            except Exception as e:
                log.warning("warehouse: horse_distance_time_analysis fetch failed: %s", e)

        # -- Helpers --
        def _sf(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        def _si(v):
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        def _pos_num(pos_str):
            try:
                return float(str(pos_str).strip())
            except (TypeError, ValueError):
                return None

        # -- Inject into each runner block --
        for pred in predictions:
            hid = pred.get("horse_id", "")
            tid = pred_trainer.get(hid)

            runs = hrh_data.get(hid, [])
            recent   = [r for r in runs if (r.get("race_date") or "") >= cutoff_90d]
            all_pos  = [_pos_num(r["position"]) for r in runs   if _pos_num(r["position"]) is not None]
            rec_pos  = [_pos_num(r["position"]) for r in recent if _pos_num(r["position"]) is not None]
            crs_runs = sum(1 for r in runs if (r.get("course") or "").strip() == race_course)
            # yards comparison with ±2y tolerance for float-to-int rounding
            if race_dist_y:
                dst_runs = sum(
                    1 for r in runs
                    if abs(_dist_label_to_yards(r.get("dist") or "") - race_dist_y) <= 2
                )
            else:
                dst_runs = sum(1 for r in runs if (r.get("dist") or "").strip() == race_dist)

            pred["horse_recent_runs_90d"] = len(recent)
            pred["horse_recent_avg_pos"]  = round(sum(rec_pos) / len(rec_pos), 2) if rec_pos else None
            pred["horse_course_runs"]     = crs_runs
            pred["horse_distance_runs"]   = dst_runs
            pred["horse_avg_pos_all"]     = round(sum(all_pos) / len(all_pos), 2) if all_pos else None

            tca = tca_data.get(tid) if tid else None
            pred["trainer_course_runners"] = _si(_sf(tca["runners"]))   if tca else None
            pred["trainer_course_1st"]     = _si(_sf(tca["wins_1st"]))  if tca else None
            pred["trainer_course_ae"]      = _sf(tca["ae"])             if tca else None
            pred["trainer_course_win_pct"] = _sf(tca["win_pct"])        if tca else None

            tda = tda_data.get(tid) if tid else None
            pred["trainer_dist_runners"]   = _si(_sf(tda["runners"]))  if tda else None
            pred["trainer_dist_1st"]       = _si(_sf(tda["wins_1st"])) if tda else None
            pred["trainer_dist_ae"]        = _sf(tda["ae"])            if tda else None

            hdta = hdta_data.get(hid)
            pred["hdta_dist_runs"] = _si(_sf(hdta["runs"]))     if hdta else None
            pred["hdta_dist_1st"]  = _si(_sf(hdta["wins_1st"])) if hdta else None
            pred["hdta_ae"]        = _sf(hdta["ae"])             if hdta else None
            pred["hdta_win_pct"]   = _sf(hdta["win_pct"])        if hdta else None

        return predictions

    except Exception as e:
        log.warning("warehouse enrichment failed — full_analysis untouched: %s", e)
        return predictions


# def _enrich_full_analysis_with_track_context(
#     predictions: list[dict],
#     race: dict,
# ) -> list[dict]:
#     """
#     Passively inject track context into each runner block.
#     Never raises — any failure returns predictions unchanged.
#     Scoring outputs and rankings are not touched.
#
#     Injects per runner (same fields for every runner in the race):
#         track_chaos_rating      int | None
#         track_pace_bias         str | None
#         track_draw_bias         str | None   (distance-specific if matched)
#         track_key_characteristics list[str]
#     """
#     try:
#         course   = (race.get("course") or "").strip()
#         distance = (race.get("distance") or race.get("dist") or "").strip()
#
#         profile = get_track_context(course)
#
#         chaos_rating      = profile.get("chaos_rating")        # int 1-5 or None
#         pace_bias         = profile.get("pace_bias")           # str or None
#         draw_bias         = resolve_draw_bias(profile, distance) if distance else None
#         key_chars         = list(profile.get("key_characteristics") or [])
#
#         for pred in predictions:
#             pred["track_chaos_rating"]       = chaos_rating
#             pred["track_pace_bias"]          = pace_bias
#             pred["track_draw_bias"]          = draw_bias
#             pred["track_key_characteristics"] = key_chars
#
#         return predictions
#
#     except Exception as e:
#         log.warning("track context enrichment failed — full_analysis untouched: %s", e)
#         return predictions
# NOTE: disabled — src/intelligence/track_context.py does not exist yet.
#       Re-enable once the module is added to the repo.


# ── Supabase persistence ──────────────────────────────────────────────────────

def persist_race_predictions(race: dict, predictions: list[dict],
                             decision_tier: str | None = None) -> bool:
    """
    Write top verdict + specialist scores to velo_verdicts.
    One row per race (top pick). Returns True on success.
    """
    if not predictions:
        return False

    # Validate tier before any DB write — non-canonical tier rejected
    if decision_tier is not None:
        from src.constants import validate_tier
        try:
            validate_tier(decision_tier)
        except ValueError as e:
            log.error("persist_race_predictions: tier rejected for %s — %s",
                      race.get("race_id"), e)
            return False

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.warning("Supabase credentials missing — skipping persist")
        return False

    try:
        from supabase import create_client
        sb = create_client(url, key)

        top = predictions[0]
        row = {
            "race_id":               race.get("race_id"),
            "region":                race.get("region", ""),   # UK/IRE filter verification — persisted at scoring time
            "generated_at":          datetime.utcnow().isoformat(),
            "engine_version":        "velo_prime_v1",
            "doctrine_version":      "d010",
            "ensemble_version":      top.get("ensemble_version", ENSEMBLE_VERSION),
            "top_rank_horse_id":     top.get("horse_id", ""),
            "top_rank_score":        top.get("velo_prime_prob"),
            "confidence_level":      top.get("confidence_level"),
            # VELO_PRIME fields
            "velo_prime_prob":       top.get("velo_prime_prob"),
            "improvement_score":     top.get("improvement_score"),
            "market_deception_score":top.get("market_deception_score"),
            "release_day_prob":      top.get("release_day_prob"),
            "place_prob":            top.get("place_prob"),
            "longshot_prob":         top.get("longshot_prob"),
            # DISPLAY-ONLY: not read by sigma, not consumed by Playbook G — see TRUTH_REGISTRY.md
            "macro_regime_label":    top.get("macro_regime_label"),
            "macro_chaos_mode":      top.get("macro_chaos_mode"),
            "favourite_trap_risk":   top.get("favourite_trap_risk"),
            "decision_tier":         decision_tier,
            # Full ranked field — enriched below before upsert
            "full_analysis":         predictions,
        }

        # Passive warehouse enrichment — injects into runner blocks only.
        # Scoring outputs, rankings, and top-level row columns are unchanged.
        # FIELD_TYPE: display-only — horse_recent_*, trainer_course_*, trainer_dist_*
        # not read by sigma or Playbook G — see TRUTH_REGISTRY.md §4
        enriched = _enrich_full_analysis_from_warehouse(predictions, race, sb)
        # Passive track context enrichment — disabled: src/intelligence/track_context.py missing
        # # adds track_chaos_rating, track_pace_bias, track_draw_bias, track_key_characteristics
        # # FIELD_TYPE: track_chaos_rating + track_pace_bias are LIVE (read by sigma)
        # # FIELD_TYPE: track_draw_bias + track_key_characteristics are display-only
        # enriched = _enrich_full_analysis_with_track_context(enriched, race)
        row["full_analysis"] = enriched

        sb.table("velo_verdicts").upsert(row, on_conflict="race_id").execute()
        log.info("Persisted verdict for race %s — top: %s (%.4f)",
                 race.get("race_id"), top.get("horse"), top.get("velo_prime_prob"))
        return True

    except Exception as e:
        log.error("Persist failed for race %s: %s", race.get("race_id"), e)
        return False


def persist_runner_derived_features(race: dict, predictions: list[dict]) -> int:
    """
    Write one runner_derived_features row per runner in the scored field.
    Uses specialist scores from predictions as the derived feature store.
    Returns count of rows written (0 on failure).
    """
    if not predictions:
        return 0

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return 0

    try:
        from supabase import create_client
        sb = create_client(url, key)

        race_id     = race.get("race_id")
        computed_at = datetime.utcnow().isoformat()
        rows = []

        for pred in predictions:
            horse_id = pred.get("horse_id", "") or pred.get("horse", "")
            if not horse_id or not race_id:
                continue

            imp  = pred.get("improvement_score")
            mkt  = pred.get("market_deception_score")
            pp   = pred.get("place_prob")
            ls   = pred.get("longshot_prob")
            rd   = pred.get("release_day_prob")
            ci   = pred.get("comment_intel_score")
            vp   = pred.get("velo_prime_prob")

            rows.append({
                "race_id":                 race_id,
                "horse_id":                horse_id,
                "computed_at":             computed_at,
                "feature_schema_version":  "velo_prime_v1",
                # Specialist model outputs mapped to doctrine feature columns
                "form_cycle_score":        imp,
                "market_confidence_score": mkt,
                "release_day_score":       rd,
                "survivability_score":     pp,
                "chaos_score":             ls,
                "trainer_intent_score":    ci,
                # Full feature vector for retraining
                "feature_vector": {
                    "velo_prime_prob":         vp,
                    "improvement_score":       imp,
                    "market_deception_score":  mkt,
                    "place_prob":              pp,
                    "longshot_prob":           ls,
                    "release_day_prob":        rd,
                    "comment_intel_score":     ci,
                    "confidence_level":        pred.get("confidence_level"),
                    "draw_bias_score":         pred.get("draw_bias_score"),
                },
            })

        if not rows:
            return 0

        result = sb.table("runner_derived_features").upsert(
            rows, on_conflict="race_id,horse_id"
        ).execute()
        log.info("Persisted %d runner_derived_features for race %s", len(rows), race_id)
        return len(rows)

    except Exception as e:
        log.warning("runner_derived_features persist failed for race %s: %s",
                    race.get("race_id"), e)
        return 0
