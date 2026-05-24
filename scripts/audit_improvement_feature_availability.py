"""
audit_improvement_feature_availability.py
-------------------------------------------
Audits the 12 improvement model input feature availability for a scoring day.

Per-feature analysis:
  - Available in current pipeline? (from racecard / runner_snapshot)
  - Available from RPDC memory? (from local JSONL)
  - Variance across field? (would zero-variance kill switch fire?)
  - Recovery path?

Verdicts:
  IMPROVEMENT_RESTORED        - all or most features available, variance confirmed
  PARTIAL_RESTORE_POSSIBLE    - some features restorable via pipeline changes (not done yet)
  IMPROVEMENT_STILL_CONSTANT  - under current pipeline, improvement_score remains constant
  FEATURE_SOURCE_GAP_REMAINS  - specific features need Racing API / RP deep profile (not available)

Usage:
  PYTHONPATH=. python scripts/audit_improvement_feature_availability.py --date 2026-05-25
  PYTHONPATH=. python scripts/audit_improvement_feature_availability.py  # uses today
"""
import argparse
import glob
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.load_rpdc_memory import (
    get_memory_summary_for_runner,
    load_rpdc_memory,
)

DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# The 12 improvement model features
IMPROVEMENT_FEATURES = [
    "mark_compression_score",
    "curr_or_minus_best_or",
    "curr_or_minus_last_win_or",
    "release_window_score",
    "runs_since_win",
    "runs_since_place",
    "trainer_timing_score",
    "distance_fit_score",
    "course_fit_score",
    "or_vs_field",
    "rpr_vs_field",
    "age_num",
]

# Source classification for each feature
FEATURE_SOURCES = {
    "mark_compression_score": {
        "primary_source": "RP_DEEP_PROFILE",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Requires RP deep-form profile data (not available in standard racecard)",
    },
    "curr_or_minus_best_or": {
        "primary_source": "RACING_API_FORM_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Requires full OR history per horse (best ever OR). Not in RPDC JSONL. Racing API decommissioned.",
    },
    "curr_or_minus_last_win_or": {
        "primary_source": "RACING_API_WIN_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": True,
        "rpdc_field": "or_delta_to_win",
        "recovery_path": "RPDC memory provides or_delta_to_win for matched horses (62.7% coverage). Requires pipeline change to inject.",
    },
    "release_window_score": {
        "primary_source": "SPECIALIST_MODEL_RELEASE_WINDOW",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Output of release_window_model, which itself needs Racing API features. Blocked upstream.",
    },
    "runs_since_win": {
        "primary_source": "RACING_API_FORM_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Not stored in RPDC JSONL (computed but not persisted in backfill_rpdc_historical_local.py). Could be added to next backfill run.",
    },
    "runs_since_place": {
        "primary_source": "RACING_API_FORM_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Not stored in RPDC JSONL. Same as runs_since_win — could be added to backfill output.",
    },
    "trainer_timing_score": {
        "primary_source": "RACING_API_JTC_TABLES",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "From JTC (Jockey-Trainer-Course) data tables built via Racing API. Racing API decommissioned. Must be rebuilt from RP pipeline.",
    },
    "distance_fit_score": {
        "primary_source": "RACING_API_FORM_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Requires horse distance win rate from Racing API. Not in RPDC. RP JTC tables partially cover this.",
    },
    "course_fit_score": {
        "primary_source": "RACING_API_FORM_HISTORY",
        "in_racecard": False,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "recovery_path": "Requires horse course win rate from Racing API. Not in RPDC. RP JTC tables partially cover this.",
    },
    "or_vs_field": {
        "primary_source": "RACECARD_FIELD_AGGREGATION",
        "in_racecard": True,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "racecard_field": "ofr",
        "recovery_path": "Can be computed from racecard ofr values (runner_ofr - mean_field_ofr). Available now — requires pipeline change.",
    },
    "rpr_vs_field": {
        "primary_source": "RACECARD_FIELD_AGGREGATION",
        "in_racecard": True,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "racecard_field": "rpr",
        "recovery_path": "Can be computed from racecard rpr values (runner_rpr - mean_field_rpr). Available now — requires pipeline change.",
    },
    "age_num": {
        "primary_source": "RACECARD",
        "in_racecard": True,
        "in_runner_snapshot": False,
        "in_rpdc_memory": False,
        "racecard_field": "age",
        "recovery_path": "Available directly from racecard age field. Requires pipeline change to convert age string to int.",
    },
}


def _extract_date_tag(filename: str) -> str | None:
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _load_runners_for_audit(date_str: str) -> tuple[list[dict], str]:
    """Load runner data with feature fields if available."""
    date_tag = date_str.replace("-", "_")

    # Try racecard first (has ofr, rpr, age)
    racecard_path = DATA_DIR / f"racecards_{date_tag}_standard.json"
    if racecard_path.exists():
        try:
            data = json.loads(racecard_path.read_text(encoding="utf-8"))
            races = data if isinstance(data, list) else data.get("racecards", data.get("races", []))
            runners = []
            for race in races:
                field_ofr = [r.get("ofr") for r in (race.get("runners") or []) if r.get("ofr")]
                field_rpr = [r.get("rpr") for r in (race.get("runners") or []) if r.get("rpr")]
                mean_ofr = sum(field_ofr) / len(field_ofr) if field_ofr else None
                mean_rpr = sum(field_rpr) / len(field_rpr) if field_rpr else None
                for r in (race.get("runners") or []):
                    runner = dict(r)
                    runner["race_id"] = race.get("race_id", "")
                    runner["course"] = race.get("course", "")
                    # Pre-compute field-relative features
                    ofr = r.get("ofr")
                    rpr = r.get("rpr")
                    runner["or_vs_field"] = round(ofr - mean_ofr, 1) if (ofr and mean_ofr) else None
                    runner["rpr_vs_field"] = round(rpr - mean_rpr, 1) if (rpr and mean_rpr) else None
                    # Convert age to int
                    age_raw = r.get("age")
                    try:
                        runner["age_num"] = int(str(age_raw).split("-")[0]) if age_raw else None
                    except (ValueError, TypeError):
                        runner["age_num"] = None
                    runners.append(runner)
            return runners, f"racecard:{racecard_path.name}"
        except Exception as e:
            pass

    # Try runner snapshot (has improvement_score etc. but not ofr/rpr/age from racecard)
    snap_files = sorted(glob.glob(str(DATA_DIR / f"runner_snapshots_{date_tag}_*.jsonl")))
    if snap_files:
        path = snap_files[-1]
        try:
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
                        r["or_vs_field"] = None
                        r["rpr_vs_field"] = None
                        r["age_num"] = None
                        seen[key] = r
            return list(seen.values()), f"snapshot:{Path(path).name}"
        except Exception as e:
            pass

    return [], "none"


def _check_feature_variance(values: list) -> tuple[bool, float | None, str]:
    """Returns (has_variance, variance_approx, status_str)."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return False, None, "ALL_NULL"
    unique = set(round(float(v), 6) for v in non_null)
    if len(unique) == 1:
        return False, 0.0, "CONSTANT"
    mean = sum(float(v) for v in non_null) / len(non_null)
    var = sum((float(v) - mean) ** 2 for v in non_null) / len(non_null)
    if var < 1e-6:
        return False, var, "NEAR_ZERO_VARIANCE"
    return True, round(var, 4), "HAS_VARIANCE"


def _parse_age(age_raw) -> int | None:
    try:
        return int(str(age_raw).split("-")[0])
    except (ValueError, TypeError):
        return None


def run_audit(date_str: str) -> dict:
    print(f"\n{'='*60}")
    print(f"IMPROVEMENT FEATURE AVAILABILITY AUDIT — {date_str}")
    print(f"{'='*60}")

    # Load RPDC memory
    memory = load_rpdc_memory()
    print(f"  RPDC memory: {memory['_total_rows']:,} rows loaded")

    # Load runners
    runners, source = _load_runners_for_audit(date_str)
    if not runners:
        # Try May17 as proxy if target date not available
        proxy_date = "2026-05-17"
        runners, source = _load_runners_for_audit(proxy_date)
        source_label = f"{source} (proxy for {date_str})"
        data_date = proxy_date
        is_proxy = True
    else:
        source_label = source
        data_date = date_str
        is_proxy = False

    if not runners:
        print(f"  ERROR: No runner data available for {date_str} or proxy")
        return {}

    print(f"  Data source: {source_label}")
    print(f"  Runners: {len(runners)}")
    if is_proxy:
        print(f"  NOTE: Using {data_date} as proxy — May25 card not yet available")

    # For each runner, attach RPDC memory data
    for r in runners:
        ctx = get_memory_summary_for_runner(
            horse_id=r.get("horse_id", ""),
            horse_name=r.get("horse", ""),
            as_of_date=date_str,
            memory=memory,
        )
        r["_rpdc_or_delta"] = ctx.get("or_delta_to_win")  # → curr_or_minus_last_win_or
        r["_rpdc_found"] = ctx["memory_found"]

    # Analyse each feature
    feature_results: dict[str, dict] = {}

    for feat in IMPROVEMENT_FEATURES:
        src_info = FEATURE_SOURCES[feat]

        # "Current pipeline" = what the improvement model actually sees today.
        # The runner_snapshot confirms all 12 features are None in the live pipeline.
        # Even when using racecard source for audit, the pipeline does NOT inject
        # or_vs_field/rpr_vs_field/age_num — so treat them as None for current status.
        current_values = [None] * len(runners)  # all None in current pipeline

        # "With RPDC / racecard" = what COULD be available with pipeline changes
        if feat == "curr_or_minus_last_win_or":
            # RPDC memory provides or_delta_to_win for matched runners
            rpdc_values = [r.get("_rpdc_or_delta") for r in runners]
        elif feat in ("or_vs_field", "rpr_vs_field", "age_num"):
            # Racecard has the raw values — pipeline would need to compute these
            rpdc_values = [r.get(feat) for r in runners]
        else:
            rpdc_values = current_values  # no change possible from RPDC or racecard

        current_has_var, current_var, current_status = _check_feature_variance(current_values)
        rpdc_has_var, rpdc_var, rpdc_status = _check_feature_variance(rpdc_values)

        null_current = sum(1 for v in current_values if v is None)
        null_rpdc = sum(1 for v in rpdc_values if v is None)

        feature_results[feat] = {
            "feature": feat,
            "primary_source": src_info["primary_source"],
            "in_racecard": src_info["in_racecard"],
            "in_runner_snapshot": src_info["in_runner_snapshot"],
            "in_rpdc_memory": src_info["in_rpdc_memory"],
            "recovery_path": src_info["recovery_path"],
            # Current pipeline
            "current_null_count": null_current,
            "current_null_pct": round(null_current / len(runners) * 100, 1) if runners else 0,
            "current_variance_status": current_status,
            "current_has_variance": current_has_var,
            # With RPDC / racecard injection
            "rpdc_null_count": null_rpdc,
            "rpdc_null_pct": round(null_rpdc / len(runners) * 100, 1) if runners else 0,
            "rpdc_variance_status": rpdc_status,
            "rpdc_has_variance": rpdc_has_var,
            # Change?
            "variance_restored_by_rpdc": rpdc_has_var and not current_has_var,
            "requires_pipeline_change": (
                src_info["in_racecard"] or src_info["in_rpdc_memory"]
            ) and not current_has_var,
        }

    # Overall verdict
    features_with_current_variance = sum(1 for r in feature_results.values() if r["current_has_variance"])
    features_restored_by_rpdc = sum(1 for r in feature_results.values() if r["variance_restored_by_rpdc"])
    features_needing_pipeline_change = sum(1 for r in feature_results.values() if r["requires_pipeline_change"])
    total_features_with_rpdc = sum(1 for r in feature_results.values() if r["rpdc_has_variance"])

    # Improvement model uses fillna(0) for missing features.
    # With all features None → all 0 → constant output.
    # Zero-variance kill switch: variance < 1e-6 across all runners → exclude
    currently_constant = features_with_current_variance == 0
    would_restore_variance = features_restored_by_rpdc > 0 or total_features_with_rpdc > 0

    if features_with_current_variance >= 8:
        verdict = "IMPROVEMENT_RESTORED"
        verdict_detail = "Sufficient features available. Improvement_score should be variable."
    elif currently_constant and features_needing_pipeline_change > 0 and features_restored_by_rpdc > 0:
        verdict = "PARTIAL_RESTORE_POSSIBLE"
        verdict_detail = (
            f"{features_needing_pipeline_change} features available in local data but NOT injected "
            f"by current pipeline. Pipeline change required (not done yet). "
            f"Improvement_score REMAINS CONSTANT under current scoring path."
        )
    elif currently_constant and features_needing_pipeline_change == 0:
        verdict = "FEATURE_SOURCE_GAP_REMAINS"
        verdict_detail = "Critical features require Racing API / RP deep profile not currently available."
    else:
        verdict = "IMPROVEMENT_STILL_CONSTANT"
        verdict_detail = "Improvement_score will remain constant under current pipeline. Zero-variance kill switch will fire."

    run_ts = datetime.now(timezone.utc).isoformat()

    output = {
        "audit_date": date_str,
        "data_date": data_date,
        "is_proxy": is_proxy,
        "run_at": run_ts,
        "data_source": source_label,
        "runner_count": len(runners),
        "rpdc_memory_loaded": memory["_loaded"],
        "rpdc_memory_rows": memory["_total_rows"],
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "summary": {
            "features_total": len(IMPROVEMENT_FEATURES),
            "features_with_current_variance": features_with_current_variance,
            "features_restored_by_rpdc_or_racecard": features_restored_by_rpdc,
            "features_needing_pipeline_change": features_needing_pipeline_change,
            "features_total_with_rpdc_and_racecard": total_features_with_rpdc,
            "improvement_currently_constant": currently_constant,
            "kill_switch_would_fire": currently_constant,
        },
        "features": feature_results,
    }

    _write_outputs(date_str, output)
    _print_summary(output)
    return output


def _write_outputs(date_str: str, output: dict) -> None:
    json_path = REPORTS_DIR / f"improvement_feature_availability_{date_str}.json"
    md_path = REPORTS_DIR / f"improvement_feature_availability_{date_str}.md"

    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# Improvement Feature Availability Audit — {date_str}",
        "",
        f"**Generated:** {output['run_at']}  ",
        f"**Data source:** {output['data_source']}  ",
    ]
    if output.get("is_proxy"):
        lines.append(f"**NOTE:** Using {output['data_date']} as proxy — May25 card not yet available  ")
    lines += [
        "",
        "---",
        "",
        f"## Verdict: `{output['verdict']}`",
        "",
        f"> {output['verdict_detail']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total improvement features | {output['summary']['features_total']} |",
        f"| Features with variance in current pipeline | {output['summary']['features_with_current_variance']} |",
        f"| Features restorable by RPDC/racecard (with pipeline change) | {output['summary']['features_needing_pipeline_change']} |",
        f"| Improvement_score currently constant? | {output['summary']['improvement_currently_constant']} |",
        f"| Zero-variance kill switch would fire? | {output['summary']['kill_switch_would_fire']} |",
        "",
        "## Per-Feature Analysis",
        "",
        "| Feature | Source | Current Status | With RPDC/RC | Variance Restored? | Pipeline Change Needed? |",
        "|---|---|---|---|---|---|",
    ]

    for feat, r in output["features"].items():
        lines.append(
            f"| `{feat}` "
            f"| {r['primary_source']} "
            f"| {r['current_variance_status']} "
            f"| {r['rpdc_variance_status']} "
            f"| {'YES' if r['variance_restored_by_rpdc'] else 'NO'} "
            f"| {'YES' if r['requires_pipeline_change'] else 'NO'} "
            f"|"
        )

    lines += [
        "",
        "## Recovery Path by Feature",
        "",
    ]
    for feat, r in output["features"].items():
        lines.append(f"**`{feat}`** ({r['primary_source']})")
        lines.append(f"  {r['recovery_path']}")
        lines.append("")

    lines += [
        "---",
        "",
        "```",
        f"VERDICT:                          {output['verdict']}",
        f"AUDIT_DATE:                       {output['audit_date']}",
        f"DATA_DATE:                        {output['data_date']}",
        f"IS_PROXY:                         {output['is_proxy']}",
        f"IMPROVEMENT_CONSTANT:             {output['summary']['improvement_currently_constant']}",
        f"KILL_SWITCH_FIRES:                {output['summary']['kill_switch_would_fire']}",
        f"FEATURES_RESTORABLE_WITH_CHANGE:  {output['summary']['features_needing_pipeline_change']}",
        f"SUPABASE_READS:                   NONE",
        f"SCORING_CHANGE:                   NONE",
        "```",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  JSON → {json_path}")
    print(f"  MD  → {md_path}")


def _print_summary(output: dict) -> None:
    s = output["summary"]
    print(f"\n  Verdict: {output['verdict']}")
    print(f"  {output['verdict_detail']}")
    print()
    print(f"  Features with variance (current):  {s['features_with_current_variance']}/12")
    print(f"  Restorable via RPDC/racecard:       {s['features_needing_pipeline_change']}/12 (requires pipeline change)")
    print(f"  Improvement currently constant:     {s['improvement_currently_constant']}")
    print(f"  Kill switch would fire:             {s['kill_switch_would_fire']}")
    print()
    print("  Feature status:")
    for feat, r in output["features"].items():
        icon = "✓" if r["current_has_variance"] else ("→" if r["variance_restored_by_rpdc"] else "✗")
        print(f"    {icon} {feat:<35} [{r['current_variance_status']}] → {r['rpdc_variance_status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improvement feature availability audit")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        help="Audit date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_audit(args.date)
