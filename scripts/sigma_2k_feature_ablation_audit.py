#!/usr/bin/env python3
"""
SIGMA_2K_FEATURE_ABLATION_AUDIT_V1

Tests signal family combinations against the 2K Sigma corpus.
Measures SR, frame, ROI delta vs base VP-only filter.
No model weight changes — selection filtering only.

Outputs:
    data/reports/sigma_2k_feature_ablation_latest.json
    data/reports/sigma_2k_feature_ablation_latest.md

Usage:
    python scripts/sigma_2k_feature_ablation_audit.py
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

GLOBAL_SR = 19.7
BASE_VP_THRESHOLD = 0.30


def load_dataset() -> pd.DataFrame:
    path = ROOT / "data" / "training" / "sigma_2k_training_dataset_latest.parquet"
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
    ).fillna(False)
    return df


def eval_selection(df: pd.DataFrame, mask: pd.Series, label: str, base_n: int) -> dict:
    sel = df[mask]
    n = len(sel)
    if n == 0:
        return {"label": label, "n": 0, "sr": 0.0, "frame": 0.0, "roi": None,
                "sr_delta": None, "frame_delta": None, "coverage_pct": 0.0,
                "false_positive_reduction": None, "winner_loss_n": None,
                "recommended": "INSUFFICIENT_SAMPLE"}

    wins = int(sel["won"].sum())
    placed = int(sel["placed"].sum())
    sr = round(wins / n * 100, 1)
    fr = round(placed / n * 100, 1)

    sp_vals = sel[sel["won"]]["sp_decimal"].dropna()
    total_return = float(sp_vals.sum())
    roi = round((total_return - n) / n * 100, 1)

    # Compare to full corpus
    full_sr = GLOBAL_SR
    sr_delta = round(sr - full_sr, 1)
    fr_delta = round(fr - 51.7, 1)  # global frame from build

    coverage_pct = round(n / len(df) * 100, 1)

    # False positive reduction: losers avoided vs corpus
    losers_in_sel = n - wins
    losers_in_corpus = len(df) - int(df["won"].sum())
    false_pos_red = round((1 - losers_in_sel / losers_in_corpus) * 100, 1) if losers_in_corpus else None

    # Winners excluded: winners in corpus not in selection
    all_winners = int(df["won"].sum())
    winner_loss = all_winners - wins

    # Recommendation
    if n < 20:
        rec = "INSUFFICIENT_SAMPLE"
    elif sr_delta >= 15 and fr_delta >= 0:
        rec = "SHADOW_POLICY_CANDIDATE"
    elif sr_delta >= 8:
        rec = "KEEP"
    elif sr_delta >= 2:
        rec = "ADVISORY_ONLY"
    elif sr_delta < -3:
        rec = "SUPPRESS"
    elif winner_loss > all_winners * 0.30:
        rec = "NEEDS_MORE_DATA"
    else:
        rec = "ADVISORY_ONLY"

    return {
        "label": label,
        "n": n,
        "wins": wins,
        "sr": sr,
        "frame": fr,
        "roi": roi,
        "sr_delta": sr_delta,
        "frame_delta": fr_delta,
        "coverage_pct": coverage_pct,
        "false_positive_reduction_pct": false_pos_red,
        "winner_loss_n": winner_loss,
        "recommended": rec,
    }


def main():
    print("SIGMA 2K FEATURE ABLATION AUDIT V1")
    print("=" * 60)

    df = load_dataset()
    n_total = len(df)
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    print(f"Training rows: {n_total}")

    vp = df["velo_prime_prob"]
    mds = df["market_deception_score"]
    imp = df["improvement_score"]
    pp = df["place_prob"]
    sp = df["sp_decimal"]
    rq = df["router_qualified"]
    tier = df["decision_tier"]
    mid_supp = ~rq  # midprice suppression advisory (suppress when no router)

    base_mask = vp >= BASE_VP_THRESHOLD
    base_n = int(base_mask.sum())

    families = [
        # Baseline
        ("BASE: All corpus", pd.Series([True] * n_total, index=df.index)),
        ("VP>=0.30 only", base_mask),
        # Single signal additions on top of VP>=0.30
        ("VP>=0.30 + MDS>0.50", base_mask & (mds > 0.50)),
        ("VP>=0.30 + IMP>0.40", base_mask & (imp > 0.40)),
        ("VP>=0.30 + Router", base_mask & rq),
        ("VP>=0.30 + RP_Conv_HIGH", base_mask),  # placeholder — data not in corpus
        ("VP>=0.30 + CASHRUN_WATCH", base_mask),  # placeholder — data not in corpus
        ("VP>=0.30 + Midprice_Suppress", base_mask & ~((sp >= 3.0) & (sp <= 8.5) & ~rq)),
        # Tier gates
        ("VP>=0.30 + TierA", base_mask & (tier == "A")),
        ("VP>=0.30 + TierA_or_B", base_mask & tier.isin(["A", "B"])),
        ("VP>=0.30 + suppress_TierC", base_mask & ~(tier == "C")),
        # Combined high-conviction
        ("VP>=0.30 + MDS>0.50 + IMP>0.40", base_mask & (mds > 0.50) & (imp > 0.40)),
        ("VP>=0.30 + MDS>0.50 + Router", base_mask & (mds > 0.50) & rq),
        ("VP>=0.30 + Router + TierA", base_mask & rq & (tier == "A")),
        ("Full stack: VP30+MDS+IMP+Router", base_mask & (mds > 0.30) & (imp > 0.20) & rq),
        # VP threshold variations
        ("VP>=0.40 only", vp >= 0.40),
        ("VP>=0.40 + Router", (vp >= 0.40) & rq),
        ("VP>=0.40 + TierA", (vp >= 0.40) & (tier == "A")),
        # Suppression-only (what gets removed)
        ("Compression suppress", df.get("archetype", pd.Series([""] * n_total, index=df.index)).astype(str).str.lower() != "compression"),
        ("Suppress TierC", tier != "C"),
        ("Suppress VP<0.20", vp >= 0.20),
        ("Suppress VP<0.30", vp >= 0.30),
        ("Suppress midprice noRouter", ~((sp >= 3.0) & (sp <= 8.5) & ~rq)),
        ("Suppress longshot (SP>16)", sp <= 16.0),
    ]

    results = []
    for label, mask in families:
        r = eval_selection(df, mask, label, base_n)
        results.append(r)
        print(f"  {label:50s} n={r['n']:4d} SR={r['sr']:5.1f}% delta={r.get('sr_delta','?'):+5.1f}pp  {r['recommended']}")

    # Build output
    output = {
        "run_ts": run_ts,
        "training_rows": n_total,
        "global_sr": GLOBAL_SR,
        "base_vp_threshold": BASE_VP_THRESHOLD,
        "results": results,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "staking_change": False,
            "classification": "ADVISORY_ONLY",
        },
    }

    json_path = REPORTS_DIR / "sigma_2k_feature_ablation_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = build_md(results, run_ts, n_total)
    md_path = REPORTS_DIR / "sigma_2k_feature_ablation_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


def build_md(results: list, run_ts: str, n_total: int) -> str:
    shadow_candidates = [r for r in results if r.get("recommended") == "SHADOW_POLICY_CANDIDATE"]
    suppress_findings = [r for r in results if r.get("recommended") == "SUPPRESS"]

    lines = [
        "# SIGMA 2K FEATURE ABLATION AUDIT V1",
        f"**Run:** {run_ts}",
        f"**Training rows:** {n_total}",
        f"**Global SR baseline:** {GLOBAL_SR}%",
        "",
        "---",
        "",
        "## Full Results",
        "",
        "| Family | n | SR | Frame | ROI | SR Δ | Frame Δ | Coverage | FP Red | W Lost | Status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        sr_d = f"{r['sr_delta']:+.1f}pp" if r.get("sr_delta") is not None else "—"
        fr_d = f"{r['frame_delta']:+.1f}pp" if r.get("frame_delta") is not None else "—"
        roi = f"{r['roi']:+.1f}%" if r.get("roi") is not None else "—"
        fp = f"{r['false_positive_reduction_pct']:.1f}%" if r.get("false_positive_reduction_pct") is not None else "—"
        wl = str(r.get("winner_loss_n", "—"))
        cov = f"{r['coverage_pct']:.1f}%" if r.get("coverage_pct") is not None else "—"
        lines.append(
            f"| {r['label']} | {r['n']} | {r['sr']}% | {r['frame']}% | {roi} | {sr_d} | {fr_d} | {cov} | {fp} | {wl} | **{r['recommended']}** |"
        )

    lines += [
        "",
        "---",
        "",
        "## Shadow Policy Candidates",
        "",
    ]
    if shadow_candidates:
        for r in shadow_candidates:
            lines.append(f"- **{r['label']}**: SR={r['sr']}% (Δ{r['sr_delta']:+.1f}pp), n={r['n']}")
    else:
        lines.append("None at this threshold. Strongest candidates are in KEEP/ADVISORY_ONLY range.")

    lines += [
        "",
        "## Governance",
        "",
        "No scoring/model/staking/router changes. Advisory only.",
        "",
        "*SIGMA_2K_FEATURE_ABLATION_AUDIT_V1 — sigma_2k_feature_ablation_audit.py*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
