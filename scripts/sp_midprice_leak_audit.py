#!/usr/bin/env python3
"""
SP_MIDPRICE_LEAK_AUDIT_V1

Dissects VELO misses in the SP 3.0–8.5 zone to find what separates
winners from bait. Uses the unified evidence corpus + innovation protocol.

Outputs:
    data/reports/sp_midprice_leak_audit_latest.json
    data/reports/sp_midprice_leak_audit_latest.md
    docs/engineering/SP_MIDPRICE_LEAK_AUDIT_V1.md

Usage:
    python scripts/sp_midprice_leak_audit.py
"""
import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SP_LOW = 3.0
SP_HIGH = 8.5


def load_corpus() -> pd.DataFrame:
    path = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
    df = pd.read_csv(path)
    df["sp_decimal"] = pd.to_numeric(df["sp_decimal"], errors="coerce")
    df["velo_prime_prob"] = pd.to_numeric(df["velo_prime_prob"], errors="coerce")
    df["market_deception_score"] = pd.to_numeric(df["market_deception_score"], errors="coerce")
    df["improvement_score"] = pd.to_numeric(df["improvement_score"], errors="coerce")
    df["place_prob"] = pd.to_numeric(df["place_prob"], errors="coerce")
    df["actual_winner_sp"] = pd.to_numeric(df["actual_winner_sp"], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    return df


def load_innovation_protocol() -> pd.DataFrame:
    path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    ip = pd.read_csv(path)
    ip["sp_decimal"] = pd.to_numeric(ip["sp_decimal"], errors="coerce")
    return ip


def sr(grp: pd.DataFrame) -> float:
    if len(grp) == 0:
        return 0.0
    return round(grp["won"].sum() / len(grp) * 100, 1)


def frame(grp: pd.DataFrame) -> float:
    if len(grp) == 0:
        return 0.0
    return round(grp["placed"].sum() / len(grp) * 100, 1)


def band_stats(df: pd.DataFrame, col: str, bins, labels) -> list:
    out = []
    df = df.copy()
    df["_band"] = pd.cut(df[col], bins=bins, labels=labels, right=False)
    for label in labels:
        g = df[df["_band"] == label]
        if len(g) < 3:
            continue
        out.append({
            "band": str(label),
            "n": len(g),
            "wins": int(g["won"].sum()),
            "placed": int(g["placed"].sum()),
            "sr": sr(g),
            "frame": frame(g),
        })
    return out


def winner_sp_profile(df: pd.DataFrame) -> dict:
    winners_among_misses = df[~df["won"]]["actual_winner_sp"].dropna()
    return {
        "median_winner_sp": round(winners_among_misses.median(), 2) if len(winners_among_misses) else None,
        "pct_winner_sp_under_4": round((winners_among_misses < 4.0).mean() * 100, 1) if len(winners_among_misses) else None,
        "pct_winner_sp_4_to_8": round(((winners_among_misses >= 4.0) & (winners_among_misses <= 8.0)).mean() * 100, 1) if len(winners_among_misses) else None,
        "pct_winner_sp_over_8": round((winners_among_misses > 8.0).mean() * 100, 1) if len(winners_among_misses) else None,
        "n_misses_with_winner_sp": int(len(winners_among_misses)),
    }


def top_n_by_col(df: pd.DataFrame, col: str, n: int = 8, min_n: int = 5) -> list:
    out = []
    for val, grp in df.groupby(col):
        if len(grp) < min_n:
            continue
        out.append({"value": str(val), "n": len(grp), "sr": sr(grp), "frame": frame(grp), "wins": int(grp["won"].sum())})
    return sorted(out, key=lambda x: x["sr"], reverse=True)[:n]


def run_audit():
    print("SP MIDPRICE LEAK AUDIT V1")
    print("=" * 60)

    corpus = load_corpus()
    ip = load_innovation_protocol()

    # Restrict to rows with known results
    with_results = corpus[corpus["result_matched"] == True].copy()
    total_with_results = len(with_results)
    print(f"Corpus rows with results: {total_with_results}")

    # Midprice universe
    mid = with_results[
        (with_results["sp_decimal"] >= SP_LOW) &
        (with_results["sp_decimal"] <= SP_HIGH)
    ].copy()
    print(f"Mid-price (SP {SP_LOW}–{SP_HIGH}) rows: {len(mid)}")
    print(f"  Winners: {mid['won'].sum()} | SR: {sr(mid)}%")
    print(f"  Placed:  {mid['placed'].sum()} | Frame: {frame(mid)}%")

    # Enrich with IP fields for class/field_size/going/distance
    ip_slim = ip[["race_id", "horse_id", "class_num", "field_size", "going", "distance", "race_type"]].drop_duplicates(
        subset=["race_id", "horse_id"]
    )
    mid = mid.merge(ip_slim, on=["race_id", "horse_id"], how="left")

    # ── SECTION 1: VP bands inside midprice ─────────────────────────────────
    vp_bands = band_stats(
        mid, "velo_prime_prob",
        bins=[0, 0.20, 0.30, 0.40, 0.55, 1.01],
        labels=["<0.20", "0.20-0.30", "0.30-0.40", "0.40-0.55", "≥0.55"]
    )

    # ── SECTION 2: MDS bands inside midprice ─────────────────────────────────
    mds_bands = band_stats(
        mid, "market_deception_score",
        bins=[0, 0.30, 0.50, 0.70, 1.01],
        labels=["<0.30", "0.30-0.50", "≥0.50 (MDS_HIGH)", "≥0.70 (ELITE)"]
    )

    # ── SECTION 3: Improvement score bands ──────────────────────────────────
    imp_bands = band_stats(
        mid, "improvement_score",
        bins=[0, 0.20, 0.40, 0.60, 1.01],
        labels=["<0.20", "0.20-0.40", "≥0.40 (IMPROVER)", "≥0.60 (STRONG)"]
    )

    # ── SECTION 4: Tier ──────────────────────────────────────────────────────
    tier_stats = []
    for tier in ["A", "B", "C", "D", "X"]:
        g = mid[mid["decision_tier"] == tier]
        if len(g) < 3:
            continue
        tier_stats.append({"tier": tier, "n": len(g), "sr": sr(g), "frame": frame(g), "wins": int(g["won"].sum())})

    # ── SECTION 5: Router lane ───────────────────────────────────────────────
    lane_stats = []
    for lane_col, label in [
        ("router_v1_shadow_pass", "V1_BASE"),
        ("router_v2_class4_shadow_pass", "V2_CLASS4"),
        ("router_v6_gold_seam_watchlist", "V6_GOLD_SEAM"),
    ]:
        if lane_col not in mid.columns:
            continue
        in_lane = mid[mid[lane_col] == True]
        out_lane = mid[mid[lane_col] != True]
        lane_stats.append({
            "lane": label,
            "in_lane_n": len(in_lane), "in_lane_sr": sr(in_lane), "in_lane_frame": frame(in_lane),
            "out_lane_n": len(out_lane), "out_lane_sr": sr(out_lane),
        })

    # ── SECTION 6: Course (top/bottom by SR) ─────────────────────────────────
    course_stats = top_n_by_col(mid, "course", n=8, min_n=4)
    course_worst = sorted(
        [x for x in [
            {"value": str(v), "n": len(g), "sr": sr(g), "frame": frame(g), "wins": int(g["won"].sum())}
            for v, g in mid.groupby("course") if len(g) >= 4
        ]],
        key=lambda x: x["sr"]
    )[:5]

    # ── SECTION 7: Race class ────────────────────────────────────────────────
    class_stats = []
    mid["class_num"] = pd.to_numeric(mid["class_num"], errors="coerce")
    for cls in sorted(mid["class_num"].dropna().unique()):
        g = mid[mid["class_num"] == cls]
        if len(g) < 3:
            continue
        class_stats.append({"class": int(cls), "n": len(g), "sr": sr(g), "frame": frame(g), "wins": int(g["won"].sum())})

    # ── SECTION 8: Field size ────────────────────────────────────────────────
    field_bands = band_stats(
        mid.dropna(subset=["field_size"]), "field_size",
        bins=[0, 6, 9, 12, 16, 100],
        labels=["≤5", "6-8", "9-11", "12-15", "16+"]
    )

    # ── SECTION 9: Going ─────────────────────────────────────────────────────
    going_stats = top_n_by_col(mid.dropna(subset=["going"]), "going", n=8, min_n=3)

    # ── SECTION 10: Winner SP profile for our misses ─────────────────────────
    wp = winner_sp_profile(mid)

    # ── SECTION 11: High-conviction midprice winners (where we got it right) ─
    winners_mid = mid[mid["won"]].copy()
    winner_signal_profile = {
        "n": int(len(winners_mid)),
        "avg_vp": round(winners_mid["velo_prime_prob"].mean(), 3) if len(winners_mid) else None,
        "avg_mds": round(winners_mid["market_deception_score"].mean(), 3) if len(winners_mid) else None,
        "avg_imp": round(winners_mid["improvement_score"].mean(), 3) if len(winners_mid) else None,
        "pct_tier_a": round((winners_mid["decision_tier"] == "A").mean() * 100, 1) if len(winners_mid) else None,
        "avg_sp": round(winners_mid["sp_decimal"].mean(), 2) if len(winners_mid) else None,
    }

    # ── SECTION 12: Bait profile (our misses where mid-price won) ───────────
    misses_mid = mid[~mid["won"]].copy()
    bait_signal_profile = {
        "n": int(len(misses_mid)),
        "avg_vp": round(misses_mid["velo_prime_prob"].mean(), 3) if len(misses_mid) else None,
        "avg_mds": round(misses_mid["market_deception_score"].mean(), 3) if len(misses_mid) else None,
        "avg_imp": round(misses_mid["improvement_score"].mean(), 3) if len(misses_mid) else None,
        "pct_tier_a": round((misses_mid["decision_tier"] == "A").mean() * 100, 1) if len(misses_mid) else None,
        "avg_sp": round(misses_mid["sp_decimal"].mean(), 2) if len(misses_mid) else None,
    }

    # ── SECTION 13: Signal separation test — winners vs bait ─────────────────
    def signal_delta(col: str) -> dict:
        w = winners_mid[col].dropna().mean()
        b = misses_mid[col].dropna().mean()
        if pd.isna(w) or pd.isna(b):
            return {"winners_avg": None, "bait_avg": None, "delta": None}
        return {
            "winners_avg": round(w, 3),
            "bait_avg": round(b, 3),
            "delta": round(w - b, 3),
        }

    separation = {
        "velo_prime_prob": signal_delta("velo_prime_prob"),
        "market_deception_score": signal_delta("market_deception_score"),
        "improvement_score": signal_delta("improvement_score"),
        "place_prob": signal_delta("place_prob"),
    }

    # ── SECTION 14: Compression suppression test in midprice ─────────────────
    if "archetype" in mid.columns:
        comp = mid[mid["archetype"] == "Compression"]
        non_comp = mid[mid["archetype"] != "Compression"]
        compression_test = {
            "compression_n": len(comp), "compression_sr": sr(comp), "compression_frame": frame(comp),
            "non_compression_n": len(non_comp), "non_compression_sr": sr(non_comp),
        }
    else:
        compression_test = {"note": "archetype column not in corpus"}

    # ── SECTION 15: MDS_HIGH + VP gate — does the combo work? ────────────────
    mds_vp_gate = mid[
        (mid["market_deception_score"] >= 0.50) &
        (mid["velo_prime_prob"] >= 0.30)
    ]
    mds_vp_gate_stats = {
        "n": len(mds_vp_gate),
        "sr": sr(mds_vp_gate),
        "frame": frame(mds_vp_gate),
        "wins": int(mds_vp_gate["won"].sum()),
    }

    imp_vp_gate = mid[
        (mid["improvement_score"] >= 0.40) &
        (mid["velo_prime_prob"] >= 0.30)
    ]
    imp_vp_gate_stats = {
        "n": len(imp_vp_gate),
        "sr": sr(imp_vp_gate),
        "frame": frame(imp_vp_gate),
        "wins": int(imp_vp_gate["won"].sum()),
    }

    # ── Build output ──────────────────────────────────────────────────────────
    result = {
        "run_ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "sp_zone": f"{SP_LOW}–{SP_HIGH}",
        "total_corpus_with_results": total_with_results,
        "midprice_n": len(mid),
        "midprice_wins": int(mid["won"].sum()),
        "midprice_sr": sr(mid),
        "midprice_frame": frame(mid),
        "global_sr_for_reference": 21.4,
        "vp_bands": vp_bands,
        "mds_bands": mds_bands,
        "improvement_bands": imp_bands,
        "tier_stats": tier_stats,
        "router_lane_stats": lane_stats,
        "course_best": course_stats,
        "course_worst": course_worst,
        "class_stats": class_stats,
        "field_size_bands": field_bands,
        "going_stats": going_stats,
        "winner_sp_profile_of_misses": wp,
        "winner_signal_profile": winner_signal_profile,
        "bait_signal_profile": bait_signal_profile,
        "signal_separation": separation,
        "compression_test": compression_test,
        "mds_high_vp_gate_in_midprice": mds_vp_gate_stats,
        "improver_vp_gate_in_midprice": imp_vp_gate_stats,
    }

    return result, mid


def build_md(r: dict) -> str:
    lines = [
        "# SP MIDPRICE LEAK AUDIT V1",
        f"**Run:** {r['run_ts']}",
        f"**SP Zone:** {r['sp_zone']}",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Mid-price rows (with results) | {r['midprice_n']} |",
        f"| Winners | {r['midprice_wins']} |",
        f"| Strike rate | **{r['midprice_sr']}%** |",
        f"| Frame rate | **{r['midprice_frame']}%** |",
        f"| Global SR (reference) | {r['global_sr_for_reference']}% |",
        f"| Mid-price lift vs global | **{round(r['midprice_sr'] - r['global_sr_for_reference'], 1)}pp** |",
        "",
        "Mid-price VELO selections have been running at **{sr}%** SR vs **{gsr}%** global — the lift here {lift}.".format(
            sr=r['midprice_sr'],
            gsr=r['global_sr_for_reference'],
            lift="is positive" if r['midprice_sr'] > r['global_sr_for_reference'] else "is below global (the leak is real)"
        ),
        "",
        "---",
        "",
        "## 1. VP Bands Inside Mid-Price",
        "",
        "| Band | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for b in r["vp_bands"]:
        lines.append(f"| {b['band']} | {b['n']} | {b['sr']}% | {b['frame']}% | {b['wins']} |")

    lines += [
        "",
        "---",
        "",
        "## 2. MDS Bands Inside Mid-Price",
        "",
        "| Band | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for b in r["mds_bands"]:
        lines.append(f"| {b['band']} | {b['n']} | {b['sr']}% | {b['frame']}% | {b['wins']} |")

    lines += [
        "",
        "---",
        "",
        "## 3. Improvement Score Bands Inside Mid-Price",
        "",
        "| Band | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for b in r["improvement_bands"]:
        lines.append(f"| {b['band']} | {b['n']} | {b['sr']}% | {b['frame']}% | {b['wins']} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Tier Breakdown Inside Mid-Price",
        "",
        "| Tier | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for b in r["tier_stats"]:
        lines.append(f"| {b['tier']} | {b['n']} | {b['sr']}% | {b['frame']}% | {b['wins']} |")

    lines += [
        "",
        "---",
        "",
        "## 5. Router Lane Performance Inside Mid-Price",
        "",
        "| Lane | In-Lane n | In-Lane SR | Out-Lane n | Out-Lane SR |",
        "|---|---|---|---|---|",
    ]
    for b in r["router_lane_stats"]:
        lines.append(f"| {b['lane']} | {b['in_lane_n']} | {b['in_lane_sr']}% | {b['out_lane_n']} | {b['out_lane_sr']}% |")

    lines += [
        "",
        "---",
        "",
        "## 6. Signal Separation: Winners vs Bait",
        "",
        "How do mid-price WINNERS differ from mid-price MISSES in signal profile?",
        "",
        "| Signal | Winners avg | Bait avg | Delta |",
        "|---|---|---|---|",
    ]
    for sig, v in r["signal_separation"].items():
        if v["delta"] is None:
            continue
        direction = "↑ winners higher" if v["delta"] > 0.01 else ("↓ bait higher" if v["delta"] < -0.01 else "≈ no separation")
        lines.append(f"| {sig} | {v['winners_avg']} | {v['bait_avg']} | {v['delta']:+.3f} ({direction}) |")

    lines += [
        "",
        "**Winner profile:**",
        f"- avg VP: {r['winner_signal_profile']['avg_vp']}",
        f"- avg MDS: {r['winner_signal_profile']['avg_mds']}",
        f"- avg improvement: {r['winner_signal_profile']['avg_imp']}",
        f"- % Tier A: {r['winner_signal_profile']['pct_tier_a']}%",
        f"- avg SP: {r['winner_signal_profile']['avg_sp']}",
        "",
        "**Bait profile (our misses):**",
        f"- avg VP: {r['bait_signal_profile']['avg_vp']}",
        f"- avg MDS: {r['bait_signal_profile']['avg_mds']}",
        f"- avg improvement: {r['bait_signal_profile']['avg_imp']}",
        f"- % Tier A: {r['bait_signal_profile']['pct_tier_a']}%",
        f"- avg SP: {r['bait_signal_profile']['avg_sp']}",
        "",
        "---",
        "",
        "## 7. Combo Gate Tests Inside Mid-Price",
        "",
        "| Gate | n | SR | Frame |",
        "|---|---|---|---|",
        f"| MDS>0.50 + VP≥0.30 | {r['mds_high_vp_gate_in_midprice']['n']} | {r['mds_high_vp_gate_in_midprice']['sr']}% | {r['mds_high_vp_gate_in_midprice']['frame']}% |",
        f"| Improvement>0.40 + VP≥0.30 | {r['improver_vp_gate_in_midprice']['n']} | {r['improver_vp_gate_in_midprice']['sr']}% | {r['improver_vp_gate_in_midprice']['frame']}% |",
        "",
        "---",
        "",
        "## 8. Compression Test Inside Mid-Price",
        "",
    ]
    ct = r["compression_test"]
    if "note" not in ct:
        lines += [
            f"| Group | n | SR | Frame |",
            f"|---|---|---|---|",
            f"| Compression archetype | {ct['compression_n']} | {ct['compression_sr']}% | {ct['compression_frame']}% |",
            f"| Non-compression | {ct['non_compression_n']} | {ct['non_compression_sr']}% | — |",
        ]

    lines += [
        "",
        "---",
        "",
        "## 9. Winner SP Profile of Misses",
        "",
        "(When we missed in mid-price — what SP did the actual winner go off at?)",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Median winner SP | {ct_safe(r['winner_sp_profile_of_misses']['median_winner_sp'])} |",
        f"| Winner SP < 4.0 | {ct_safe(r['winner_sp_profile_of_misses']['pct_winner_sp_under_4'])}% |",
        f"| Winner SP 4.0–8.0 | {ct_safe(r['winner_sp_profile_of_misses']['pct_winner_sp_4_to_8'])}% |",
        f"| Winner SP > 8.0 | {ct_safe(r['winner_sp_profile_of_misses']['pct_winner_sp_over_8'])}% |",
        "",
        "---",
        "",
        "## 10. Race Class",
        "",
        "| Class | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for b in r["class_stats"]:
        lines.append(f"| Class {b['class']} | {b['n']} | {b['sr']}% | {b['frame']}% | {b['wins']} |")

    lines += [
        "",
        "---",
        "",
        "## 11. Field Size",
        "",
        "| Band | n | SR | Frame |",
        "|---|---|---|---|",
    ]
    for b in r["field_size_bands"]:
        lines.append(f"| {b['band']} | {b['n']} | {b['sr']}% | {b['frame']}% |")

    lines += [
        "",
        "---",
        "",
        "## 12. Going (top 8 by SR, min n=3)",
        "",
        "| Going | n | SR | Frame |",
        "|---|---|---|---|",
    ]
    for b in r["going_stats"]:
        lines.append(f"| {b['value']} | {b['n']} | {b['sr']}% | {b['frame']}% |")

    lines += [
        "",
        "---",
        "",
        "## 13. Course — Best and Worst",
        "",
        "**Best SR (min n=4):**",
        "",
        "| Course | n | SR | Frame |",
        "|---|---|---|---|",
    ]
    for b in r["course_best"]:
        lines.append(f"| {b['value']} | {b['n']} | {b['sr']}% | {b['frame']}% |")
    lines += [
        "",
        "**Worst SR (min n=4):**",
        "",
        "| Course | n | SR | Frame |",
        "|---|---|---|---|",
    ]
    for b in r["course_worst"]:
        lines.append(f"| {b['value']} | {b['n']} | {b['sr']}% | {b['frame']}% |")

    lines += [
        "",
        "---",
        "",
        "*SP_MIDPRICE_LEAK_AUDIT_V1 — generated by scripts/sp_midprice_leak_audit.py*",
    ]

    return "\n".join(lines)


def ct_safe(v):
    return v if v is not None else "n/a"


def main():
    result, mid_df = run_audit()

    # Write JSON
    json_path = REPORTS_DIR / "sp_midprice_leak_audit_latest.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    # Write markdown
    md = build_md(result)
    md_path = REPORTS_DIR / "sp_midprice_leak_audit_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    # Copy to docs/engineering
    docs_path = ROOT / "docs" / "engineering" / "SP_MIDPRICE_LEAK_AUDIT_V1.md"
    docs_path.write_text(md)
    print(f"Written: {docs_path}")

    # Print headline findings
    print("\n" + "=" * 60)
    print("HEADLINE FINDINGS")
    print("=" * 60)
    print(f"Mid-price SR overall: {result['midprice_sr']}% (n={result['midprice_n']})")
    sep = result["signal_separation"]
    print(f"\nSignal separation (winners vs bait):")
    for sig, v in sep.items():
        if v["delta"] is not None:
            print(f"  {sig}: winners={v['winners_avg']} bait={v['bait_avg']} delta={v['delta']:+.3f}")
    gates = result["mds_high_vp_gate_in_midprice"]
    print(f"\nMDS>0.5 + VP≥0.30 gate in mid-price: n={gates['n']} SR={gates['sr']}% Frame={gates['frame']}%")
    gates2 = result["improver_vp_gate_in_midprice"]
    print(f"Improvement>0.40 + VP≥0.30 gate in mid-price: n={gates2['n']} SR={gates2['sr']}% Frame={gates2['frame']}%")


if __name__ == "__main__":
    main()
