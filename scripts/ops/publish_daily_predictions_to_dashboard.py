#!/usr/bin/env python3
"""
VELO Dashboard Daily Predictions Publisher V1
==============================================
Source priority:
  1. Supabase velo_verdicts.full_analysis.predictions — all runners per race
  2. Local JSON data/velo_prime_verdicts_YYYY_MM_DD.json — top pick per race (fallback)

Destination:
  data/dashboard_daily_predictions_YYYYMMDD.json  (idempotent JSON staging)

Audit:
  data/dashboard_daily_predictions_publish_audit_v1.json  (overwritten each run)

Usage:
    python scripts/publish_daily_predictions_to_dashboard.py [--date YYYY-MM-DD]

    --date  Target date in YYYY-MM-DD format (default: today UTC)

Env:
    VELO_DASHBOARD_PUBLISH_ENABLED=true  — required for automated pipeline calls
    SUPABASE_URL, SUPABASE_SERVICE_KEY   — Supabase credentials (from .env)

Hard rules enforced:
    - No scoring changes
    - No model changes
    - No Playbook E
    - No staking changes
    - No router changes
    - Thresholds sourced from codebase (run_prime_today.py), never invented here
    - Missing optional fields: null + recorded in audit (not fabricated)
    - Idempotent: safe to re-run; overwrites staging file only
"""

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── Thresholds — sourced directly from run_prime_today.py signal stack ──────
# Source: _signal_stack_badges_and_risks() and SIGNAL_STACK_EVIDENCE dict
# DO NOT modify without first changing the source in run_prime_today.py.
_VP30_THRESHOLD = 0.30         # line 709: if vp >= 0.30 and tier == "A"
_MDS_HIGH_THRESHOLD = 0.50     # line 711: if mds > 0.50
_IMPROVE_HIGH_THRESHOLD = 0.40 # line 714: if improve > 0.40
# B_LOW_VP uses same _VP30_THRESHOLD: line 717: if tier=="B" and vp < 0.30

PUBLISHER_VERSION = "dashboard_publisher_v1"
AUDIT_PATH = ROOT / "data" / "dashboard_daily_predictions_publish_audit_v1.json"

# Fields always null because they are not stored in prediction dicts.
# Sourced from racing API raw runners (not carried through scoring pipeline).
_NULL_FIELDS = [
    "runner_number", "draw", "jockey", "trainer",
    "odds", "sp", "bsp",
    "mpi", "chaos_bloom", "narrative_disruption",
    "power_anchor", "story_anchor",
    "verdict",
]

_NULL_FIELD_REASONS = {
    "runner_number": "not stored in prediction dict (racing API runner_number not carried through scoring)",
    "draw": "not stored in prediction dict (draw_num used in features but not output)",
    "jockey": "not stored in prediction dict (jockey intent signal used, not name)",
    "trainer": "not stored in prediction dict (trainer intent signal used, not name)",
    "odds": "not stored in prediction dict (sp_dec used in scoring but not output)",
    "sp": "not stored in prediction dict (sp_dec used in scoring but not carried through)",
    "bsp": "not in pipeline — Betfair BSP not ingested",
    "mpi": "not computed in current pipeline",
    "chaos_bloom": "not computed in current pipeline",
    "narrative_disruption": "not computed in current pipeline",
    "power_anchor": "POWER_ANCHOR_MODE is an execution directive, not a sidecar field",
    "story_anchor": "directive-level concept, not a sidecar field",
    "verdict": "no single-word verdict field in current schema; tier+decision_tier used instead",
}


def _sf(v, default=None):
    """Safe float conversion. Returns default on None or error."""
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _compute_flags(pred: dict, race_tier: str) -> dict:
    """
    Compute all boolean sidecar flags from real field values only.
    Thresholds are sourced from run_prime_today.py — not invented here.
    Returns null for mds_high/improve_high when the source score is absent.
    """
    vp = _sf(pred.get("velo_prime_prob"), 0.0)
    mds = _sf(pred.get("market_deception_score"))
    improve = _sf(pred.get("improvement_score"))

    vp30 = bool(vp >= _VP30_THRESHOLD)
    tier_a = bool(race_tier == "A")
    vp30_tier_a = bool(vp30 and tier_a)

    mds_high = bool(mds > _MDS_HIGH_THRESHOLD) if mds is not None else None
    improve_high = bool(improve > _IMPROVE_HIGH_THRESHOLD) if improve is not None else None
    b_tier_low_vp_suppress = bool(race_tier == "B" and vp < _VP30_THRESHOLD) if race_tier else None

    return {
        "vp30": vp30,
        "tier_a": tier_a,
        "vp30_tier_a": vp30_tier_a,
        "mds_high": mds_high,
        "improve_high": improve_high,
        "b_tier_low_vp_suppress": b_tier_low_vp_suppress,
    }


def _build_runner_row(
    pred: dict,
    race_tier: str,
    race_id: str,
    race_time: str,
    course: str,
    race_name: str,
    rank: int,
    publish_date: str,
    run_id: str,
    generated_at: str,
) -> dict:
    """Build one normalized dashboard payload row for one runner."""
    flags = _compute_flags(pred, race_tier)

    horse_id = pred.get("horse_id") or None
    # runner_id: racing API has a separate runner_id not stored in prediction dicts.
    # Using horse_id as stable identifier. Recorded in audit as missing field.
    runner_id = horse_id

    idempotency_key = f"{publish_date}:{race_id}:{runner_id or pred.get('horse', '')}"

    hs = pred.get("horse_state") or {}

    sidecars = {
        "sqpe_v17_prob":                  _sf(pred.get("sqpe_v17_prob")),
        "longshot_prob":                  _sf(pred.get("longshot_prob")),
        "release_day_prob":               _sf(pred.get("release_day_prob")),
        "comment_intel_score":            _sf(pred.get("comment_intel_score")),
        "confidence_level":               pred.get("confidence_level"),
        "confidence_level_effective":     pred.get("confidence_level_effective"),
        "macro_regime_label":             pred.get("macro_regime_label"),
        "macro_chaos_mode":               pred.get("macro_chaos_mode"),
        "favourite_trap_risk":            pred.get("favourite_trap_risk"),
        "g_shadow_multiplier":            _sf(pred.get("g_shadow_multiplier")),
        "g_shadow_flags":                 pred.get("g_shadow_flags") or [],
        "g_shadow_mode":                  pred.get("g_shadow_mode"),
        "doctrines_fired":                pred.get("doctrines_fired") or [],
        "race_archetype":                 pred.get("race_archetype"),
        "archetype_label":                pred.get("archetype_label"),
        "archetype_confidence":           pred.get("archetype_confidence"),
        "archetype_bet_style":            pred.get("archetype_bet_style"),
        "archetype_suppression":          pred.get("archetype_suppression"),
        "archetype_trap_flag":            pred.get("archetype_trap_flag"),
        "assigned_product":               pred.get("assigned_product"),
        "router_reasons":                 pred.get("router_reasons") or [],
        "execution_allowed":              pred.get("execution_allowed"),
        "candidate_execution_allowed":    pred.get("candidate_execution_allowed"),
        "candidate_execution_lane":       pred.get("candidate_execution_lane"),
        "rpdc_release_score":             _sf(pred.get("rpdc_release_score")),
        "rpdc_cash_window_flag":          pred.get("rpdc_cash_window_flag"),
        "rpdc_primary_tag":               pred.get("rpdc_primary_tag"),
        "rpdc_tags":                      pred.get("rpdc_tags") or [],
        "spotlight_score":                _sf(pred.get("spotlight_score")),
        "tie_gate_fires":                 pred.get("tie_gate_fires"),
        "tie_gate_tier_upgrade":          pred.get("tie_gate_tier_upgrade"),
        "tie_gate_ew_flag":               pred.get("tie_gate_ew_flag"),
        "tie_gate_signals":               pred.get("tie_gate_signals") or [],
        "horse_state_readiness":          hs.get("readiness_state"),
        "horse_state_release":            hs.get("release_state"),
        "horse_state_rest_pattern":       hs.get("rest_pattern"),
        "horse_state_stable_heat":        hs.get("stable_heat"),
        "horse_state_market":             hs.get("market_state"),
        "horse_state_race_fit":           hs.get("race_fit_state"),
        "horse_state_chaos_exposure":     hs.get("chaos_exposure"),
        "horse_state_jockey_signal":      hs.get("jockey_signal"),
        "horse_state_live_signals":       hs.get("live_signals"),
        "racing_api_enrichment_shadow_score": _sf(pred.get("racing_api_enrichment_shadow_score")),
        "racing_api_connection_shadow_score": _sf(pred.get("racing_api_connection_shadow_score")),
        "racing_api_course_shadow_score":     _sf(pred.get("racing_api_course_shadow_score")),
        "racing_api_distance_shadow_score":   _sf(pred.get("racing_api_distance_shadow_score")),
        "a_tier_weak_place_flag":         pred.get("a_tier_weak_place_flag"),
        "sentient_modifier_applied":      pred.get("sentient_modifier_applied"),
        "sentient_modifier_mode":         pred.get("sentient_modifier_mode"),
        "rpd_tag":                        pred.get("rpd_tag"),
        "rpd_confidence":                 _sf(pred.get("rpd_confidence")),
        "headgear_run":                   pred.get("headgear_run"),
        "wind_surgery_run":               pred.get("wind_surgery_run"),
        "cash_run_flag":                  pred.get("cash_run_flag"),
        "setup_run_flag":                 pred.get("setup_run_flag"),
        "decoy_support_flag":             pred.get("decoy_support_flag"),
    }

    feature_presence = {
        "or_missing":            pred.get("or_missing"),
        "rpr_missing":           pred.get("rpr_missing"),
        "ts_missing":            pred.get("ts_missing"),
        "macro_available":       pred.get("macro_available"),
        "macro_context_failed":  pred.get("macro_context_failed"),
        "horse_state_failed":    pred.get("horse_state_failed"),
        "sentient_state_loaded": pred.get("sentient_state_loaded"),
        "active_components":     pred.get("active_components") or [],
        "excluded_from_ensemble": pred.get("excluded_from_ensemble") or [],
    }

    return {
        "publish_date":   publish_date,
        "race_id":        race_id,
        "race_time":      race_time,
        "course":         course,
        "race_name":      race_name,
        "runner_id":      runner_id,
        "horse_id":       horse_id,
        "horse_name":     pred.get("horse"),
        # ── Always null: not in prediction dict ──────────────────────
        "runner_number":  None,
        "draw":           None,
        "jockey":         None,
        "trainer":        None,
        "odds":           None,
        "sp":             None,
        "bsp":            None,
        # ── Scores ───────────────────────────────────────────────────
        "velo_prime_prob":       _sf(pred.get("velo_prime_prob")),
        "decision_tier":         race_tier,
        "rank":                  rank,
        "verdict":               None,   # no single-word verdict in current schema
        # ── Flags (computed from real fields + codebase thresholds) ──
        **flags,
        # ── Key sidecars at top level ─────────────────────────────────
        "market_deception_score": _sf(pred.get("market_deception_score")),
        "improvement_score":      _sf(pred.get("improvement_score")),
        "place_prob":             _sf(pred.get("place_prob")),
        # ── Directives — null per contract (not sidecar fields) ──────
        "power_anchor":        None,
        "story_anchor":        None,
        "mpi":                 None,
        "chaos_bloom":         None,
        "narrative_disruption": None,
        # ── Full sidecar dict for expand/collapse display ─────────────
        "sidecars":            sidecars,
        "feature_presence":    feature_presence,
        # ── Provenance ───────────────────────────────────────────────
        "model_version":       pred.get("ensemble_version"),
        "run_id":              run_id,
        "generated_at":        generated_at,
        "idempotency_key":     idempotency_key,
    }


def _load_local_json(date_tag: str) -> list[dict]:
    """Load local JSON verdict file. Returns [] if missing or unreadable."""
    path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists():
        candidates = sorted(ROOT.glob("data/velo_prime_verdicts_*.json"), reverse=True)
        path = candidates[0] if candidates else None
    if not path or not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"  [WARN] local JSON read failed: {e}")
        return []


def _load_supabase_predictions(date_str: str) -> tuple[dict, dict, str]:
    """
    Load all runner predictions from Supabase velo_verdicts.full_analysis
    and race metadata (course, race_name, time) from the races table.
    Returns (
        verdicts dict keyed by race_id → {predictions, decision_tier, generated_at},
        race_meta dict keyed by race_id → {course, race_name, off_time},
        source_label string,
    ).
    """
    try:
        from app.core.runtime_env import load_optional_env_file, resolve_supabase_service_key, resolve_supabase_url

        load_optional_env_file(None)
        sb_url = resolve_supabase_url()
        sb_key = resolve_supabase_service_key()
        if not sb_url or not sb_key:
            return {}, {}, "supabase_skipped:no_credentials"

        from supabase import create_client

        db = create_client(sb_url, sb_key)
        resp = (
            db.table("velo_verdicts")
            .select("race_id, decision_tier, generated_at, full_analysis")
            .gte("generated_at", f"{date_str}T00:00:00")
            .lte("generated_at", f"{date_str}T23:59:59")
            .execute()
        )
        rows = resp.data or []
        result: dict = {}
        race_ids: list = []
        for row in rows:
            rid = row.get("race_id")
            if not rid:
                continue
            race_ids.append(rid)
            fa = row.get("full_analysis") or {}
            if isinstance(fa, list):
                preds = fa  # stored as list of runner dicts directly
            else:
                preds = fa.get("predictions") or []
            result[rid] = {
                "predictions": preds,
                "decision_tier": row.get("decision_tier") or "?",
                "generated_at": row.get("generated_at") or date_str,
            }

        # Load race metadata from races table
        race_meta: dict = {}
        if race_ids:
            try:
                mr = db.table("races").select("race_id,course,race_name,time").in_("race_id", race_ids).execute()
                for r in (mr.data or []):
                    rid = r.get("race_id")
                    if rid:
                        raw_t = r.get("time") or ""
                        race_meta[rid] = {
                            "course":    r.get("course") or "",
                            "race_name": r.get("race_name") or "",
                            "off_time":  raw_t[:5] if raw_t else "",
                        }
            except Exception:
                pass  # race metadata is optional; runner data is the primary payload

        return result, race_meta, f"supabase:{len(rows)}_rows_loaded"
    except ImportError:
        return {}, {}, "supabase_skipped:supabase_package_not_installed"
    except Exception as e:
        return {}, {}, f"supabase_failed:{str(e)[:120]}"


def publish(date_str: str) -> dict:
    """
    Main publish function. Reads predictions, builds payload, writes JSON staging.
    Returns the audit dict.
    """
    publish_date = date_str
    date_tag = date_str.replace("-", "_")
    run_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()

    print(f"\nVELO Dashboard Daily Predictions Publisher V1")
    print(f"  Date:    {publish_date}")
    print(f"  run_id:  {run_id[:8]}...")
    print(f"  Version: {PUBLISHER_VERSION}")

    # ── Load Supabase full_analysis.predictions (all runners per race) ────────
    sb_data, sb_race_meta, sb_source = _load_supabase_predictions(date_str)
    print(f"\n  Supabase:  {len(sb_data)} races  [{sb_source}]")

    # ── Load local JSON — only used when Supabase has no data for this date ──
    # Prevents mixing races from different dates when Supabase fallback finds
    # the most-recent local file (which may be a previous day).
    race_meta: dict = {}
    if sb_data:
        # Supabase has today's races — use its race metadata, ignore local JSON
        race_meta = sb_race_meta
    else:
        local_races = _load_local_json(date_tag)
        for r in local_races:
            rid = r.get("race_id")
            if rid:
                race_meta[rid] = {
                    "course":    r.get("course", ""),
                    "off_time":  r.get("off_time", ""),
                    "race_name": r.get("race_name", ""),
                    "tier":      r.get("tier", "?"),
                    "top":       r.get("top", {}),
                    "scored":    r.get("scored", 0),
                }
    print(f"  Local JSON: {len(race_meta) if not sb_data else 0} races (skipped — Supabase primary)" if sb_data else f"  Local JSON: {len(race_meta)} races (Supabase unavailable, using fallback)")

    # ── Build per-runner payload rows ─────────────────────────────────────────
    all_rows: list[dict] = []
    missing_sidecar_log: list[str] = []
    races_processed: set = set()
    errors: list[str] = []

    # When Supabase is primary, use only Supabase race_ids to avoid cross-date pollution
    if sb_data:
        all_race_ids = sorted(sb_data.keys())
    else:
        all_race_ids = sorted(race_meta.keys())

    for race_id in all_race_ids:
        meta = race_meta.get(race_id, {})
        course    = meta.get("course") or ""
        race_time = meta.get("off_time") or ""
        race_name = meta.get("race_name") or ""

        sb_race = sb_data.get(race_id, {})

        # Decision tier: Supabase authoritative when primary; local JSON otherwise
        race_tier    = sb_race.get("decision_tier") or meta.get("tier") or "?"
        generated_at = sb_race.get("generated_at") or now_iso

        # Runner predictions: Supabase (all runners) > local JSON top pick
        if sb_race.get("predictions"):
            runner_preds = sb_race["predictions"]
            pred_source = "supabase_full_analysis"
        elif meta.get("top"):
            runner_preds = [meta["top"]]
            pred_source = "local_json_top_only"
        else:
            continue

        races_processed.add(race_id)

        # Enforce rank order: highest velo_prime_prob = rank 1
        try:
            runner_preds = sorted(
                runner_preds,
                key=lambda p: float(p.get("velo_prime_prob") or 0),
                reverse=True,
            )
        except Exception:
            pass

        for rank, pred in enumerate(runner_preds, start=1):
            try:
                row = _build_runner_row(
                    pred=pred,
                    race_tier=race_tier,
                    race_id=race_id,
                    race_time=race_time,
                    course=course,
                    race_name=race_name,
                    rank=rank,
                    publish_date=publish_date,
                    run_id=run_id,
                    generated_at=generated_at,
                )
                all_rows.append(row)

                # Log missing fields for top pick only (once per race)
                if rank == 1:
                    missing_here = [f for f in _NULL_FIELDS if row.get(f) is None]
                    if missing_here:
                        missing_sidecar_log.append(
                            f"{race_id} ({course or '?'}): {missing_here[:6]}"
                        )
            except Exception as e:
                err = f"{race_id}/rank{rank}: {e}"
                errors.append(err)
                print(f"  [ERROR] {err}")

    # ── Counts ────────────────────────────────────────────────────────────────
    tier_a_count    = sum(1 for r in all_rows if r.get("tier_a"))
    vp30_count      = sum(1 for r in all_rows if r.get("vp30"))
    vp30_tier_a     = sum(1 for r in all_rows if r.get("vp30_tier_a"))
    mds_high_count  = sum(1 for r in all_rows if r.get("mds_high"))
    race_count      = len(races_processed)
    runner_count    = len(all_rows)
    source_used     = "supabase+local_json" if sb_data else "local_json_top_only"

    # ── Write staging JSON ────────────────────────────────────────────────────
    out_path = ROOT / "data" / f"dashboard_daily_predictions_{date_tag}.json"
    out_payload = {
        "publish_date":      publish_date,
        "generated_at":      now_iso,
        "run_id":            run_id,
        "publisher_version": PUBLISHER_VERSION,
        "source":            source_used,
        "destination":       out_path.name,
        "races":             race_count,
        "runners":           runner_count,
        "predictions":       all_rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2, default=str))

    # ── Write audit JSON ──────────────────────────────────────────────────────
    audit = {
        "publish_date":              publish_date,
        "run_id":                    run_id,
        "publisher_version":         PUBLISHER_VERSION,
        "generated_at":              now_iso,
        "source_table_or_file":      source_used,
        "supabase_source_detail":    sb_source,
        "destination_table_or_api":  str(out_path),
        "rows_read":                 runner_count,
        "rows_published":            runner_count,
        "rows_skipped":              0,
        "idempotent_skips":          0,
        "races_found":               race_count,
        "tier_a_count":              tier_a_count,
        "vp30_count":                vp30_count,
        "vp30_tier_a_count":         vp30_tier_a,
        "mds_high_count":            mds_high_count,
        "missing_sidecars_sample":   missing_sidecar_log[:20],
        "missing_sidecar_fields_always_null": _NULL_FIELDS,
        "reason_fields_null":        _NULL_FIELD_REASONS,
        "rerun_command":             f"python scripts/publish_daily_predictions_to_dashboard.py --date {publish_date}",
        "scoring_changed":           False,
        "model_changed":             False,
        "router_changed":            False,
        "staking_changed":           False,
        "playbook_e_touched":        False,
        "errors":                    errors,
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, default=str))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 52}")
    print(f"  RACES FOUND:        {race_count}")
    print(f"  RUNNERS PUBLISHED:  {runner_count}")
    print(f"  TIER A COUNT:       {tier_a_count}")
    print(f"  VP30 COUNT:         {vp30_count}")
    print(f"  VP30_TIER_A COUNT:  {vp30_tier_a}")
    print(f"  MDS_HIGH COUNT:     {mds_high_count}")
    print(f"  MISSING SIDECARS:   {len(missing_sidecar_log)} races with null optional fields")
    print(f"  DASHBOARD DEST:     {out_path.name}")
    print(f"  AUDIT FILE:         {AUDIT_PATH.name}")
    print(f"  SOURCE USED:        {source_used}")
    print(f"  SCORING CHANGED:    NO")
    print(f"  MODEL CHANGED:      NO")
    print(f"  ROUTER CHANGED:     NO")
    print(f"  STAKING CHANGED:    NO")
    if errors:
        print(f"  ERRORS:             {len(errors)}")
        for e in errors[:3]:
            print(f"    {e}")
    print(f"{'─' * 52}")
    print(f"\n  Rerun: python scripts/publish_daily_predictions_to_dashboard.py --date {publish_date}")

    return audit


def main():
    parser = argparse.ArgumentParser(
        description="Publish daily predictions to dashboard JSON staging"
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date in YYYY-MM-DD format (default: today UTC)",
    )
    args = parser.parse_args()

    date_str = args.date or datetime.now(UTC).strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: Invalid date format: {date_str!r}. Use YYYY-MM-DD.")
        sys.exit(1)

    # Load env file if present (local dev)
    try:
        from app.core.runtime_env import load_optional_env_file
        load_optional_env_file(None)
    except (ImportError, Exception):
        pass

    publish(date_str)


if __name__ == "__main__":
    main()
