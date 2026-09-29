"""Read-only canonical dashboard analytics.

The module consumes rows already read from Supabase.  It never reads local
artifacts and has no persistence path.  Captured-price and settled-SP returns
are deliberately separate: a missing captured price stays unavailable.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from datetime import datetime
from typing import Any


def _cdm_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _cdm_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _cdm_lane_kind(row: dict[str, Any]) -> str:
    model = str(row.get("model_name") or "").upper()
    lane = str(row.get("lane_name") or "").upper()
    if model == "MAIN_VELO_PRIME":
        return "PRODUCTION"
    if "PROXY" in model or "PROXY" in lane:
        return "PROXY"
    if "SELECTIVE_VALUE" in lane or "CAPTAIN" in model:
        return "SELECTIVE_VALUE_SHADOW"
    if model.startswith("NEW_BUILD_"):
        return "SHADOW"
    if model.startswith("OLD_VELO_"):
        return "REPORT_ONLY"
    if "SHADOW" in model or "SHADOW" in lane or "FORWARD" in lane:
        return "SHADOW"
    return "UNKNOWN"


def _cdm_family(row: dict[str, Any]) -> str:
    model = str(row.get("model_name") or "UNKNOWN").upper()
    if model.startswith("CAPTAIN"):
        return "CAPTAIN_VALUE"
    if model.startswith("NEW_BUILD_LANE_"):
        return "NEW_BUILD_FAMILY"
    if model.startswith("OLD_VELO_"):
        return "OLD_VELO_ROLE_FAMILY"
    if model in {"MAIN_VELO_PRIME", "SQPE_NO_RPR_SHADOW"}:
        return "VELO_PRIME_CORE"
    if "MDS" in model:
        return "MDS_FAMILY"
    if "CHAMPION" in model:
        return "CHAMPION_INTENT_FAMILY"
    return model


def _cdm_profit(win: bool, odds: float) -> float:
    return odds - 1.0 if win else -1.0


def _cdm_sort_key(row: dict[str, Any]) -> tuple[str, int, str, str]:
    """Chronological UK race-day key with deterministic identity tie-breaks."""
    day = str(row.get("run_date") or row.get("date") or "")
    value = str(row.get("off_time") or "")
    match = re.search(r"(?:T|^)(\d{1,2})[:.](\d{2})", value)
    minutes = 24 * 60
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        # Governed race-card convention: 1 through 9 are UK afternoon/evening.
        if 1 <= hour <= 9:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            minutes = hour * 60 + minute
    return day, minutes, str(row.get("race_id") or ""), str(row.get("horse_id") or row.get("horse") or "")


def _cdm_forward_evidence(row: dict[str, Any]) -> str:
    """Recognise only explicit Captain decision-packet provenance."""
    source = str(row.get("source_path") or "").replace("\\", "/")
    packet_match = re.search(
        r"(?:^|/)captain_velo_shadow_(\d{4})_(\d{2})_(\d{2})\.json$", source
    )
    packet_date = "-".join(packet_match.groups()) if packet_match else None
    row_date = str(row.get("run_date") or row.get("date") or "")
    capture_ts = str(row.get("odds_capture_ts") or "")
    try:
        parsed_capture_ts = datetime.fromisoformat(capture_ts.replace("Z", "+00:00"))
        timestamp_valid = parsed_capture_ts.tzinfo is not None
    except ValueError:
        timestamp_valid = False
    if (
        str(row.get("model_name") or "").upper().startswith("CAPTAIN")
        and str(row.get("price_source") or "") == "CAPTAIN_FORWARD_PACKET_DECIMAL_ODDS"
        and packet_date == row_date
        and timestamp_valid
        and (_cdm_num(row.get("captured_odds_dec")) or 0.0) > 1.0
        and _cdm_true(row.get("odds_timestamp_before_off"))
    ):
        return "PREDECLARED_PACKET_PROVEN"
    return "UNAVAILABLE_NOT_PROVEN"


def _cdm_max_drawdown(profits: list[float]) -> float:
    equity = peak = 0.0
    drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return round(drawdown, 6)


def _cdm_day_bootstrap_roi(day_profits: dict[str, list[float]], seed_text: str) -> dict[str, Any]:
    days = sorted(day_profits)
    if len(days) < 3:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "days": len(days),
            "method": "day_cluster_bootstrap",
            "roi_95pct": None,
        }
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(1000):
        chosen = [days[rng.randrange(len(days))] for _ in days]
        values = [profit for day in chosen for profit in day_profits[day]]
        if values:
            samples.append(sum(values) / len(values) * 100.0)
    samples.sort()
    lo = samples[int((len(samples) - 1) * 0.025)]
    hi = samples[int((len(samples) - 1) * 0.975)]
    return {
        "status": "AVAILABLE",
        "days": len(days),
        "method": "day_cluster_bootstrap",
        "samples": len(samples),
        "roi_95pct": [round(lo, 3), round(hi, 3)],
    }


def _cdm_model_summary(model: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=_cdm_sort_key)
    eligible = [r for r in ordered if _cdm_true(r.get("dashboard_metrics_eligible"))]
    settled = [r for r in eligible if r.get("settlement_status") == "SETTLED"]
    voids = [r for r in eligible if r.get("settlement_status") == "VOID"]
    unresolved = [
        r for r in ordered
        if not _cdm_true(r.get("dashboard_metrics_eligible"))
        or r.get("settlement_status") not in {"SETTLED", "VOID"}
    ]
    wins = sum(_cdm_true(r.get("win")) for r in settled)
    frames = sum(_cdm_true(r.get("frame")) for r in settled)

    captured_profits: list[float] = []
    sp_profits: list[float] = []
    captured_days: dict[str, list[float]] = defaultdict(list)
    ratios: list[float] = []
    for row in settled:
        captured = _cdm_num(row.get("captured_odds_dec"))
        settled_sp = _cdm_num(row.get("settled_sp_dec"))
        win = _cdm_true(row.get("win"))
        day = str(row.get("run_date") or row.get("date") or "UNKNOWN")
        if captured is not None and captured > 1.0 and _cdm_true(row.get("odds_timestamp_before_off")):
            profit = _cdm_profit(win, captured)
            captured_profits.append(profit)
            captured_days[day].append(profit)
            if settled_sp is not None and settled_sp > 1.0:
                ratios.append(captured / settled_sp)
        if settled_sp is not None and settled_sp > 1.0:
            sp_profits.append(_cdm_profit(win, settled_sp))

    captured_available = len(captured_profits) == len(settled) and bool(settled)
    sp_available = len(sp_profits) == len(settled) and bool(settled)
    captured_profit = sum(captured_profits) if captured_available else None
    sp_profit = sum(sp_profits) if sp_available else None
    winning_returns = sorted(
        (_cdm_num(r.get("captured_odds_dec")) or 0.0) - 1.0
        for r in settled
        if _cdm_true(r.get("win")) and (_cdm_num(r.get("captured_odds_dec")) or 0.0) > 1.0
        and _cdm_true(r.get("odds_timestamp_before_off"))
    )
    ex_big = None
    if captured_available and captured_profits:
        ex_big = sum(captured_profits) - (winning_returns[-1] if winning_returns else 0.0)

    first = eligible[0] if eligible else (ordered[0] if ordered else {})
    return {
        "model_name": model,
        "lane_type": _cdm_lane_kind(first),
        "model_family": _cdm_family(first),
        "forward_evidence_status": (
            "PREDECLARED_PACKET_PROVEN"
            if eligible and all(_cdm_forward_evidence(r) == "PREDECLARED_PACKET_PROVEN" for r in eligible)
            else "UNAVAILABLE_NOT_PROVEN"
        ),
        "selections": len(eligible),
        "settled": len(settled),
        "voids": len(voids),
        "unresolved": len(unresolved),
        "wins": wins,
        "frames": frames,
        "strike_rate_pct": round(wins / len(settled) * 100.0, 3) if settled else None,
        "frame_rate_pct": round(frames / len(settled) * 100.0, 3) if settled else None,
        "captured_price": {
            "status": "AVAILABLE" if captured_available else "UNAVAILABLE",
            "priced_settled": len(captured_profits),
            "missing_or_unsafe": len(settled) - len(captured_profits),
            "stake": len(captured_profits) if captured_available else None,
            "return": round((captured_profit or 0.0) + len(captured_profits), 6) if captured_available else None,
            "profit": round(captured_profit, 6) if captured_profit is not None else None,
            "roi_pct": round(captured_profit / len(captured_profits) * 100.0, 3) if captured_available else None,
            "profit_ex_biggest_winner": round(ex_big, 6) if ex_big is not None else None,
            "max_drawdown": _cdm_max_drawdown(captured_profits) if captured_available else None,
            "uncertainty": (
                _cdm_day_bootstrap_roi(captured_days, model)
                if captured_available
                else {
                    "status": "UNAVAILABLE",
                    "days": len(captured_days),
                    "method": "day_cluster_bootstrap",
                    "roi_95pct": None,
                }
            ),
        },
        "settled_sp": {
            "status": "AVAILABLE" if sp_available else "UNAVAILABLE",
            "priced_settled": len(sp_profits),
            "missing": len(settled) - len(sp_profits),
            "stake": len(sp_profits) if sp_available else None,
            "return": round((sp_profit or 0.0) + len(sp_profits), 6) if sp_available else None,
            "profit": round(sp_profit, 6) if sp_profit is not None else None,
            "roi_pct": round(sp_profit / len(sp_profits) * 100.0, 3) if sp_available else None,
        },
        "clv_price_ratio": {
            "status": "AVAILABLE" if ratios else "UNAVAILABLE",
            "observations": len(ratios),
            "mean_captured_over_sp": round(sum(ratios) / len(ratios), 6) if ratios else None,
        },
    }


def _cdm_family_groups(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for family in sorted({m["model_family"] for m in models}):
        members = [m for m in models if m["model_family"] == family]
        settled = sum(m["settled"] for m in members)
        wins = sum(m["wins"] for m in members)
        groups.append({
            "family": family,
            "members": [m["model_name"] for m in members],
            "member_count": len(members),
            "non_independent": len(members) > 1,
            "observation_unit": "MEMBER_ROWS_NON_INDEPENDENT",
            "selections": sum(m["selections"] for m in members),
            "settled": settled,
            "wins": wins,
            "strike_rate_pct": round(wins / settled * 100.0, 3) if settled else None,
        })
    return groups


def build_canonical_dashboard_payload(
    rows: list[dict[str, Any]],
    through_date: str,
    mission_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Legacy/backfilled rows are intentionally excluded from the forward window.
    # Only rows rebuilt under the governed V2 truth contract may contribute.
    top_rows = [
        r for r in rows
        if int(r.get("rank") or 0) == 1
        and r.get("truth_contract_version") == "CANONICAL_TRUTH_V2"
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in top_rows:
        grouped[str(row.get("model_name") or "UNKNOWN")].append(row)
    models = [_cdm_model_summary(model, grouped[model]) for model in sorted(grouped)]

    production_by_race: dict[tuple[str, str], str] = {}
    for row in top_rows:
        if str(row.get("model_name")) == "MAIN_VELO_PRIME" and _cdm_true(row.get("dashboard_metrics_eligible")):
            key = (str(row.get("run_date") or row.get("date") or ""), str(row.get("race_id") or ""))
            production_by_race[key] = str(row.get("horse_id") or row.get("horse") or "")
    for model in models:
        cohorts = {
            "overlap": {"selections": 0, "settled": 0, "wins": 0},
            "disagreement": {"selections": 0, "settled": 0, "wins": 0},
        }
        for row in grouped[model["model_name"]]:
            if not _cdm_true(row.get("dashboard_metrics_eligible")):
                continue
            key = (str(row.get("run_date") or row.get("date") or ""), str(row.get("race_id") or ""))
            if key not in production_by_race:
                continue
            pick = str(row.get("horse_id") or row.get("horse") or "")
            cohort = cohorts["overlap" if pick == production_by_race[key] else "disagreement"]
            cohort["selections"] += 1
            if _cdm_true(row.get("dashboard_metrics_eligible")) and row.get("settlement_status") == "SETTLED":
                cohort["settled"] += 1
                cohort["wins"] += int(_cdm_true(row.get("win")))
        model["production_cohort"] = cohorts

    day_rows = [r for r in top_rows if str(r.get("run_date") or r.get("date") or "") == through_date]
    captain_rows = [r for r in day_rows if str(r.get("model_name") or "").upper().startswith("CAPTAIN")]
    captain = []
    for row in sorted(captain_rows, key=_cdm_sort_key):
        captain.append({
            "race_id": row.get("race_id"), "course": row.get("course"), "off_time": row.get("off_time"),
            "horse": row.get("horse"), "horse_id": row.get("horse_id"),
            "settlement_status": row.get("settlement_status"), "outcome_code": row.get("subject_outcome_code"),
            "win": row.get("win"), "frame": row.get("frame"),
            "captured_odds_dec": row.get("captured_odds_dec"), "settled_sp_dec": row.get("settled_sp_dec"),
            "captured_price_status": "AVAILABLE" if (_cdm_num(row.get("captured_odds_dec")) or 0.0) > 1.0 and _cdm_true(row.get("odds_timestamp_before_off")) else "UNAVAILABLE",
            "forward_evidence_status": _cdm_forward_evidence(row),
        })

    mc = mission_control or {}
    mc_payload = mc.get("payload") if isinstance(mc.get("payload"), dict) else {}
    learning_admission = mc_payload.get("learning_admission") if isinstance(mc_payload.get("learning_admission"), dict) else {}
    return {
        "through_date": through_date,
        "window": {
            "mode": "GOVERNED_TRUTH_V2",
            "start_date": min((str(r.get("run_date") or r.get("date")) for r in top_rows), default=None),
            "end_date": through_date,
            "days": len({str(r.get("run_date") or r.get("date")) for r in top_rows}),
            "forward_evidence_status": "UNAVAILABLE_NOT_PROVEN_FOR_WHOLE_WINDOW",
        },
        "models": models,
        "correlated_families": _cdm_family_groups(models),
        "captain": {"date": through_date, "canonical_selections": captain},
        "post_learning_mission_control": {
            "status": "AVAILABLE" if mc else "UNAVAILABLE",
            "run_date": mc.get("run_date"),
            "generated_at": mc.get("generated_at"),
            "learning_gate_status": mc.get("learning_gate_status"),
            "promotion_gate_status": mc.get("promotion_gate_status"),
            "council_verdict": mc.get("council_verdict"),
            "learning_admission_status": learning_admission.get("eligibility_status"),
            "learning_eligible_rows": learning_admission.get("eligible_rows"),
            "learning_excluded_rows": learning_admission.get("excluded_rows"),
            "source_sha256": mc.get("source_sha256"),
        },
        "small_sample_warning": "Intervals are day-clustered; fewer than 3 race days is insufficient evidence.",
        "no_supabase_write": True,
    }
