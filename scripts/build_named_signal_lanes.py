#!/usr/bin/env python3
"""
BUILD_NAMED_SIGNAL_LANES_V1

Computes per-lane statistics from the SIGMA_2K_SAFE_TRAINING_SLICE_V1 corpus
and identifies today's candidates in each named lane.

Lanes tracked:
  MDS_HIGH_LANE          — VP>=0.30 and MDS>0.50
  IMPROVER_LANE          — VP>=0.30 and improvement>0.40
  VP40_LANE              — VP>=0.40
  VP40_TIER_A_LANE       — VP>=0.40 and tier A
  SHORTFAV_VP30          — SP<3.0 and VP>=0.30
  MIDPRICE_ROUTER_QUAL   — SP 3.0–8.5 and router qualified (V1/V2/V6)
  MIDPRICE_SUPPRESS      — SP 3.0–8.5 and no router qualification
  LONGSHOT_SUPPRESS      — SP>8.5

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Outputs:
    data/reports/named_signal_lanes_latest.json
    data/reports/named_signal_lanes_latest.md

Usage:
    python scripts/build_named_signal_lanes.py [--date YYYY-MM-DD]
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

GLOBAL_SR = 19.7
GLOBAL_FRAME = 51.7
TARGET_2K = 2000

LANE_DEFINITIONS = {
    "MDS_HIGH_LANE": {
        "description": "VP>=0.30 AND MDS>0.50 — crown jewel signal",
        "promotion_target": "SHADOW_LANE_TRACKING",
        "min_n_meaningful": 50,
    },
    "IMPROVER_LANE": {
        "description": "VP>=0.30 AND improvement_score>0.40",
        "promotion_target": "SHADOW_LANE_TRACKING",
        "min_n_meaningful": 50,
    },
    "VP40_LANE": {
        "description": "VP>=0.40",
        "promotion_target": "WATCH",
        "min_n_meaningful": 50,
    },
    "VP40_TIER_A_LANE": {
        "description": "VP>=0.40 AND tier A",
        "promotion_target": "WATCH",
        "min_n_meaningful": 30,
    },
    "SHORTFAV_VP30": {
        "description": "SP<3.0 AND VP>=0.30 — short-price + high conviction",
        "promotion_target": "WATCH",
        "min_n_meaningful": 30,
    },
    "MIDPRICE_ROUTER_QUAL": {
        "description": "SP 3.0–8.5 AND router qualified (V1/V2/V6)",
        "promotion_target": "SHADOW_LANE_TRACKING",
        "min_n_meaningful": 30,
    },
    "MIDPRICE_SUPPRESS": {
        "description": "SP 3.0–8.5 AND no router — advisory suppression",
        "promotion_target": "SUPPRESS_ADVISORY",
        "min_n_meaningful": 50,
    },
    "LONGSHOT_SUPPRESS": {
        "description": "SP>8.5 — confirmed dead zone",
        "promotion_target": "SUPPRESS",
        "min_n_meaningful": 50,
    },
}


def _promotion_status(n: int, sr: float, frame: float, definition: dict) -> str:
    if n < 20:
        return "INSUFFICIENT_SAMPLE"
    lift = sr - GLOBAL_SR
    target = definition["promotion_target"]
    if target == "SUPPRESS_ADVISORY" or target == "SUPPRESS":
        if sr < 17:
            return "SUPPRESS_CONFIRMED"
        return "SUPPRESS_WATCH"
    if lift >= 15 and frame >= 70:
        return "PROVEN"
    if lift >= 8 and frame >= 60:
        return "SHADOW_POLICY_CANDIDATE"
    if lift >= 2:
        return "ADVISORY_ONLY"
    if lift < -5 or sr < 12:
        return "SUPPRESS"
    if n < definition.get("min_n_meaningful", 50):
        return "NEEDS_MORE_DATA"
    return "ADVISORY_ONLY"


def _lane_stats(df: pd.DataFrame, lane_name: str, definition: dict) -> dict:
    n = len(df)
    if n == 0:
        return {
            "lane": lane_name,
            "n": 0,
            "wins": 0,
            "placed": 0,
            "sr": 0.0,
            "frame": 0.0,
            "roi": None,
            "avg_sp": None,
            "median_sp": None,
            "sr_delta": None,
            "frame_delta": None,
            "sample_warning": True,
            "promotion_status": "INSUFFICIENT_SAMPLE",
            "description": definition["description"],
        }

    wins = int(df["won"].sum())
    placed = int(df["placed"].sum())
    sr = round(wins / n * 100, 1)
    frame = round(placed / n * 100, 1)

    sp_col = df["sp_decimal"].dropna()
    avg_sp = round(float(sp_col.mean()), 2) if len(sp_col) else None
    med_sp = round(float(sp_col.median()), 2) if len(sp_col) else None

    winner_sps = df[df["won"]]["sp_decimal"].dropna()
    roi = round((float(winner_sps.sum()) - n) / n * 100, 1) if len(winner_sps) else None

    sr_delta = round(sr - GLOBAL_SR, 1)
    frame_delta = round(frame - GLOBAL_FRAME, 1)
    promo = _promotion_status(n, sr, frame, definition)

    return {
        "lane": lane_name,
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
        "sample_warning": n < definition.get("min_n_meaningful", 50),
        "promotion_status": promo,
        "description": definition["description"],
    }


def _apply_lane_filter(df: pd.DataFrame, lane_name: str) -> pd.DataFrame:
    vp = df["velo_prime_prob"]
    mds = df["market_deception_score"]
    imp = df["improvement_score"]
    sp = df["sp_decimal"]
    tier = df["decision_tier"]
    router_q = df["router_qualified"]

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
        return df[(sp >= 3.0) & (sp <= 8.5) & router_q]
    if lane_name == "MIDPRICE_SUPPRESS":
        return df[(sp >= 3.0) & (sp <= 8.5) & ~router_q]
    if lane_name == "LONGSHOT_SUPPRESS":
        return df[sp > 8.5]
    return df


def load_training_corpus() -> pd.DataFrame:
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


def _verdict_to_candidate_check(top: dict) -> dict:
    """Check which lanes a verdict top pick qualifies for."""
    vp = float(top.get("velo_prime_prob") or 0.0)
    mds = float(top.get("market_deception_score") or 0.0)
    imp = float(top.get("improvement_score") or 0.0)
    sp = float(top.get("sp_decimal") or 0.0)
    tier = str(top.get("decision_tier") or top.get("confidence_level") or "")
    # Router: check lane flags or execution lane
    router_flags = (
        top.get("router_v1_shadow_pass") is True or
        top.get("router_v2_class4_shadow_pass") is True or
        top.get("router_v6_gold_seam_watchlist") is True
    )
    exec_lane = str(top.get("candidate_execution_lane") or "")
    router_q = router_flags or (exec_lane not in {"", "NO_BET", "ATTACK_LANE_MISS"})

    lanes = []
    if vp >= 0.30 and mds > 0.50:
        lanes.append("MDS_HIGH_LANE")
    if vp >= 0.30 and imp > 0.40:
        lanes.append("IMPROVER_LANE")
    if vp >= 0.40:
        lanes.append("VP40_LANE")
    if vp >= 0.40 and tier.upper() == "A":
        lanes.append("VP40_TIER_A_LANE")
    if sp > 0 and sp < 3.0 and vp >= 0.30:
        lanes.append("SHORTFAV_VP30")
    if sp >= 3.0 and sp <= 8.5 and router_q:
        lanes.append("MIDPRICE_ROUTER_QUAL")
    if sp >= 3.0 and sp <= 8.5 and not router_q:
        lanes.append("MIDPRICE_SUPPRESS")
    if sp > 8.5:
        lanes.append("LONGSHOT_SUPPRESS")
    return {"lanes": lanes, "vp": vp, "mds": mds, "imp": imp, "sp": sp, "tier": tier}


def load_today_candidates(date: str) -> dict[str, list[dict]]:
    """Load today's verdict JSON and classify each selection into lanes."""
    date_str = date.replace("-", "_")
    path = DATA / f"velo_prime_verdicts_{date_str}.json"
    if not path.exists():
        return {}

    try:
        verdicts = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    by_lane: dict[str, list[dict]] = {lane: [] for lane in LANE_DEFINITIONS}
    for verdict in verdicts:
        top = verdict.get("top") or {}
        horse = top.get("horse", "?")
        course = verdict.get("course", "?")
        off = verdict.get("off_time", "?")
        check = _verdict_to_candidate_check(top)
        for lane in check["lanes"]:
            if lane in by_lane:
                by_lane[lane].append({
                    "horse": horse,
                    "race": f"{course} {off}",
                    "vp": round(check["vp"], 3),
                    "mds": round(check["mds"], 3),
                    "imp": round(check["imp"], 3),
                    "sp": check["sp"],
                    "tier": check["tier"],
                })
    return by_lane


def _corpus_progress() -> dict:
    """Read training corpus size and 2K milestone progress."""
    path = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"
    manifest_path = DATA / "training" / "sigma_2k_training_manifest_latest.json"
    if not path.exists():
        return {"training_safe_rows": None, "milestone_2k": TARGET_2K, "rows_to_2k": None, "pct_to_2k": None}

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            n = int(manifest.get("result_matched_rows") or manifest.get("rows_with_results", 0))
        except Exception:
            n = None
    else:
        try:
            df = pd.read_parquet(path, columns=["result_matched"])
            n = int(df["result_matched"].sum())
        except Exception:
            n = None

    rows_to_2k = (TARGET_2K - n) if n is not None else None
    pct = round(n / TARGET_2K * 100, 1) if n is not None else None
    return {
        "training_safe_rows": n,
        "milestone_2k": TARGET_2K,
        "rows_to_2k": rows_to_2k,
        "pct_to_2k": pct,
        "corpus_name": "SIGMA_2K_SAFE_TRAINING_SLICE_V1",
        "growth_path": "daily_clean_accumulation",
    }


def build_md(lane_results: list[dict], today_candidates: dict, corpus: dict, run_ts: str, n_total: int, date: str) -> str:
    lines = [
        "# VELO NAMED SIGNAL LANES — TRACKING REPORT",
        f"**Run:** {run_ts}",
        f"**Training rows:** {n_total}",
        f"**Date:** {date}",
        "",
        "---",
        "",
        "## 2K Milestone Progress",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Training-safe rows | **{corpus.get('training_safe_rows', '?')}** |",
        f"| Target (2K milestone) | {corpus.get('milestone_2k', 2000)} |",
        f"| Rows remaining | {corpus.get('rows_to_2k', '?')} |",
        f"| Progress | {corpus.get('pct_to_2k', '?')}% |",
        f"| Growth path | {corpus.get('growth_path', 'daily accumulation')} |",
        "",
        "---",
        "",
        "## Lane Performance — Historical Corpus",
        "",
        "| Lane | n | SR | Frame | ROI | SR Δ | Frame Δ | Avg SP | Med SP | Status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in lane_results:
        sr_d = f"{r['sr_delta']:+.1f}pp" if r.get("sr_delta") is not None else "—"
        fr_d = f"{r['frame_delta']:+.1f}pp" if r.get("frame_delta") is not None else "—"
        roi = f"{r['roi']:+.1f}%" if r.get("roi") is not None else "—"
        avg = str(r.get("avg_sp", "—"))
        med = str(r.get("median_sp", "—"))
        warn = " ⚠️" if r.get("sample_warning") else ""
        lines.append(
            f"| {r['lane']}{warn} | {r['n']} | {r['sr']}% | {r['frame']}% | {roi} | {sr_d} | {fr_d} | {avg} | {med} | **{r['promotion_status']}** |"
        )

    lines += ["", "---", "", f"## Today's Lane Candidates ({date})", ""]
    any_candidates = False
    for lane_name, candidates in today_candidates.items():
        if not candidates:
            continue
        any_candidates = True
        lines.append(f"### {lane_name}")
        lines.append("")
        lines.append("| Horse | Race | VP | MDS | IMP | SP | Tier |")
        lines.append("|---|---|---|---|---|---|---|")
        for c in candidates:
            sp_str = str(c["sp"]) if c["sp"] else "?"
            lines.append(f"| {c['horse']} | {c['race']} | {c['vp']} | {c['mds']} | {c['imp']} | {sp_str} | {c['tier']} |")
        lines.append("")
    if not any_candidates:
        lines.append("No candidates in any named lane for today.")

    lines += [
        "---",
        "",
        "## Lane Definitions",
        "",
        "| Lane | Definition | Promotion Target |",
        "|---|---|---|",
    ]
    for lane_name, defn in LANE_DEFINITIONS.items():
        lines.append(f"| {lane_name} | {defn['description']} | {defn['promotion_target']} |")

    lines += [
        "",
        "---",
        "",
        "## Governance",
        "",
        "Advisory only. No scoring / model / router / staking / Telegram changes.",
        "",
        "*BUILD_NAMED_SIGNAL_LANES_V1 — build_named_signal_lanes.py*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date for today's candidate check (YYYY-MM-DD)")
    args = parser.parse_args()

    print("BUILD NAMED SIGNAL LANES V1")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    df = load_training_corpus()
    n_total = len(df)
    print(f"Training rows (with results): {n_total}")

    lane_results = []
    for lane_name, defn in LANE_DEFINITIONS.items():
        subset = _apply_lane_filter(df, lane_name)
        stats = _lane_stats(subset, lane_name, defn)
        lane_results.append(stats)
        warn = " ⚠️" if stats["sample_warning"] else ""
        print(f"  {lane_name:30s}{warn}  n={stats['n']:4d}  SR={stats['sr']:5.1f}%  Δ={stats.get('sr_delta', 0):+.1f}pp  {stats['promotion_status']}")

    today_candidates = load_today_candidates(args.date)
    total_candidates = sum(len(v) for v in today_candidates.values())
    print(f"\nToday's candidates ({args.date}): {total_candidates} total")
    for lane, cands in today_candidates.items():
        if cands:
            print(f"  {lane}: {len(cands)} — {', '.join(c['horse'] for c in cands[:5])}")

    corpus = _corpus_progress()
    print(f"\n2K Milestone: {corpus['training_safe_rows']}/{corpus['milestone_2k']} "
          f"({corpus['pct_to_2k']}%) — {corpus['rows_to_2k']} rows remaining")

    output = {
        "run_ts": run_ts,
        "date": args.date,
        "training_rows": n_total,
        "global_sr": GLOBAL_SR,
        "global_frame": GLOBAL_FRAME,
        "lanes": lane_results,
        "today_candidates": {k: v for k, v in today_candidates.items() if v},
        "corpus_progress": corpus,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "ADVISORY_TRACKING_ONLY",
        },
    }

    json_path = REPORTS_DIR / "named_signal_lanes_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = build_md(lane_results, today_candidates, corpus, run_ts, n_total, args.date)
    md_path = REPORTS_DIR / "named_signal_lanes_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
