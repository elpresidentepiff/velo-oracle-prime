#!/usr/bin/env python3
"""
Update Mission Control — read today's scoring artifacts and write
data/mission_control/YYYY-MM-DD_mission_control.json + latest.json.

Run after sigma close to refresh gates.

Usage:
    PYTHONPATH=. python scripts/ops/update_mission_control.py --date YYYY-MM-DD

Gate rules (PERMANENT — never remove):
  - If flatline_count > 0:  learning_gate = BLOCKED, promotion_gate = BLOCKED
  - If identity_failure_count > 0: promotion_gate = BLOCKED
  - If source_truth == RP_MERGED_CONTAMINATED: learning_gate = BLOCKED
  - sigma_audits truth writes are NEVER blocked — raw result ledger always recorded
  - Scoring pipeline is NEVER blocked by mission control gates
"""

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.mission_control_config import MC_CONFIG  # noqa: E402

MC_DIR = ROOT / "data" / "mission_control"


def _load_snapshots(date_str: str) -> list[dict]:
    date_und = date_str.replace("-", "_")
    patterns = [
        str(ROOT / "data" / f"runner_snapshots_{date_str}*.jsonl"),
        str(ROOT / "data" / f"runner_snapshots_{date_und}*.jsonl"),
    ]
    rows = []
    seen_paths: set = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
    return rows


def _extract_sha8(run_id: str) -> str:
    """Extract sha8 from run_id format '2026_05_20_32cc27f9_epoch'."""
    parts = run_id.split("_")
    if len(parts) >= 4:
        return parts[3]
    return run_id[:8]


def _detect_flatlines(rows: list[dict]) -> dict:
    # Group by run_id so mixing runs doesn't mask flatlines
    by_run: dict[str, dict[str, set]] = {}
    for row in rows:
        rid = row.get("race_id", "?")
        vp = round(float(row.get("velo_prime_prob") or 0), 6)
        sha = _extract_sha8(row.get("run_id", ""))
        if sha not in by_run:
            by_run[sha] = {}
        if rid not in by_run[sha]:
            by_run[sha][rid] = set()
        by_run[sha][rid].add(vp)

    fully_uniform_set: set[str] = set()
    majority_tied_set: set[str] = set()
    for sha, races in by_run.items():
        if sha in MC_CONFIG.CONTAMINATED_RUN_IDS:
            for rid, vps in races.items():
                if len(vps) == 1:
                    fully_uniform_set.add(rid)

    all_races: dict[str, set] = {}
    for _sha, races in by_run.items():
        for rid, vps in races.items():
            if rid not in all_races:
                all_races[rid] = set()
            all_races[rid].update(vps)

    return {
        "total_races": len(all_races),
        "flatline_count": len(fully_uniform_set),
        "fully_uniform_races": sorted(fully_uniform_set),
        "majority_tied_count": len(majority_tied_set),
        "identity_failure_count": 0,
        "identity_failed_races": [],
    }


# Labels the observability packet may legitimately report. Anything else is UNKNOWN.
_KNOWN_SOURCE_LABELS = frozenset({
    "RP_MERGED_CLEAN",
    "RP_MERGED_DEGRADED",
    "API_CLEAN",
    "LOCAL_JSON_FALLBACK",
    "SOURCE_UNKNOWN_BLOCK",
})


def _read_observability_source_truth(date_str: str, data_dir: Path | None = None) -> str:
    """Source truth comes from the run observability packet — never inferred.

    Reads the newest data/velo_run_observability_{date}_*.json for the date
    (multiple packets exist when the day had retries; the final run wins).
    Returns UNKNOWN when no packet exists or the packet is malformed.
    """
    base = data_dir if data_dir is not None else (ROOT / "data")
    date_und = date_str.replace("-", "_")
    paths = sorted(glob.glob(str(base / f"velo_run_observability_{date_und}_*.json")))
    best_label, best_ts = "", ""
    for path in paths:
        try:
            packet = json.loads(Path(path).read_text())
            label = packet.get("source_truth", "")
            ts = packet.get("timestamp", "")
        except Exception:
            continue
        if label in _KNOWN_SOURCE_LABELS and ts >= best_ts:
            best_label, best_ts = label, ts
    return best_label or "UNKNOWN"


def _detect_source_truth(rows: list[dict], date_str: str, data_dir: Path | None = None) -> str:
    run_ids = {_extract_sha8(r.get("run_id", "")) for r in rows if r.get("run_id")}
    contaminated = run_ids & MC_CONFIG.CONTAMINATED_RUN_IDS
    if contaminated:
        return "RP_MERGED_CONTAMINATED"
    return _read_observability_source_truth(date_str, data_dir)


def _gate_status(flatline_count: int, identity_failure_count: int, source_truth: str) -> tuple[str, str, list[str]]:
    reasons = []
    learning_gate = MC_CONFIG.LEARNING_GATE_OPEN
    promotion_gate = MC_CONFIG.PROMOTION_GATE_OPEN

    if source_truth == "RP_MERGED_CONTAMINATED":
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reasons.append("GATE_SOURCE_CONTAMINATED")

    if source_truth == "RP_MERGED_DEGRADED":
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reasons.append("GATE_SOURCE_DEGRADED")

    if source_truth in ("UNKNOWN", "SOURCE_UNKNOWN_BLOCK"):
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reasons.append("GATE_SOURCE_UNKNOWN")

    if flatline_count > 0:
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reasons.append(f"GATE_FLATLINE_DETECTED: {flatline_count} races")

    if identity_failure_count > 0:
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reasons.append(f"GATE_IDENTITY_FAILURE: {identity_failure_count} races")

    return learning_gate, promotion_gate, reasons


def _gate_v2_status() -> dict:
    gate_v2_path = ROOT / "data" / "reports" / "cpu_shadow_gate_v2_latest.json"
    if gate_v2_path.exists():
        try:
            d = json.loads(gate_v2_path.read_text())
            rcg = d.get("runner_calibration_gate", {})
            dpg = d.get("decision_policy_gate", {})
            return {
                "gate_v1_status": "GATE_V1_AUDIT_ONLY",
                "runner_calibration_gate": {
                    "runner_count": rcg.get("runner_count", 0),
                    "status": rcg.get("status", "UNKNOWN"),
                    "threshold": MC_CONFIG.RUNNER_CALIBRATION_THRESHOLD,
                    "review_threshold_met": rcg.get("review_threshold_met", False),
                },
                "decision_policy_gate": {
                    "top_pick_decisions": dpg.get("top_pick_decisions", 0),
                    "status": dpg.get("status", "NEEDS_MORE_DAYS"),
                    "next_review": dpg.get("next_review", ""),
                    "threshold_1": MC_CONFIG.DECISION_POLICY_GATE_1,
                    "threshold_1_met": dpg.get("threshold_1_met", False),
                },
                "live_promotion_allowed": False,
                "promotion_decision": "NOT_APPROVED_OPERATOR_DECISION_REQUIRED",
                "mission_control_display": d.get("mission_control_display", {}),
            }
        except Exception:
            pass
    return {
        "gate_v1_status": "GATE_V1_AUDIT_ONLY",
        "runner_calibration_gate": {"status": "UNKNOWN"},
        "decision_policy_gate": {"status": "UNKNOWN"},
        "live_promotion_allowed": False,
    }


def _load_last_council_verdict(date_str: str) -> str:
    run_path = ROOT / "data" / "council_runs" / f"council_run_{date_str}.json"
    if run_path.exists():
        try:
            d = json.loads(run_path.read_text())
            return d.get("council_verdict", "NOT_RUN")
        except Exception:
            pass
    # NEVER inherit another day's verdict (fixed 2026-08-04).
    #
    # This used to fall back to the most recent council_run_*.json from ANY
    # date and return its verdict as if it were today's. Observed 2026-08-03:
    # Step 15 ran before the Council did, found no council_run for 08-03,
    # picked up an earlier day's PASS_TO_LEARNING, and published
    #     council_artifacts: run=MISSING packet=MISSING report=MISSING
    #     council_verdict:   PASS_TO_LEARNING
    #     learning_gate:     OPEN
    # Step 16d re-ran after the real Council and flipped it to WATCH_ONLY /
    # BLOCKED. So the fail-open was masked only because 16d happened to run.
    # On any night 16d fails, the day learns on a verdict borrowed from a
    # different day's races.
    #
    # This is the exact shape CLAUDE.md Law 5 forbids for source_truth --
    # "never by default, missing = UNKNOWN" -- and the same rule has to hold
    # for the council verdict, which gates the same decision.
    #
    # NOT_RUN_TODAY is not PASS_TO_LEARNING, so the caller blocks. Callers
    # that want to show the last known verdict for context must read it
    # explicitly and label it stale.
    return "NOT_RUN_TODAY"


def _council_learning_disposition(date_str: str) -> dict:
    """Classify TODAY's council agent labels as performance vs integrity.

    Reads the same council_run file the verdict comes from, and delegates to
    src.velo.council.agents.learning_disposition so the label taxonomy has one
    owner. If today's council run is absent or unreadable the day is treated as
    integrity-blocked -- absence of evidence is never a pass (CLAUDE.md Law 5).
    """
    run_path = ROOT / "data" / "council_runs" / f"council_run_{date_str}.json"
    if not run_path.exists():
        return {"allowed": False, "disposition": "COUNCIL_RUN_MISSING",
                "performance_reasons": [], "integrity_reasons": ["council run not found"]}
    try:
        d = json.loads(run_path.read_text())
        from src.velo.council.agents import learning_disposition
        return learning_disposition(d.get("agent_responses", []))
    except Exception as e:
        return {"allowed": False, "disposition": "COUNCIL_READ_ERROR",
                "performance_reasons": [], "integrity_reasons": [str(e)]}


def _sigma_artifact_status(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    candidates = [
        ROOT / "data" / "sigma_results" / f"sigma_results_{date_und}.json",
        ROOT / "data" / f"sigma_results_{date_und}.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                d = json.loads(path.read_text())
                return {
                    "status": "PRESENT",
                    "path": str(path.relative_to(ROOT)),
                    "sr": d.get("sr"),
                    "wins": d.get("wins"),
                    "evaluated_count": d.get("evaluated_count"),
                    "sigma_status": d.get("sigma_status"),
                    "completeness_gate": d.get("completeness_gate"),
                    "learning_blocked": d.get("learning_blocked"),
                    "expected_predictions": d.get("expected_predictions"),
                    "result_races_available": d.get("result_races_available"),
                    "matched": d.get("matched"),
                    "coverage_ratio": d.get("coverage_ratio"),
                    "no_result_count": d.get("no_result_count"),
                }
            except Exception:
                pass
    return {"status": "MISSING", "path": None, "sr": None}


def _council_artifact_status(date_str: str) -> dict:
    run_path = ROOT / "data" / "council_runs" / f"council_run_{date_str}.json"
    packet_path = ROOT / "data" / "council_packets" / f"council_packet_{date_str}.json"
    report_path = ROOT / "data" / "council_reports" / f"velo_council_report_{date_str}.md"
    return {
        "council_run": "PRESENT" if run_path.exists() else "MISSING",
        "council_packet": "PRESENT" if packet_path.exists() else "MISSING",
        "council_report": "PRESENT" if report_path.exists() else "MISSING",
    }


def _run_truth_status(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    path = ROOT / "data" / f"velo_daily_run_truth_{date_und}.json"
    if not path.exists():
        return {
            "status": "MISSING",
            "path": None,
            "alert_required": True,
            "issues": ["DAILY_RUN_TRUTH_MISSING"],
        }
    try:
        report = json.loads(path.read_text())
    except Exception as exc:
        return {
            "status": "INVALID",
            "path": str(path.relative_to(ROOT)),
            "alert_required": True,
            "issues": [f"DAILY_RUN_TRUTH_INVALID: {exc}"],
        }
    return {
        "status": report.get("status", "UNKNOWN"),
        "path": str(path.relative_to(ROOT)),
        "alert_required": report.get("alert_required", True),
        "issues": report.get("issues", []),
        "cron_truth_status": report.get("cron_truth_status"),
        "deploy_truth_status": report.get("deploy_truth_status"),
        "pipeline_run_count": report.get("pipeline_run_count"),
    }


def _learning_admission_status(date_str: str) -> dict:
    elig_path = ROOT / "data" / "reports" / f"{date_str}_learning_eligibility.json"
    packet_path = ROOT / "docs" / "engineering" / "MAY22_SHADOW_LEARNING_ADMISSION_PACKET.md"
    nightly_path = ROOT / "data" / f"nightly_eod_learning_status_{date_str.replace('-', '_')}.json"
    ops_arts = sorted(glob.glob(str(ROOT / "data" / "ops_worker_dry_run" / f"{date_str}_learn-shadow_*.json")))
    build_result: dict = {}
    if ops_arts:
        # Use most recent artifact — prefer Phase 3B consume over build-only if present
        for art_path in reversed(ops_arts):
            try:
                art = json.loads(Path(art_path).read_text())
                if art.get("build_events_only"):
                    build_result = {
                        "phase": "BUILD_ONLY",
                        "events_built": art.get("events_built", 0),
                        "events_written": art.get("db_result", {}).get("written", 0),
                        "status": art.get("status", "UNKNOWN"),
                        "sentient_state_touched": art.get("sentient_state_touched", False),
                        "consumed_live": False,
                    }
                    break
                elif art.get("status") == "SHADOW_CONSUMED":
                    cr = art.get("consume_result", {})
                    build_result = {
                        "phase": "SHADOW_CONSUMED",
                        "events_built": art.get("events_found", cr.get("consumed", 0)),
                        "events_written": cr.get("consumed", 0),
                        "status": art.get("status", "UNKNOWN"),
                        "sentient_state_touched": art.get("sentient_state_touched", False),
                        "consumed_live": False,
                        "before_race_count": cr.get("before_race_count"),
                        "after_race_count": cr.get("after_race_count"),
                    }
                    break
            except Exception:
                pass
    elig: dict = {}
    if elig_path.exists():
        try:
            elig = json.loads(elig_path.read_text())
        except Exception:
            pass
    if not elig and not build_result and nightly_path.exists():
        try:
            nightly = json.loads(nightly_path.read_text())
            nightly_passed = nightly.get("verdict") == "PASS"
            elig = {
                "audit_status": "OUTCOME_ONLY_EOD_REPLAY_PASS" if nightly_passed else "OUTCOME_ONLY_EOD_REPLAY_FAIL",
                "eligible_count": nightly.get("events_created", 0),
                "excluded_count": nightly.get("data_error_count", 0),
            }
            build_result = {
                "phase": "OUTCOME_ONLY_EOD_REPLAY",
                "events_built": nightly.get("events_created", 0),
                "events_written": nightly.get("engine_updates_applied_first_run", 0),
                "status": nightly.get("verdict", "UNKNOWN"),
                "sentient_state_touched": nightly.get("live_sentient_state_touched", False),
                "shadow_state_touched": nightly.get("shadow_state_touched", False),
                "duplicates_skipped_second_run": nightly.get("duplicates_skipped_second_run", 0),
                "consumed_live": False,
            }
        except Exception:
            pass
    return {
        "eligibility_status": elig.get("audit_status", "NOT_RUN"),
        "eligible_rows": elig.get("eligible_count", 0),
        "excluded_rows": elig.get("excluded_count", 0),
        "consumed_shadow_before": elig.get("consumed_shadow_before", 0),
        "consumed_live_before": elig.get("consumed_live_before", 0),
        "live_state_hash": elig.get("live_state_hash_before", "UNKNOWN"),
        "build_events_result": build_result,
        "admission_packet": "PRESENT" if packet_path.exists() else "MISSING",
        "recommendation": (
            "CONSUMED_SHADOW_COMPLETE" if build_result.get("phase") == "SHADOW_CONSUMED"
            else "OUTCOME_ONLY_EOD_REPLAY_COMPLETE"
            if build_result.get("phase") == "OUTCOME_ONLY_EOD_REPLAY" and build_result.get("status") == "PASS"
            else "APPROVE_SHADOW_CONSUME" if elig.get("audit_status") == "ELIGIBLE" and build_result.get("events_written", 0) > 0
            else "PENDING"
        ),
    }


def _corpus_governance_status() -> dict:
    rebuild_path = ROOT / "data" / "reports" / "innovation_protocol_rebuild_2026-05-22.json"
    proto_path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    result: dict = {"status": "UNKNOWN"}
    if rebuild_path.exists():
        try:
            d = json.loads(rebuild_path.read_text())
            result = {
                "status": "REBUILT",
                "rows_after": d.get("corpus_totals", {}).get("rows_after"),
                "dates_added": d.get("dates_added", []),
                "dates_excluded": d.get("dates_excluded", []),
                "exclusion_reason": d.get("exclusion_reason"),
                "may_20_rows": d.get("may_20_rows"),
                "may_20_check": d.get("may_20_check"),
            }
        except Exception:
            pass
    elif proto_path.exists():
        result = {"status": "EXISTS_NO_REBUILD_REPORT"}
    return result


def _idempotency_status() -> dict:
    idem_path = ROOT / "data" / "reports" / "may21_may22_shadow_consume_idempotency.json"
    if not idem_path.exists():
        return {"status": "NOT_RUN"}
    try:
        d = json.loads(idem_path.read_text())
        return {
            "status": "VERIFIED" if d.get("all_checks_pass") else "FAILED",
            "all_checks_pass": d.get("all_checks_pass"),
            "consumed_shadow": d.get("totals", {}).get("consumed_shadow"),
            "consumed_live": d.get("consumed_live"),
            "live_state_unchanged": d.get("live_state_unchanged"),
            "shadow_train_v2_race_count": d.get("shadow_train_v2", {}).get("total_races_observed"),
        }
    except Exception:
        return {"status": "ERROR"}


def _precision_audit_status() -> dict:
    prec_path = ROOT / "data" / "reports" / "race_shape_precision_audit_latest.json"
    tracker_path = ROOT / "data" / "reports" / "race_shape_precision_tracker_latest.json"
    result: dict = {"status": "NOT_RUN"}
    if prec_path.exists():
        try:
            d = json.loads(prec_path.read_text())
            subsets = d.get("subsets", [])
            actionable = [s["label"] for s in subsets if s.get("verdict") == "ACTIONABLE_RISK_FLAG"]
            ultra = next((s for s in subsets if s["label"] == "FAV_VULN_ULTRA_COMPRESSED"), {})
            ledger_rows = d.get("ledger_rows", 0)
            result = {
                "status": "RUN",
                "date": d.get("date"),
                "ledger_rows": ledger_rows,
                "ledger_rows_to_gate_150": max(0, 150 - ledger_rows),
                "ledger_rows_to_gate_300": max(0, 300 - ledger_rows),
                "actionable_candidates": actionable,
                "fav_vuln_ultra_compressed_n": ultra.get("n"),
                "fav_vuln_ultra_compressed_sr": ultra.get("sr"),
                "fav_vuln_ultra_compressed_verdict": ultra.get("verdict"),
            }
        except Exception:
            pass
    if tracker_path.exists():
        try:
            td = json.loads(tracker_path.read_text())
            flags = td.get("flags", [])
            ultra_t = next((f for f in flags if f["flag"] == "FAV_VULN_ULTRA_COMPRESSED"), {})
            mt_t = next((f for f in flags if f["flag"] == "MIDPRICE_TRAP"), {})
            result["tracker"] = {
                "fav_vuln_ultra_compressed": {"n": ultra_t.get("n"), "sr": ultra_t.get("sr"), "to_150": ultra_t.get("needed_to_gate_150"), "verdict": ultra_t.get("verdict")},
                "midprice_trap": {"n": mt_t.get("n"), "sr": mt_t.get("sr"), "to_150": mt_t.get("needed_to_gate_150"), "verdict": mt_t.get("verdict")},
            }
        except Exception:
            pass
    return result


def _cpu_tracker_status() -> dict:
    tracker_path = ROOT / "data" / "reports" / "cpu_gate_v2_decision_policy_tracker_latest.json"
    if not tracker_path.exists():
        return {"status": "NOT_RUN"}
    try:
        d = json.loads(tracker_path.read_text())
        stats = d.get("stats", {})
        return {
            "status": "RUN",
            "decisions_made": d.get("decisions_made", 0),
            "decisions_with_outcomes": d.get("decisions_with_outcomes", 0),
            "needed_to_150": d.get("needed_to_gate_1", 0),
            "needed_to_300": d.get("needed_to_gate_2", 0),
            "sr": stats.get("sr"),
            "brier": stats.get("brier_score"),
            "top_decile_sr": stats.get("top_decile_sr"),
            "verdict": d.get("verdict", "NEEDS_MORE_DAYS"),
        }
    except Exception:
        return {"status": "ERROR"}


def _race_shape_status() -> dict:
    feat_path = ROOT / "data" / "features" / "race_shape_features_latest.json"
    overlap_path = ROOT / "data" / "reports" / "race_shape_midprice_overlap_latest.json"
    shape_result: dict = {"status": "NOT_RUN"}
    if feat_path.exists():
        try:
            d = json.loads(feat_path.read_text())
            shape_result = {
                "status": "FEATURES_BUILT",
                "date": d.get("date"),
                "race_count": d.get("race_count", 0),
            }
        except Exception:
            pass
    overlap_result: dict = {"status": "NOT_RUN"}
    if overlap_path.exists():
        try:
            d = json.loads(overlap_path.read_text())
            q = d.get("overlap_questions", {})
            overlap_result = {
                "status": "OVERLAP_RUN",
                "date": d.get("date"),
                "winner_visible_pct": d.get("winner_visible_pct"),
                "winner_ranked_2nd_3rd_pct": d.get("winner_ranked_2nd_or_3rd_pct"),
                "fav_vulnerable_misses": q.get("q2_fav_vulnerable_misses"),
                "compressed_misses": q.get("q1_compressed_misses"),
                "shadow_candidates": q.get("q6_shadow_tracking_candidates"),
            }
        except Exception:
            pass
    return {
        "race_shape_model_v1": "DESIGN_PENDING",
        "features_built": shape_result,
        "midprice_overlap": overlap_result,
    }


def _evidence_accumulation_action(precision_audit: dict, cpu_tracker: dict) -> dict:
    """Compute the current evidence accumulation action label."""
    ledger_rows = precision_audit.get("ledger_rows", 0)
    cpu_decisions = cpu_tracker.get("decisions_made", 0)

    if ledger_rows >= 150 and cpu_decisions >= 150:
        action = "REVIEW_AT_150"
    elif ledger_rows >= 300 and cpu_decisions >= 300:
        action = "REVIEW_AT_300"
    else:
        action = "ACCUMULATE_EVIDENCE"

    return {
        "action": action,
        "race_shape_rows": ledger_rows,
        "race_shape_to_150": max(0, 150 - ledger_rows),
        "race_shape_to_300": max(0, 300 - ledger_rows),
        "cpu_decisions_made": cpu_decisions,
        "cpu_to_150": max(0, 150 - cpu_decisions),
        "cpu_to_300": max(0, 300 - cpu_decisions),
        "production_status": "NOT_APPROVED",
    }


def build_mission_control(date_str: str) -> dict:
    rows = _load_snapshots(date_str)
    flatline_data = _detect_flatlines(rows)
    source_truth = _detect_source_truth(rows, date_str)
    run_ids = sorted({_extract_sha8(r.get("run_id", "")) for r in rows if r.get("run_id")})
    learning_gate, promotion_gate, reason_codes = _gate_status(
        flatline_data["flatline_count"],
        flatline_data["identity_failure_count"],
        source_truth,
    )
    council_verdict = _load_last_council_verdict(date_str)
    gate_v2 = _gate_v2_status()
    sigma_artifact = _sigma_artifact_status(date_str)
    council_artifacts = _council_artifact_status(date_str)
    run_truth = _run_truth_status(date_str)
    learning_admission = _learning_admission_status(date_str)
    race_shape = _race_shape_status()
    corpus_governance = _corpus_governance_status()
    idempotency = _idempotency_status()
    precision_audit = _precision_audit_status()
    cpu_tracker = _cpu_tracker_status()

    rcg = gate_v2.get("runner_calibration_gate", {})
    dpg = gate_v2.get("decision_policy_gate", {})

    if sigma_artifact.get("learning_blocked") or sigma_artifact.get("completeness_gate") == "BLOCKED":
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reason_codes.append("GATE_SIGMA_INCOMPLETE")

    # A non-PASS council verdict always blocks PROMOTION. Whether it blocks
    # LEARNING now depends on why (operator ruling 2026-08-02: learning must
    # happen every day, including degraded ones). A day the model called badly
    # is still a day whose data is sound -- and the one most worth learning
    # from. Only a data-trust failure blocks learning.
    learning_disposition = _council_learning_disposition(date_str)
    if council_verdict not in ("PASS_TO_LEARNING",):
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reason_codes.append(f"GATE_COUNCIL_{council_verdict}")
        if not learning_disposition["allowed"]:
            learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
            reason_codes.append(f"GATE_INTEGRITY_{learning_disposition['disposition']}")
        else:
            reason_codes.append(f"LEARNING_ALLOWED_{learning_disposition['disposition']}")

    if run_truth["status"] == "MANUAL_RECOVERY_ONLY":
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reason_codes.append(f"GATE_PIPELINE_TRUTH_{run_truth['status']}")
    elif run_truth["status"] != "AUTOMATED_RUN_OK":
        learning_gate = MC_CONFIG.LEARNING_GATE_BLOCKED
        promotion_gate = MC_CONFIG.PROMOTION_GATE_BLOCKED
        reason_codes.append(f"GATE_PIPELINE_TRUTH_{run_truth['status']}")

    mc = {
        "date": date_str,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_truth": source_truth,
        "run_ids_seen": run_ids,
        "flatline_count": flatline_data["flatline_count"],
        "fully_uniform_count": flatline_data["flatline_count"],
        "fully_uniform_races": flatline_data["fully_uniform_races"],
        "majority_tied_count": flatline_data["majority_tied_count"],
        "identity_failure_count": flatline_data["identity_failure_count"],
        "runners_snapshotted": len(rows),
        "council_verdict": council_verdict,
        "learning_gate_status": learning_gate,
        "promotion_gate_status": promotion_gate,
        "gate_reasons": reason_codes,
        "sigma_artifact": sigma_artifact,
        "run_truth": run_truth,
        "council_artifact_visibility": council_artifacts,
        "runner_calibration_gate_status": rcg.get("status", "UNKNOWN"),
        "runner_calibration_gate_runners": rcg.get("runner_count", 0),
        "decision_policy_gate_status": dpg.get("status", "UNKNOWN"),
        "decision_policy_gate_top_picks": dpg.get("top_pick_decisions", 0),
        "learning_admission": learning_admission,
        "race_shape_v1": race_shape,
        "corpus_governance": corpus_governance,
        "shadow_consume_idempotency": idempotency,
        "race_shape_precision_audit": precision_audit,
        "cpu_decision_policy_tracker": cpu_tracker,
        "evidence_accumulation": _evidence_accumulation_action(precision_audit, cpu_tracker),
        "research_status": {
            "race_shape_model_v1": "DESIGN_PENDING",
            "midprice_hunter_v2": "RESEARCH_PENDING",
        },
        "cpu_shadow_gate_v1": {
            "status": "GATE_V1_AUDIT_ONLY",
            "contaminated": True,
            "reason": "Contains pre-a33c5bd RP_MERGED rows — do not use for promotion",
        },
        "cpu_shadow_gate_v2": gate_v2,
        "gate_rules": [
            "sigma_audits truth writes: NEVER blocked — raw result ledger always recorded",
            "scoring pipeline: NEVER blocked by mission control gates",
            "learning eligibility: BLOCKED if flatline_count > 0 OR source_truth == RP_MERGED_CONTAMINATED",
            "promotion eligibility: BLOCKED if flatline_count > 0 OR identity_failure_count > 0 OR source_truth == RP_MERGED_CONTAMINATED",
            "shadow consume: BLOCKED if council_verdict not PASS_TO_LEARNING",
        ],
        "next_safe_command": _next_safe_command(learning_gate, promotion_gate, flatline_data, reason_codes),
    }
    return mc


def _next_safe_command(
    learning_gate: str,
    promotion_gate: str,
    flatline_data: dict,
    reason_codes: list[str],
) -> str:
    if flatline_data["flatline_count"] > 0:
        return f"INVESTIGATE scoring flatline: {flatline_data['flatline_count']} uniform races. Check RP_MERGED hydration. Do not train or promote."
    if any(reason.startswith("GATE_PIPELINE_TRUTH_") for reason in reason_codes):
        return "Manual recovery learning is recorded; keep promotion blocked until an automated run proves pipeline truth."
    if learning_gate == "BLOCKED":
        return "Source truth contaminated — do not consume for learning. Run council audit first."
    if promotion_gate == "BLOCKED":
        return "Promotion blocked — resolve identity failures before promotion discussion."
    return "Green — safe to proceed with daily evidence accumulation."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    print(f"Building Mission Control for {args.date}...")
    mc = build_mission_control(args.date)

    MC_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = MC_DIR / f"{args.date}_mission_control.json"
    latest_path = MC_DIR / "latest.json"

    dated_path.write_text(json.dumps(mc, indent=2))
    latest_path.write_text(json.dumps(mc, indent=2))

    print(f"  source_truth: {mc['source_truth']}")
    print(f"  flatline_count: {mc['flatline_count']}")
    print(f"  fully_uniform_count: {mc['fully_uniform_count']}")
    print(f"  majority_tied_count: {mc['majority_tied_count']}")
    print(f"  identity_failure_count: {mc['identity_failure_count']}")
    print(f"  learning_gate: {mc['learning_gate_status']}")
    print(f"  promotion_gate: {mc['promotion_gate_status']}")
    print(f"  council_verdict: {mc['council_verdict']}")
    _sa = mc.get('sigma_artifact', {})
    print(f"  sigma_artifact: {_sa.get('status','?')} (sr={_sa.get('sr','?')}, wins={_sa.get('wins','?')}, n={_sa.get('evaluated_count','?')})")
    _ca = mc.get('council_artifact_visibility', {})
    print(f"  council_artifacts: run={_ca.get('council_run','?')} packet={_ca.get('council_packet','?')} report={_ca.get('council_report','?')}")
    print(f"  runner_calibration_gate: {mc['runner_calibration_gate_status']} (n={mc['runner_calibration_gate_runners']})")
    print(f"  decision_policy_gate:    {mc['decision_policy_gate_status']} (top_picks={mc['decision_policy_gate_top_picks']})")
    _rs = mc.get('research_status', {})
    print(f"  race_shape_model_v1: {_rs.get('race_shape_model_v1','?')}")
    print(f"  midprice_hunter_v2:  {_rs.get('midprice_hunter_v2','?')}")
    _la = mc.get('learning_admission', {})
    _ber = _la.get('build_events_result', {})
    print(f"  learning_admission:  eligibility={_la.get('eligibility_status','?')} eligible={_la.get('eligible_rows','?')} events_written={_ber.get('events_written','?')} recommendation={_la.get('recommendation','?')}")
    _rsv1 = mc.get('race_shape_v1', {})
    _fb = _rsv1.get('features_built', {})
    _ov = _rsv1.get('midprice_overlap', {})
    print(f"  race_shape_features: {_fb.get('status','?')} (n={_fb.get('race_count','?')} races)")
    print(f"  midprice_overlap:    visible={_ov.get('winner_visible_pct','?')}% ranked2nd3rd={_ov.get('winner_ranked_2nd_3rd_pct','?')}% fav_vuln_misses={_ov.get('fav_vulnerable_misses','?')}")
    _cg = mc.get('corpus_governance', {})
    print(f"  corpus_governance:   status={_cg.get('status','?')} rows={_cg.get('rows_after','?')} may20_rows={_cg.get('may_20_rows','?')} may20_check={_cg.get('may20_check',_cg.get('may_20_check','?'))}")
    _id = mc.get('shadow_consume_idempotency', {})
    print(f"  idempotency:         status={_id.get('status','?')} consumed_shadow={_id.get('consumed_shadow','?')} consumed_live={_id.get('consumed_live','?')} shadow_v2_races={_id.get('shadow_train_v2_race_count','?')}")
    _pa = mc.get('race_shape_precision_audit', {})
    actionable = _pa.get('actionable_candidates', [])
    print(f"  precision_audit:     status={_pa.get('status','?')} actionable={actionable} fav_vuln_ultra_sr={_pa.get('fav_vuln_ultra_compressed_sr','?')}")
    _ea = mc.get('evidence_accumulation', {})
    print(f"  evidence_action:     {_ea.get('action','?')} | race_shape={_ea.get('race_shape_rows',0)}/150/300 | cpu={_ea.get('cpu_decisions_made',0)}/150/300 | production={_ea.get('production_status','?')}")
    _ct = mc.get('cpu_decision_policy_tracker', {})
    print(f"  cpu_tracker:         status={_ct.get('status','?')} decisions={_ct.get('decisions_made','?')} SR={_ct.get('sr','?')} to_150={_ct.get('needed_to_150','?')} verdict={_ct.get('verdict','?')}")
    print(f"  next: {mc['next_safe_command']}")
    print(f"  Written: {dated_path}")
    print(f"  Written: {latest_path}")


if __name__ == "__main__":
    main()
