"""
VÉLØ Signal Promotion Board
===========================

Builds an evidence-to-live governance board from the unified evidence corpus.

Inputs:
  - data/velo_unified_evidence_corpus_v1.csv

Outputs:
  - data/signal_promotion_board_latest.csv
  - data/signal_promotion_board_latest.md

This is an audit/governance script only.
It does not change production scoring, routing, staking, or execution.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CORPUS_CSV = DATA / "velo_unified_evidence_corpus_v1.csv"
OUT_CSV = DATA / "signal_promotion_board_latest.csv"
OUT_MD = DATA / "signal_promotion_board_latest.md"
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class Observation:
    won: float | None = None
    placed: float | None = None
    sp_decimal: float | None = None
    velo_prime_prob: float | None = None
    result_matched: bool = False


def _f(v, default=None):
    if v in (None, ""):
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
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _flat_roi(obs: list[Observation]) -> tuple[float | None, float | None, int | None]:
    pnl = []
    for o in obs:
        if o.sp_decimal is None or not o.result_matched:
            continue
        pnl.append((o.sp_decimal - 1.0) if o.won else -1.0)
    if not pnl:
        return None, None, None
    total = sum(pnl)
    curve = 0.0
    peak = 0.0
    max_dd = 0.0
    losing_run = 0
    longest = 0
    for x in pnl:
        curve += x
        peak = max(peak, curve)
        max_dd = min(max_dd, curve - peak)
        if x < 0:
            losing_run += 1
            longest = max(longest, losing_run)
        else:
            losing_run = 0
    return total / len(pnl), max_dd, longest


def _metrics(obs: list[Observation]) -> dict:
    n = len(obs)
    matched = [o for o in obs if o.result_matched]
    matched_n = len(matched)
    wins = sum(1 for o in matched if o.won)
    places = sum(1 for o in matched if o.placed)
    sr = (wins / matched_n * 100.0) if matched_n else None
    fr = (places / matched_n * 100.0) if matched_n else None
    roi, max_dd, llr = _flat_roi(obs)
    paired = [o for o in matched if o.velo_prime_prob is not None and o.won is not None and o.placed is not None]
    probs = [o.velo_prime_prob for o in paired]
    win_targets = [float(o.won) for o in paired]
    place_targets = [float(o.placed) for o in paired]
    return {
        "sample_size": n,
        "matched_sample_size": matched_n,
        "strike_rate": sr,
        "frame_rate": fr,
        "flat_1pt_roi": roi,
        "max_drawdown": max_dd,
        "longest_losing_run": llr,
        "corr_won": _safe_corr(probs, win_targets) if probs else None,
        "corr_placed": _safe_corr(probs, place_targets) if probs else None,
    }


def _fmt(v, pct: bool = False):
    if v is None:
        return ""
    if pct:
        return f"{v:.2f}"
    return f"{v:.4f}" if isinstance(v, float) else str(v)


def _load_corpus() -> list[dict]:
    with CORPUS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _obs(rows: list[dict]) -> list[Observation]:
    return [
        Observation(
            won=1.0 if _b(r.get("won")) else 0.0 if r.get("won") not in ("", None) else None,
            placed=1.0 if _b(r.get("placed")) else 0.0 if r.get("placed") not in ("", None) else None,
            sp_decimal=_f(r.get("sp_decimal")),
            velo_prime_prob=_f(r.get("velo_prime_prob")),
            result_matched=_b(r.get("result_matched")),
        )
        for r in rows
    ]


def _register_signal(board: list[dict], name: str, status: str, live_weight, rows: list[dict], *,
                     coverage_base: int | None = None, leakage_risk="none",
                     duplicate_risk="low", forward_status="not_started", recommendation="KEEP_SHADOW",
                     reason="", operating_role="", rank_hint: int = 0):
    m = _metrics(_obs(rows))
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


def build_board() -> list[dict]:
    corpus = _load_corpus()
    board: list[dict] = []
    coverage_base = len(corpus)

    def filt(fn):
        return [r for r in corpus if fn(r)]

    _register_signal(
        board, "improvement_score / IMPROVE_HIGH", "STORED_ONLY", "",
        filt(lambda r: (_f(r.get("improvement_score"), 0.0) or 0.0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="operator_visible_only",
        recommendation="HOLD",
        reason="Unified corpus still shows a live-truth gap; hold pending corpus stabilization and ablation.",
        operating_role="Strong evidence but not live-weighted",
        rank_hint=1,
    )
    _register_signal(
        board, "market_deception_score / MDS_HIGH", "LIVE_WEIGHTED", "0.10",
        filt(lambda r: (_f(r.get("market_deception_score"), 0.0) or 0.0) > 0.50),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live",
        recommendation="KEEP_LIVE",
        reason="Best live sidecar with clean evidence in the unified corpus.",
        operating_role="Best live sidecar",
        rank_hint=2,
    )
    _register_signal(
        board, "place_prob / PLACE_PROB_HIGH", "LIVE_WEIGHTED", "0.08",
        filt(lambda r: (_f(r.get("place_prob"), 0.0) or 0.0) > 0.80),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live",
        recommendation="KEEP_LIVE",
        reason="Supportive live sidecar; useful for stability and frame support.",
        operating_role="Best support sidecar",
        rank_hint=3,
    )
    _register_signal(
        board, "longshot_score", "LIVE_WEIGHTED", "0.07_gated",
        filt(lambda r: (_f(r.get("longshot_prob"), 0.0) or 0.0) > 0.35 and (_f(r.get("sp_decimal"), 0.0) or 0.0) >= 10.0),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live_gated",
        recommendation="KEEP_LIVE",
        reason="Gated live component only for genuine longshot context.",
        operating_role="Situational live sidecar",
        rank_hint=4,
    )
    _register_signal(
        board, "release_day_prob", "STORED_ONLY", "",
        filt(lambda r: (_f(r.get("release_day_prob"), 0.0) or 0.0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="observability_only",
        recommendation="DO_NOT_PROMOTE",
        reason="Disabled and not a current production driver.",
        operating_role="Observability only",
        rank_hint=12,
    )
    _register_signal(
        board, "comment_intel_score", "STORED_ONLY", "",
        filt(lambda r: (_f(r.get("comment_intel_score"), 0.0) or 0.0) > 0.40),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="observability_only",
        recommendation="DO_NOT_PROMOTE",
        reason="Disabled and not proven as a production driver.",
        operating_role="Observability only",
        rank_hint=13,
    )
    _register_signal(
        board, "Playbook G shadow", "SHADOW_ONLY", "",
        filt(lambda r: _b(r.get("g_shadow_mode"))),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="shadow_logging_only",
        recommendation="KEEP_SHADOW",
        reason="Shadow-only layer with no live probability impact.",
        operating_role="Shadow modifier only",
        rank_hint=10,
    )
    _register_signal(
        board, "B_LOW_VP_SUPPRESS / suppress flags", "OPERATOR_VISIBLE", "",
        filt(lambda r: _b(r.get("b_low_vp_suppress"))),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="medium",
        forward_status="live_warning",
        recommendation="FREEZE",
        reason="Confirmed drag zone; suppress overconfidence instead of promoting.",
        operating_role="Suppress and warning layer",
        rank_hint=8,
    )
    _register_signal(
        board, "router_v1_shadow_pass", "SHADOW_ONLY", "",
        filt(lambda r: _b(r.get("router_v1_shadow_pass"))),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="shadow_ledger",
        recommendation="KEEP_SHADOW",
        reason="Positive lane evidence, but still route-shadow only.",
        operating_role="Shadow routing candidate",
        rank_hint=6,
    )
    _register_signal(
        board, "router_v2_class4_shadow_pass", "CANDIDATE_FOR_LIVE_REVIEW", "",
        filt(lambda r: _b(r.get("router_v2_class4_shadow_pass"))),
        coverage_base=coverage_base,
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
        filt(lambda r: _b(r.get("router_v6_gold_seam_watchlist"))),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="watchlist",
        recommendation="KEEP_SHADOW",
        reason="Insufficient sample; no promotion path yet.",
        operating_role="Watchlist only",
        rank_hint=14,
    )
    _register_signal(
        board, "Racing API enrichment shadow score", "SHADOW_ONLY", "",
        filt(lambda r: (_f(r.get("racing_api_enrichment_shadow_score"), 0.0) or 0.0) >= 0.50),
        coverage_base=coverage_base,
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Retrospective strength exists but leakage risk remains active.",
        operating_role="Forward-test only",
        rank_hint=7,
    )
    _register_signal(
        board, "Racing API connection shadow score", "SHADOW_ONLY", "",
        filt(lambda r: (_f(r.get("racing_api_connection_shadow_score"), 0.0) or 0.0) >= 0.50),
        coverage_base=coverage_base,
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
        filt(lambda r: (_f(r.get("racing_api_course_shadow_score"), 0.0) or 0.0) >= 0.50),
        coverage_base=coverage_base,
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
        filt(lambda r: (_f(r.get("racing_api_distance_shadow_score"), 0.0) or 0.0) >= 0.50),
        coverage_base=coverage_base,
        leakage_risk="high",
        duplicate_risk="low",
        forward_status="forward_test_started",
        recommendation="KEEP_SHADOW",
        reason="Retrospective signal, but leakage risk blocks promotion.",
        operating_role="Forward-test only",
        rank_hint=16,
    )
    _register_signal(
        board, "POWER_ANCHOR_MODE paper directives", "PAPER_ONLY", "",
        filt(lambda r: _b(r.get("power_anchor_mode"))),
        coverage_base=coverage_base,
        leakage_risk="none",
        duplicate_risk="low",
        forward_status="paper_only",
        recommendation="PROMOTE_TO_PAPER_TEST",
        reason="Paper evidence is positive but still too small for any live discussion.",
        operating_role="Paper execution gate only",
        rank_hint=9,
    )
    _register_signal(
        board, "WATCH_ONLY paper directives", "PAPER_ONLY", "",
        filt(lambda r: _b(r.get("watch_only_mode"))),
        coverage_base=coverage_base,
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
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    lines = [
        "# VÉLØ Signal Promotion Board",
        "",
        f"Generated: {RUN_TS}",
        "",
        "## Summary",
        "",
        "- This board ranks candidate signals by current role, evidence, and promotion readiness.",
        "- It reads the unified evidence corpus only.",
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
            f"{_fmt((row['flat_1pt_roi'] or 0) * 100 if row['flat_1pt_roi'] is not None else None, True)} | "
            f"{row['recommendation']} | {row['reason']} |"
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    board = build_board()
    write_outputs(board)
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
