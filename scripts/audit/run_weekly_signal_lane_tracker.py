#!/usr/bin/env python3
"""
RUN_WEEKLY_SIGNAL_LANE_TRACKER_V1

Computes weekly named signal lane performance and delta vs last saved snapshot.
Run every Sunday or after 100+ new training rows are added.

What it tracks:
  - per-lane n, SR, frame, ROI
  - delta from previous snapshot
  - promotion status
  - collapse warning (SR drops >5pp vs reference)
  - sample warning (n < min_n_meaningful)
  - 2K corpus milestone progress

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Outputs:
    data/reports/weekly_signal_lane_tracker_latest.json
    data/reports/weekly_signal_lane_tracker_latest.md
    data/reports/weekly_signal_lane_tracker_YYYY_MM_DD.json  (dated snapshot)

Usage:
    python scripts/run_weekly_signal_lane_tracker.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

GLOBAL_SR = 19.7
GLOBAL_FRAME = 51.7
TARGET_2K = 2000

# Reference values from 2026-05-17 baseline (1310-row corpus)
SR_REFERENCE = {
    "MDS_HIGH_LANE": 69.2,
    "IMPROVER_LANE": 42.1,
    "VP40_LANE": 45.3,
    "VP40_TIER_A_LANE": 44.7,
    "SHORTFAV_VP30": 52.2,
    "MIDPRICE_ROUTER_QUAL": 33.3,
    "MIDPRICE_SUPPRESS": 16.0,
    "LONGSHOT_SUPPRESS": 6.3,
}

COLLAPSE_THRESHOLD_PP = 5.0  # SR drop >5pp from reference triggers warning

LANE_DEFINITIONS = {
    "MDS_HIGH_LANE": {"min_n": 50, "description": "VP>=0.30 AND MDS>0.50"},
    "IMPROVER_LANE": {"min_n": 50, "description": "VP>=0.30 AND improvement>0.40"},
    "VP40_LANE": {"min_n": 50, "description": "VP>=0.40"},
    "VP40_TIER_A_LANE": {"min_n": 30, "description": "VP>=0.40 AND tier A"},
    "SHORTFAV_VP30": {"min_n": 30, "description": "SP<3.0 AND VP>=0.30"},
    "MIDPRICE_ROUTER_QUAL": {"min_n": 30, "description": "SP 3.0-8.5 AND router qualified"},
    "MIDPRICE_SUPPRESS": {"min_n": 50, "description": "SP 3.0-8.5 AND no router"},
    "LONGSHOT_SUPPRESS": {"min_n": 50, "description": "SP>8.5"},
}


def _apply_filter(df: pd.DataFrame, lane: str) -> pd.DataFrame:
    vp = df["velo_prime_prob"]
    mds = df["market_deception_score"]
    imp = df["improvement_score"]
    sp = df["sp_decimal"]
    tier = df["decision_tier"]
    rq = df["router_qualified"]

    if lane == "MDS_HIGH_LANE":
        return df[(vp >= 0.30) & (mds > 0.50)]
    if lane == "IMPROVER_LANE":
        return df[(vp >= 0.30) & (imp > 0.40)]
    if lane == "VP40_LANE":
        return df[vp >= 0.40]
    if lane == "VP40_TIER_A_LANE":
        return df[(vp >= 0.40) & (tier == "A")]
    if lane == "SHORTFAV_VP30":
        return df[(sp < 3.0) & (vp >= 0.30)]
    if lane == "MIDPRICE_ROUTER_QUAL":
        return df[(sp >= 3.0) & (sp <= 8.5) & rq]
    if lane == "MIDPRICE_SUPPRESS":
        return df[(sp >= 3.0) & (sp <= 8.5) & ~rq]
    if lane == "LONGSHOT_SUPPRESS":
        return df[sp > 8.5]
    return df


def _lane_stats(df: pd.DataFrame, lane: str) -> dict:
    n = len(df)
    defn = LANE_DEFINITIONS[lane]
    ref_sr = SR_REFERENCE.get(lane)

    if n == 0:
        return {
            "lane": lane, "n": 0, "wins": 0, "placed": 0,
            "sr": 0.0, "frame": 0.0, "roi": None,
            "avg_sp": None, "median_sp": None,
            "sr_delta": None, "frame_delta": None,
            "sample_warning": True,
            "collapse_warning": False,
            "promotion_status": "INSUFFICIENT_SAMPLE",
            "description": defn["description"],
        }

    wins = int(df["won"].sum())
    placed = int(df["placed"].sum())
    sr = round(wins / n * 100, 1)
    frame = round(placed / n * 100, 1)
    sr_delta = round(sr - GLOBAL_SR, 1)
    frame_delta = round(frame - GLOBAL_FRAME, 1)

    sp_vals = df["sp_decimal"].dropna()
    avg_sp = round(float(sp_vals.mean()), 2) if len(sp_vals) else None
    med_sp = round(float(sp_vals.median()), 2) if len(sp_vals) else None

    winner_sps = df[df["won"]]["sp_decimal"].dropna()
    roi = round((float(winner_sps.sum()) - n) / n * 100, 1) if len(winner_sps) else None

    # Promotion status
    if n < 20:
        promo = "INSUFFICIENT_SAMPLE"
    elif lane in ("MIDPRICE_SUPPRESS", "LONGSHOT_SUPPRESS"):
        promo = "SUPPRESS_CONFIRMED" if sr < 17 else "SUPPRESS_WATCH"
    elif sr_delta >= 15 and frame >= 70:
        promo = "PROVEN"
    elif sr_delta >= 8 and frame >= 60:
        promo = "SHADOW_POLICY_CANDIDATE"
    elif sr_delta >= 2:
        promo = "ADVISORY_ONLY"
    elif sr_delta < -5 or sr < 12:
        promo = "SUPPRESS"
    elif n < defn["min_n"]:
        promo = "NEEDS_MORE_DATA"
    else:
        promo = "ADVISORY_ONLY"

    # Collapse warning: SR dropped >5pp from reference at same or larger n
    collapse_warning = False
    if ref_sr is not None and n >= 20:
        collapse_warning = (ref_sr - sr) > COLLAPSE_THRESHOLD_PP

    return {
        "lane": lane,
        "n": n,
        "wins": wins,
        "placed": placed,
        "sr": sr,
        "frame": frame,
        "roi": roi,
        "avg_sp": avg_sp,
        "median_sp": med_sp,
        "sr_delta": sr_delta,
        "frame_delta": frame_delta,
        "sample_warning": n < defn["min_n"],
        "collapse_warning": collapse_warning,
        "promotion_status": promo,
        "description": defn["description"],
    }


def _load_corpus() -> pd.DataFrame:
    path = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"
    df = pd.read_parquet(path)
    df = df[df["result_matched"] == True].copy()
    for col in ["velo_prime_prob", "market_deception_score", "improvement_score",
                "place_prob", "sp_decimal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    df["router_qualified"] = (
        df.get("router_v1_shadow_pass", False) |
        df.get("router_v2_class4_shadow_pass", False) |
        df.get("router_v6_gold_seam_watchlist", False)
    ).fillna(False).astype(bool)
    return df


def _load_previous_snapshot() -> dict | None:
    """Load the most recent dated snapshot (not latest) for delta calculation."""
    snapshots = sorted(REPORTS_DIR.glob("weekly_signal_lane_tracker_2026_*.json"))
    if not snapshots:
        return None
    try:
        return json.loads(snapshots[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _compute_delta(current: dict, previous: dict | None) -> dict:
    if previous is None:
        return {"delta_n": None, "delta_sr": None, "delta_frame": None}
    prev_lanes = {r["lane"]: r for r in previous.get("lanes", [])}
    prev_stats = prev_lanes.get(current["lane"], {})
    return {
        "delta_n": (current["n"] - prev_stats["n"]) if prev_stats.get("n") is not None else None,
        "delta_sr": round((current["sr"] - prev_stats["sr"]), 1) if prev_stats.get("sr") is not None else None,
        "delta_frame": round((current["frame"] - prev_stats["frame"]), 1) if prev_stats.get("frame") is not None else None,
        "prev_promo": prev_stats.get("promotion_status"),
    }


def _corpus_progress() -> dict:
    manifest_path = DATA / "training" / "sigma_2k_training_manifest_latest.json"
    n = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            n = int(manifest.get("result_matched_rows") or manifest.get("rows_with_results", 0))
        except Exception:
            pass
    if n is None:
        try:
            df = pd.read_parquet(DATA / "training" / "sigma_2k_training_dataset_latest.parquet",
                                  columns=["result_matched"])
            n = int(df["result_matched"].sum())
        except Exception:
            n = 1310  # fallback to known baseline
    return {
        "training_safe_rows": n,
        "milestone_2k": TARGET_2K,
        "rows_to_2k": TARGET_2K - n,
        "pct_to_2k": round(n / TARGET_2K * 100, 1),
    }


def _build_md(results: list[dict], corpus: dict, prev_ts: str | None,
              run_ts: str, date: str, n_total: int) -> str:
    lines = [
        "# VELO WEEKLY SIGNAL LANE TRACKER",
        f"**Run:** {run_ts}",
        f"**Date:** {date}",
        f"**Training rows (with results):** {n_total}",
        f"**Previous snapshot:** {prev_ts or 'None (first run)'}",
        "",
        "---",
        "",
        "## 2K Milestone Progress",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Training-safe rows | **{corpus['training_safe_rows']}** |",
        f"| Target | {corpus['milestone_2k']} |",
        f"| Remaining | {corpus['rows_to_2k']} |",
        f"| Progress | **{corpus['pct_to_2k']}%** |",
        "",
        "---",
        "",
        "## Lane Performance This Week",
        "",
        "| Lane | n | SR | Frame | ROI | SR Δ | Frame Δ | wk n Δ | wk SR Δ | Status | Flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        sr_d = f"{r['sr_delta']:+.1f}pp" if r.get("sr_delta") is not None else "—"
        fr_d = f"{r['frame_delta']:+.1f}pp" if r.get("frame_delta") is not None else "—"
        roi = f"{r['roi']:+.1f}%" if r.get("roi") is not None else "—"
        wk_n = f"+{r['delta_n']}" if r.get("delta_n") else "—"
        wk_sr = f"{r['delta_sr']:+.1f}pp" if r.get("delta_sr") is not None else "—"
        flags = []
        if r.get("sample_warning"):
            flags.append("⚠️ n<min")
        if r.get("collapse_warning"):
            flags.append("🔴 COLLAPSE")
        if r.get("prev_promo") and r.get("prev_promo") != r["promotion_status"]:
            flags.append(f"→{r['promotion_status']}")
        flag_str = " ".join(flags) if flags else "—"
        lines.append(
            f"| {r['lane']} | {r['n']} | {r['sr']}% | {r['frame']}% | {roi} | "
            f"{sr_d} | {fr_d} | {wk_n} | {wk_sr} | **{r['promotion_status']}** | {flag_str} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Collapse Warnings",
        "",
    ]
    collapses = [r for r in results if r.get("collapse_warning")]
    if collapses:
        for r in collapses:
            ref = SR_REFERENCE.get(r["lane"], "?")
            lines.append(f"- **{r['lane']}**: SR={r['sr']}% vs reference {ref}% (drop={round(ref - r['sr'], 1)}pp) — INVESTIGATE")
    else:
        lines.append("None — all lanes within normal range.")

    lines += [
        "",
        "## Promotion Changes This Week",
        "",
    ]
    promo_changes = [r for r in results if r.get("prev_promo") and r["prev_promo"] != r["promotion_status"]]
    if promo_changes:
        for r in promo_changes:
            lines.append(f"- **{r['lane']}**: {r['prev_promo']} → **{r['promotion_status']}**")
    else:
        lines.append("None — all lanes at same promotion status as last week.")

    lines += [
        "",
        "---",
        "",
        "## Governance Confirmation",
        "",
        "- [ ] No scoring change",
        "- [ ] No model change",
        "- [ ] No router change",
        "- [ ] No staking change",
        "- [ ] No Telegram change",
        "- [ ] No Playbook G promotion",
        "- [ ] No live state mutation",
        "",
        "*RUN_WEEKLY_SIGNAL_LANE_TRACKER_V1 — advisory accumulation only*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print("RUN WEEKLY SIGNAL LANE TRACKER V1")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    previous = _load_previous_snapshot()
    prev_ts = previous.get("run_ts") if previous else None
    print(f"Previous snapshot: {prev_ts or 'None'}")

    df = _load_corpus()
    n_total = len(df)
    print(f"Training rows (with results): {n_total}")

    results = []
    for lane in LANE_DEFINITIONS:
        subset = _apply_filter(df, lane)
        stats = _lane_stats(subset, lane)
        delta = _compute_delta(stats, previous)
        stats.update(delta)
        results.append(stats)
        warn = " COLLAPSE⚠️" if stats.get("collapse_warning") else ""
        wk_sr = f" wk_sr={delta['delta_sr']:+.1f}pp" if delta.get("delta_sr") is not None else ""
        print(f"  {lane:30s}  n={stats['n']:4d}  SR={stats['sr']:5.1f}%  {stats['promotion_status']}{warn}{wk_sr}")

    corpus = _corpus_progress()
    print(f"\n2K Milestone: {corpus['training_safe_rows']}/{corpus['milestone_2k']} ({corpus['pct_to_2k']}%)")

    output = {
        "run_ts": run_ts,
        "date": date,
        "training_rows": n_total,
        "global_sr": GLOBAL_SR,
        "previous_snapshot_ts": prev_ts,
        "lanes": results,
        "corpus_progress": corpus,
        "collapse_warnings": [r["lane"] for r in results if r.get("collapse_warning")],
        "promotion_changes": [
            {"lane": r["lane"], "from": r.get("prev_promo"), "to": r["promotion_status"]}
            for r in results if r.get("prev_promo") and r["prev_promo"] != r["promotion_status"]
        ],
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "ADVISORY_WEEKLY_TRACKING",
        },
    }

    # Write latest
    latest_json = REPORTS_DIR / "weekly_signal_lane_tracker_latest.json"
    latest_json.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {latest_json}")

    latest_md = REPORTS_DIR / "weekly_signal_lane_tracker_latest.md"
    latest_md.write_text(_build_md(results, corpus, prev_ts, run_ts, date, n_total))
    print(f"Written: {latest_md}")

    # Write dated snapshot for delta tracking
    dated_json = REPORTS_DIR / f"weekly_signal_lane_tracker_{date.replace('-', '_')}.json"
    dated_json.write_text(json.dumps(output, indent=2, default=str))
    print(f"Written: {dated_json}")

    return output


if __name__ == "__main__":
    main()
