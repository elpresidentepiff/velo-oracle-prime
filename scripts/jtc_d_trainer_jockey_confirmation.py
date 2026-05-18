#!/usr/bin/env python3
"""
JTC_D_TRAINER_JOCKEY_CONFIRMATION_V1

Tests whether trainer_jockey_sr (shrinkage-adjusted partnership strike rate)
improves outcome prediction for VÉLØ-selected candidates.

Uses runner_master_profile_latest.parquet (1,310 sigma rows with results).
Joins race metadata (dist, type, handicap) from results JSONs.

Analyses:
  1. TJ quartile → win rate, ROI, frame rate
  2. VP x TJ interaction (VP≥0.30 vs VP<0.30)
  3. Race type breakdown (Flat/Chase/Hurdle/NH Flat)
  4. Distance breakdown (sprint/mile/route)
  5. Handicap vs non-handicap
  6. SP band breakdown (short/medium/long price)
  7. Winner concentration — what % of wins sit in top TJ quartile?

Governance:
  NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
  JTC_D_TJ_CONFIRMATION = SHADOW_ONLY

Usage:
  python scripts/jtc_d_trainer_jockey_confirmation.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "features" / "runner_master_profile_latest.parquet"
RESULTS_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ── Race metadata from results JSONs ─────────────────────────────────────────

def _build_race_meta(sigma_race_ids: set) -> dict:
    """Extract dist, type, race_name for each race_id from results JSONs."""
    meta = {}
    for f in sorted(RESULTS_DIR.glob("results_*.json")):
        if "_partial" in f.name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            races = data.get("results", data) if isinstance(data, dict) else data
            if not isinstance(races, list):
                continue
            for race in races:
                rid = race.get("race_id", "")
                if rid not in sigma_race_ids:
                    continue
                meta[rid] = {
                    "dist": race.get("dist", ""),
                    "race_type_full": race.get("type", ""),
                    "race_name": race.get("race_name", ""),
                    "race_class": race.get("class", ""),
                }
        except Exception:
            continue
    return meta


def _dist_cat(dist_text: str) -> str:
    """sprint = ≤7f, mile = 8-10f, route = 11f+"""
    t = str(dist_text or "").lower().replace(" ", "").replace("½", ".5").replace("¼", ".25")
    m = re.match(r"(?:(\d+)m)?(\d+(?:\.\d+)?f)?", t)
    if not m:
        return "unknown"
    miles = int(m.group(1) or 0)
    furlongs = float((m.group(2) or "0f").replace("f", "") or 0)
    total_f = miles * 8 + furlongs
    if total_f <= 7:
        return "sprint"
    elif total_f <= 10:
        return "mile"
    else:
        return "route"


# ── ROI calculation ───────────────────────────────────────────────────────────

def _roi(df: pd.DataFrame) -> float:
    """Flat stake ROI at SP for a set of candidates."""
    if len(df) == 0:
        return float("nan")
    wins = df[df["won"] == True]
    total_return = float(wins["sp_decimal"].sum())
    total_stake = float(len(df))
    return round((total_return - total_stake) / total_stake * 100, 1)


def _stats(df: pd.DataFrame, label: str = "") -> dict:
    if len(df) == 0:
        return {"label": label, "n": 0, "win_rate": None, "frame_rate": None,
                "roi": None, "avg_vp": None, "avg_tj": None, "avg_sp": None}
    return {
        "label": label,
        "n": len(df),
        "win_rate": round(df["won"].mean() * 100, 1),
        "frame_rate": round(df["placed"].mean() * 100, 1) if "placed" in df.columns else None,
        "roi": _roi(df),
        "avg_vp": round(df["velo_prime_prob"].mean(), 4),
        "avg_tj": round(df["trainer_jockey_sr"].mean(), 4),
        "avg_sp": round(df["sp_decimal"].mean(), 2),
        "n_wins": int(df["won"].sum()),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("JTC-D TRAINER-JOCKEY CONFIRMATION V1")
    print("=" * 60)

    master = pd.read_parquet(MASTER)
    master = master[master["won"].notna()].copy()

    # Filter to TJ-available sigma candidates
    df = master[master["trainer_jockey_sr"].notna()].copy()
    print(f"Master: {len(master):,} rows  |  TJ available: {len(df):,} "
          f"({len(df)/len(master):.0%})")

    # ── Join race metadata ──────────────────────────────────────────────────
    race_ids = set(df["race_id"].unique())
    race_meta = _build_race_meta(race_ids)
    meta_df = pd.DataFrame.from_dict(race_meta, orient="index")
    meta_df.index.name = "race_id"
    df = df.join(meta_df, on="race_id", how="left")

    df["dist_cat"] = df["dist"].apply(_dist_cat)
    df["is_handicap"] = df["race_name"].str.lower().str.contains(
        r"handicap|h'cap|hcap", na=False, regex=True)
    df["is_jumps"] = df["race_type_full"].str.contains(
        "Chase|Hurdle|NH Flat", na=False)

    # SP bands
    df["sp_band"] = pd.cut(
        df["sp_decimal"],
        bins=[0, 3.0, 5.0, 8.5, 15.0, 9999],
        labels=["short(<3)", "fav(3-5)", "mid(5-8.5)", "long(8.5-15)", "outsider(15+)"],
        right=False,
    )

    n_meta = df["dist"].notna().sum()
    print(f"Race metadata joined: {n_meta:,} / {len(df):,} rows")
    print(f"Dist breakdown: {df['dist_cat'].value_counts().to_dict()}")
    print(f"Race type: {df['race_type_full'].value_counts().to_dict()}")
    print(f"Handicap: {df['is_handicap'].value_counts().to_dict()}")

    # ── TJ quartile split ──────────────────────────────────────────────────
    df["tj_quartile"] = pd.qcut(
        df["trainer_jockey_sr"], q=4,
        labels=["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]
    )
    df["tj_decile"] = pd.qcut(
        df["trainer_jockey_sr"], q=10,
        labels=[f"D{i}" for i in range(1, 11)]
    )

    print("\n── TJ Quartile Analysis ─────────────────────────────────────")
    quartile_stats = []
    for q in ["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]:
        sub = df[df["tj_quartile"] == q]
        s = _stats(sub, q)
        quartile_stats.append(s)
        print(f"  {q:<20} n={s['n']:>4}  WR={s['win_rate']:>5.1f}%  "
              f"ROI={s['roi']:>+7.1f}%  Frame={s['frame_rate']:>5.1f}%  "
              f"AvgVP={s['avg_vp']:.3f}  AvgTJ={s['avg_tj']:.4f}")

    # Monotonicity check
    wrs = [s["win_rate"] for s in quartile_stats if s["win_rate"] is not None]
    monotone = all(wrs[i] <= wrs[i+1] for i in range(len(wrs)-1))
    print(f"  Win rate monotonically increasing Q1→Q4: {'YES ✓' if monotone else 'NO'}")

    # ── Winner concentration ────────────────────────────────────────────────
    total_wins = int(df["won"].sum())
    q4_wins = int(df[df["tj_quartile"] == "Q4 (highest)"]["won"].sum())
    d10_wins = int(df[df["tj_decile"] == "D10"]["won"].sum())
    d9_wins = int(df[df["tj_decile"] == "D9"]["won"].sum())
    winner_conc = round(q4_wins / total_wins * 100, 1) if total_wins else 0
    print(f"\n  Total wins: {total_wins}  |  In Q4: {q4_wins} ({winner_conc}%)")
    print(f"  In D10 (top decile): {d10_wins} ({round(d10_wins/total_wins*100,1)}%)")

    # ── VP x TJ interaction ─────────────────────────────────────────────────
    print("\n── VP × TJ Interaction ──────────────────────────────────────")
    vp_cuts = [(0.0, 0.30, "VP<0.30"), (0.30, 1.0, "VP≥0.30")]
    tj_cuts = [("low", df["trainer_jockey_sr"] <= df["trainer_jockey_sr"].median()),
               ("high", df["trainer_jockey_sr"] > df["trainer_jockey_sr"].median())]

    vp_tj_stats = []
    for vp_lo, vp_hi, vp_label in vp_cuts:
        for tj_label, tj_mask in tj_cuts:
            sub = df[(df["velo_prime_prob"] >= vp_lo) & (df["velo_prime_prob"] < vp_hi) & tj_mask]
            s = _stats(sub, f"{vp_label} + TJ_{tj_label}")
            vp_tj_stats.append(s)
            print(f"  {s['label']:<30} n={s['n']:>4}  WR={s['win_rate'] or 0:>5.1f}%  "
                  f"ROI={s['roi'] or 0:>+7.1f}%  AvgSP={s['avg_sp'] or 0:.2f}")

    # ── Distance breakdown ──────────────────────────────────────────────────
    print("\n── Distance Category (TJ Q4 vs rest) ───────────────────────")
    dist_stats = []
    for cat in ["sprint", "mile", "route", "unknown"]:
        sub = df[df["dist_cat"] == cat]
        if len(sub) < 10:
            continue
        sub_q4 = sub[sub["tj_quartile"] == "Q4 (highest)"]
        sub_rest = sub[sub["tj_quartile"] != "Q4 (highest)"]
        s_all = _stats(sub, f"{cat} ALL")
        s_q4 = _stats(sub_q4, f"{cat} TJ_Q4")
        s_rest = _stats(sub_rest, f"{cat} TJ_Q1-3")
        dist_stats.append({"cat": cat, "all": s_all, "q4": s_q4, "rest": s_rest})
        lift = (s_q4["win_rate"] or 0) - (s_rest["win_rate"] or 0)
        print(f"  {cat:<8}  ALL={s_all['win_rate'] or 0:.1f}%  "
              f"Q4={s_q4['win_rate'] or 0:.1f}%  Q1-3={s_rest['win_rate'] or 0:.1f}%  "
              f"lift={lift:+.1f}pp  n_q4={s_q4['n']}")

    # ── Race type breakdown ─────────────────────────────────────────────────
    print("\n── Race Type (Flat vs Jumps) ────────────────────────────────")
    type_stats = []
    for is_j, label in [(False, "Flat"), (True, "Jumps")]:
        sub = df[df["is_jumps"] == is_j]
        sub_q4 = sub[sub["tj_quartile"] == "Q4 (highest)"]
        sub_rest = sub[sub["tj_quartile"] != "Q4 (highest)"]
        if len(sub) < 5:
            continue
        s_all = _stats(sub, f"{label} ALL")
        s_q4 = _stats(sub_q4, f"{label} TJ_Q4")
        s_rest = _stats(sub_rest, f"{label} TJ_Q1-3")
        type_stats.append({"type": label, "all": s_all, "q4": s_q4, "rest": s_rest})
        lift = (s_q4["win_rate"] or 0) - (s_rest["win_rate"] or 0)
        print(f"  {label:<8}  ALL={s_all['win_rate'] or 0:.1f}%  "
              f"Q4={s_q4['win_rate'] or 0:.1f}%  Q1-3={s_rest['win_rate'] or 0:.1f}%  "
              f"lift={lift:+.1f}pp  n_q4={s_q4['n']}")

    # ── Handicap breakdown ──────────────────────────────────────────────────
    print("\n── Handicap vs Non-Handicap ─────────────────────────────────")
    hcap_stats = []
    for is_h, label in [(True, "Handicap"), (False, "Non-Handicap")]:
        sub = df[df["is_handicap"] == is_h]
        sub_q4 = sub[sub["tj_quartile"] == "Q4 (highest)"]
        sub_rest = sub[sub["tj_quartile"] != "Q4 (highest)"]
        if len(sub) < 5:
            continue
        s_all = _stats(sub, f"{label} ALL")
        s_q4 = _stats(sub_q4, f"{label} TJ_Q4")
        s_rest = _stats(sub_rest, f"{label} TJ_Q1-3")
        hcap_stats.append({"type": label, "all": s_all, "q4": s_q4, "rest": s_rest})
        lift = (s_q4["win_rate"] or 0) - (s_rest["win_rate"] or 0)
        print(f"  {label:<15}  ALL={s_all['win_rate'] or 0:.1f}%  "
              f"Q4={s_q4['win_rate'] or 0:.1f}%  Q1-3={s_rest['win_rate'] or 0:.1f}%  "
              f"lift={lift:+.1f}pp  n_q4={s_q4['n']}")

    # ── SP band breakdown ────────────────────────────────────────────────────
    print("\n── SP Band (Q4 vs Q1-3) ─────────────────────────────────────")
    sp_band_stats = []
    for band in ["short(<3)", "fav(3-5)", "mid(5-8.5)", "long(8.5-15)", "outsider(15+)"]:
        sub = df[df["sp_band"] == band]
        sub_q4 = sub[sub["tj_quartile"] == "Q4 (highest)"]
        sub_rest = sub[sub["tj_quartile"] != "Q4 (highest)"]
        if len(sub) < 5:
            continue
        s_all = _stats(sub, f"{band}")
        s_q4 = _stats(sub_q4)
        s_rest = _stats(sub_rest)
        lift = (s_q4["win_rate"] or 0) - (s_rest["win_rate"] or 0)
        sp_band_stats.append({"band": band, "all": s_all, "q4": s_q4, "rest": s_rest})
        print(f"  {band:<18}  ALL={s_all['win_rate'] or 0:.1f}%  "
              f"Q4={s_q4['win_rate'] or 0:.1f}%  Q1-3={s_rest['win_rate'] or 0:.1f}%  "
              f"lift={lift:+.1f}pp  n_q4={s_q4['n']}")

    # ── Decile monotonicity strip ────────────────────────────────────────────
    print("\n── TJ Decile Strip (D1=lowest → D10=highest) ────────────────")
    decile_stats = []
    for d in [f"D{i}" for i in range(1, 11)]:
        sub = df[df["tj_decile"] == d]
        if len(sub) == 0:
            continue
        s = _stats(sub, d)
        decile_stats.append(s)
        bar = "█" * int(s["win_rate"] // 2) if s["win_rate"] else ""
        print(f"  {d:<4} n={s['n']:>3}  WR={s['win_rate'] or 0:>5.1f}%  "
              f"ROI={s['roi'] or 0:>+7.1f}%  {bar}")

    # ── Summary verdict ──────────────────────────────────────────────────────
    q1_wr = quartile_stats[0]["win_rate"] or 0
    q4_wr = quartile_stats[3]["win_rate"] or 0
    q4_roi = quartile_stats[3]["roi"] or 0
    q1_roi = quartile_stats[0]["roi"] or 0
    lift_pp = q4_wr - q1_wr
    roi_delta = q4_roi - q1_roi

    print("\n" + "=" * 60)
    print(f"Q1 win rate: {q1_wr:.1f}%  |  Q4 win rate: {q4_wr:.1f}%")
    print(f"Win rate lift Q4 vs Q1: {lift_pp:+.1f}pp")
    print(f"ROI delta Q4 vs Q1: {roi_delta:+.1f}pp")
    print(f"Winner concentration in Q4: {winner_conc}% of all wins")

    if monotone and lift_pp >= 5 and q4_roi > 0:
        verdict = "STRONG — TJ monotonically increases WR, Q4 ROI positive. Use as quality filter."
        status = "CONFIRMED_QUALITY_FILTER"
    elif monotone and lift_pp >= 3:
        verdict = "MODERATE — TJ monotone uplift. Q4 shows meaningful lift but ROI needs caution."
        status = "WATCHLIST_QUALITY_FILTER"
    elif lift_pp >= 2:
        verdict = "WEAK — Some Q4 lift but not monotone. Accumulate sample before acting."
        status = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "NO SIGNAL — TJ quartile does not consistently separate winners."
        status = "NOT_USEFUL"

    print(f"VERDICT: {verdict}")
    print(f"STATUS:  {status}")
    print(f"\nGovernance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE")
    print(f"JTC_D_TJ_CONFIRMATION = SHADOW_ONLY")

    # ── Write outputs ────────────────────────────────────────────────────────
    output = {
        "version": "JTC_D_TRAINER_JOCKEY_CONFIRMATION_V1",
        "n_candidates": len(df),
        "n_with_tj": len(df[df["trainer_jockey_sr"].notna()]),
        "total_wins": total_wins,
        "tj_median": round(float(df["trainer_jockey_sr"].median()), 5),
        "quartile_analysis": quartile_stats,
        "winner_concentration": {
            "q4_pct": winner_conc,
            "d10_pct": round(d10_wins / total_wins * 100, 1) if total_wins else 0,
        },
        "vp_tj_interaction": vp_tj_stats,
        "dist_breakdown": [
            {**d["all"], "q4": d["q4"], "rest": d["rest"]} for d in dist_stats
        ],
        "race_type_breakdown": [
            {**d["all"], "q4": d["q4"], "rest": d["rest"]} for d in type_stats
        ],
        "handicap_breakdown": [
            {**d["all"], "q4": d["q4"], "rest": d["rest"]} for d in hcap_stats
        ],
        "sp_band_breakdown": [
            {**d["all"], "q4": d["q4"], "rest": d["rest"]} for d in sp_band_stats
        ],
        "decile_strip": decile_stats,
        "verdict": verdict,
        "status": status,
        "monotone_wr": monotone,
        "lift_q4_vs_q1_pp": round(lift_pp, 1),
        "roi_delta_q4_vs_q1_pp": round(roi_delta, 1),
        "governance": "NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_ONLY",
    }

    json_path = REPORTS_DIR / "jtc_d_trainer_jockey_confirmation_latest.json"
    import json as json_mod
    json_path.write_text(json_mod.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(output, quartile_stats, decile_stats, vp_tj_stats,
                   dist_stats, type_stats, hcap_stats, sp_band_stats,
                   winner_conc, d10_wins, total_wins, monotone, lift_pp, roi_delta, verdict)
    md_path = REPORTS_DIR / "jtc_d_trainer_jockey_confirmation_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")


def _build_md(output, quartile_stats, decile_stats, vp_tj_stats,
              dist_stats, type_stats, hcap_stats, sp_band_stats,
              winner_conc, d10_wins, total_wins, monotone, lift_pp, roi_delta, verdict):
    lines = [
        "# JTC-D Trainer-Jockey Confirmation V1",
        "",
        f"n={output['n_candidates']} VÉLØ candidates | {output['n_with_tj']} with trainer_jockey_sr",
        "",
        "Post-score confirmation audit. TJ signal applied AFTER VÉLØ scores — not blended into VP.",
        "Shadow analysis only. No scoring change. No live mutation.",
        "",
        "---",
        "",
        "## TJ Quartile Analysis",
        "",
        "| Quartile | n | Win Rate | Frame | ROI | Avg VP | Avg TJ |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in quartile_stats:
        lines.append(
            f"| {s['label']} | {s['n']} | **{s['win_rate'] or 0:.1f}%** | "
            f"{s['frame_rate'] or 0:.1f}% | {s['roi'] or 0:+.1f}% | "
            f"{s['avg_vp'] or 0:.3f} | {s['avg_tj'] or 0:.4f} |"
        )
    lines += [
        "",
        f"Monotonically increasing Q1→Q4: **{'YES' if monotone else 'NO'}**",
        f"Win rate lift (Q4 vs Q1): **{lift_pp:+.1f}pp**",
        f"ROI delta (Q4 vs Q1): **{roi_delta:+.1f}pp**",
        "",
        "---",
        "",
        "## Winner Concentration",
        "",
        f"- Q4 contains **{winner_conc}%** of all {total_wins} wins",
        f"- Top decile (D10) contains **{round(d10_wins/total_wins*100,1) if total_wins else 0}%** of wins",
        "",
        "---",
        "",
        "## VP × TJ Interaction",
        "",
        "| Group | n | Win Rate | ROI | Avg SP |",
        "|---|---|---|---|---|",
    ]
    for s in vp_tj_stats:
        lines.append(
            f"| {s['label']} | {s['n']} | {s['win_rate'] or 0:.1f}% | "
            f"{s['roi'] or 0:+.1f}% | {s['avg_sp'] or 0:.2f} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Breakdown by Distance",
        "",
        "| Distance | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in dist_stats:
        lift = (d["q4"]["win_rate"] or 0) - (d["rest"]["win_rate"] or 0)
        lines.append(
            f"| {d['cat']} | {d['all']['n']} | {d['all']['win_rate'] or 0:.1f}% | "
            f"**{d['q4']['win_rate'] or 0:.1f}%** | {d['rest']['win_rate'] or 0:.1f}% | "
            f"{lift:+.1f}pp | {d['q4']['roi'] or 0:+.1f}% |"
        )
    lines += [
        "",
        "## Breakdown by Race Type (Flat vs Jumps)",
        "",
        "| Type | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in type_stats:
        lift = (d["q4"]["win_rate"] or 0) - (d["rest"]["win_rate"] or 0)
        lines.append(
            f"| {d['type']} | {d['all']['n']} | {d['all']['win_rate'] or 0:.1f}% | "
            f"**{d['q4']['win_rate'] or 0:.1f}%** | {d['rest']['win_rate'] or 0:.1f}% | "
            f"{lift:+.1f}pp | {d['q4']['roi'] or 0:+.1f}% |"
        )
    lines += [
        "",
        "## Handicap vs Non-Handicap",
        "",
        "| Type | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in hcap_stats:
        lift = (d["q4"]["win_rate"] or 0) - (d["rest"]["win_rate"] or 0)
        lines.append(
            f"| {d['type']} | {d['all']['n']} | {d['all']['win_rate'] or 0:.1f}% | "
            f"**{d['q4']['win_rate'] or 0:.1f}%** | {d['rest']['win_rate'] or 0:.1f}% | "
            f"{lift:+.1f}pp | {d['q4']['roi'] or 0:+.1f}% |"
        )
    lines += [
        "",
        "## SP Band Breakdown",
        "",
        "| SP Band | n | ALL WR | Q4 WR | Q1-3 WR | Lift |",
        "|---|---|---|---|---|---|",
    ]
    for d in sp_band_stats:
        lift = (d["q4"]["win_rate"] or 0) - (d["rest"]["win_rate"] or 0)
        lines.append(
            f"| {d['all']['label']} | {d['all']['n']} | {d['all']['win_rate'] or 0:.1f}% | "
            f"**{d['q4']['win_rate'] or 0:.1f}%** | {d['rest']['win_rate'] or 0:.1f}% | "
            f"{lift:+.1f}pp |"
        )
    lines += [
        "",
        "## TJ Decile Strip",
        "",
        "| Decile | n | Win Rate | ROI |",
        "|---|---|---|---|",
    ]
    for s in decile_stats:
        lines.append(
            f"| {s['label']} | {s['n']} | {s['win_rate'] or 0:.1f}% | {s['roi'] or 0:+.1f}% |"
        )
    lines += [
        "",
        "---",
        "",
        "## Summary Verdict",
        "",
        f"**{verdict}**",
        "",
        "```",
        "JTC_D_TJ_CONFIRMATION = SHADOW_ONLY",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE",
        "trainer_jockey_sr = post-score confirmation signal only",
        "```",
        "",
        "*JTC_D_TRAINER_JOCKEY_CONFIRMATION_V1 — advisory only*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
