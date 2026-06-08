"""
audit_improvement_restored_scoring_compare.py
----------------------------------------------
Compare-only scoring simulation: current vs improvement-restored paths.

Runs the improvement model on May24/25 runner data with and without RPDC
feature injection, assesses whether the zero-variance kill switch is defeated,
and estimates the VP score impact if improvement_score re-enters the ensemble.

Hard rules:
  - Same formula only — no formula changes
  - Same model only — no model changes
  - No writes to official artifacts
  - No Supabase
  - No Telegram
  - No dashboard publish

Paths compared:
  PATH A: current (improvement_score constant, kill switch fires, excluded)
  PATH B: RPDC injection (curr_or_minus_last_win_or from JSONL, 62.7% coverage)
  PATH C: racecard proxy (or_vs_field/rpr_vs_field/age_num from May17, cross-date)

Verdicts:
  FULL_FORMULA_RESTORABLE  — kill switch defeated, meaningful variance, VP delta significant
  PARTIAL_RESTORE_ONLY     — kill switch defeated but variance is small
  FEATURE_GAP_REMAINS      — kill switch still fires in all paths

Outputs:
  data/reports/improvement_restored_scoring_compare_latest.json
  data/reports/improvement_restored_scoring_compare_latest.md

Usage:
  PYTHONPATH=. python scripts/audit_improvement_restored_scoring_compare.py --date 2026-05-25
"""
from __future__ import annotations

import argparse
import glob
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.ops.load_rpdc_memory import get_memory_summary_for_runner, load_rpdc_memory
from app.services.v17_feature_extractor import DEFAULTS as V17_DEFAULTS

DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ROOT / "models" / "specialist" / "improvement_model" / "improvement_model.pkl"
META_PATH  = ROOT / "models" / "specialist" / "improvement_model" / "metadata.json"

IMPROVEMENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_best_or", "curr_or_minus_last_win_or",
    "release_window_score", "runs_since_win", "runs_since_place", "trainer_timing_score",
    "distance_fit_score", "course_fit_score", "or_vs_field", "rpr_vs_field", "age_num",
]

FEATURE_DEFAULTS = {
    "mark_compression_score": 0.0,
    "curr_or_minus_best_or":  0.0,
    "curr_or_minus_last_win_or": 0.0,
    "release_window_score":   0.0,
    "runs_since_win":         5.0,
    "runs_since_place":       2.0,
    "trainer_timing_score":   0.12,
    "distance_fit_score":     0.33,
    "course_fit_score":       0.33,
    "or_vs_field":            0.0,
    "rpr_vs_field":           0.0,
    "age_num":                0.0,
}

IMPROVEMENT_LIVE_WEIGHT = 0.12  # From SQPE_IMPROVEMENT_MDS_V1 profile
KILL_SWITCH_THRESHOLD = 1e-6


def _load_model():
    if not MODEL_PATH.exists():
        return None
    model = joblib.load(MODEL_PATH)
    return model


def _score(model, rows: list[dict]) -> list[float]:
    df = pd.DataFrame(rows)
    for feat in IMPROVEMENT_FEATURES:
        if feat not in df.columns:
            df[feat] = FEATURE_DEFAULTS.get(feat, 0.0)
    X = df[IMPROVEMENT_FEATURES].fillna(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return list(model.predict_proba(X)[:, 1])


def _fires(scores: list[float]) -> bool:
    valid = [s for s in scores if s is not None]
    if not valid:
        return True
    return (max(valid) - min(valid)) < KILL_SWITCH_THRESHOLD


def _load_snapshot_runners(date_str: str) -> tuple[list[dict], str]:
    date_tag = date_str.replace("-", "_")
    snaps = sorted(glob.glob(str(DATA_DIR / f"runner_snapshots_{date_tag}_*.jsonl")))
    if not snaps:
        return [], ""
    path = snaps[-1]
    seen: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = f"{r.get('horse_id','')}__{r.get('race_id','')}"
            if key not in seen:
                seen[key] = r
    return list(seen.values()), f"snapshot:{Path(path).name}"


def _load_racecard_ratings(date_str: str) -> dict[str, dict]:
    """Load OFR/RPR/age from standard racecard, or most recent proxy."""
    date_tag = date_str.replace("-", "_")
    p = DATA_DIR / f"racecards_{date_tag}_standard.json"
    if not p.exists():
        files = sorted(glob.glob(str(DATA_DIR / "racecards_*_standard.json")))
        if not files:
            return {}
        p = Path(files[-1])
    return _parse_racecard_ratings(p)


def _parse_racecard_ratings(path: Path) -> dict[str, dict]:
    from scripts.ops.load_rpdc_memory import _normalise_name
    data = json.loads(path.read_text(encoding="utf-8"))
    races = data if isinstance(data, list) else data.get("racecards", data.get("races", []))
    result: dict[str, dict] = {}
    for race in races:
        runners = race.get("runners") or []
        ofr_vals = []
        rpr_vals = []
        for r in runners:
            try:
                v = float(r.get("ofr") or 0)
                if v > 0:
                    ofr_vals.append(v)
            except (TypeError, ValueError):
                pass
            try:
                v = float(r.get("rpr") or 0)
                if v > 0:
                    rpr_vals.append(v)
            except (TypeError, ValueError):
                pass
        avg_ofr = sum(ofr_vals) / len(ofr_vals) if ofr_vals else 0.0
        avg_rpr = sum(rpr_vals) / len(rpr_vals) if rpr_vals else 0.0

        for r in runners:
            hid = r.get("horse_id", "")
            hname = r.get("horse", "")
            try:
                ofr = float(r.get("ofr") or 0) or None
            except (TypeError, ValueError):
                ofr = None
            try:
                rpr = float(r.get("rpr") or 0) or None
            except (TypeError, ValueError):
                rpr = None
            try:
                age = float(r.get("age") or 0) or None
            except (TypeError, ValueError):
                age = None

            entry = {
                "or_vs_field": (ofr - avg_ofr) if ofr is not None else 0.0,
                "rpr_vs_field": (rpr - avg_rpr) if rpr is not None else 0.0,
                "age_num": age if age is not None else 0.0,
            }
            if hid:
                result[hid] = entry
            nname = _normalise_name(hname)
            if nname:
                result[f"__name__{nname}"] = entry
    return result


def _rc_lookup(horse_id: str, horse_name: str, rc: dict) -> dict | None:
    from scripts.ops.load_rpdc_memory import _normalise_name
    if horse_id and horse_id in rc:
        return rc[horse_id]
    nname = _normalise_name(horse_name)
    if nname and f"__name__{nname}" in rc:
        return rc[f"__name__{nname}"]
    return None


def _tier_from_vp(vp: float) -> str:
    if vp >= 0.40:
        return "A"
    if vp >= 0.30:
        return "B"
    if vp >= 0.20:
        return "C"
    return "D"


def run_comparison(date_str: str) -> dict:
    print(f"\n{'='*60}")
    print(f"IMPROVEMENT RESTORED SCORING COMPARISON — {date_str}")
    print(f"  (Compare-only — NO writes, NO formula change)")
    print(f"{'='*60}")

    model = _load_model()
    if model is None:
        print("  ERROR: improvement_model.pkl not found")
        return {"status": "MODEL_NOT_FOUND"}

    # Load runners (May25 → May24 proxy)
    runners, snap_source = _load_snapshot_runners(date_str)
    is_proxy = False
    data_date = date_str
    if not runners:
        print(f"  No snapshot for {date_str} — using May24 proxy")
        runners, snap_source = _load_snapshot_runners("2026-05-24")
        is_proxy = True
        data_date = "2026-05-24"
    if not runners:
        return {"status": "NO_RUNNER_DATA"}

    print(f"  Runner source: {snap_source}")
    print(f"  Runners: {len(runners)}")

    # Load RPDC memory
    memory = load_rpdc_memory()
    print(f"  RPDC memory: {memory['_total_rows']:,} rows")

    # Load racecard ratings (cross-date proxy if needed)
    rc = _load_racecard_ratings(data_date)
    rc_dates = sorted(glob.glob(str(DATA_DIR / "racecards_*_standard.json")))
    rc_proxy_source = Path(rc_dates[-1]).name if rc_dates else "none"
    rc_is_proxy = not (DATA_DIR / f"racecards_{data_date.replace('-','_')}_standard.json").exists()
    print(f"  Racecard: {rc_proxy_source}{'  (cross-date proxy)' if rc_is_proxy else ''}")

    # Build feature rows and collect baseline scores
    path_a_rows, path_b_rows, path_c_rows = [], [], []
    rpdc_matched = 0
    rc_matched = 0
    runner_records = []

    for r in runners:
        hid = r.get("horse_id", "")
        hname = r.get("horse", "") or r.get("top_pick_name", "")
        race_id = r.get("race_id", "")
        vp_current = r.get("velo_prime_prob") or r.get("top_pick_vp")
        tier_current = r.get("tier") or r.get("decision_tier", "D")
        imp_current = r.get("improvement_score", FEATURE_DEFAULTS["or_vs_field"])

        # RPDC lookup
        rpdc_ctx = get_memory_summary_for_runner(
            horse_id=hid,
            horse_name=hname,
            as_of_date=date_str,
            memory=memory,
        )
        rpdc_delta = rpdc_ctx.get("curr_or_minus_last_win_or") if rpdc_ctx["memory_found"] else None
        if rpdc_ctx["memory_found"]:
            rpdc_matched += 1

        # Racecard lookup
        rc_entry = _rc_lookup(hid, hname, rc)
        if rc_entry:
            rc_matched += 1

        # Path A: all defaults
        row_a = dict(FEATURE_DEFAULTS)

        # Path B: RPDC curr_or_minus_last_win_or injected
        row_b = dict(FEATURE_DEFAULTS)
        if rpdc_delta is not None:
            row_b["curr_or_minus_last_win_or"] = float(rpdc_delta)

        # Path C: racecard OFR/RPR/age + RPDC
        row_c = dict(FEATURE_DEFAULTS)
        if rpdc_delta is not None:
            row_c["curr_or_minus_last_win_or"] = float(rpdc_delta)
        if rc_entry:
            row_c["or_vs_field"] = rc_entry["or_vs_field"]
            row_c["rpr_vs_field"] = rc_entry["rpr_vs_field"]
            row_c["age_num"] = rc_entry["age_num"]

        path_a_rows.append(row_a)
        path_b_rows.append(row_b)
        path_c_rows.append(row_c)

        runner_records.append({
            "horse_id": hid, "horse": hname, "race_id": race_id,
            "vp_current": vp_current, "tier_current": tier_current,
            "imp_score_current": imp_current,
            "rpdc_matched": rpdc_ctx["memory_found"],
            "rpdc_or_delta": rpdc_delta,
            "rc_matched": rc_entry is not None,
        })

    # Score all paths
    scores_a = _score(model, path_a_rows)
    scores_b = _score(model, path_b_rows)
    scores_c = _score(model, path_c_rows)

    kill_a = _fires(scores_a)
    kill_b = _fires(scores_b)
    kill_c = _fires(scores_c)

    def _stats(scores: list[float]) -> dict:
        return {
            "min": round(float(np.min(scores)), 4),
            "max": round(float(np.max(scores)), 4),
            "mean": round(float(np.mean(scores)), 4),
            "std": round(float(np.std(scores)), 4),
            "range": round(float(np.max(scores) - np.min(scores)), 4),
        }

    stats_a = _stats(scores_a)
    stats_b = _stats(scores_b)
    stats_c = _stats(scores_c)

    # Compute approximate VP delta from improvement_score change
    # VP delta ≈ (imp_b - imp_a) * IMPROVEMENT_LIVE_WEIGHT (pre-normalization)
    # This is an approximation — full VP change requires running the whole ensemble
    vp_deltas_b = [(b - a) * IMPROVEMENT_LIVE_WEIGHT for a, b in zip(scores_a, scores_b)]
    vp_deltas_c = [(c - a) * IMPROVEMENT_LIVE_WEIGHT for a, c in zip(scores_a, scores_c)]

    def _delta_stats(deltas: list[float]) -> dict:
        return {
            "min": round(float(np.min(deltas)), 4),
            "max": round(float(np.max(deltas)), 4),
            "mean": round(float(np.mean(deltas)), 4),
            "std": round(float(np.std(deltas)), 4),
            "movers_gt_001": sum(1 for d in deltas if abs(d) > 0.01),
            "movers_gt_002": sum(1 for d in deltas if abs(d) > 0.02),
        }

    delta_stats_b = _delta_stats(vp_deltas_b)
    delta_stats_c = _delta_stats(vp_deltas_c)

    # Tier analysis — using estimated VP from current VP + delta
    tier_changes_b = 0
    tier_changes_c = 0
    for i, rec in enumerate(runner_records):
        vp_cur = rec.get("vp_current") or 0.0
        try:
            vp_cur = float(vp_cur)
        except (TypeError, ValueError):
            vp_cur = 0.0
        tier_est_b = _tier_from_vp(vp_cur + vp_deltas_b[i])
        tier_est_c = _tier_from_vp(vp_cur + vp_deltas_c[i])
        rec["imp_score_b"] = round(scores_b[i], 4)
        rec["imp_score_c"] = round(scores_c[i], 4)
        rec["vp_delta_b"] = round(vp_deltas_b[i], 4)
        rec["vp_delta_c"] = round(vp_deltas_c[i], 4)
        tier_b_changed = tier_est_b != _tier_from_vp(vp_cur)
        tier_c_changed = tier_est_c != _tier_from_vp(vp_cur)
        rec["tier_change_b"] = tier_b_changed
        rec["tier_change_c"] = tier_c_changed
        if tier_b_changed:
            tier_changes_b += 1
        if tier_c_changed:
            tier_changes_c += 1

    # Classify verdict for each path
    def _classify_path(kill: bool, stats: dict, delta_stats: dict, label: str) -> dict:
        if kill:
            verdict = "KILL_SWITCH_FIRES — improvement_score excluded"
        elif stats["range"] > 0.05:
            verdict = "FULL_FORMULA_RESTORABLE" if "racecard" in label.lower() else "PARTIAL_RESTORE_ONLY"
        elif stats["range"] > 0.005:
            verdict = "PARTIAL_RESTORE_ONLY — variance present, kill switch defeated"
        else:
            verdict = "MARGINAL — variance near threshold"
        return {"kill_switch": kill, "score_stats": stats, "vp_delta_stats": delta_stats, "verdict": verdict}

    path_a_result = {"kill_switch": kill_a, "score_stats": stats_a, "verdict": "KILL_SWITCH_FIRES — current state"}
    path_b_result = _classify_path(kill_b, stats_b, delta_stats_b, "RPDC path")
    path_c_result = _classify_path(kill_c, stats_c, delta_stats_c, "racecard path")

    # May25 pre-score gate
    if is_proxy:
        may25_gate = "FEATURE_DEGRADED_WARN"
        may25_gate_detail = (
            f"May25 card not available. Using May24 proxy. "
            f"Path B (RPDC only) kills switch status: {'FIRE' if kill_b else 'PASS'}. "
            f"Racecard source needed (OFR/RPR/age) for PARTIAL_RESTORE_ONLY. "
            f"May25 must run as FEATURE_DEGRADED unless same-date racecard with ratings is available."
        )
    elif not kill_b and stats_b["range"] > 0.005:
        may25_gate = "PARTIAL_FORMULA_RPDC"
        may25_gate_detail = "RPDC injection restores improvement_score variance. Racecard OFR/RPR/age still needed for full restore."
    else:
        may25_gate = "FEATURE_DEGRADED_BLOCK_RECOMMENDED"
        may25_gate_detail = "Kill switch fires on all paths with available data. improvement_score cannot be restored."

    run_ts = datetime.now(timezone.utc).isoformat()
    output = {
        "audit_date": date_str,
        "data_date": data_date,
        "is_proxy": is_proxy,
        "racecard_proxy_source": rc_proxy_source,
        "racecard_is_cross_date": rc_is_proxy,
        "run_at": run_ts,
        "runner_source": snap_source,
        "runner_count": len(runners),
        "rpdc_matched": rpdc_matched,
        "rpdc_match_rate_pct": round(rpdc_matched / len(runners) * 100, 1) if runners else 0.0,
        "rc_matched": rc_matched,
        "rc_match_rate_pct": round(rc_matched / len(runners) * 100, 1) if runners else 0.0,
        "improvement_live_weight": IMPROVEMENT_LIVE_WEIGHT,
        "path_a": path_a_result,
        "path_b": path_b_result,
        "path_c": path_c_result,
        "tier_changes_b": tier_changes_b,
        "tier_changes_c": tier_changes_c,
        "may25_gate": may25_gate,
        "may25_gate_detail": may25_gate_detail,
        "supabase_mutated": False,
        "scoring_changed": False,
        "formula_changed": False,
        "model_changed": False,
        "runner_detail": runner_records,
    }

    _write_outputs(date_str, output)
    _print_summary(output)
    return output


def _write_outputs(date_str: str, output: dict) -> None:
    json_path = REPORTS_DIR / "improvement_restored_scoring_compare_latest.json"
    md_path   = REPORTS_DIR / "improvement_restored_scoring_compare_latest.md"

    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    a = output["path_a"]
    b = output["path_b"]
    c = output["path_c"]

    proxy_note = ""
    if output.get("is_proxy"):
        proxy_note = f"\n**NOTE:** May25 card not available. Using {output['data_date']} as proxy.  "
    rc_note = ""
    if output.get("racecard_is_cross_date"):
        rc_note = f"\n**NOTE:** Path C uses cross-date racecard proxy ({output['racecard_proxy_source']}). OFR/RPR/age are from a different day — demonstrative only.  "

    lines = [
        f"# Improvement Restored Scoring Comparison — {date_str}",
        "",
        f"**Generated:** {output['run_at']}  ",
        f"**Runner source:** {output['runner_source']}  ",
        proxy_note, rc_note,
        "",
        "---",
        "",
        f"## May25 Gate: `{output['may25_gate']}`",
        "",
        f"> {output['may25_gate_detail']}",
        "",
        "## Path Comparison",
        "",
        "| Path | Description | Kill switch | Score range | VP delta max | Tier changes |",
        "|---|---|---|---|---|---|",
        f"| A (current) | DEFAULTS only | {'FIRES' if a['kill_switch'] else 'OK'} | {a['score_stats']['range']:.4f} | — | — |",
        f"| B (RPDC) | + curr_or_minus_last_win_or | {'FIRES' if b['kill_switch'] else 'OK'} | {b['score_stats']['range']:.4f} | {b['vp_delta_stats']['max']:.4f} | {output['tier_changes_b']} |",
        f"| C (racecard+RPDC) | + or/rpr/age (proxy) | {'FIRES' if c['kill_switch'] else 'OK'} | {c['score_stats']['range']:.4f} | {c['vp_delta_stats']['max']:.4f} | {output['tier_changes_c']} |",
        "",
        "## RPDC Coverage",
        "",
        f"| Metric | Value |",
        "|---|---|",
        f"| Runners | {output['runner_count']} |",
        f"| RPDC matched | {output['rpdc_matched']} ({output['rpdc_match_rate_pct']}%) |",
        f"| Racecard matched | {output['rc_matched']} ({output['rc_match_rate_pct']}%) |",
        "",
        "## Path Verdicts",
        "",
        f"| Path | Verdict |",
        "|---|---|",
        f"| A | {a['verdict']} |",
        f"| B | {b['verdict']} |",
        f"| C | {c['verdict']} |",
        "",
        "```",
        f"AUDIT_DATE:          {date_str}",
        f"IMPROVEMENT_WEIGHT:  {output['improvement_live_weight']}",
        f"PATH_A_KILL_SWITCH:  {a['kill_switch']}",
        f"PATH_B_KILL_SWITCH:  {b['kill_switch']}",
        f"PATH_C_KILL_SWITCH:  {c['kill_switch']}",
        f"PATH_B_RANGE:        {b['score_stats']['range']:.4f}",
        f"PATH_C_RANGE:        {c['score_stats']['range']:.4f}",
        f"TIER_CHANGES_B:      {output['tier_changes_b']}",
        f"TIER_CHANGES_C:      {output['tier_changes_c']}",
        f"MAY25_GATE:          {output['may25_gate']}",
        "SUPABASE_MUTATED:    False",
        "SCORING_CHANGED:     False",
        "FORMULA_CHANGED:     False",
        "MODEL_CHANGED:       False",
        "```",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  JSON → {json_path}")
    print(f"  MD  → {md_path}")


def _print_summary(output: dict) -> None:
    a, b, c = output["path_a"], output["path_b"], output["path_c"]
    print(f"\n  Runners:          {output['runner_count']} ({'proxy' if output['is_proxy'] else 'actual'})")
    print(f"  RPDC match rate:  {output['rpdc_match_rate_pct']}%")
    print(f"  Path A:           kill_switch={a['kill_switch']}, range={a['score_stats']['range']:.6f}")
    print(f"  Path B (RPDC):    kill_switch={b['kill_switch']}, range={b['score_stats']['range']:.6f}, tier_changes={output['tier_changes_b']}")
    print(f"  Path C (rc proxy): kill_switch={c['kill_switch']}, range={c['score_stats']['range']:.6f}, tier_changes={output['tier_changes_c']}")
    print(f"  Path B verdict:   {b['verdict']}")
    print(f"  May25 gate:       {output['may25_gate']}")
    print(f"  Supabase mutated: {output['supabase_mutated']}")
    print(f"  Scoring changed:  {output['scoring_changed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improvement restored scoring comparison (compare-only)")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_comparison(args.date)
