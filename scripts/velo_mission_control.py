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
SP_MIDPRICE_LOW = 3.0
SP_MIDPRICE_HIGH = 8.5
TRAINING_SAFE_BASELINE = 1310
TRAINING_2K_TARGET = 2000

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

    lane_candidates: dict[str, list[dict[str, Any]]] = {
        "MDS_HIGH_LANE": [],
        "IMPROVER_LANE": [],
        "VP40_LANE": [],
        "VP40_TIER_A_LANE": [],
        "SHORTFAV_VP30": [],
        "MIDPRICE_ROUTER_QUAL": [],
        "MIDPRICE_SUPPRESS": [],
    }

    for row in rows:
        tier = str(row.get("tier", "X")).upper()
        if tier in tier_counts:
            tier_counts[tier] += 1
        top = row.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0.0)
        mds = float(top.get("market_deception_score") or 0.0)
        imp = float(top.get("improvement_score") or 0.0)
        sp = float(top.get("sp_decimal") or 0.0)
        horse = top.get("horse", "?")
        race_label = f"{row.get('course','?')} {row.get('off_time','?')}"
        candidate_base = {"horse": horse, "race": race_label, "vp": round(vp, 3)}

        if vp >= VP30_THRESHOLD:
            vp30_count += 1
        if vp >= VP40_THRESHOLD:
            vp40_count += 1
            lane_candidates["VP40_LANE"].append({**candidate_base, "tier": tier})
            if tier == "A":
                lane_candidates["VP40_TIER_A_LANE"].append({**candidate_base, "tier": tier})
        if mds > MDS_HIGH_THRESHOLD:
            mds_high_count += 1
            if vp >= VP30_THRESHOLD:
                lane_candidates["MDS_HIGH_LANE"].append({**candidate_base, "mds": round(mds, 3)})
        if imp >= IMPROVEMENT_HIGH_THRESHOLD:
            improvement_high_count += 1
            if vp >= VP30_THRESHOLD:
                lane_candidates["IMPROVER_LANE"].append({**candidate_base, "imp": round(imp, 3)})
        if sp > 0 and sp < SP_MIDPRICE_LOW and vp >= VP30_THRESHOLD:
            lane_candidates["SHORTFAV_VP30"].append({**candidate_base, "sp": sp})

        # Midprice router advisory — advisory flag only, no scoring impact
        qualified = _is_router_qualified(top)
        if qualified:
            router_qualified_count += 1
            if SP_MIDPRICE_LOW <= sp <= SP_MIDPRICE_HIGH:
                lane_candidates["MIDPRICE_ROUTER_QUAL"].append({**candidate_base, "sp": sp})
        else:
            router_suppressed_advisory_count += 1
            if SP_MIDPRICE_LOW <= sp <= SP_MIDPRICE_HIGH:
                lane_candidates["MIDPRICE_SUPPRESS"].append({**candidate_base, "sp": sp})
            suppressed_horses.append({
                "race": race_label,
                "horse": horse,
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
        "named_lanes": {
            lane: {"count": len(cands), "horses": cands[:10]}
            for lane, cands in lane_candidates.items()
        },
        "midprice_advisory": {
            "router_qualified_count": router_qualified_count,
            "router_suppressed_advisory_count": router_suppressed_advisory_count,
            "suppressed_horses": suppressed_horses[:20],
            "note": "ADVISORY ONLY — no scoring or staking change",
        },
    }


def _load_named_lane_corpus() -> dict[str, dict[str, Any]]:
    """Load cumulative corpus n/SR per named lane from latest lane stats report."""
    path = ROOT / "data" / "reports" / "named_signal_lanes_latest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {lane["lane"]: lane for lane in data.get("lanes", [])}
    except Exception:
        return {}


def _load_lane_outcome_summary() -> dict[str, Any]:
    """Load lane outcome tracker and promotion gate report for Mission Control display."""
    outcome: dict[str, Any] = {}
    tracker_path = ROOT / "data" / "reports" / "named_lane_outcome_tracker_latest.json"
    gate_path = ROOT / "data" / "reports" / "named_lane_promotion_gate_report_latest.json"

    if tracker_path.exists():
        try:
            data = json.loads(tracker_path.read_text(encoding="utf-8"))
            outcome["tracker_date"] = data.get("date")
            outcome["lanes"] = {lane["lane"]: lane for lane in data.get("lanes", [])}
            outcome["today_candidates"] = data.get("today_candidates", {})
        except Exception:
            pass

    if gate_path.exists():
        try:
            data = json.loads(gate_path.read_text(encoding="utf-8"))
            by_lane = {}
            for r in data.get("results", []):
                gs = r.get("gate_analysis", {})
                by_lane[r["lane"]] = {"verdict": gs.get("verdict"), "gates_passed": gs.get("gates_passed"), "gates_total": gs.get("gates_total")}
            outcome["gate_verdicts"] = by_lane
        except Exception:
            pass

    return outcome


def _load_corpus_progress() -> dict[str, Any]:
    """Read training corpus size from manifest or parquet and compute 2K progress."""
    manifest_path = ROOT / "data" / "training" / "sigma_2k_training_manifest_latest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            n = int(manifest.get("result_matched_rows") or manifest.get("rows_with_results", 0))
        except Exception:
            n = TRAINING_SAFE_BASELINE
    else:
        n = TRAINING_SAFE_BASELINE

    rows_to_2k = TRAINING_2K_TARGET - n
    pct = round(n / TRAINING_2K_TARGET * 100, 1)
    return {
        "training_safe_rows": n,
        "milestone_2k_target": TRAINING_2K_TARGET,
        "rows_to_2k": rows_to_2k,
        "pct_to_2k": pct,
        "corpus_name": "SIGMA_2K_SAFE_TRAINING_SLICE_V1",
        "growth_path": "daily_clean_accumulation",
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
    corpus_progress = _load_corpus_progress()
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
        "corpus_progress": corpus_progress,
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
    named = pred.get("named_lanes", {})
    corp = payload.get("corpus_progress", {})

    print(f"VELO Mission Control - {payload['date']}")
    print(f"Prediction: {pred['status']}  Verdicts={pred['verdict_count']}")
    print(f"  VP≥0.30: {pred['vp30_count']}  VP≥0.40: {pred['vp40_count']}  MDS_HIGH: {pred['mds_high_count']}  IMPROVER: {pred['improvement_high_count']}")
    print(f"  Tier A: {pred['tier_counts']['A']}  Tier B: {pred['tier_counts']['B']}  Tier C: {pred['tier_counts']['C']}")
    print(f"  MIDPRICE ADVISORY — Router-qualified: {mid.get('router_qualified_count',0)}  Suppressed advisory: {mid.get('router_suppressed_advisory_count',0)}")

    # ── Named Lane V2 Card ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("NAMED SIGNAL LANES — V2 CARD (advisory only, no execution)")
    print("=" * 62)

    # PRIORITY_WATCH — detailed horse cards
    print("\n[PRIORITY_WATCH]")
    pw_any = False
    for lane, signal_key, label in [
        ("MDS_HIGH_LANE",    "mds", "MDS"),
        ("IMPROVER_LANE",    "imp", "IMP"),
        ("VP40_TIER_A_LANE", None,  None),
    ]:
        info = named.get(lane, {})
        horses = info.get("horses", [])
        if not horses:
            continue
        pw_any = True
        print(f"  {lane}  ({info.get('count', 0)} today)")
        for c in horses[:5]:
            h = c.get("horse", "?")
            vp = c.get("vp", "?")
            race = c.get("race", "?")
            sig_str = f"  {label}={c[signal_key]}" if signal_key and signal_key in c else ""
            tier_str = f"  [{c['tier']}]" if "tier" in c else ""
            print(f"    {h:<22} VP={vp}{sig_str}{tier_str}  {race}")
    if not pw_any:
        print("  (none today)")

    # WATCH — brief listing
    print("\n[WATCH]")
    for lane in ("VP40_LANE", "SHORTFAV_VP30", "MIDPRICE_ROUTER_QUAL"):
        info = named.get(lane, {})
        n = info.get("count", 0)
        names = [c.get("horse", "?") for c in info.get("horses", [])[:6]]
        if n:
            print(f"  {lane}: {n} — {', '.join(names)}")
        else:
            print(f"  {lane}: 0")

    # SUPPRESS_ADVISORY — names as advisory reference
    print("\n[SUPPRESS_ADVISORY]")
    sup = named.get("MIDPRICE_SUPPRESS", {})
    sup_n = sup.get("count", 0)
    if sup_n:
        sup_names = [c.get("horse", "?") for c in sup.get("horses", [])[:8]]
        print(f"  MIDPRICE_SUPPRESS: {sup_n} — {', '.join(sup_names)}")
    else:
        print("  MIDPRICE_SUPPRESS: 0")

    # 2K milestone progress
    print(f"\nSIGMA CORPUS: {corp.get('training_safe_rows', '?')}/{corp.get('milestone_2k_target', 2000)} "
          f"training-safe rows ({corp.get('pct_to_2k', '?')}%) — {corp.get('rows_to_2k', '?')} to 2K")

    # Next review thresholds from cumulative corpus stats
    corpus_lanes = _load_named_lane_corpus()
    if corpus_lanes:
        print("NEXT REVIEW THRESHOLDS (corpus):")
        gates = [
            ("MDS_HIGH_LANE", 50, "SHADOW_LANE_TRACKING"),
            ("IMPROVER_LANE", 100, "shadow policy discussion"),
            ("VP40_LANE", 300, "model weight discussion"),
            ("MIDPRICE_ROUTER_QUAL", 50, "advisory promotion"),
        ]
        for lane_name, gate_n, gate_label in gates:
            cl = corpus_lanes.get(lane_name, {})
            cn = cl.get("n", 0)
            remaining = max(0, gate_n - cn)
            sr = cl.get("sr", 0.0)
            if remaining > 0:
                print(f"  {lane_name}: n={cn} SR={sr:.1f}%  →  +{remaining} to n={gate_n} ({gate_label})")
            else:
                print(f"  {lane_name}: n={cn} SR={sr:.1f}%  →  GATE REACHED (n={gate_n}, {gate_label})")
    print("=" * 62)

    # ── Lane Outcome Closure Section ─────────────────────────────────────────
    lane_outcomes = _load_lane_outcome_summary()
    if lane_outcomes.get("lanes"):
        print()
        print("─" * 62)
        print("LANE OUTCOME CLOSURE (from outcome tracker + gate report)")
        print("─" * 62)
        tracker_date = lane_outcomes.get("tracker_date", "?")
        print(f"Tracker date: {tracker_date}")
        print()

        gate_verdicts = lane_outcomes.get("gate_verdicts", {})
        lanes_data = lane_outcomes.get("lanes", {})

        # Priority lanes: show outcome health
        print("Outcome health by action:")
        for group_label, group_lanes in [
            ("PRIORITY_WATCH", ["MDS_HIGH_LANE", "IMPROVER_LANE", "VP40_TIER_A_LANE"]),
            ("WATCH",          ["VP40_LANE", "SHORTFAV_VP30", "MIDPRICE_ROUTER_QUAL"]),
            ("SUPPRESS_ADV",   ["MIDPRICE_SUPPRESS", "LONGSHOT_SUPPRESS"]),
        ]:
            print(f"  [{group_label}]")
            for lane_name in group_lanes:
                ld = lanes_data.get(lane_name, {})
                gv = gate_verdicts.get(lane_name, {})
                if not ld:
                    continue
                n = ld.get("n", 0)
                sr = ld.get("sr", 0.0)
                roi = ld.get("roi")
                roi_str = f" ROI={roi:+.1f}%" if roi is not None else ""
                verdict = gv.get("verdict", "?")
                gates_str = f"{gv.get('gates_passed', '?')}/{gv.get('gates_total', '?')}" if gv else "?"
                coll = ld.get("collapse_check", {}).get("status", "")
                coll_str = f" *** COLLAPSE ***" if coll == "COLLAPSE_WARNING" else ""
                print(f"    {lane_name:<24} n={n:>4} SR={sr:.1f}%{roi_str}  [{verdict}] {gates_str} gates{coll_str}")

        # Shadow policy candidates alert
        sp_cands = [ln for ln, gv in gate_verdicts.items() if gv.get("verdict") == "SHADOW_POLICY_CANDIDATE"]
        if sp_cands:
            print()
            print(f"*** SHADOW_POLICY_CANDIDATE: {', '.join(sp_cands)}")
            print("    Operator promotion discussion required.")

        # Weekly health: next review date estimate
        print()
        print("Next promotion review thresholds:")
        review_gates = [
            ("MDS_HIGH_LANE", 50), ("IMPROVER_LANE", 100),
            ("VP40_LANE", 300), ("MIDPRICE_ROUTER_QUAL", 50),
        ]
        for lane_name, gate_n in review_gates:
            ld = lanes_data.get(lane_name, {})
            cn = ld.get("n", 0)
            remaining = max(0, gate_n - cn)
            sr = ld.get("sr", 0.0)
            est_days = f"~{remaining // 5}–{remaining // 3} days" if remaining > 0 else "REACHED"
            if remaining > 0:
                print(f"  {lane_name}: n={cn} SR={sr:.1f}%  +{remaining} to n={gate_n}  ({est_days} at 3–5 rows/day)")
            else:
                print(f"  {lane_name}: n={cn} SR={sr:.1f}%  GATE n={gate_n} REACHED")
        print("─" * 62)

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
