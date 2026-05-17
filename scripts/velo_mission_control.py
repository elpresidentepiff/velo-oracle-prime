from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ops_service import OpsService
from app.services.safety_sentinel import APPROVED_SHADOW_TARGET, SafetySentinel

VP30_THRESHOLD = 0.30
VP40_THRESHOLD = 0.40
MDS_HIGH_THRESHOLD = 0.50
IMPROVEMENT_HIGH_THRESHOLD = 0.40
IMPROVEMENT_ANY_THRESHOLD = 0.20

# Router lane labels that indicate a qualified selection
ROUTER_QUALIFIED_LANES = {"V1_BASE", "V2_CLASS4", "V6_GOLD_SEAM"}
# candidate_execution_lane values that indicate no router qualification
ROUTER_UNQUALIFIED_LANE_VALUES = {"NO_BET", "ATTACK_LANE_MISS", None, ""}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.stdout.strip()


def _load_run_truth(date: str) -> dict[str, Any] | None:
    path = ROOT / "data" / f"velo_daily_run_truth_{date.replace('-', '_')}.json"
    if not path.exists():
        return None
    try:
        return _read_json(path)
    except Exception:
        return None


def _is_router_qualified(top: dict[str, Any]) -> bool:
    """True if the selection passed at least one router lane."""
    lane = top.get("candidate_execution_lane") or ""
    if lane and lane not in ROUTER_UNQUALIFIED_LANE_VALUES:
        return True
    # Also check per-lane boolean flags when present
    for flag in ("router_v1_shadow_pass", "router_v2_class4_shadow_pass", "router_v6_gold_seam_watchlist"):
        if top.get(flag) is True:
            return True
    return False


def _load_verdict_summary(date: str) -> dict[str, Any]:
    path = ROOT / "data" / f"velo_prime_verdicts_{date.replace('-', '_')}.json"
    if not path.exists():
        return {
            "status": "MISSING",
            "verdict_count": 0,
            "vp30_count": 0,
            "vp40_count": 0,
            "mds_high_count": 0,
            "improvement_high_count": 0,
            "tier_counts": {"A": 0, "B": 0, "C": 0, "X": 0},
            "midprice_advisory": {
                "router_qualified_count": 0,
                "router_suppressed_advisory_count": 0,
                "suppressed_horses": [],
            },
        }
    data = _read_json(path)
    rows = data if isinstance(data, list) else []
    tier_counts = {"A": 0, "B": 0, "C": 0, "X": 0}
    vp30_count = 0
    vp40_count = 0
    mds_high_count = 0
    improvement_high_count = 0
    router_qualified_count = 0
    router_suppressed_advisory_count = 0
    suppressed_horses: list[dict[str, Any]] = []

    for row in rows:
        tier = str(row.get("tier", "X")).upper()
        if tier in tier_counts:
            tier_counts[tier] += 1
        top = row.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0.0)
        if vp >= VP30_THRESHOLD:
            vp30_count += 1
        if vp >= VP40_THRESHOLD:
            vp40_count += 1
        if float(top.get("market_deception_score") or 0.0) > MDS_HIGH_THRESHOLD:
            mds_high_count += 1
        if float(top.get("improvement_score") or 0.0) >= IMPROVEMENT_HIGH_THRESHOLD:
            improvement_high_count += 1
        # Midprice router advisory — advisory flag only, no scoring impact
        qualified = _is_router_qualified(top)
        if qualified:
            router_qualified_count += 1
        else:
            router_suppressed_advisory_count += 1
            suppressed_horses.append({
                "race": f"{row.get('course','?')} {row.get('off_time','?')}",
                "horse": top.get("horse", "?"),
                "vp": round(vp, 3),
                "tier": tier,
                "lane": top.get("candidate_execution_lane", ""),
            })

    return {
        "status": "PASS" if rows else "MISSING",
        "verdict_count": len(rows),
        "vp30_count": vp30_count,
        "vp40_count": vp40_count,
        "mds_high_count": mds_high_count,
        "improvement_high_count": improvement_high_count,
        "tier_counts": tier_counts,
        "midprice_advisory": {
            "router_qualified_count": router_qualified_count,
            "router_suppressed_advisory_count": router_suppressed_advisory_count,
            "suppressed_horses": suppressed_horses[:20],
            "note": "ADVISORY ONLY — no scoring or staking change",
        },
    }


def _load_rp_summary(date: str, total_velo_races: int) -> dict[str, Any]:
    merged_dir = ROOT / "data" / "racecard_merged"
    race_count = 0
    horse_count = 0
    for path in sorted(merged_dir.glob(f"racecard_*_{date}.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        races = data.get("races", {})
        if not isinstance(races, dict):
            continue
        race_count += len(races)
        for race in races.values():
            horse_count += len(race.get("horses", []))
    coverage_pct = round((race_count / total_velo_races) * 100.0, 1) if total_velo_races else 0.0
    status = "PASS" if race_count and coverage_pct >= 90.0 else ("WARN" if race_count else "MISSING")
    return {
        "status": status,
        "races": race_count,
        "horses": horse_count,
        "coverage_pct": coverage_pct,
    }


def _extract_count(pattern: str, text: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _load_cashrun_summary(date: str) -> dict[str, Any]:
    path = ROOT / "data" / f"cashrun_report_{date.replace('-', '_')}.md"
    if not path.exists():
        return {"status": "MISSING", "ready": 0, "watch": 0, "weak": 0, "suppress": 0, "top_watch": []}
    text = path.read_text(encoding="utf-8", errors="replace")
    ready = _extract_count(r"## CASHRUN_READY \((\d+)\)", text)
    watch = _extract_count(r"## CASHRUN_WATCH \((\d+)\)", text)
    weak = _extract_count(r"## WEAK_SIGNAL \((\d+)\)", text)
    suppress = _extract_count(r"## SUPPRESS \((\d+)\)", text)
    top_watch: list[str] = []
    current_section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current_section = line.strip()
            continue
        if current_section.startswith("## CASHRUN_WATCH") and line.startswith("### "):
            top_watch.append(line[4:].split(" - ", 1)[0].strip())
    return {
        "status": "PASS",
        "ready": ready,
        "watch": watch,
        "weak": weak,
        "suppress": suppress,
        "top_watch": top_watch[:10],
    }


def _load_convergence_summary(date: str) -> dict[str, Any]:
    path = ROOT / "data" / "reports" / f"rp_velo_convergence_{date}.json"
    if not path.exists():
        return {
            "status": "MISSING",
            "high_convergence_count": 0,
            "conflict_count": 0,
            "cashrun_velo_overlap_count": 0,
        }
    data = _read_json(path)
    summary = data.get("summary", {})
    watchlist = summary.get("top_operator_watchlist", []) or []
    conflict_count = sum(1 for row in watchlist if row.get("classification") == "CONFLICT")
    cashrun_overlap = sum(
        1 for row in watchlist if str(row.get("cashrun_status", "")).upper() == "CASHRUN_WATCH"
    )
    return {
        "status": "READY",
        "high_convergence_count": int(summary.get("high_convergence_picks", 0)),
        "conflict_count": conflict_count,
        "cashrun_velo_overlap_count": cashrun_overlap,
    }


def _load_sigma_summary(date: str, ops: OpsService) -> dict[str, Any]:
    report_path = ROOT / "data" / "phase4_daily_reports" / f"{date}_daily_eod_report.json"
    if report_path.exists():
        report = _read_json(report_path)
        sigma = (report.get("pipeline") or {}).get("sigma") or {}
        return {
            "status": report.get("overall_status", sigma.get("status", "UNKNOWN")),
            "result_races": int(sigma.get("results_races", 0) or 0),
            "matched_races": int(sigma.get("sigma_audits_written", 0) or 0),
            "audit_rows": int(sigma.get("sigma_audits_written", 0) or 0),
        }

    results_path = ROOT / "data" / f"results_{date.replace('-', '_')}.json"
    result_races = 0
    if results_path.exists():
        try:
            payload = _read_json(results_path)
            races = payload.get("results", []) if isinstance(payload, dict) else payload
            result_races = len(races) if isinstance(races, list) else 0
        except Exception:
            result_races = 0

    audit_rows = 0
    try:
        resp = (
            ops._get_sb()
            .client.table("sigma_audits")
            .select("race_id", count="exact")
            .eq("date", date)
            .execute()
        )
        audit_rows = int(resp.count or 0) if getattr(resp, "count", None) is not None else len(resp.data or [])
    except Exception:
        audit_rows = 0

    if result_races == 0 and audit_rows == 0:
        status = "WAITING"
    elif result_races > 0 and audit_rows == 0:
        status = "PARTIAL"
    else:
        status = "PASS"
    return {
        "status": status,
        "result_races": result_races,
        "matched_races": audit_rows,
        "audit_rows": audit_rows,
    }


def _load_learning_summary(date: str, sigma: dict[str, Any], sentinel_report: dict[str, Any]) -> dict[str, Any]:
    if sigma["status"] in {"WAITING", "SIGMA_RESULTS_NOT_READY"}:
        allowed = False
        reason = "SIGMA_WAITING"
    elif sigma["status"] == "PARTIAL":
        allowed = False
        reason = "SIGMA_PARTIAL_RERUN_REQUIRED"
    elif sentinel_report["classification"] == "BLOCK":
        allowed = False
        reason = "SAFETY_BLOCK"
    else:
        allowed = True
        reason = "READY"
    return {
        "allowed": allowed,
        "reason": reason,
        "approved_shadow_target": APPROVED_SHADOW_TARGET,
        "shadow_race_count": sentinel_report["state"].get("shadow_race_count"),
        "consumed_live_count": sentinel_report["state"].get("consumed_live_count", 0),
    }


def _next_safe_command(
    *,
    date: str,
    sentinel_report: dict[str, Any],
    sigma: dict[str, Any],
    convergence: dict[str, Any],
) -> tuple[str | None, str | None]:
    if sentinel_report["classification"] == "BLOCK":
        return "audit dirty worktree before any live-affecting command", sentinel_report.get("blocked_reason") or "SAFETY_BLOCK"
    if convergence["status"] == "MISSING":
        return f"python scripts/build_rp_velo_convergence_report.py --date {date}", None
    if sigma["status"] == "WAITING":
        return f"wait for results, then: python scripts/run_results_sigma.py --date {date} --sigma-only", None
    if sigma["status"] == "PARTIAL":
        return f"python scripts/run_results_sigma.py --date {date} --sigma-only", "SIGMA_PARTIAL_RERUN_REQUIRED"
    return f"python workers/velo_ops_worker.py daily-eod --date {date} --execute --allow-network --target-state {APPROVED_SHADOW_TARGET}", None


def build_mission_control(date: str) -> dict[str, Any]:
    ops = OpsService(dry_run=True, execute=False)
    sentinel = SafetySentinel()
    sentinel_report = sentinel.evaluate(date=date, command="mission-control", target_state=APPROVED_SHADOW_TARGET)

    run_truth = _load_run_truth(date)
    prediction = _load_verdict_summary(date)
    racing_post = _load_rp_summary(date, prediction["verdict_count"])
    cashrun = _load_cashrun_summary(date)
    convergence = _load_convergence_summary(date)
    sigma = _load_sigma_summary(date, ops)
    learning = _load_learning_summary(date, sigma, sentinel_report)

    next_cmd, blocked_reason = _next_safe_command(
        date=date,
        sentinel_report=sentinel_report,
        sigma=sigma,
        convergence=convergence,
    )

    current_branch = _safe_git(["branch", "--show-current"]) or "UNKNOWN"
    if sentinel_report["classification"] == "BLOCK":
        overall_status = "BLOCKED"
    elif sigma["status"] == "PARTIAL":
        overall_status = "WARN"
    elif sentinel_report["classification"] == "WARN":
        overall_status = "WARN"
    else:
        overall_status = "READY"

    payload = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "next_safe_command": next_cmd,
        "blocked_reason": blocked_reason,
        "latest_prediction_job": (run_truth or {}).get("latest_pipeline_run"),
        "prediction": prediction,
        "racing_post": racing_post,
        "cashrun": cashrun,
        "convergence": convergence,
        "sigma": sigma,
        "learning": learning,
        "state_audit": {
            "live_state_hash": sentinel_report["state"].get("live_state_hash"),
            "live_state_touched": False,
            "cloud_backup_updated_at": (sentinel_report["state"].get("cloud_backup") or {}).get("updated_at"),
            "cloud_backup_touched": False,
        },
        "repo": {
            "dirty": sentinel_report["repo"].get("dirty", False),
            "forbidden_files_modified": sentinel_report["repo"].get("forbidden_files_modified", False),
            "current_branch": current_branch,
            "ops_worker_visible": (ROOT / "workers" / "velo_ops_worker.py").exists(),
        },
        "safety": {
            "classification": sentinel_report["classification"],
            "checks": sentinel_report["checks"],
        },
    }

    out_dir = ROOT / "data" / "mission_control"
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_path = out_dir / f"{date}_mission_control.json"
    latest_path = out_dir / "latest.json"
    encoded = json.dumps(payload, indent=2)
    dated_path.write_text(encoded, encoding="utf-8")
    latest_path.write_text(encoded, encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only VELO Mission Control collector")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = parser.parse_args()

    payload = build_mission_control(args.date)
    pred = payload["prediction"]
    mid = pred.get("midprice_advisory", {})
    print(f"VELO Mission Control - {payload['date']}")
    print(f"Prediction: {pred['status']}  Verdicts={pred['verdict_count']}")
    print(f"  VP≥0.30: {pred['vp30_count']}  VP≥0.40: {pred['vp40_count']}  MDS_HIGH: {pred['mds_high_count']}  IMPROVER: {pred['improvement_high_count']}")
    print(f"  Tier A: {pred['tier_counts']['A']}  Tier B: {pred['tier_counts']['B']}  Tier C: {pred['tier_counts']['C']}")
    print(f"  MIDPRICE ADVISORY — Router-qualified: {mid.get('router_qualified_count',0)}  Suppressed advisory: {mid.get('router_suppressed_advisory_count',0)}")
    print(f"RP Coverage: {payload['racing_post']['status']} ({payload['racing_post']['coverage_pct']}%)")
    print(f"CASHRUN: WATCH={payload['cashrun']['watch']}")
    print(f"Sigma: {payload['sigma']['status']}")
    print(f"Learning: {'ALLOWED' if payload['learning']['allowed'] else 'BLOCKED'}")
    print(f"Approved Shadow: {payload['learning']['approved_shadow_target']}")
    print(f"Live State: {'UNTOUCHED' if not payload['state_audit']['live_state_touched'] else 'TOUCHED'}")
    print(f"Safety: {payload['safety']['classification']}")
    print(f"Next Safe Command: {payload['next_safe_command'] or payload['blocked_reason']}")


if __name__ == "__main__":
    main()
