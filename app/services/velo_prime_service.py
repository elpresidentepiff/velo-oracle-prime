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
from datetime import UTC, datetime, timedelta

from src.intelligence.explanation_generator import generate_decision_explanation

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


def _build_live_features(runner: dict, race: dict, field_or_vals: list[float], field_rpr_vals: list[float]) -> dict:
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
    # API sends '-' or other non-numeric strings for missing ratings — clean them.
    def _clean_rating(v):
        if v is None:
            return None
        try:
            f = float(v)
            return f if f > 0 else None
        except (TypeError, ValueError):
            return None

    or_raw = _clean_rating(runner.get("official_rating"))
    rpr_raw = _clean_rating(runner.get("rpr"))
    ts_raw = _clean_rating(runner.get("ts"))

    or_missing = float(runner.get("or_missing", or_raw is None))
    rpr_missing = float(runner.get("rpr_missing", rpr_raw is None))
    ts_missing = float(runner.get("ts_missing", ts_raw is None))

    odds = _safe(runner.get("best_odds_decimal"))
    sp_dec = odds if odds > 1.0 else 10.0
    log_sp = math.log(max(sp_dec, 1.01))
    imp_prob = 1.0 / max(sp_dec, 1.01)

    # Field averages computed only from rated runners (those with real values).
    # field_or_vals / field_rpr_vals are pre-filtered to > 0 by caller.
    avg_or = sum(field_or_vals) / len(field_or_vals) if field_or_vals else 0.0
    avg_rpr = sum(field_rpr_vals) / len(field_rpr_vals) if field_rpr_vals else 0.0

    # vs_field: neutral (0.0) when the runner has no rating.
    # This avoids fabricating a negative penalty for unrated horses.
    if or_raw is not None:
        or_num = float(or_raw)
        or_vs_field = or_num - avg_or
    else:
        or_num = avg_or  # placeholder only — not used in model when or_missing=1
        or_vs_field = 0.0

    if rpr_raw is not None:
        rpr_num = float(rpr_raw)
        rpr_vs_field = rpr_num - avg_rpr
    else:
        rpr_num = avg_rpr  # placeholder only
        rpr_vs_field = 0.0

    ts_num = float(ts_raw) if ts_raw is not None else 0.0

    # Emit structured log for any fallback so incidence can be counted
    if or_missing or rpr_missing or ts_missing:
        missing = [f for f, v in [("or", or_missing), ("rpr", rpr_missing), ("ts", ts_missing)] if v]
        log.debug(
            "rating_fallback race=%s horse=%s missing=%s or_vs_field=neutral",
            race.get("race_id"),
            runner.get("horse_name"),
            missing,
        )

    # Total field size — use actual runner count, not rated-runner count
    field_size = max(len(race.get("runners", [])), 1)

    # Market rank (1 = shortest odds)
    all_odds = sorted(
        [r.get("best_odds_decimal", 0) or 999 for r in race.get("runners", []) if (r.get("best_odds_decimal") or 0) > 0]
    )
    sp_rank = (all_odds.index(sp_dec) + 1) if sp_dec in all_odds else field_size
    is_fav = 1.0 if sp_rank == 1 else 0.0

    # Race-level
    from app.services.sqpe_v17_service import _parse_dist, _parse_going, _parse_class

    dist_f = _parse_dist(race.get("distance_f") or race.get("distance"))
    going_code, is_aw = _parse_going(race.get("going"))
    class_num = _parse_class(race.get("race_class"))
    draw_num = _safe(runner.get("draw"))
    draw_pct = draw_num / field_size

    # Rating/market gap helpers for market_deception_model
    rating_mkt_gap = rpr_vs_field - (1.0 / max(sp_dec, 1.01)) * 100
    or_mkt_gap = or_vs_field - (1.0 / max(sp_dec, 1.01)) * 100

    pdf_intel = runner.get("pdf_intel", {})

    feats = {
        # v16 base
        "sp_dec": sp_dec,
        "log_sp": log_sp,
        "implied_prob": imp_prob,
        "dist_f": dist_f,
        "going_code": going_code,
        "is_aw": float(is_aw),
        "class_num": class_num,
        "wgt_lbs": _safe(runner.get("weight_lbs"), 126.0),
        "or_num": or_num,
        "rpr_num": rpr_num,
        "ts_num": ts_num,
        "or_vs_field": or_vs_field,
        "rpr_vs_field": rpr_vs_field,
        "field_size": float(field_size),
        "draw_num": draw_num,
        "draw_pct": draw_pct,
        "age_num": _safe(runner.get("age")),
        "sp_rank": float(sp_rank),
        "is_fav": is_fav,
        "is_second_choice": 1.0 if sp_rank == 2 else 0.0,
        "market_rank": float(sp_rank),
        # draw model extras
        "draw_going": going_code * draw_pct,
        "draw_dist": dist_f * draw_pct,
        "draw_aw": float(is_aw) * draw_pct,
        "draw_class": class_num * draw_pct,
        "draw_size": field_size * draw_pct,
        # market deception extras
        "rating_mkt_gap": rating_mkt_gap,
        "or_mkt_gap": or_mkt_gap,
        # explicit missingness flags (1.0 = absent, 0.0 = present)
        # models can use these as uncertainty signals rather than inferring from zero
        "or_missing": or_missing,
        "rpr_missing": rpr_missing,
        "ts_missing": ts_missing,
        # PDF Intelligence
        "plot_conviction": float(pdf_intel.get("plot_conviction", 0.0)),
        "or_compression_score": float(pdf_intel.get("or_compression_score", 0.0)),
        "postdata_score": float(pdf_intel.get("postdata_score", 0.0)),
        "ts_master": float(pdf_intel.get("ts_master", 0.0)),
        "or_delta_to_best_win": float(pdf_intel.get("or_delta_to_best_win", 0.0)),
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
            "sentient_state_loaded": False,
            "sentient_state_source": "none",
            "sentient_races_observed": 0,
            "sentient_aggression_level": None,
            "sentient_modifier_applied": False,
            "sentient_modifier_mode": "audit_only",
        }
        for row in results:
            row.update(audit)
        return results

    source = sentient_state.get("_source", "unknown")
    races_observed = sentient_state.get("total_races_observed", 0)
    appetite = sentient_state.get("appetite_state", {})
    aggression = appetite.get("aggression_level", None)

    audit = {
        "sentient_state_loaded": True,
        "sentient_state_source": source,
        "sentient_races_observed": races_observed,
        "sentient_aggression_level": round(float(aggression), 4) if aggression is not None else None,
        "sentient_modifier_applied": False,
        "sentient_modifier_mode": "audit_only",
    }

    log.info(
        "[sentient] bridge active — source=%s races_observed=%d aggression=%.3f mode=audit_only",
        source,
        races_observed,
        aggression if aggression is not None else -1.0,
    )

    for row in results:
        row.update(audit)

    return results


_POPULATION_STATS: dict = {}


def _load_population_stats() -> None:
    """Load the BHA 2026 population report extracts for the Decline-Curve heuristic."""
    global _POPULATION_STATS
    path = ROOT / "data" / "bha_population_stats_2026.json"
    if path.exists():
        try:
            with open(path) as f:
                _POPULATION_STATS = json.load(f)
        except Exception as e:
            log.warning("[BHA] Population stats load failed: %s", e)


def _apply_bha_intelligence(prob: float, runner: dict, race_code: str) -> tuple[float, list[str]]:
    """
    Apply BHA Intelligence penalties (Collateral & Decline-Curve).
    
    1. Collateral Flag: -15% if BHA themselves are uncertain of the rating.
    2. Decline-Curve: -10% if horse is past peak age and trajectory is declining.
    """
    reasons = []
    final_prob = prob

    # 1. Collateral Rating Penalty
    if runner.get("is_collateral") or runner.get("pdf_intel", {}).get("_rp_raw", {}).get("is_collateral"):
        final_prob *= 0.85
        reasons.append("BHA_COLLATERAL_PENALTY(-15%)")

    # 2. Decline-Curve Penalty
    age = runner.get("age")
    try:
        age_num = int(age) if age else 0
        is_flat = race_code == "flat"
        
        # Thresholds from 2026 Population Report: Flat 5+, Jump 8+
        threshold = 5 if is_flat else 8
        if age_num >= threshold:
            # Check trajectory from BHA perf figures (attached in run_prime_today)
            # or from raw RP data if present
            traj = runner.get("surf_traj_flag") or "UNKNOWN"
            if traj in ("DECLINING", "REGRESSING"):
                final_prob *= 0.90
                reasons.append(f"DECLINE_CURVE_PENALTY({traj}:-10%)")
    except (ValueError, TypeError):
        pass

    return round(final_prob, 4), reasons


def score_race_velo_prime(
    race: dict,
    sentient_state: dict | None = None,
    ablation_mode: str | None = None,
) -> list[dict]:
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
    from app.services.sqpe_v17_service import predict_sqpe_v17, build_v17_feature_vector
    from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race
    from src.intelligence.specialist_models.loader import score_runner
    from src.intelligence.velo_prime_ensemble import VeloPrimeEnsemble

    ensemble = VeloPrimeEnsemble()
    runners = race.get("runners", [])
    race_id = race.get("race_id", "unknown")

    if not runners:
        return []

    # Pre-compute field OR/RPR arrays for relative features.
    # Only include runners with a real rating — exclude None and any stray zeros.
    def _to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    field_or = [
        _to_float(r["official_rating"])
        for r in runners
        if r.get("official_rating") is not None and _to_float(r["official_rating"]) > 0
    ]
    field_rpr = [_to_float(r["rpr"]) for r in runners if r.get("rpr") is not None and _to_float(r["rpr"]) > 0]

    # Pre-inject rpr_vs_field so build_v17_feature_vector picks up the relative value.
    # build_v17_feature_vector reads runner.get("rpr_vs_field", 0.0) — inject before the loop.
    avg_rpr = sum(field_rpr) / len(field_rpr) if field_rpr else 0.0
    for r in runners:
        rpr_val = _to_float(r.get("rpr") or 0)
        if rpr_val > 0 and avg_rpr > 0:
            r["rpr_vs_field"] = round(rpr_val - avg_rpr, 1)
        else:
            r.setdefault("rpr_vs_field", 0.0)

    # Macro context — current year, race type
    race_date = race.get("date") or datetime.now().strftime("%Y-%m-%d")
    race_type = race.get("type", "").lower()
    code = "jump" if any(x in race_type for x in ["hurdle", "chase", "nh flat"]) else "flat"
    macro_context_failed = False
    try:
        macro_ctx = get_macro_context_for_race(race_date, code)
    except Exception as e:
        log.error(
            "Macro context FAILED for race_id=%s date=%s code=%s: %s — "
            "chaos_mode will be treated as unknown (not False), macro features absent",
            race_id,
            race_date,
            code,
            e,
        )
        macro_ctx = None
        macro_context_failed = True

    # Score each runner
    ensemble_inputs = []
    _feats_by_horse: dict[str, dict] = {}
    for runner in runners:
        horse_name = runner.get("horse_name", "Unknown")
        
        # Build features using clean service
        feats = build_v17_feature_vector(runner, race)
        _feats_by_horse[horse_name] = feats
        sqpe_prob_raw = predict_sqpe_v17(feats)

        # Apply BHA Intelligence (Collateral & Decline-Curve)
        sqpe_prob, bha_reasons = _apply_bha_intelligence(sqpe_prob_raw, runner, code)
        if bha_reasons:
            log.info("  [BHA] %s: %s (%.4f -> %.4f)", horse_name, ", ".join(bha_reasons), sqpe_prob_raw, sqpe_prob)
            # Add reasons to runner for later retrieval if needed
            runner.setdefault("bha_intelligence_reasons", []).extend(bha_reasons)

        # Specialist scores — graceful on missing features
        try:
            spec_scores = score_runner(feats)
        except Exception as e:
            log.warning("Specialist scoring failed for %s: %s", horse_name, e)
            spec_scores = {}

        sp_dec = feats["sp_dec"]

        # Ensure PDF intel is explicitly stored on the runner dict for persistence
        runner["plot_conviction"] = feats.get("plot_conviction")
        runner["or_delta_to_best_win"] = feats.get("or_delta_to_best_win")
        runner["postdata_score"] = feats.get("postdata_score")
        runner["ts_master"] = feats.get("ts_master")
        runner["intent_signals"] = runner.get("pdf_intel", {}).get("intent_signals", [])

        ensemble_inputs.append(
            {
                "horse": horse_name,
                "horse_id": runner.get("horse_id", ""),
                "race_id": race_id,
                "sqpe_v17_prob": sqpe_prob,
                "improvement_score": spec_scores.get("improvement_score"),
                "release_window_score": spec_scores.get("release_window_score"),
                "market_deception_score": spec_scores.get("market_deception_score"),
                "place_prob": spec_scores.get("place_prob"),
                "comment_intel_score": spec_scores.get("comment_intelligence_score"),
                "longshot_score": spec_scores.get("longshot_score"),
                "sp_dec": sp_dec,
                "is_fav": feats["is_fav"] == 1.0,
                # Rating missingness — forwarded to full_analysis for observability
                "or_missing": bool(feats["or_missing"]),
                "rpr_missing": bool(feats["rpr_missing"]),
                "ts_missing": bool(feats["ts_missing"]),
            }
        )

    # Run VeloPrimeEnsemble
    predictions = ensemble.predict_race(ensemble_inputs, macro_context=macro_ctx, mode=ablation_mode)

    # Flatten to dicts
    results = []
    for pred in predictions:
        row = pred.to_dict()
        # Rename keys to canonical output names.
        # NOTE: release_day_prob and comment_intel_score are raw specialist model outputs
        # stored here for observability only. They are NOT included in the active ensemble
        # when their components are in _DISABLED_COMPONENTS (see excluded_from_ensemble field).
        row["release_day_prob"] = row.pop("release_window_score", None)
        row["longshot_prob"] = row.pop("longshot_score", None)
        row["macro_regime_label"] = row.pop("macro_regime", None)
        row["macro_chaos_mode"] = macro_ctx.chaos_mode if macro_ctx else None  # None = unknown (not False)
        row["macro_context_failed"] = macro_context_failed
        row["favourite_trap_risk"] = macro_ctx.favourite_trap_risk if macro_ctx else "normal"
        row["ensemble_version"] = ENSEMBLE_VERSION
        # Add horse_id + rating missingness flags from ensemble_inputs lookup
        for ei in ensemble_inputs:
            if ei["horse"] == row["horse"]:
                row["horse_id"] = ei["horse_id"]
                row["or_missing"] = ei["or_missing"]
                row["rpr_missing"] = ei["rpr_missing"]
                row["ts_missing"] = ei["ts_missing"]
                break
        results.append(row)

    # Phase 1 sentient bridge — audit only, no scoring change
    results = _apply_sentient_modifiers(results, sentient_state)

    # ── Horse State Brain + TIE v3 signal computation ────────────────────────
    # Runs after ensemble scoring, before persist.
    # Uses merged live feats (doctrine signals) + row (ensemble outputs).
    # Does NOT alter velo_prime_prob, decision_tier, or active_components.
    #
    # Horse State: row["horse_state"] = full state dict → into full_analysis
    # TIE signals: row["tie_gate_signal_count"] + row["tie_gate_signals"]
    #   — signals computed here (live feats available); upgrade/EW decision
    #   deferred to run_prime_today.py after synthesize_decision() when
    #   current_tier is known.
    from src.intelligence.horse_state_engine import HorseStateEngine as _HorseStateEngine
    from src.intelligence.tie_v3_gate import TIEv3Gate as _TIEv3Gate

    _state_engine = _HorseStateEngine()
    _tie_gate = _TIEv3Gate()
    for row in results:
        # Merge: live feats supply doctrine signals; row fields take priority
        _live_feats = _feats_by_horse.get(row.get("horse", ""), {})

        # ── CASH RUN & DOCTRINE PERSISTENCE ────────────────────────────────
        # Extract features computed in v17_feature_extractor that need to
        # survive into full_analysis for the Sigma Audit / Training Truth plane.
        row["cash_run_flag"] = bool(_live_feats.get("cash_run_flag", 0.0) == 1.0)
        row["setup_run_flag"] = bool(_live_feats.get("setup_run_flag", 0.0) == 1.0)
        row["decoy_support_flag"] = bool(_live_feats.get("decoy_support_flag", 0.0) == 1.0)
        # ───────────────────────────────────────────────────────────────────

        _merged = {**_live_feats, **row}
        try:
            _state = _state_engine.tag(_merged)
            row["horse_state"] = _state.to_dict()
            row["horse_state_failed"] = False
        except Exception as _e:
            log.error(
                "Horse state tagging FAILED for %s: %s — tier blocker active: A/B evaluation skipped for this runner",
                row.get("horse"),
                _e,
            )
            row["horse_state"] = {}
            row["horse_state_failed"] = True
        try:
            # Evaluate without current_tier — signals only, no upgrade logic yet
            _gate_pre = _tie_gate.evaluate(_merged, current_tier=None)
            row["tie_gate_signal_count"] = _gate_pre.signal_count
            row["tie_gate_signals"] = _gate_pre.signals_found
        except Exception as _e:
            log.warning("TIE gate signal computation failed for %s: %s", row.get("horse"), _e)
            row["tie_gate_signal_count"] = 0
            row["tie_gate_signals"] = []

    if results:
        results[0]["verdict_explanation"] = generate_decision_explanation(results[0], race)

    return results


# ── Warehouse enrichment (passive, non-scoring) ───────────────────────────────

_DIST_LABEL_RE = re.compile(r"^(?:(\d+)m)?(?:(\d+)?(½)?f)?$", re.IGNORECASE)


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
    furlongs = (int(miles_s) * 8 if miles_s else 0) + (int(furlongs_s) if furlongs_s else 0) + (0.5 if half else 0)
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
    f = dist_f_tenths / 10.0  # 70 -> 7.0, 85 -> 8.5
    miles = int(f) // 8
    remaining = f - miles * 8  # furlongs after subtracting whole miles
    whole_f = int(remaining)
    is_half = abs(remaining - whole_f - 0.5) < 0.05

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
        race_course = (race.get("course") or "").strip()

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

        race_date_str = race.get("date") or datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            race_date = datetime.strptime(race_date_str[:10], "%Y-%m-%d").date()
        except Exception:
            race_date = datetime.now(UTC).date()
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
            for r in result.data or []:
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
                for r in result.data or []:
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
                for r in result.data or []:
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
                for r in result.data or []:
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
            recent = [r for r in runs if (r.get("race_date") or "") >= cutoff_90d]
            all_pos = [_pos_num(r["position"]) for r in runs if _pos_num(r["position"]) is not None]
            rec_pos = [_pos_num(r["position"]) for r in recent if _pos_num(r["position"]) is not None]
            crs_runs = sum(1 for r in runs if (r.get("course") or "").strip() == race_course)
            # yards comparison with ±2y tolerance for float-to-int rounding
            if race_dist_y:
                dst_runs = sum(1 for r in runs if abs(_dist_label_to_yards(r.get("dist") or "") - race_dist_y) <= 2)
            else:
                dst_runs = sum(1 for r in runs if (r.get("dist") or "").strip() == race_dist)

            pred["horse_recent_runs_90d"] = len(recent)
            pred["horse_recent_avg_pos"] = round(sum(rec_pos) / len(rec_pos), 2) if rec_pos else None
            pred["horse_course_runs"] = crs_runs
            pred["horse_distance_runs"] = dst_runs
            pred["horse_avg_pos_all"] = round(sum(all_pos) / len(all_pos), 2) if all_pos else None

            tca = tca_data.get(tid) if tid else None
            pred["trainer_course_runners"] = _si(_sf(tca["runners"])) if tca else None
            pred["trainer_course_1st"] = _si(_sf(tca["wins_1st"])) if tca else None
            pred["trainer_course_ae"] = _sf(tca["ae"]) if tca else None
            pred["trainer_course_win_pct"] = _sf(tca["win_pct"]) if tca else None

            tda = tda_data.get(tid) if tid else None
            pred["trainer_dist_runners"] = _si(_sf(tda["runners"])) if tda else None
            pred["trainer_dist_1st"] = _si(_sf(tda["wins_1st"])) if tda else None
            pred["trainer_dist_ae"] = _sf(tda["ae"]) if tda else None

            hdta = hdta_data.get(hid)
            pred["hdta_dist_runs"] = _si(_sf(hdta["runs"])) if hdta else None
            pred["hdta_dist_1st"] = _si(_sf(hdta["wins_1st"])) if hdta else None
            pred["hdta_ae"] = _sf(hdta["ae"]) if hdta else None
            pred["hdta_win_pct"] = _sf(hdta["win_pct"]) if hdta else None

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


def persist_race_predictions(
    race: dict,
    predictions: list[dict],
    decision_tier: str | None = None,
    commit_sha: str | None = None,
) -> bool:
    """
    Write top verdict + specialist scores to velo_verdicts.
    One row per race (top pick). Returns True on success.
    """
    if not predictions:
        return False

    # Validate tier before any DB write — non-canonical tier rejected
    if decision_tier is None:
        log.warning(
            "persist_race_predictions: decision_tier is None for race %s — "
            "verdict will be written without a tier (audit gap). "
            "Caller must pass decision_tier from synthesize_decision().",
            race.get("race_id"),
        )
    else:
        from src.constants import validate_tier

        try:
            validate_tier(decision_tier)
        except ValueError as e:
            log.error("persist_race_predictions: tier rejected for %s — %s", race.get("race_id"), e)
            return False

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.warning("Supabase credentials missing — skipping persist")
        return False

    try:
        from supabase import create_client

        sb = create_client(url, key)

        # predictions is list[dict] — serialized runner rows.
        results = predictions
        top = results[0]

        if not top.get("horse_id"):
            log.error(
                "persist_race_predictions: top prediction missing horse_id for race %s — rejecting",
                race.get("race_id"),
            )
            return False

        _hs = top.get("horse_state") or {}  # compact horse-state for top selection

        # ── G Shadow instrumentation: top-3 runners with G-adjusted scores ──────
        top3_scores = []
        for pred_dict in results[:3]:
            g_mult = pred_dict.get("g_shadow_multiplier", 1.0)
            top3_scores.append(
                {
                    "horse_id": pred_dict.get("horse_id", ""),
                    "velo_prime_prob": pred_dict.get("velo_prime_prob"),
                    "g_base_prob": pred_dict.get("g_base_prob"),
                    "g_shadow_multiplier": g_mult,
                    "g_adjusted_prob": round(pred_dict.get("g_base_prob", 0.0) * g_mult, 4)
                    if pred_dict.get("g_base_prob")
                    else None,
                    "g_shadow_flags": pred_dict.get("g_shadow_flags") or [],
                    "doctrines_fired": pred_dict.get("doctrines_fired") or [],
                    "is_top_pick": (pred_dict == top),
                }
            )

        row = {
            "race_id": race.get("race_id"),
            "region": race.get("region", ""),  # UK/IRE filter verification — persisted at scoring time
            "generated_at": datetime.now(UTC).isoformat(),
            "fetch_timestamp": race.get("fetch_timestamp") or datetime.now(UTC).isoformat(),
            "predicted_field_size": len(race.get("runners") or []),
            "engine_version": "velo_prime_v1",
            "doctrine_version": "d010",
            "ensemble_version": top.get("ensemble_version", ENSEMBLE_VERSION),
            "top_rank_horse_id": top.get("horse_id", ""),
            "top_rank_score": top.get("velo_prime_prob"),
            "confidence_level": top.get("confidence_level"),
            # Confidence split — persists both raw (pre-normalisation) and effective
            # (post-normalisation, same boundary as synthesize_decision tier gating).
            # Requires migration: 20260412_002_confidence_level_split.sql
            "confidence_level_raw": top.get("confidence_level_raw"),
            "confidence_level_effective": top.get("confidence_level_effective"),
            # Shadow suspect cohort — A-tier with weak place support (place_prob < 0.75).
            # Passive monitor. No gate change. Track 30 days then decide on conditional tighten.
            # Requires migration: 20260412_003_a_tier_suspect_cohort.sql
            "a_tier_weak_place_flag": top.get("a_tier_weak_place_flag", False),
            # VELO_PRIME fields
            "velo_prime_prob": top.get("velo_prime_prob"),
            "improvement_score": top.get("improvement_score"),
            "market_deception_score": top.get("market_deception_score"),
            "release_day_prob": top.get("release_day_prob"),
            "place_prob": top.get("place_prob"),
            "longshot_prob": top.get("longshot_prob"),
            # Genuine RPDC fields — attached upstream from runner_release_candidates.
            # PDF plot/intent intelligence is a SEPARATE feature and lives in
            # full_analysis["pdf_plot"]; it must never overwrite RPDC columns
            # (hijack regression fda78d4, fixed 2026-06-10 by operator mandate).
            "rpdc_release_score": float(top.get("rpdc_release_score") or 0.0),
            "rpdc_cash_window_flag": bool(top.get("rpdc_cash_window_flag", False)),
            "rpdc_primary_tag": top.get("rpdc_primary_tag"),
            "rpdc_tags": top.get("rpdc_tags") or [],
            "rpdc_tag_count": int(top.get("rpdc_tag_count") or 0),
            # NOTE: this inline dict is replaced below by full_analysis_data before
            # upsert; PDF plot intelligence is preserved there under "plot_intel".
            "full_analysis": {
                "top_horse": top.get("horse"),
                "plot_conviction": top.get("plot_conviction"),
                "or_delta": top.get("or_delta_to_best_win"),
                "postdata_score": top.get("postdata_score"),
                "ts_peak": top.get("ts_master"),
                "signals": top.get("intent_signals", []),
                "reasons": top.get("router_reasons", []),
                "verdict_explanation": generate_decision_explanation(top, race),
            },
            # Ensemble observability — queryable without reading source code.
            # active_components: what actually entered the weighted average this race.
            # excluded_from_ensemble: what was computed but excluded (_DISABLED or zero-variance).
            # Requires migration: supabase/migrations/20260405_001_velo_verdicts_observability.sql
            "active_components": top.get("active_components") or [],
            "excluded_from_ensemble": top.get("excluded_from_ensemble") or [],
            # Horse State Brain — compact queryable state for top selection.
            # Full raw per-runner state lives in full_analysis[*].horse_state.
            # Requires migration: supabase/migrations/20260405_002_velo_verdicts_horse_state.sql
            "top_horse_readiness_state": _hs.get("readiness_state"),
            "top_horse_release_state": _hs.get("release_state"),
            "top_horse_rest_pattern": _hs.get("rest_pattern"),
            "top_horse_class_move_state": _hs.get("class_move_state"),
            "top_horse_stable_heat": _hs.get("stable_heat"),
            "top_horse_jockey_signal": _hs.get("jockey_signal"),
            "top_horse_market_state": _hs.get("market_state"),
            "top_horse_race_fit_state": _hs.get("race_fit_state"),
            "top_horse_chaos_exposure": _hs.get("chaos_exposure"),
            "top_horse_signal_count": _hs.get("live_signals"),
            "top_horse_state_evidence": _hs.get("state_evidence") or [],
            # Race Archetype — Layer 3 classification. Stored on top dict by _apply_archetype()
            # in run_prime_today.py. Requires migration: supabase/migrations/20260405_003_velo_verdicts_archetype.sql
            "race_archetype": top.get("race_archetype"),
            "archetype_confidence": top.get("archetype_confidence"),
            "archetype_bet_style": top.get("archetype_bet_style"),
            "archetype_suppression": top.get("archetype_suppression"),
            "archetype_trap_flag": top.get("archetype_trap_flag"),
            # ── Playbook G Shadow instrumentation ──────────────────────────────────
            # Requires migration: 20260408_005_velo_verdicts_g_shadow_instrumentation.sql
            # These columns are NULL if migration not applied — graceful degradation.
            "g_shadow_multiplier": top.get("g_shadow_multiplier"),
            "g_shadow_flags": top.get("g_shadow_flags") or [],
            "g_shadow_horse_id": top.get("g_shadow_horse_id") or "",
            "g_shadow_mode": top.get("g_shadow_mode") or "shadow",
            "g_top3_scores": top3_scores,
            # ── Governed Execution ────────────────────────────────────────────────
            "assigned_product": top.get("assigned_product"),
            "router_reasons": top.get("router_reasons"),
            "execution_allowed": top.get("execution_allowed"),
            # ── Audit traceability ────────────────────────────────────────────────
            # decision_tier: canonical tier from synthesize_decision() — previously
            # accepted as parameter and validated but never written to the row dict.
            # git_commit_sha: scoring run commit for audit queries; NULL until fixed.
            "decision_tier": decision_tier,
            "git_commit_sha": commit_sha,
        }

        # VÉLØ Oracle — Narrative and regime
        # Include plot intel in full_analysis for observability
        full_analysis_data = {
            "predictions": predictions,
            "plot_intel": {
                "plot_conviction": top.get("plot_conviction"),
                # pdf_plot_flag preserves the signal the old (hijacked) rpdc_primary_tag
                # column encoded as "PDF_PLOT" — kept here, never in rpdc_* columns.
                "pdf_plot_flag": bool((top.get("plot_conviction") or 0.0) >= 0.7),
                "or_delta": top.get("or_delta_to_best_win"),
                "postdata_score": top.get("postdata_score"),
                "ts_peak": top.get("ts_master"),
                "intent_signals": top.get("intent_signals", []),
            },
            "governance": {
                "assigned_product": top.get("assigned_product"),
                "router_reasons": top.get("router_reasons"),
                "rp_flatline_warning": top.get("rp_flatline_warning"),
            },
        }

        # Passive warehouse enrichment — injects into runner blocks only.
        # Scoring outputs, rankings, and top-level row columns are unchanged.
        # FIELD_TYPE: display-only — horse_recent_*, trainer_course_*, trainer_dist_*
        # not read by sigma or Playbook G — see TRUTH_REGISTRY.md §4
        enriched = _enrich_full_analysis_from_warehouse(full_analysis_data["predictions"], race, sb)
        full_analysis_data["predictions"] = enriched

        row["full_analysis"] = full_analysis_data

        # Upsert with graceful degradation for optional column groups.
        # Each group is stripped on its first error so scoring is never blocked
        # by a missing migration. Core fields (race_id, velo_prime_prob etc.) always persist.
        _optional_col_groups = [
            (
                "honesty_labels",
                ["fetch_timestamp", "predicted_field_size"],
                "Apply supabase/migrations/20260418_001_velo_verdicts_honesty_labels.sql",
            ),
            (
                "observability",
                ["active_components", "excluded_from_ensemble"],
                "Apply supabase/migrations/20260405_001_velo_verdicts_observability.sql",
            ),
            (
                "horse_state",
                [
                    "top_horse_readiness_state",
                    "top_horse_release_state",
                    "top_horse_rest_pattern",
                    "top_horse_class_move_state",
                    "top_horse_stable_heat",
                    "top_horse_jockey_signal",
                    "top_horse_market_state",
                    "top_horse_race_fit_state",
                    "top_horse_chaos_exposure",
                    "top_horse_signal_count",
                    "top_horse_state_evidence",
                ],
                "Apply supabase/migrations/20260405_002_velo_verdicts_horse_state.sql",
            ),
            (
                "archetype",
                [
                    "race_archetype",
                    "archetype_confidence",
                    "archetype_bet_style",
                    "archetype_suppression",
                    "archetype_trap_flag",
                ],
                "Apply supabase/migrations/20260405_003_velo_verdicts_archetype.sql",
            ),
            (
                "g_shadow_instrumentation",
                [
                    "g_shadow_multiplier",
                    "g_shadow_flags",
                    "g_shadow_horse_id",
                    "g_shadow_mode",
                    "g_top3_scores",
                ],
                "Apply supabase/migrations/20260408_005_velo_verdicts_g_shadow_instrumentation.sql",
            ),
            (
                "confidence_split",
                ["confidence_level_raw", "confidence_level_effective"],
                "Apply supabase/migrations/20260412_002_confidence_level_split.sql",
            ),
            (
                "a_tier_suspect_cohort",
                ["a_tier_weak_place_flag"],
                "Apply supabase/migrations/20260412_003_a_tier_suspect_cohort.sql",
            ),
            (
                "governance",
                ["assigned_product", "router_reasons", "execution_allowed"],
                "Apply migration to add governance columns to velo_verdicts.",
            ),
        ]

        def _is_schema_error(exc: Exception) -> bool:
            msg = str(exc).lower()
            return "schema cache" in msg or "could not find the" in msg or "column" in msg

        def _error_names_group(exc: Exception, cols: list[str]) -> bool:
            msg = str(exc)
            return any(col in msg for col in cols)

        try:
            sb.table("velo_verdicts").upsert(row, on_conflict="race_id").execute()
        except Exception as _upsert_err:
            if _is_schema_error(_upsert_err):
                log.critical(
                    "SCHEMA_DRIFT DETECTED: Hard block on persist. Truth integrity compromised. | race=%s",
                    race.get("race_id"),
                )
                raise RuntimeError(f"SCHEMA_DRIFT on velo_verdicts: {_upsert_err}") from _upsert_err
            raise _upsert_err

        log.info(
            "Persisted verdict for race %s — top: %s (%.4f)",
            race.get("race_id"),
            top.get("horse"),
            top.get("velo_prime_prob"),
        )
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

        race_id = race.get("race_id")
        computed_at = datetime.now(UTC).isoformat()
        rows = []

        for pred in predictions:
            horse_id = pred.get("horse_id", "") or pred.get("horse", "")
            if not horse_id or not race_id:
                continue

            imp = pred.get("improvement_score")
            mkt = pred.get("market_deception_score")
            pp = pred.get("place_prob")
            ls = pred.get("longshot_prob")
            rd = pred.get("release_day_prob")
            ci = pred.get("comment_intel_score")
            vp = pred.get("velo_prime_prob")

            rows.append(
                {
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "computed_at": computed_at,
                    "feature_schema_version": "velo_prime_v1",
                    # Specialist model outputs mapped to doctrine feature columns
                    "form_cycle_score": imp,
                    "market_confidence_score": mkt,
                    "release_day_score": rd,
                    "survivability_score": pp,
                    "chaos_score": ls,
                    "trainer_intent_score": ci,
                    # Full feature vector for retraining
                    "feature_vector": {
                        "velo_prime_prob": vp,
                        "improvement_score": imp,
                        "market_deception_score": mkt,
                        "place_prob": pp,
                        "longshot_prob": ls,
                        "release_day_prob": rd,
                        "comment_intel_score": ci,
                        "confidence_level": pred.get("confidence_level"),
                        "draw_bias_score": pred.get("draw_bias_score"),
                    },
                }
            )

        if not rows:
            return 0

        sb.table("runner_derived_features").upsert(rows, on_conflict="race_id,horse_id").execute()
        log.info("Persisted %d runner_derived_features for race %s", len(rows), race_id)
        return len(rows)

    except Exception as e:
        log.warning("runner_derived_features persist failed for race %s: %s", race.get("race_id"), e)
        return 0
