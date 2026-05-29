"""
new_build_historical_replay_requirement.py
Generate the historical replay requirement report.

Defines what is required for a valid AUC comparison between Old VELO and New Build.
Does NOT run the replay — it documents the exact conditions needed and checks
whether the required artifacts exist.

Output:
  data/new_build/reports/historical_replay_requirement.json
  data/new_build/reports/historical_replay_requirement.md

Usage:
  python scripts/ops/new_build_historical_replay_requirement.py [--execute]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
NB_MODEL_DIR = ROOT / "data" / "new_build" / "models"
NB_PRED_DIR = ROOT / "data" / "new_build" / "paper_predictions"
SIGMA_DIR = DATA_DIR / "sigma_results"
VELO_VERDICT_GLOB = "velo_prime_verdicts_*.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _check_artifacts() -> dict:
    """Audit existing artifacts to determine what is already available."""
    # Old VELO verdict files
    old_velo_files = sorted(DATA_DIR.glob(VELO_VERDICT_GLOB))
    old_velo_dates = []
    for f in old_velo_files:
        stem = f.stem.replace("velo_prime_verdicts_", "")
        date_str = stem.replace("_", "-")
        old_velo_dates.append(date_str)

    # Sigma result files
    sigma_files = sorted(SIGMA_DIR.glob("sigma_results_*.json")) if SIGMA_DIR.exists() else []
    sigma_dates = []
    for f in sigma_files:
        stem = f.stem.replace("sigma_results_", "")
        sigma_dates.append(stem.replace("_", "-"))

    # New Build prediction files (date-specific)
    nb_pred_files = sorted(NB_PRED_DIR.glob("new_build_predictions_2*.jsonl")) if NB_PRED_DIR.exists() else []
    nb_pred_dates = []
    for f in nb_pred_files:
        stem = f.stem.replace("new_build_predictions_", "")
        nb_pred_dates.append(stem.replace("_", "-"))

    # Champion registry
    registry_path = NB_MODEL_DIR / "champion" / "champion_registry.json"
    registry = _load_json(registry_path, {})

    # Overlap: dates with both Old VELO verdicts AND sigma results
    overlap_dates = sorted(set(old_velo_dates) & set(sigma_dates))

    # Dates with Old VELO but no NB predictions (replay needed)
    velo_only_dates = sorted(set(old_velo_dates) - set(nb_pred_dates))

    return {
        "old_velo_verdict_files": len(old_velo_files),
        "old_velo_dates": old_velo_dates,
        "sigma_result_files": len(sigma_files),
        "sigma_dates": sigma_dates,
        "nb_prediction_files": len(nb_pred_files),
        "nb_prediction_dates": nb_pred_dates,
        "champion_registry_present": registry_path.exists(),
        "champion_version": registry.get("champion_version", "UNKNOWN"),
        "overlap_dates_both_velo_and_sigma": overlap_dates,
        "velo_only_dates_no_nb_predictions": velo_only_dates,
    }


def build_report(execute: bool = False) -> dict:
    artifacts = _check_artifacts()
    overlap = artifacts["overlap_dates_both_velo_and_sigma"]

    # Determine readiness classification
    if not artifacts["old_velo_verdict_files"]:
        classification = "OLD_VELO_PROBABILITIES_NOT_FOUND"
    elif not artifacts["sigma_result_files"]:
        classification = "SIGMA_RESULTS_NOT_FOUND"
    elif not overlap:
        classification = "NO_OVERLAP_DATES_AVAILABLE"
    elif artifacts["velo_only_dates_no_nb_predictions"]:
        classification = "PARTIAL_OVERLAP_NB_REPLAY_REQUIRED"
    else:
        classification = "REPLAY_FEASIBLE_ON_OVERLAP_DATES"

    report = {
        "generated_at": _utc_now(),
        "classification": classification,
        "auc_comparison_status": "OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY",
        "auc_note": (
            "AUC comparison requires identical race/runner/target populations, "
            "same chronological split, and both model probabilities on the same rows. "
            "Single-day strike rate is indicative only."
        ),
        "artifact_audit": artifacts,
        "requirements": {
            "required_for_valid_auc_comparison": [
                {
                    "id": "REQ-1",
                    "name": "Same race population",
                    "description": (
                        "Both models must be evaluated on exactly the same set of race_ids. "
                        "Old VELO may cover different races than New Build if one system missed "
                        "certain fixture types (e.g., AW vs turf filtering differences)."
                    ),
                    "status": "NOT_VERIFIED" if not overlap else "PARTIAL",
                },
                {
                    "id": "REQ-2",
                    "name": "Same runner population",
                    "description": (
                        "Both models must include the same horses per race. If Old VELO "
                        "excluded non-runners post-declaration while New Build included them "
                        "at capture time, the populations differ."
                    ),
                    "status": "NOT_VERIFIED",
                },
                {
                    "id": "REQ-3",
                    "name": "Old VELO probability extraction",
                    "description": (
                        "Old VELO top-pick probabilities (velo_prime_prob from velo_prime_verdicts) "
                        "are available for each runner, not just the top pick. "
                        "Currently only top pick is stored — full runner-level distribution needed."
                    ),
                    "status": "PARTIAL_TOP_PICK_ONLY",
                    "blocker": (
                        "Old VELO stores only top.horse and top.velo_prime_prob per race. "
                        "Full runner-level probability distribution not captured in verdict files. "
                        "AUC requires probability per runner, not just the winner pick."
                    ),
                },
                {
                    "id": "REQ-4",
                    "name": "New Build historical re-score",
                    "description": (
                        "New Build must be re-scored on historical race populations using the "
                        "same champion model (Challenger_V1) with training data cutoff respected. "
                        "Cannot use current-card feed scores for historical races — model must "
                        "not have seen the outcome when scoring."
                    ),
                    "status": "NOT_STARTED",
                    "action": "Run new_build_two_lane_score.py --date HISTORICAL_DATE for each overlap date",
                },
                {
                    "id": "REQ-5",
                    "name": "Identical target variable",
                    "description": (
                        "Both models must be evaluated against the same binary target: "
                        "did the top-ranked horse win the race? (win=1, otherwise=0). "
                        "Sigma results must be matched by race_id and horse name."
                    ),
                    "status": "SIGMA_FORMAT_COMPATIBLE" if artifacts["sigma_result_files"] else "NO_SIGMA_DATA",
                },
                {
                    "id": "REQ-6",
                    "name": "Chronological split respected",
                    "description": (
                        "Replay must use only dates AFTER the model training cutoff (2025 test split). "
                        "New Build Challenger_V1 trained on <= 2023, validated 2024, tested 2025. "
                        "Replay on 2026 live dates is valid. Replay on 2024/2025 risks train-test contamination "
                        "for Old VELO if it was trained on overlapping data."
                    ),
                    "status": "2026_DATES_ARE_SAFE",
                },
                {
                    "id": "REQ-7",
                    "name": "Sufficient sample size",
                    "description": (
                        "Minimum n=200 closed races for statistically meaningful AUC comparison (95% CI). "
                        "Single-day or small-n comparisons are indicative only."
                    ),
                    "status": (
                        f"INSUFFICIENT_N_{len(overlap)}_OVERLAP_DATES" if len(overlap) < 30
                        else "SUFFICIENT"
                    ),
                    "current_overlap_dates": len(overlap),
                    "target": "30+ race days (approx 200+ races)",
                },
            ],
            "critical_blocker": (
                "REQ-3: Old VELO runner-level probability distribution is not captured. "
                "Only the top pick probability exists in verdict files. "
                "AUC requires P(win) for every runner in every race. "
                "Until Old VELO produces runner-level scores, true AUC comparison is impossible."
            ),
            "feasible_comparison_today": [
                "Top-1 strike rate comparison (Old VELO top pick vs New Build rank-1 pick) — indicative only",
                "Alignment rate (is Old VELO top pick inside New Build top-3?)",
                "OR baseline comparison (highest official_rating pick as naive baseline)",
                "Outcome evaluation when sigma results are available",
            ],
        },
        "action_plan": [
            {
                "step": 1,
                "action": "Accumulate sigma results for May-June 2026 race days",
                "command": "python scripts/run_results_sigma.py --date YYYY-MM-DD",
                "gates": "Need 30+ race days with closed outcomes",
            },
            {
                "step": 2,
                "action": "Re-run New Build scorer on each historical date with sigma results",
                "command": "python scripts/ops/new_build_two_lane_score.py --date YYYY-MM-DD --execute",
                "gates": "Must use same Challenger_V1 champion (registry version matches)",
            },
            {
                "step": 3,
                "action": "Assess Old VELO runner-level probability availability",
                "description": (
                    "Check if velo_prime_verdicts files contain per-runner probs or only top pick. "
                    "If only top pick: AUC is not computable. SR comparison remains the primary metric."
                ),
                "current_status": "PARTIAL_TOP_PICK_ONLY",
            },
            {
                "step": 4,
                "action": "Run comparison evaluator across accumulated dates",
                "command": "python scripts/ops/new_build_old_velo_comparison.py --date YYYY-MM-DD --execute",
                "gates": "Run for each date with both Old VELO verdict AND sigma results",
            },
            {
                "step": 5,
                "action": "Aggregate multi-date SR/alignment statistics",
                "description": "Compute rolling SR for Old VELO vs New Build vs OR baseline across all evaluated dates",
                "gates": "n >= 200 races before drawing promotion conclusions",
            },
        ],
        "promotion_gate": {
            "description": (
                "New Build is not promoted to Old VELO scoring until ALL of the following are met:"
            ),
            "gates": [
                "n >= 200 closed races evaluated",
                "New Build SR statistically above OR baseline (p < 0.05)",
                "New Build SR >= Old VELO SR on identical race population (or Old VELO absent)",
                "RPR violations = 0 confirmed across all evaluated dates",
                "JTC-D sidecar rebuilt with rolling date-bounded lookback (no leakage)",
                "Intent coverage gate (>= 80%) achieved on at least 5 consecutive race days",
                "Operator explicit promotion decision — no automatic promotion",
            ],
            "current_status": "NOT_READY",
            "estimated_earliest": "After 30+ live race days with closed outcomes (approx July 2026)",
        },
    }

    if execute:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_DIR / "historical_replay_requirement.json"
        md_path = REPORT_DIR / "historical_replay_requirement.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(_markdown(report), encoding="utf-8")
        print(f"Written: {json_path}")
        print(f"Written: {md_path}")

    return report


def _markdown(r: dict) -> str:
    art = r["artifact_audit"]
    reqs = r["requirements"]["required_for_valid_auc_comparison"]
    lines = [
        "# Historical Replay Requirement — New Build vs Old VELO AUC Comparison",
        f"Generated: {r['generated_at']}",
        "",
        f"**Classification:** `{r['classification']}`",
        f"**AUC Status:** `{r['auc_comparison_status']}`",
        "",
        f"> {r['auc_note']}",
        "",
        "## Artifact Audit",
        "| Artifact | Count | Dates |",
        "|---|---|---|",
        f"| Old VELO verdict files | {art['old_velo_verdict_files']} | {', '.join(art['old_velo_dates'][-5:]) or 'none'} |",
        f"| Sigma result files | {art['sigma_result_files']} | {', '.join(art['sigma_dates'][-5:]) or 'none'} |",
        f"| NB prediction files | {art['nb_prediction_files']} | {', '.join(art['nb_prediction_dates'][-5:]) or 'none'} |",
        f"| Overlap dates (VELO + sigma) | {len(art['overlap_dates_both_velo_and_sigma'])} | {', '.join(art['overlap_dates_both_velo_and_sigma']) or 'none'} |",
        f"| Champion version | — | {art['champion_version']} |",
        "",
        "## Requirements for Valid AUC Comparison",
        "| ID | Requirement | Status |",
        "|---|---|---|",
    ]
    for req in reqs:
        lines.append(f"| {req['id']} | {req['name']} | `{req['status']}` |")

    lines += [
        "",
        "## Critical Blocker",
        f"> {r['requirements']['critical_blocker']}",
        "",
        "## What Can Be Compared Today",
    ]
    for item in r["requirements"]["feasible_comparison_today"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Action Plan",
        "| Step | Action | Command |",
        "|---|---|---|",
    ]
    for s in r["action_plan"]:
        cmd = s.get("command", s.get("description", ""))[:80]
        lines.append(f"| {s['step']} | {s['action']} | `{cmd}` |")

    pg = r["promotion_gate"]
    lines += [
        "",
        "## Promotion Gate",
        f"**Status:** `{pg['current_status']}`",
        f"**Estimated earliest:** {pg['estimated_earliest']}",
        "",
        "All of the following must be met before New Build is integrated into Old VELO scoring:",
        "",
    ]
    for g in pg["gates"]:
        lines.append(f"- [ ] {g}")

    lines += [
        "",
        "## Boundaries",
        "- This report is read-only. No Old VELO model or scoring pipeline changes.",
        "- No Telegram, staking, or live table writes.",
        "- AUC comparison remains `NOT_COMPARABLE` until REQ-3 (runner-level probs) is resolved.",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    report = build_report(execute=args.execute)
    print(f"Classification: {report['classification']}")
    print(f"AUC status: {report['auc_comparison_status']}")
    art = report["artifact_audit"]
    print(f"Old VELO dates: {len(art['old_velo_dates'])}, Sigma dates: {len(art['sigma_dates'])}")
    print(f"Overlap dates: {len(art['overlap_dates_both_velo_and_sigma'])}")
    print(f"Critical blocker: {report['requirements']['critical_blocker'][:80]}...")


if __name__ == "__main__":
    main()
