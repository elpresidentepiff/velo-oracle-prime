"""
VÉLØ Signal Promotion Board
===========================

Builds an evidence-to-live governance board from the current local ledgers.

Outputs:
  - data/signal_promotion_board_latest.csv
  - data/signal_promotion_board_latest.md

This is an audit/governance script only.
It does not change production scoring, routing, staking, or execution.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

INNOVATION_PROTOCOL = DATA / "velo_innovation_protocol_1k_deduped.csv"
ROUTER_LATEST = DATA / "router_shadow_audit_latest.csv"
ROUTER_LEDGER = DATA / "router_shadow_audit_ledger.csv"
RACING_SHADOW = DATA / "racing_api_shadow_forward_ledger.csv"
EXECUTION_LEDGER = DATA / "velo_execution_bridge_paper_ledger.csv"

OUT_CSV = DATA / "signal_promotion_board_latest.csv"
OUT_MD = DATA / "signal_promotion_board_latest.md"


@dataclass
class Observation:
    won: float | None = None
    placed: float | None = None
    sp_decimal: float | None = None
    velo_prime_prob: float | None = None
    result_matched: bool = False
    note: str = ""


def _f(v, default: float | None = None) -> float | None:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _b(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _safe_corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _brier_loss(probs: list[float], outcomes: list[float]) -> float | None:
    if not probs or len(probs) != len(outcomes):
        return None
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def _log_loss(probs: list[float], outcomes: list[float]) -> float | None:
    if not probs or len(probs) != len(outcomes):
        return None
    eps = 1e-9
    total = 0.0
    for p, y in zip(probs, outcomes):
        p = min(max(p, eps), 1 - eps)
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(probs)


def _flat_roi(obs: list[Observation]) -> tuple[float | None, float | None, int | None]:
    pnl_series: list[float] = []
    for o in obs:
        if o.sp_decimal is None or not o.result_matched:
            continue
        pnl_series.append((o.sp_decimal - 1.0) if o.won else -1.0)
    if not pnl_series:
        return None, None, None

    total = sum(pnl_series)
    roi = total / len(pnl_series)
    peak = 0.0
    curve = 0.0
    max_dd = 0.0
    losing_run = 0
    longest_losing_run = 0
    for x in pnl_series:
        curve += x
        peak = max(peak, curve)
        max_dd = min(max_dd, curve - peak)
        if x < 0:
            losing_run += 1
            longest_losing_run = max(longest_losing_run, losing_run)
        else:
            losing_run = 0
    return roi, max_dd, longest_losing_run


def _metrics(obs: list[Observation]) -> dict:
    n = len(obs)
    matched = [o for o in obs if o.result_matched]
    matched_n = len(matched)
    wins = sum(1 for o in matched if o.won)
    places = sum(1 for o in matched if o.placed)
    sr = (wins / matched_n * 100.0) if matched_n else None
    fr = (places / matched_n * 100.0) if matched_n else None
    roi, max_dd, llr = _flat_roi(obs)
    probs = [o.velo_prime_prob for o in matched if o.velo_prime_prob is not None]
    win_targets = [float(o.won) for o in matched if o.velo_prime_prob is not None]
    place_targets = [float(o.placed) for o in matched if o.velo_prime_prob is not None]
    return {
        "sample_size": n,
        "matched_sample_size": matched_n,
        "strike_rate": sr,
        "frame_rate": fr,
        "flat_1pt_roi": roi,
        "max_drawdown": max_dd,
        "longest_losing_run": llr,
        "brier_loss": _brier_loss(probs, win_targets) if probs else None,
        "log_loss": _log_loss(probs, win_targets) if probs else None,
        "corr_won": _safe_corr(probs, win_targets) if probs else None,
        "corr_placed": _safe_corr(probs, place_targets) if probs else None,
    }


def _fmt(v, pct: bool = False):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if pct:
        return f"{v:.2f}"
    return f"{v:.4f}" if isinstance(v, float) else str(v)


def _load_top_verdict_observations() -> list[dict]:
    results_by_race: dict[str, dict] = {}
    for path in sorted(DATA.glob("results_2026_04_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for race in payload.get("results", []):
            race_id = race.get("race_id")
            if not race_id:
                continue
            winner = None
            top3 = set()
            sp_map: dict[str, float] = {}
            for runner in race.get("runners", []):
                hid = runner.get("horse_id")
                pos = str(runner.get("position") or "").strip()
                if hid:
                    sp_map[hid] = _f(runner.get("sp_dec"))
                    if pos == "1":
                        winner = hid
                    if pos in {"1", "2", "3"}:
                        top3.add(hid)
            results_by_race[race_id] = {"winner": winner, "placed": top3, "sp_map": sp_map}

    observations: list[dict] = []
    for path in sorted(DATA.glob("velo_prime_verdicts_2026_04_*.json")):
        try:
            verdicts = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in verdicts:
            top = row.get("top") or {}
            race_id = row.get("race_id")
            horse_id = top.get("horse_id")
            res = results_by_race.get(race_id, {})
            observations.append(
                {
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "tier": row.get("tier"),
                    "velo_prime_prob": _f(top.get("velo_prime_prob")),
                    "improvement_score": _f(top.get("improvement_score")),
                    "market_deception_score": _f(top.get("market_deception_score")),
                    "place_prob": _f(top.get("place_prob")),
                    "longshot_prob": _f(top.get("longshot_prob")),
                    "release_day_prob": _f(top.get("release_day_prob")),
                    "comment_intel_score": _f(top.get("comment_intel_score")),
                    "active_components": top.get("active_components") or [],
                    "excluded_from_ensemble": top.get("excluded_from_ensemble") or [],
                    "g_shadow_mode": top.get("g_shadow_mode"),
                    "g_shadow_multiplier": _f(top.get("g_shadow_multiplier")),
                    "result_matched": bool(res),
                    "won": 1.0 if horse_id and horse_id == res.get("winner") else 0.0 if res else None,
                    "placed": 1.0 if horse_id and horse_id in res.get("placed", set()) else 0.0 if res else None,
                    "sp_decimal": res.get("sp_map", {}).get(horse_id),
                }
            )
    return observations


def _register_signal(board: list[dict], name: str, status: str, live_weight, obs: list[Observation], *,
                     coverage_base: int | None = None, leakage_risk="none",
                     duplicate_risk="low", forward_status="not_started", recommendation="KEEP_SHADOW",
                     reason="", operating_role="", rank_hint: int = 0):
    m = _metrics(obs)
    coverage = (m["sample_size"] / coverage_base * 100.0) if coverage_base else None
    board.append(
        {
            "signal_name": name,
            "current_status": status,
            "current_live_weight": live_weight,
            "sample_size": m["sample_size"],
            "result_matched_sample_size": m["matched_sample_size"],
            "strike_rate": m["strike_rate"],
            "frame_rate": m["frame_rate"],
            "flat_1pt_roi": m["flat_1pt_roi"],
            "max_drawdown": m["max_drawdown"],
            "longest_losing_run": m["longest_losing_run"],
            "brier_log_loss_impact": "",
            "corr_won": m["corr_won"],
            "corr_placed": m["corr_placed"],
            "coverage_percentage": coverage,
            "leakage_risk": leakage_risk,
            "duplicate_contamination_risk": duplicate_risk,
            "forward_test_status": forward_status,
            "matched_subset_lift": "",
            "recommendation": recommendation,
            "reason": reason,
            "current_operating_role": operating_role,
            "_rank_hint": rank_hint,
        }
    )


def _from_protocol_rows() -> list[dict]:
    with INNOVATION_PROTOCOL.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _from_shadow_rows() -> list[dict]:
    with RACING_SHADOW.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _from_execution_rows() -> list[dict]:
    with EXECUTION_LEDGER.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_board() -> list[dict]:
    board: list[dict] = []
    verdict_obs = _load_top_verdict_observations()
    coverage_base = len(verdict_obs)

    def verdict_filter(fn) -> list[Observation]:
        out: list[Observation] = []
        for row in verdict_obs:
            if fn(row):
                out.append(
                    Observation(
                        won=row["won"],
                        placed=row["placed"],
                        sp_decimal=row["sp_decimal"],
                        velo_prime_prob=row["velo_prime_prob"],
                        result_matched=row["result_matched"],
                    )
                )
        return out

    _register_signal(
        board, "improvement_score / IMPROVE_HIGH", "STORED_ONLY", "",
        verdict_filter(lambda r: (r["improvement_score"] or 0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="operator_visible_only",
        recommendation="CANDIDATE_FOR_WEIGHT_REVIEW",
        reason="Strong evidence signal, but explicitly disabled in live ensemble pending formal review.",
        operating_role="Strong evidence but not live-weighted",
        rank_hint=1,
    )
    _register_signal(
        board, "market_deception_score / MDS_HIGH", "LIVE_WEIGHTED", "0.10",
        verdict_filter(lambda r: (r["market_deception_score"] or 0) > 0.50),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live",
        recommendation="KEEP_LIVE",
        reason="Best live sidecar with strong closed-result evidence.",
        operating_role="Best live sidecar",
        rank_hint=2,
    )
    _register_signal(
        board, "place_prob / PLACE_PROB_HIGH", "LIVE_WEIGHTED", "0.08",
        verdict_filter(lambda r: (r["place_prob"] or 0) > 0.80),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live",
        recommendation="KEEP_LIVE",
        reason="Positive support signal with large coverage; useful for stability and frame support.",
        operating_role="Best support sidecar",
        rank_hint=3,
    )
    _register_signal(
        board, "longshot_score", "LIVE_WEIGHTED", "0.07_gated",
        verdict_filter(lambda r: (r["longshot_prob"] or 0) > 0.35 and (r["sp_decimal"] or 0) >= 10.0),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live_gated",
        recommendation="KEEP_LIVE",
        reason="Contributes only in genuine longshot context; already constrained appropriately.",
        operating_role="Situational live sidecar",
        rank_hint=4,
    )
    _register_signal(
        board, "release_day_prob", "STORED_ONLY", "",
        verdict_filter(lambda r: (r["release_day_prob"] or 0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="observability_only",
        recommendation="DO_NOT_PROMOTE",
        reason="Declared weight exists in code but component is disabled and not currently a production driver.",
        operating_role="Observability only",
        rank_hint=12,
    )
    _register_signal(
        board, "comment_intel_score", "STORED_ONLY", "",
        verdict_filter(lambda r: (r["comment_intel_score"] or 0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="observability_only",
        recommendation="DO_NOT_PROMOTE",
        reason="Disabled in ensemble and not proven as a live driver.",
        operating_role="Observability only",
        rank_hint=13,
    )
    _register_signal(
        board, "Playbook G shadow", "SHADOW_ONLY", "",
        verdict_filter(lambda r: bool(r["g_shadow_mode"])),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="shadow_logging_only",
        recommendation="KEEP_SHADOW",
        reason="Explicitly shadow-only in code; no live probability impact.",
        operating_role="Shadow modifier only",
        rank_hint=10,
    )
    _register_signal(
        board, "B_LOW_VP_SUPPRESS / suppress flags", "OPERATOR_VISIBLE", "",
        verdict_filter(lambda r: r["tier"] == "B" and (r["velo_prime_prob"] or 0) < 0.30),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live_warning",
        recommendation="FREEZE",
        reason="Confirmed drag zone; should suppress overconfidence rather than be promoted.",
        operating_role="Suppress and warning layer",
        rank_hint=8,
    )

    protocol_rows = _from_protocol_rows()
    def protocol_obs(filter_fn) -> list[Observation]:
        out = []
        for row in protocol_rows:
            if filter_fn(row):
                out.append(
                    Observation(
                        won=_f(row.get("won")),
                        placed=_f(row.get("placed")),
                        sp_decimal=_f(row.get("sp_decimal")),
                        velo_prime_prob=_f(row.get("model_probability")),
                        result_matched=row.get("result_position", "") != "",
                    )
                )
        return out

    _register_signal(
        board, "router_v1_shadow_pass", "SHADOW_ONLY", "",
        protocol_obs(lambda r: _b(r.get("router_v1_shadow_pass"))),
        coverage_base=len(protocol_rows),
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="shadow_ledger",
        recommendation="KEEP_SHADOW",
        reason="Positive lane evidence but still route-shadow only.",
        operating_role="Shadow routing candidate",
        rank_hint=6,
    )
    _register_signal(
        board, "router_v2_class4_shadow_pass", "CANDIDATE_FOR_LIVE_REVIEW", "",
        protocol_obs(lambda r: _b(r.get("router_v2_class4_shadow_pass"))),
        coverage_base=len(protocol_rows),
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="shadow_ledger",
        recommendation="PROMOTE_TO_PAPER_TEST",
        reason="Strong early lane with n below full gate; keep accumulating.",
        operating_role="Router lane watchlist",
        rank_hint=5,
    )
    _register_signal(
        board, "router_v6_gold_seam_watchlist", "SHADOW_ONLY", "",
        protocol_obs(lambda r: _b(r.get("router_v6_gold_seam_watchlist"))),
        coverage_base=len(protocol_rows),
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="watchlist",
        recommendation="KEEP_SHADOW",
        reason="Insufficient sample; no promotion path yet.",
        operating_role="Watchlist only",
        rank_hint=14,
    )

    shadow_rows = _from_shadow_rows()
    def shadow_metric_obs(key: str, threshold: float = 0.50) -> list[Observation]:
        out = []
        for row in shadow_rows:
            if (_f(row.get(key)) or 0) >= threshold:
                out.append(
                    Observation(
                        won=_f(row.get("won")),
                        placed=_f(row.get("placed")),
                        sp_decimal=_f(row.get("sp_decimal")),
                        velo_prime_prob=_f(row.get("velo_prime_prob")),
                        result_matched=row.get("result_position", "") != "",
                    )
                )
        return out

    _register_signal(
        board, "Racing API enrichment shadow score", "SHADOW_ONLY", "",
        shadow_metric_obs("racing_api_enrichment_shadow_score", 0.50),
        coverage_base=len(shadow_rows),
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Retrospective strength exists but leakage risk is explicitly active.",
        operating_role="Forward-test only",
        rank_hint=7,
    )
    _register_signal(
        board, "Racing API connection shadow score", "SHADOW_ONLY", "",
        shadow_metric_obs("racing_api_connection_shadow_score", 0.50),
        coverage_base=len(shadow_rows),
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Leakage-flagged retrospective enrichment; no scoring impact allowed.",
        operating_role="Forward-test only",
        rank_hint=11,
    )
    _register_signal(
        board, "Racing API course shadow score", "SHADOW_ONLY", "",
        shadow_metric_obs("racing_api_course_shadow_score", 0.50),
        coverage_base=len(shadow_rows),
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Retrospective signal, but leakage risk blocks promotion.",
        operating_role="Forward-test only",
        rank_hint=15,
    )
    _register_signal(
        board, "Racing API distance shadow score", "SHADOW_ONLY", "",
        shadow_metric_obs("racing_api_distance_shadow_score", 0.50),
        coverage_base=len(shadow_rows),
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Retrospective signal, but leakage risk blocks promotion.",
        operating_role="Forward-test only",
        rank_hint=16,
    )

    execution_rows = _from_execution_rows()
    def exec_obs(filter_fn) -> list[Observation]:
        out = []
        for row in execution_rows:
            if filter_fn(row):
                out.append(
                    Observation(
                        won=_f(row.get("won")),
                        placed=_f(row.get("placed")),
                        sp_decimal=_f(row.get("sp_decimal")),
                        velo_prime_prob=_f(row.get("velo_prime_prob")),
                        result_matched=row.get("result_position", "") != "",
                    )
                )
        return out

    _register_signal(
        board, "POWER_ANCHOR_MODE paper directives", "PAPER_ONLY", "",
        exec_obs(lambda r: (r.get("directive_type") or "") == "POWER_ANCHOR_MODE"),
        coverage_base=len(execution_rows),
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="paper_only",
        recommendation="PROMOTE_TO_PAPER_TEST",
        reason="Paper evidence is positive but n is far too small for any live discussion.",
        operating_role="Paper execution gate only",
        rank_hint=9,
    )
    _register_signal(
        board, "WATCH_ONLY paper directives", "PAPER_ONLY", "",
        exec_obs(lambda r: (r.get("directive_type") or "") == "WATCH_ONLY"),
        coverage_base=len(execution_rows),
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="paper_only",
        recommendation="KEEP_SHADOW",
        reason="Watch-only paper directives are evidence context, not probability signals.",
        operating_role="Paper watch layer",
        rank_hint=17,
    )

    board.sort(key=lambda r: (r["_rank_hint"], -(r["strike_rate"] or -999), -(r["sample_size"] or 0)))
    return board


def write_outputs(board: list[dict]) -> None:
    fieldnames = [
        "signal_name", "current_status", "current_live_weight", "sample_size",
        "result_matched_sample_size", "strike_rate", "frame_rate", "flat_1pt_roi",
        "max_drawdown", "longest_losing_run", "brier_log_loss_impact", "corr_won",
        "corr_placed", "coverage_percentage", "leakage_risk",
        "duplicate_contamination_risk", "forward_test_status",
        "matched_subset_lift", "recommendation", "reason", "current_operating_role",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in board:
            clean = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean)

    lines = [
        "# VÉLØ Signal Promotion Board",
        "",
        "Generated: 2026-04-30",
        "",
        "## Summary",
        "",
        "- This board ranks candidate signals by current role, evidence, and promotion readiness.",
        "- It does **not** change live scoring, router logic, or staking.",
        "",
        "## Board",
        "",
        "| Signal | Status | Weight | n | matched n | SR | Frame | ROI | Recommendation | Reason |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in board:
        lines.append(
            f"| {row['signal_name']} | {row['current_status']} | {row['current_live_weight']} | "
            f"{row['sample_size']} | {row['result_matched_sample_size']} | "
            f"{_fmt(row['strike_rate'], True)} | {_fmt(row['frame_rate'], True)} | "
            f"{_fmt(row['flat_1pt_roi'], True)} | {row['recommendation']} | {row['reason']} |"
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    board = build_board()
    write_outputs(board)
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
