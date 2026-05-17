#!/usr/bin/env python3
"""
NAMED_LANE_OUTCOME_TRACKER_V1

Tracks every named signal lane from pre-race classification to post-race result.
Closes the candidate → lane → result → SR/frame/ROI loop daily.

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Inputs:
    data/training/sigma_2k_training_dataset_latest.parquet  — historical outcomes
    data/reports/named_lane_operator_card_latest.json       — today's candidates

Outputs:
    data/reports/named_lane_outcome_tracker_latest.json
    data/reports/named_lane_outcome_tracker_latest.md
    data/reports/named_lane_outcome_tracker_YYYY_MM_DD.json  — dated snapshot

Usage:
    python scripts/named_lane_outcome_tracker.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

PARQUET_PATH = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"

# ── Lane definitions ──────────────────────────────────────────────────────────

LANE_DEFS = {
    "MDS_HIGH_LANE":         ("PRIORITY_WATCH", "VP>=0.30 AND MDS>0.50 — crown jewel"),
    "IMPROVER_LANE":         ("PRIORITY_WATCH", "VP>=0.30 AND improvement>0.40"),
    "VP40_TIER_A_LANE":      ("PRIORITY_WATCH", "VP>=0.40 AND tier A"),
    "VP40_LANE":             ("WATCH",           "VP>=0.40"),
    "SHORTFAV_VP30":         ("WATCH",           "SP<3.0 AND VP>=0.30"),
    "MIDPRICE_ROUTER_QUAL":  ("WATCH",           "SP 3.0-8.5 AND router qualified"),
    "MIDPRICE_SUPPRESS":     ("SUPPRESS_ADVISORY", "SP 3.0-8.5 AND no router"),
    "LONGSHOT_SUPPRESS":     ("SUPPRESS_ADVISORY", "SP>8.5"),
}

# SR reference from 2026-05-17 1310-row corpus
SR_REFERENCE = {
    "MDS_HIGH_LANE":        69.2,
    "IMPROVER_LANE":        42.1,
    "VP40_TIER_A_LANE":     44.7,
    "VP40_LANE":            45.3,
    "SHORTFAV_VP30":        52.2,
    "MIDPRICE_ROUTER_QUAL": 33.3,
    "MIDPRICE_SUPPRESS":    16.0,
    "LONGSHOT_SUPPRESS":     6.3,
}

# Promotion gate thresholds per lane: (n_gate, label, sr_floor)
PROMOTION_GATES = {
    "MDS_HIGH_LANE":        [(50, "SHADOW_LANE_TRACKING", 64.0), (100, "shadow_policy_discussion", 60.0)],
    "IMPROVER_LANE":        [(50, "early_review", 37.0), (100, "shadow_policy_discussion", 37.0)],
    "VP40_TIER_A_LANE":     [(100, "confirmed_proven", 40.0), (200, "policy_candidate", 40.0)],
    "VP40_LANE":            [(200, "stability_review", 40.0), (300, "model_weight_discussion", 40.0)],
    "SHORTFAV_VP30":        [(200, "stability_review", 47.0), (300, "model_weight_discussion", 47.0)],
    "MIDPRICE_ROUTER_QUAL": [(50, "advisory_promotion", 30.0), (100, "shadow_policy_discussion", 30.0)],
    "MIDPRICE_SUPPRESS":    [(600, "suppression_review", 0.0)],
    "LONGSHOT_SUPPRESS":    [(500, "suppression_review", 0.0)],
}

COLLAPSE_THRESHOLD_PP = 5.0


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_corpus() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET_PATH)
    df = df[df["result_matched"] == True].copy()
    for col in ["velo_prime_prob", "market_deception_score", "improvement_score",
                "place_prob", "sp_decimal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    df["router_qualified"] = (
        df.get("router_v1_shadow_pass", False)
        | df.get("router_v2_class4_shadow_pass", False)
        | df.get("router_v6_gold_seam_watchlist", False)
    ).fillna(False).astype(bool)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _load_previous_snapshot() -> dict[str, dict]:
    """Load most recent dated snapshot for delta computation."""
    snapshots = sorted(REPORTS_DIR.glob("named_lane_outcome_tracker_2*.json"))
    if not snapshots:
        return {}
    try:
        data = json.loads(snapshots[-1].read_text(encoding="utf-8"))
        return {lane["lane"]: lane for lane in data.get("lanes", [])}
    except Exception:
        return {}


def _load_today_candidates(date: str) -> dict[str, list[str]]:
    """Load today's operator card and return horse names per lane."""
    card_path = REPORTS_DIR / "named_lane_operator_card_latest.json"
    result: dict[str, list[str]] = {lane: [] for lane in LANE_DEFS}
    if not card_path.exists():
        return result
    try:
        data = json.loads(card_path.read_text(encoding="utf-8"))
        if data.get("date") != date:
            return result
        for card in data.get("cards", []):
            for lane in card.get("lanes", []):
                if lane in result:
                    result[lane].append(card.get("horse", "?"))
    except Exception:
        pass
    return result


# ── Lane filter ───────────────────────────────────────────────────────────────

def _apply_lane_filter(df: pd.DataFrame, lane_name: str) -> pd.DataFrame:
    vp = df["velo_prime_prob"]
    mds = df["market_deception_score"]
    imp = df["improvement_score"]
    sp = df["sp_decimal"]
    tier = df["decision_tier"]
    rq = df["router_qualified"]

    if lane_name == "MDS_HIGH_LANE":
        return df[(vp >= 0.30) & (mds > 0.50)]
    if lane_name == "IMPROVER_LANE":
        return df[(vp >= 0.30) & (imp > 0.40)]
    if lane_name == "VP40_LANE":
        return df[vp >= 0.40]
    if lane_name == "VP40_TIER_A_LANE":
        return df[(vp >= 0.40) & (tier == "A")]
    if lane_name == "SHORTFAV_VP30":
        return df[(sp < 3.0) & (vp >= 0.30)]
    if lane_name == "MIDPRICE_ROUTER_QUAL":
        return df[(sp >= 3.0) & (sp <= 8.5) & rq]
    if lane_name == "MIDPRICE_SUPPRESS":
        return df[(sp >= 3.0) & (sp <= 8.5) & ~rq]
    if lane_name == "LONGSHOT_SUPPRESS":
        return df[sp > 8.5]
    return df


# ── Stats computation ─────────────────────────────────────────────────────────

def _longest_losing_run(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    ordered = df.sort_values("date") if "date" in df.columns else df
    results = ordered["won"].tolist()
    max_run = cur_run = 0
    for w in results:
        if not w:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0
    return max_run


def _promotion_gate_status(lane_name: str, n: int, sr: float) -> str:
    gates = PROMOTION_GATES.get(lane_name, [])
    for n_gate, label, sr_floor in reversed(gates):
        if n >= n_gate and sr >= sr_floor:
            return f"GATE_REACHED:{label}"
    if not gates:
        return "NO_GATE_DEFINED"
    lowest_n = gates[0][0]
    return f"PENDING:{gates[0][1]} (need +{max(0, lowest_n - n)} to n={lowest_n})"


def _collapse_flag(sr: float, lane_name: str, n: int) -> dict:
    ref = SR_REFERENCE.get(lane_name)
    if ref is None or n < 20:
        return {"status": "INSUFFICIENT_N", "ref_sr": ref}
    delta = sr - ref
    if delta < -COLLAPSE_THRESHOLD_PP:
        return {"status": "COLLAPSE_WARNING", "ref_sr": ref, "delta_pp": round(delta, 1)}
    return {"status": "STABLE", "ref_sr": ref, "delta_pp": round(delta, 1)}


def _compute_lane_stats(df: pd.DataFrame, lane_name: str) -> dict:
    df_lane = _apply_lane_filter(df, lane_name)
    action, description = LANE_DEFS[lane_name]

    if df_lane.empty:
        return {
            "lane": lane_name, "action": action, "description": description,
            "n": 0, "wins": 0, "frames": 0, "misses": 0,
            "sr": 0.0, "frame_rate": 0.0, "roi": None,
            "avg_sp": None, "median_sp": None,
            "biggest_winner": None, "worst_false_positive": None,
            "longest_losing_run": 0, "sample_warning": True,
            "promotion_gate": "PENDING:n=0",
            "collapse_check": {"status": "INSUFFICIENT_N"},
        }

    n = len(df_lane)
    wins = int(df_lane["won"].sum())
    frames = int(df_lane["placed"].sum())
    misses = n - wins

    sr = round(wins / n * 100, 1)
    frame_rate = round(frames / n * 100, 1)

    sp_col = df_lane["sp_decimal"].dropna()
    avg_sp = round(float(sp_col.mean()), 2) if len(sp_col) else None
    median_sp = round(float(sp_col.median()), 2) if len(sp_col) else None

    winner_sps = df_lane[df_lane["won"]]["sp_decimal"].dropna()
    roi = round((float(winner_sps.sum()) - n) / n * 100, 1) if len(winner_sps) else None

    # Biggest winner
    winner_df = df_lane[df_lane["won"]].sort_values("sp_decimal", ascending=False)
    biggest_winner = None
    if not winner_df.empty:
        w = winner_df.iloc[0]
        biggest_winner = {
            "horse": str(w.get("horse", "?")),
            "sp": round(float(w["sp_decimal"]), 2),
            "vp": round(float(w["velo_prime_prob"]), 3),
            "date": str(w["date"].date()) if hasattr(w.get("date"), "date") else str(w.get("date", "?")),
        }

    # Worst false positive — highest VP among losers
    loser_df = df_lane[~df_lane["won"]].sort_values("velo_prime_prob", ascending=False)
    worst_fp = None
    if not loser_df.empty:
        l = loser_df.iloc[0]
        worst_fp = {
            "horse": str(l.get("horse", "?")),
            "vp": round(float(l["velo_prime_prob"]), 3),
            "sp": round(float(l["sp_decimal"]), 2) if pd.notna(l["sp_decimal"]) else None,
            "date": str(l["date"].date()) if hasattr(l.get("date"), "date") else str(l.get("date", "?")),
        }

    llr = _longest_losing_run(df_lane)
    promo = _promotion_gate_status(lane_name, n, sr)
    collapse = _collapse_flag(sr, lane_name, n)

    return {
        "lane": lane_name,
        "action": action,
        "description": description,
        "n": n,
        "wins": wins,
        "frames": frames,
        "misses": misses,
        "sr": sr,
        "frame_rate": frame_rate,
        "roi": roi,
        "avg_sp": avg_sp,
        "median_sp": median_sp,
        "biggest_winner": biggest_winner,
        "worst_false_positive": worst_fp,
        "longest_losing_run": llr,
        "sample_warning": n < 50,
        "promotion_gate": promo,
        "collapse_check": collapse,
    }


# ── Delta computation ─────────────────────────────────────────────────────────

def _compute_delta(current: dict, previous: dict[str, dict]) -> dict:
    if not previous:
        return {}
    lane = current["lane"]
    prev = previous.get(lane)
    if not prev:
        return {}
    delta_n = current["n"] - prev.get("n", current["n"])
    delta_sr = round(current["sr"] - prev.get("sr", current["sr"]), 1)
    return {"delta_n": delta_n, "delta_sr": delta_sr, "prev_n": prev.get("n")}


# ── Markdown builder ──────────────────────────────────────────────────────────

def _build_md(lanes: list[dict], today_candidates: dict, date: str, run_ts: str) -> str:
    lines = [
        "# NAMED LANE OUTCOME TRACKER",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        "",
        "Advisory only. No scoring change. No model change. No staking.",
        "",
        "---",
        "",
        "## Cumulative Lane Outcomes (from training corpus)",
        "",
        "| Lane | Action | n | Wins | SR | Frame | ROI | Avg SP | LLR | Gate | Collapse |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for lane in lanes:
        gate = lane["promotion_gate"]
        gate_short = gate.split(":")[0] if ":" in gate else gate
        collapse = lane["collapse_check"]
        collapse_str = collapse.get("status", "?")
        if "delta_pp" in collapse:
            collapse_str += f" ({collapse['delta_pp']:+.1f}pp)"
        roi_str = f"{lane['roi']:+.1f}%" if lane["roi"] is not None else "—"
        avg_sp_str = str(lane["avg_sp"]) if lane["avg_sp"] else "—"
        warn = " ⚠️" if lane["sample_warning"] else ""
        lines.append(
            f"| {lane['lane']}{warn} | {lane['action']} | {lane['n']} | {lane['wins']} "
            f"| {lane['sr']}% | {lane['frame_rate']}% | {roi_str} | {avg_sp_str} "
            f"| {lane['longest_losing_run']} | {gate_short} | {collapse_str} |"
        )
    lines.append("")

    # Per-lane detail
    for lane in lanes:
        lines += [
            f"## {lane['lane']}",
            "",
            f"*{lane['description']}*",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| n (resulted) | {lane['n']}{' ⚠️ sample warning' if lane['sample_warning'] else ''} |",
            f"| Wins | {lane['wins']} |",
            f"| Frames/placed | {lane['frames']} |",
            f"| Misses | {lane['misses']} |",
            f"| Strike rate | {lane['sr']}% |",
            f"| Frame rate | {lane['frame_rate']}% |",
            f"| ROI (flat £1) | {(str(lane['roi']) + '%') if lane['roi'] is not None else '—'} |",
            f"| Avg SP | {lane['avg_sp'] or '—'} |",
            f"| Median SP | {lane['median_sp'] or '—'} |",
            f"| Longest losing run | {lane['longest_losing_run']} |",
            f"| Promotion gate | {lane['promotion_gate']} |",
            f"| Collapse check | {lane['collapse_check']['status']}"
            + (f" ({lane['collapse_check'].get('delta_pp', 0):+.1f}pp vs {lane['collapse_check'].get('ref_sr')}% ref)" if "delta_pp" in lane["collapse_check"] else "") + " |",
        ]

        if lane.get("delta"):
            d = lane["delta"]
            lines.append(f"| Delta vs prev snapshot | n: {d.get('prev_n')} → {lane['n']} (+{d.get('delta_n', 0)}) | SR delta: {d.get('delta_sr', 0):+.1f}pp |")

        if lane["biggest_winner"]:
            bw = lane["biggest_winner"]
            lines.append(f"| Biggest winner | {bw['horse']} SP={bw['sp']} VP={bw['vp']} ({bw['date']}) |")

        if lane["worst_false_positive"]:
            wf = lane["worst_false_positive"]
            sp_str = f"SP={wf['sp']}" if wf["sp"] else ""
            lines.append(f"| Worst false positive | {wf['horse']} VP={wf['vp']} {sp_str} ({wf['date']}) |")

        lines.append("")

        # Today's candidates for this lane
        cands = today_candidates.get(lane["lane"], [])
        if cands:
            lines.append(f"**Today's candidates ({len(cands)}):** {', '.join(cands[:10])}")
        else:
            lines.append("**Today's candidates:** none")
        lines.append("")

    # Footer
    lines += [
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE",
        "NO_MODEL_CHANGE",
        "NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE",
        "NO_TELEGRAM_CHANGE",
        "NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION",
        "ADVISORY_TRACKING_ONLY",
        "```",
        "",
        "*NAMED_LANE_OUTCOME_TRACKER_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"NAMED LANE OUTCOME TRACKER V1 — {date}")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    if not PARQUET_PATH.exists():
        print(f"  ERROR: training parquet not found — {PARQUET_PATH}")
        return

    df = _load_corpus()
    print(f"  Corpus rows: {len(df)} (result_matched=True)")

    previous = _load_previous_snapshot()
    today_candidates = _load_today_candidates(date)

    lanes = []
    for lane_name in LANE_DEFS:
        stats = _compute_lane_stats(df, lane_name)
        stats["delta"] = _compute_delta(stats, previous)
        lanes.append(stats)

    # Console summary
    print(f"\n{'Lane':<24} {'n':>5} {'SR':>7} {'Frame':>7} {'ROI':>7}  {'Gate'}")
    print("-" * 80)
    for lane in lanes:
        roi_str = f"{lane['roi']:+.1f}%" if lane["roi"] is not None else "    —"
        gate_raw = lane["promotion_gate"]
        gate_display = gate_raw.split(":")[1] if ":" in gate_raw else gate_raw
        warn = "⚠" if lane["sample_warning"] else " "
        delta_str = ""
        if lane.get("delta") and lane["delta"].get("delta_n", 0) > 0:
            delta_str = f"  [+{lane['delta']['delta_n']}n {lane['delta']['delta_sr']:+.1f}pp]"
        print(f"  {warn}{lane['lane']:<23} {lane['n']:>5} {lane['sr']:>6.1f}% {lane['frame_rate']:>6.1f}% {roi_str:>7}  {gate_display}{delta_str}")

    # Collapse warnings
    collapses = [l for l in lanes if l["collapse_check"]["status"] == "COLLAPSE_WARNING"]
    if collapses:
        print(f"\n*** COLLAPSE WARNING: {', '.join(l['lane'] for l in collapses)}")

    # Build outputs
    output = {
        "run_ts": run_ts,
        "date": date,
        "corpus_rows": len(df),
        "lanes": [
            {k: v for k, v in lane.items() if k != "delta"} for lane in lanes
        ],
        "deltas": {
            lane["lane"]: lane["delta"] for lane in lanes if lane.get("delta")
        },
        "today_candidates": today_candidates,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "ADVISORY_TRACKING_ONLY",
        },
    }

    json_path = REPORTS_DIR / "named_lane_outcome_tracker_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(lanes, today_candidates, date, run_ts)
    md_path = REPORTS_DIR / "named_lane_outcome_tracker_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    # Dated snapshot
    date_tag = date.replace("-", "_")
    snap_path = REPORTS_DIR / f"named_lane_outcome_tracker_{date_tag}.json"
    snap_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"Written: {snap_path}")

    return output


if __name__ == "__main__":
    main()
