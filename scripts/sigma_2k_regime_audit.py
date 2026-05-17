#!/usr/bin/env python3
"""
SIGMA_2K_REGIME_AUDIT_V1

Audits all signal regimes in the 2K Sigma training corpus.
For each regime partition: SR, frame, ROI, avg SP, median SP,
losing run, winner/loser ratio, sample warning, classification.

Outputs:
    data/reports/sigma_2k_regime_audit_latest.json
    data/reports/sigma_2k_regime_audit_latest.md
    docs/engineering/SIGMA_2K_REGIME_AUDIT_V1.md

Usage:
    python scripts/sigma_2k_regime_audit.py
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

GLOBAL_SR = 19.7  # from training dataset build


def load_dataset() -> pd.DataFrame:
    path = ROOT / "data" / "training" / "sigma_2k_training_dataset_latest.parquet"
    df = pd.read_parquet(path)
    df = df[df["result_matched"] == True].copy()
    for col in ["velo_prime_prob", "market_deception_score", "improvement_score",
                "place_prob", "sp_decimal", "actual_winner_sp"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    return df


def classify(n: int, sr: float, frame: float, roi_val, global_sr: float = GLOBAL_SR) -> str:
    if n < 20:
        return "INSUFFICIENT_SAMPLE"
    lift = sr - global_sr
    if lift >= 15 and frame >= 70:
        return "PROVEN"
    if lift >= 8 and frame >= 60:
        return "PROMISING"
    if lift >= 2:
        return "WATCH"
    if lift < -5 or sr < 12:
        return "SUPPRESS"
    if sr < global_sr - 2 and frame < 45:
        return "SUPPRESS"
    return "WATCH"


def regime_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    wins = int(df["won"].sum())
    placed = int(df["placed"].sum())
    sr = round(wins / n * 100, 1) if n else 0.0
    fr = round(placed / n * 100, 1) if n else 0.0
    losers = n - wins

    # Avg / median SP
    sp_vals = df["sp_decimal"].dropna()
    avg_sp = round(float(sp_vals.mean()), 2) if len(sp_vals) else None
    med_sp = round(float(sp_vals.median()), 2) if len(sp_vals) else None

    # Longest losing run
    max_run = 0
    cur_run = 0
    for w in df["won"].tolist():
        if not w:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0

    winner_loser_ratio = round(losers / wins, 1) if wins else None

    # Approximate ROI at level stakes SP
    if "sp_decimal" in df.columns and wins:
        winner_sps = df[df["won"]]["sp_decimal"].dropna()
        total_return = float(winner_sps.sum())
        roi_val = round((total_return - n) / n * 100, 1)
    else:
        roi_val = None

    clf = classify(n, sr, fr, roi_val)

    return {
        "label": label,
        "n": n,
        "wins": wins,
        "placed": placed,
        "losers": losers,
        "sr": sr,
        "frame": fr,
        "roi": roi_val,
        "avg_sp": avg_sp,
        "median_sp": med_sp,
        "longest_losing_run": max_run,
        "winner_loser_ratio": winner_loser_ratio,
        "sample_warning": n < 50,
        "classification": clf,
    }


def audit_dimension(df: pd.DataFrame, name: str, groups: list) -> list:
    """groups: list of (label, boolean_mask_series)"""
    results = []
    for label, mask in groups:
        grp = df[mask]
        results.append(regime_stats(grp, f"{name}:{label}"))
    return results


def build_all_regimes(df: pd.DataFrame) -> dict:
    out = {}

    # ── VP bands ──────────────────────────────────────────────────────────────
    vp = df["velo_prime_prob"]
    out["vp_bands"] = audit_dimension(df, "VP", [
        ("VP<0.20", vp < 0.20),
        ("VP0.20-0.30", (vp >= 0.20) & (vp < 0.30)),
        ("VP0.30-0.40", (vp >= 0.30) & (vp < 0.40)),
        ("VP>=0.40", vp >= 0.40),
        ("VP>=0.30", vp >= 0.30),
        ("VP>=0.30+TierA", (vp >= 0.30) & (df["decision_tier"] == "A")),
    ])

    # ── MDS bands ─────────────────────────────────────────────────────────────
    mds = df["market_deception_score"]
    out["mds_bands"] = audit_dimension(df, "MDS", [
        ("MDS<0.30", mds < 0.30),
        ("MDS0.30-0.50", (mds >= 0.30) & (mds <= 0.50)),
        ("MDS>0.50", mds > 0.50),
    ])

    # ── Improvement bands ─────────────────────────────────────────────────────
    imp = df["improvement_score"]
    out["improvement_bands"] = audit_dimension(df, "IMP", [
        ("IMP<0.20", imp < 0.20),
        ("IMP0.20-0.40", (imp >= 0.20) & (imp <= 0.40)),
        ("IMP>0.40", imp > 0.40),
    ])

    # ── SP bands ──────────────────────────────────────────────────────────────
    sp = df["sp_decimal"]
    out["sp_bands"] = audit_dimension(df, "SP", [
        ("SP<3.0", sp < 3.0),
        ("SP3.0-8.5", (sp >= 3.0) & (sp <= 8.5)),
        ("SP8.5-16.0", (sp > 8.5) & (sp <= 16.0)),
        ("SP>16.0", sp > 16.0),
    ])

    # ── Router lanes ──────────────────────────────────────────────────────────
    v1 = df.get("router_v1_shadow_pass", pd.Series([False] * len(df), index=df.index)).fillna(False).astype(bool)
    v2 = df.get("router_v2_class4_shadow_pass", pd.Series([False] * len(df), index=df.index)).fillna(False).astype(bool)
    v6 = df.get("router_v6_gold_seam_watchlist", pd.Series([False] * len(df), index=df.index)).fillna(False).astype(bool)
    router_qual = v1 | v2 | v6
    out["router_lanes"] = audit_dimension(df, "ROUTER", [
        ("V1_BASE", v1),
        ("V2_CLASS4", v2),
        ("V6_GOLD_SEAM", v6),
        ("Any_Router", router_qual),
        ("No_Router", ~router_qual),
    ])

    # ── Archetypes ────────────────────────────────────────────────────────────
    arch_col = "archetype" if "archetype" in df.columns else None
    if arch_col:
        archetype_groups = []
        for arch in ["Compression", "Structure", "Improver", "Market-Deception", "Cash-Run"]:
            mask = df[arch_col].astype(str).str.lower() == arch.lower()
            if mask.sum() >= 5:
                archetype_groups.append((arch, mask))
        # Compound archetypes
        archetype_groups.append(("Compression+VP<0.30", (df[arch_col].astype(str).str.lower() == "compression") & (df["velo_prime_prob"] < 0.30)))
        out["archetypes"] = audit_dimension(df, "ARCH", archetype_groups)
    else:
        out["archetypes"] = []

    # ── Tier ─────────────────────────────────────────────────────────────────
    out["tiers"] = audit_dimension(df, "TIER", [
        ("A", df["decision_tier"] == "A"),
        ("B", df["decision_tier"] == "B"),
        ("C", df["decision_tier"] == "C"),
        ("D", df["decision_tier"] == "D"),
        ("X", df["decision_tier"] == "X"),
        ("B_VP>=0.30", (df["decision_tier"] == "B") & (df["velo_prime_prob"] >= 0.30)),
        ("B_VP<0.30", (df["decision_tier"] == "B") & (df["velo_prime_prob"] < 0.30)),
    ])

    # ── Combo zones ───────────────────────────────────────────────────────────
    out["combos"] = audit_dimension(df, "COMBO", [
        ("MDS>0.5+VP>=0.30", (mds > 0.50) & (vp >= 0.30)),
        ("IMP>0.40+VP>=0.30", (imp > 0.40) & (vp >= 0.30)),
        ("MidPrice+Router", (sp >= 3.0) & (sp <= 8.5) & router_qual),
        ("MidPrice+NoRouter", (sp >= 3.0) & (sp <= 8.5) & ~router_qual),
        ("VP>=0.40+TierA", (vp >= 0.40) & (df["decision_tier"] == "A")),
        ("VP>=0.30+Router", (vp >= 0.30) & router_qual),
        ("ShortFav+VP>=0.30", (sp < 3.0) & (vp >= 0.30)),
        ("Outsider+Router", (sp > 8.5) & router_qual),
    ])

    return out


def render_md(all_regimes: dict, run_ts: str, n_total: int) -> str:
    lines = [
        "# SIGMA 2K REGIME AUDIT V1",
        f"**Run:** {run_ts}",
        f"**Training rows:** {n_total}",
        f"**Global SR (reference):** {GLOBAL_SR}%",
        "",
        "---",
        "",
        "## Classification Key",
        "",
        "| Class | Meaning |",
        "|---|---|",
        "| PROVEN | SR lift ≥+15pp, Frame ≥70% |",
        "| PROMISING | SR lift ≥+8pp, Frame ≥60% |",
        "| WATCH | SR lift ≥+2pp |",
        "| SUPPRESS | SR lift <-5pp or SR<12% |",
        "| INSUFFICIENT_SAMPLE | n<20 |",
        "",
        "---",
        "",
    ]

    section_names = {
        "vp_bands": "1. VP Bands",
        "mds_bands": "2. MDS Bands",
        "improvement_bands": "3. Improvement Score Bands",
        "sp_bands": "4. SP Bands",
        "router_lanes": "5. Router Lanes",
        "archetypes": "6. Archetypes",
        "tiers": "7. Tiers",
        "combos": "8. Combo Zones",
    }

    for key, section_name in section_names.items():
        rows = all_regimes.get(key, [])
        if not rows:
            continue
        lines.append(f"## {section_name}")
        lines.append("")
        lines.append("| Regime | n | SR | Frame | ROI | Avg SP | Med SP | Max Losing Run | W:L Ratio | Classification |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            roi_str = f"{r['roi']:+.1f}%" if r["roi"] is not None else "—"
            avg_sp = str(r["avg_sp"]) if r["avg_sp"] is not None else "—"
            med_sp = str(r["median_sp"]) if r["median_sp"] is not None else "—"
            wl = str(r["winner_loser_ratio"]) if r["winner_loser_ratio"] is not None else "—"
            sample_warn = " ⚠️" if r["sample_warning"] else ""
            lines.append(
                f"| {r['label']}{sample_warn} | {r['n']} | {r['sr']}% | {r['frame']}% | {roi_str} | {avg_sp} | {med_sp} | {r['longest_losing_run']} | {wl} | **{r['classification']}** |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    lines += [
        "## Governance",
        "",
        "Advisory only. No scoring/model/staking/router/Telegram changes.",
        "",
        "*SIGMA_2K_REGIME_AUDIT_V1 — sigma_2k_regime_audit.py*",
    ]
    return "\n".join(lines)


def main():
    print("SIGMA 2K REGIME AUDIT V1")
    print("=" * 60)

    df = load_dataset()
    n_total = len(df)
    print(f"Training rows (with results): {n_total}")

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    all_regimes = build_all_regimes(df)

    # Flatten to summary
    all_rows = []
    for section, rows in all_regimes.items():
        for r in rows:
            r["section"] = section
            all_rows.append(r)

    # Print headline findings
    print("\nHEADLINE CLASSIFICATIONS:")
    for r in all_rows:
        if r["classification"] in ("PROVEN", "SUPPRESS") and not r["sample_warning"]:
            print(f"  {r['classification']:20s} {r['label']:40s} n={r['n']:4d} SR={r['sr']}%")

    result = {
        "run_ts": run_ts,
        "training_rows": n_total,
        "global_sr": GLOBAL_SR,
        "regimes": all_regimes,
        "all_rows_flat": all_rows,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "staking_change": False,
            "classification": "ADVISORY_ONLY",
        },
    }

    json_path = REPORTS_DIR / "sigma_2k_regime_audit_latest.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = render_md(all_regimes, run_ts, n_total)
    md_path = REPORTS_DIR / "sigma_2k_regime_audit_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    docs_path = ROOT / "docs" / "engineering" / "SIGMA_2K_REGIME_AUDIT_V1.md"
    docs_path.write_text(md)
    print(f"Written: {docs_path}")


if __name__ == "__main__":
    main()
