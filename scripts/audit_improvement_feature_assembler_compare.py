"""
audit_improvement_feature_assembler_compare.py
------------------------------------------------
Compare-only improvement model feature assembly.

Builds the improvement model input matrix from available local sources:
  1. RP standard racecard JSON (OFR/RPR/age → or_vs_field, rpr_vs_field, age_num)
  2. RPDC memory JSONL (or_delta_to_win → curr_or_minus_last_win_or)
  3. Runner snapshot JSONL (existing scores, race/horse metadata)

Hard rules:
  - NO official prediction writes
  - NO Supabase writes
  - NO scoring publication
  - NO Telegram
  - NO dashboard publish
  - Output reports only

Compares three paths:
  PATH A: current pipeline (DEFAULTS only, no OFR/RPR/age)
  PATH B: RPDC features injected (curr_or_minus_last_win_or from JSONL)
  PATH C: racecard features injected (or_vs_field, rpr_vs_field, age_num from standard racecard)

For May24/25: no standard racecard → Path C uses most recent available racecard as proxy.

Outputs:
  data/reports/improvement_feature_assembler_compare_latest.json
  data/reports/improvement_feature_assembler_compare_latest.md

Usage:
  PYTHONPATH=. python scripts/audit_improvement_feature_assembler_compare.py --date 2026-05-25
  PYTHONPATH=. python scripts/audit_improvement_feature_assembler_compare.py  # uses today
"""
from __future__ import annotations

import argparse
import glob
import json
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from scripts.ops.load_rpdc_memory import (
    _normalise_name,
    get_memory_summary_for_runner,
    load_rpdc_memory,
)
from app.services.v17_feature_extractor import DEFAULTS

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

# DEFAULTS for each improvement feature (from v17_feature_extractor)
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


def _load_model():
    if not MODEL_PATH.exists():
        return None, None
    model = joblib.load(MODEL_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    return model, meta


def _score_batch(model, feature_rows: list[dict]) -> list[float]:
    df = pd.DataFrame(feature_rows)
    for feat in IMPROVEMENT_FEATURES:
        if feat not in df.columns:
            df[feat] = FEATURE_DEFAULTS.get(feat, 0.0)
    X = df[IMPROVEMENT_FEATURES].fillna(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return list(model.predict_proba(X)[:, 1])


def _kill_switch_fires(scores: list[float], threshold: float = 1e-6) -> bool:
    if not scores:
        return True
    valid = [s for s in scores if s is not None]
    if not valid:
        return True
    return (max(valid) - min(valid)) < threshold


def _load_runners_from_snapshot(date_str: str) -> tuple[list[dict], str]:
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


def _load_standard_racecard(date_str: str) -> tuple[dict[str, dict], str]:
    """Load standard racecard for date. Returns {horse_id → runner_info}, source."""
    date_tag = date_str.replace("-", "_")
    path = DATA_DIR / f"racecards_{date_tag}_standard.json"
    if path.exists():
        return _parse_racecard(path), f"racecard:{path.name}"
    return {}, ""


def _find_most_recent_racecard() -> tuple[dict[str, dict], str]:
    """Find most recent standard racecard available."""
    files = sorted(glob.glob(str(DATA_DIR / "racecards_*_standard.json")))
    if not files:
        return {}, ""
    path = Path(files[-1])
    return _parse_racecard(path), f"racecard_proxy:{path.name}"


def _parse_racecard(path: Path) -> dict[str, dict]:
    """Parse standard racecard into {horse_id → {ofr, rpr, age, race_ofr_vals, race_rpr_vals}}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    races = data if isinstance(data, list) else data.get("racecards", data.get("races", []))
    result: dict[str, dict] = {}

    for race in races:
        runners = race.get("runners") or []
        # Compute field averages for this race
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

            or_vs_field = (ofr - avg_ofr) if ofr is not None else 0.0
            rpr_vs_field = (rpr - avg_rpr) if rpr is not None else 0.0

            entry = {
                "horse_id": hid,
                "horse": hname,
                "ofr": ofr,
                "rpr": rpr,
                "age": age,
                "or_vs_field": or_vs_field,
                "rpr_vs_field": rpr_vs_field,
                "age_num": age if age is not None else 0.0,
                "avg_ofr": avg_ofr,
                "avg_rpr": avg_rpr,
            }
            if hid:
                result[hid] = entry
            # Also index by normalised name for cross-date matching
            nname = _normalise_name(hname)
            if nname:
                result[f"__name__{nname}"] = entry

    return result


def _lookup_racecard(horse_id: str, horse_name: str, racecard: dict) -> dict | None:
    """Look up a horse in the racecard index by ID or normalised name."""
    if horse_id and horse_id in racecard:
        return racecard[horse_id]
    nname = _normalise_name(horse_name)
    if nname and f"__name__{nname}" in racecard:
        return racecard[f"__name__{nname}"]
    # Try rp_slug extraction
    if horse_id and horse_id.startswith("rp_"):
        parts = horse_id.split("_", 2)
        if len(parts) >= 3:
            slug = parts[2].replace("_", " ").lower()
            if f"__name__{slug}" in racecard:
                return racecard[f"__name__{slug}"]
    return None


def _build_feature_row(path: str, runner: dict, racecard_entry: dict | None, rpdc_ctx: dict) -> dict:
    """Build a feature row for a single runner for one path."""
    row = dict(FEATURE_DEFAULTS)  # start with defaults

    if path in ("C", "C+RPDC") and racecard_entry:
        row["or_vs_field"] = racecard_entry.get("or_vs_field", 0.0)
        row["rpr_vs_field"] = racecard_entry.get("rpr_vs_field", 0.0)
        row["age_num"] = racecard_entry.get("age_num", 0.0)

    if path in ("B", "C+RPDC") and rpdc_ctx.get("memory_found"):
        delta = rpdc_ctx.get("curr_or_minus_last_win_or")
        if delta is not None:
            row["curr_or_minus_last_win_or"] = float(delta)

    return row


def run_assembler(date_str: str) -> dict:
    print(f"\n{'='*60}")
    print(f"IMPROVEMENT FEATURE ASSEMBLER — {date_str}")
    print(f"  (Compare-only — NO scoring changes, NO writes)")
    print(f"{'='*60}")

    model, meta = _load_model()
    if model is None:
        print("  ERROR: improvement_model.pkl not found")
        return {"status": "MODEL_NOT_FOUND"}

    # Load runners
    runners, snap_source = _load_runners_from_snapshot(date_str)
    is_proxy = False
    data_date = date_str

    if not runners:
        print(f"  No snapshot for {date_str} — using May24 proxy")
        runners, snap_source = _load_runners_from_snapshot("2026-05-24")
        is_proxy = True
        data_date = "2026-05-24"

    if not runners:
        return {"status": "NO_RUNNER_DATA"}

    print(f"  Runner source: {snap_source} ({'proxy' if is_proxy else 'actual'})")
    print(f"  Runners: {len(runners)}")

    # Load RPDC memory
    memory = load_rpdc_memory()
    print(f"  RPDC memory: {memory['_total_rows']:,} rows")

    # Load standard racecard for the scoring date
    racecard, rc_source = _load_standard_racecard(date_str)
    if not racecard and is_proxy:
        racecard, rc_source = _load_standard_racecard(data_date)
    racecard_is_proxy = False
    if not racecard:
        print(f"  No standard racecard for {data_date} — finding most recent...")
        racecard, rc_source = _find_most_recent_racecard()
        racecard_is_proxy = True

    print(f"  Racecard source: {rc_source}{'  *** CROSS-DATE PROXY — OR/RPR/age values are from different card ***' if racecard_is_proxy else ''}")

    # Process each runner through all paths
    path_a_rows, path_b_rows, path_c_rows = [], [], []
    rpdc_match_count = 0
    racecard_match_count = 0
    runner_details = []

    for runner in runners:
        horse_id = runner.get("horse_id", "")
        horse_name = runner.get("horse", "") or runner.get("top_pick_name", "")

        # RPDC lookup
        rpdc_ctx = get_memory_summary_for_runner(
            horse_id=horse_id,
            horse_name=horse_name,
            as_of_date=date_str,
            memory=memory,
        )
        if rpdc_ctx["memory_found"]:
            rpdc_match_count += 1

        # Racecard lookup
        rc_entry = _lookup_racecard(horse_id, horse_name, racecard)
        rc_matched = rc_entry is not None
        if rc_matched:
            racecard_match_count += 1

        # Build feature rows for each path
        row_a = _build_feature_row("A", runner, None, {})
        row_b = _build_feature_row("B", runner, None, rpdc_ctx)
        row_c = _build_feature_row("C+RPDC", runner, rc_entry, rpdc_ctx)

        path_a_rows.append(row_a)
        path_b_rows.append(row_b)
        path_c_rows.append(row_c)

        runner_details.append({
            "horse_id": horse_id,
            "horse": horse_name,
            "race_id": runner.get("race_id", ""),
            "rpdc_matched": rpdc_ctx["memory_found"],
            "rpdc_curr_or_minus_last_win_or": rpdc_ctx.get("curr_or_minus_last_win_or"),
            "racecard_matched": rc_matched,
            "racecard_is_cross_date": racecard_is_proxy,
            "or_vs_field": rc_entry["or_vs_field"] if rc_matched else None,
            "rpr_vs_field": rc_entry["rpr_vs_field"] if rc_matched else None,
            "age_num": rc_entry["age_num"] if rc_matched else None,
        })

    # Score all paths
    scores_a = _score_batch(model, path_a_rows)
    scores_b = _score_batch(model, path_b_rows)
    scores_c = _score_batch(model, path_c_rows)

    def _stats(scores: list[float]) -> dict:
        if not scores:
            return {"min": None, "max": None, "mean": None, "std": None, "range": None}
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

    kill_a = _kill_switch_fires(scores_a)
    kill_b = _kill_switch_fires(scores_b)
    kill_c = _kill_switch_fires(scores_c)

    # Feature null rates (what's at default vs real)
    def _null_rate(rows: list[dict], feat: str) -> float:
        default_val = FEATURE_DEFAULTS.get(feat, 0.0)
        at_default = sum(1 for r in rows if abs(r.get(feat, default_val) - default_val) < 1e-6)
        return round(at_default / len(rows) * 100, 1) if rows else 100.0

    feature_null_rates = {}
    for feat in IMPROVEMENT_FEATURES:
        feature_null_rates[feat] = {
            "path_a": _null_rate(path_a_rows, feat),
            "path_b": _null_rate(path_b_rows, feat),
            "path_c": _null_rate(path_c_rows, feat),
        }

    rpdc_match_rate = round(rpdc_match_count / len(runners) * 100, 1) if runners else 0.0
    rc_match_rate = round(racecard_match_count / len(runners) * 100, 1) if runners else 0.0

    # Verdict
    if not kill_c and rc_match_rate >= 70:
        overall_verdict = "PARTIAL_RESTORE_POSSIBLE"
        verdict_detail = (
            f"Racecard-sourced or_vs_field/rpr_vs_field/age_num restores variance "
            f"(range={stats_c['range']:.4f}). Kill switch does NOT fire on Path C. "
            f"Racecard match rate: {rc_match_rate}%. "
            f"{'Cross-date proxy used — real card needed for production.' if racecard_is_proxy else 'Same-date racecard available.'}"
        )
    elif not kill_c:
        overall_verdict = "PARTIAL_RESTORE_POSSIBLE_LOW_COVERAGE"
        verdict_detail = f"Path C kills switch does not fire but racecard match rate is {rc_match_rate}% (low)."
    elif not kill_b:
        overall_verdict = "RPDC_PARTIAL_ONLY"
        verdict_detail = f"RPDC injection alone produces variance (range={stats_b['range']:.4f}) but kill switch threshold is tight."
    else:
        overall_verdict = "FEATURE_GAP_REMAINS"
        verdict_detail = (
            "Kill switch fires on all paths. Racecard OFR/RPR/age data not available for this card. "
            "improvement_score cannot be restored without a standard racecard source."
        )

    racecard_needed = racecard_is_proxy or not racecard

    run_ts = datetime.now(timezone.utc).isoformat()
    output = {
        "audit_date": date_str,
        "data_date": data_date,
        "is_proxy": is_proxy,
        "racecard_is_cross_date_proxy": racecard_is_proxy,
        "run_at": run_ts,
        "runner_source": snap_source,
        "racecard_source": rc_source,
        "runner_count": len(runners),
        "rpdc_matched": rpdc_match_count,
        "rpdc_match_rate_pct": rpdc_match_rate,
        "racecard_matched": racecard_match_count,
        "racecard_match_rate_pct": rc_match_rate,
        "racecard_source_needed_for_production": racecard_needed,
        "paths": {
            "A": {
                "description": "Current pipeline — DEFAULTS only, no OFR/RPR/age",
                "features_restored": 0,
                "score_stats": stats_a,
                "kill_switch_fires": kill_a,
            },
            "B": {
                "description": "RPDC injection — curr_or_minus_last_win_or from JSONL",
                "features_restored": 1,
                "score_stats": stats_b,
                "kill_switch_fires": kill_b,
            },
            "C+RPDC": {
                "description": "Racecard + RPDC — or_vs_field, rpr_vs_field, age_num, curr_or_minus_last_win_or",
                "features_restored": 4,
                "score_stats": stats_c,
                "kill_switch_fires": kill_c,
                "note": "CROSS-DATE PROXY — racecard OFR/RPR values from different scoring day" if racecard_is_proxy else "Same-date racecard",
            },
        },
        "feature_at_default_rate": feature_null_rates,
        "verdict": overall_verdict,
        "verdict_detail": verdict_detail,
        "racecard_source_needed_detail": (
            "Standard racecard with OFR/RPR/age required. RP F_0010 PDF does not contain ratings. "
            "Last available: data/racecards_2026_05_17_standard.json (Racing API cached). "
            "Restoration options: Racing API resubscription, RP premium data API, or alternative ratings source."
        ) if racecard_needed else None,
        "runner_detail": runner_details,
    }

    _write_outputs(output)
    _print_summary(output)
    return output


def _write_outputs(output: dict) -> None:
    json_path = REPORTS_DIR / "improvement_feature_assembler_compare_latest.json"
    md_path   = REPORTS_DIR / "improvement_feature_assembler_compare_latest.md"

    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    paths = output["paths"]
    a, b, c = paths["A"], paths["B"], paths["C+RPDC"]

    proxy_banner = ""
    if output.get("racecard_is_cross_date_proxy"):
        proxy_banner = "\n> **WARNING — Path C uses cross-date racecard proxy.** OFR/RPR/age values are from a different scoring day. This demonstrates what variance WOULD look like with real racecard data, not actual May25 values.\n"

    lines = [
        f"# Improvement Feature Assembler — {output['audit_date']}",
        "",
        f"**Generated:** {output['run_at']}  ",
        f"**Runner source:** {output['runner_source']}  ",
        f"**Racecard source:** {output['racecard_source']}  ",
        proxy_banner,
        "---",
        "",
        f"## Verdict: `{output['verdict']}`",
        "",
        f"> {output['verdict_detail']}",
        "",
        "## Path Comparison",
        "",
        "| Path | Description | Features restored | Kill switch | Score range | Mean |",
        "|---|---|---|---|---|---|",
        f"| A (current) | DEFAULTS only | 0 | {'FIRES' if a['kill_switch_fires'] else 'OK'} | {a['score_stats']['range']} | {a['score_stats']['mean']} |",
        f"| B (RPDC) | + curr_or_minus_last_win_or | 1 | {'FIRES' if b['kill_switch_fires'] else 'OK'} | {b['score_stats']['range']} | {b['score_stats']['mean']} |",
        f"| C+RPDC (racecard) | + or_vs_field, rpr_vs_field, age_num | 4 | {'FIRES' if c['kill_switch_fires'] else 'OK'} | {c['score_stats']['range']} | {c['score_stats']['mean']} |",
        "",
        "## Coverage",
        "",
        f"| Source | Matched | Rate |",
        "|---|---|---|",
        f"| RPDC memory (JSONL) | {output['rpdc_matched']} | {output['rpdc_match_rate_pct']}% |",
        f"| Standard racecard (OFR/RPR/age) | {output['racecard_matched']} | {output['racecard_match_rate_pct']}% |",
        "",
        "## Feature at-default rates (100% = all runners at neutral default)",
        "",
        "| Feature | Default | Path A | Path B | Path C+RPDC |",
        "|---|---|---|---|---|",
    ]
    for feat in IMPROVEMENT_FEATURES:
        d = output["feature_at_default_rate"][feat]
        default_val = FEATURE_DEFAULTS.get(feat, 0.0)
        lines.append(f"| `{feat}` | {default_val} | {d['path_a']}% | {d['path_b']}% | {d['path_c']}% |")

    lines += [
        "",
        "```",
        f"AUDIT_DATE:          {output['audit_date']}",
        f"RACECARD_PROXY:      {output['racecard_is_cross_date_proxy']}",
        f"RPDC_MATCH_RATE:     {output['rpdc_match_rate_pct']}%",
        f"RACECARD_MATCH_RATE: {output['racecard_match_rate_pct']}%",
        f"PATH_A_KILL_SWITCH:  {a['kill_switch_fires']}",
        f"PATH_B_KILL_SWITCH:  {b['kill_switch_fires']}",
        f"PATH_C_KILL_SWITCH:  {c['kill_switch_fires']}",
        f"VERDICT:             {output['verdict']}",
        "SUPABASE_WRITES:     NONE",
        "SCORING_CHANGE:      NONE",
        "```",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  JSON → {json_path}")
    print(f"  MD  → {md_path}")


def _print_summary(output: dict) -> None:
    paths = output["paths"]
    a, b, c = paths["A"], paths["B"], paths["C+RPDC"]
    print(f"\n  Runners:          {output['runner_count']}")
    print(f"  RPDC match rate:  {output['rpdc_match_rate_pct']}%")
    print(f"  Racecard match:   {output['racecard_match_rate_pct']}%{'  (cross-date proxy)' if output['racecard_is_cross_date_proxy'] else ''}")
    print(f"  Path A (current): kill_switch={a['kill_switch_fires']}, range={a['score_stats']['range']:.4f}")
    print(f"  Path B (RPDC):    kill_switch={b['kill_switch_fires']}, range={b['score_stats']['range']:.4f}")
    print(f"  Path C+RPDC:      kill_switch={c['kill_switch_fires']}, range={c['score_stats']['range']:.4f}")
    print(f"  Verdict:          {output['verdict']}")
    if output.get("racecard_source_needed_for_production"):
        print(f"  *** RACECARD SOURCE REQUIRED for production: OFR/RPR/age not in RP F_0010 PDF ***")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improvement feature assembler (compare-only)")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_assembler(args.date)
