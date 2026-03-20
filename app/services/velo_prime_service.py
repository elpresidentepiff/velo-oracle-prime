"""
VELO Prime Service
==================
Canonical wire-in layer: Standard API racecard → VELO_PRIME_prob

Calling contract:
  from app.services.velo_prime_service import score_race_velo_prime
  predictions = score_race_velo_prime(normalized_race)

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
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
load_dotenv()

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
    normalized runner + race.  Missing doctrine features default to 0.0
    (handled by model_manager DEFAULTS and loader.py fill-with-zero logic).
    """
    or_num   = _safe(runner.get("official_rating") or runner.get("or"))
    rpr_num  = _safe(runner.get("rpr"))
    ts_num   = _safe(runner.get("ts"))
    odds     = _safe(runner.get("best_odds_decimal"))
    sp_dec   = odds if odds > 1.0 else 10.0
    log_sp   = math.log(max(sp_dec, 1.01))
    imp_prob = 1.0 / max(sp_dec, 1.01)

    field_size = max(len(field_or_vals), 1)
    avg_or     = sum(field_or_vals) / field_size if field_or_vals else 0.0
    avg_rpr    = sum(field_rpr_vals) / field_size if field_rpr_vals else 0.0
    or_vs_field  = or_num  - avg_or
    rpr_vs_field = rpr_num - avg_rpr

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
    }
    # v17 doctrine features — filled with 0.0 / defaults when not pre-computed
    from app.services.v17_feature_extractor import DEFAULTS
    for k, v in DEFAULTS.items():
        feats.setdefault(k, v)

    return feats


# ── main entry point ──────────────────────────────────────────────────────────

def score_race_velo_prime(race: dict) -> list[dict]:
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

    # Pre-compute field OR/RPR arrays for relative features
    field_or  = [_safe(r.get("official_rating") or r.get("or")) for r in runners]
    field_rpr = [_safe(r.get("rpr")) for r in runners]
    field_or  = [v for v in field_or  if v > 0]
    field_rpr = [v for v in field_rpr if v > 0]

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
        # Add horse_id from ensemble_inputs lookup
        for ei in ensemble_inputs:
            if ei["horse"] == row["horse"]:
                row["horse_id"] = ei["horse_id"]
                break
        results.append(row)

    return results


# ── Warehouse enrichment (passive, non-scoring) ───────────────────────────────

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

        # Prefer race["distance"] (API string e.g. "7f", "1m2f") set by normalize_race().
        # Fallback: if missing, convert distance_f (tenths-of-furlongs encoding) to label.
        _dist_raw = (race.get("distance") or race.get("dist") or "").strip()
        if not _dist_raw:
            _df = race.get("distance_f")
            if _df is not None:
                try:
                    _dist_raw = _dist_tenths_to_label(float(_df))
                except Exception:
                    pass
        race_dist = _dist_raw

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
            dst_runs = sum(1 for r in runs if (r.get("dist")   or "").strip() == race_dist)

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

        return predictions

    except Exception as e:
        log.warning("warehouse enrichment failed — full_analysis untouched: %s", e)
        return predictions


# ── Supabase persistence ──────────────────────────────────────────────────────

def persist_race_predictions(race: dict, predictions: list[dict],
                             decision_tier: str | None = None) -> bool:
    """
    Write top verdict + specialist scores to velo_verdicts.
    One row per race (top pick). Returns True on success.
    """
    if not predictions:
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
            "macro_regime_label":    top.get("macro_regime_label"),
            "macro_chaos_mode":      top.get("macro_chaos_mode"),
            "favourite_trap_risk":   top.get("favourite_trap_risk"),
            "decision_tier":         decision_tier,
            # Full ranked field — enriched below before upsert
            "full_analysis":         predictions,
        }

        # Passive warehouse enrichment — injects into runner blocks only.
        # Scoring outputs, rankings, and top-level row columns are unchanged.
        enriched = _enrich_full_analysis_from_warehouse(predictions, race, sb)
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
