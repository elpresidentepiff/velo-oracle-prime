#!/usr/bin/env python3
"""
MIDPRICE_ROUTER_SUPPRESSION_AUDIT_V1

Answers the money question:
  If we suppress SP 3.0–8.5 selections without router qualification,
  how many losers do we remove — and how many winners do we lose?

Evidence base: velo_innovation_protocol_1k_deduped.csv
  (has sp_decimal, router lane booleans, won, placed per selection)

Outputs:
    data/reports/midprice_router_suppression_audit_latest.json
    data/reports/midprice_router_suppression_audit_latest.md

Usage:
    python scripts/midprice_router_suppression_audit.py
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SP_LOW = 3.0
SP_HIGH = 8.5

ROUTER_LANE_COLS = {
    "V1_BASE": "router_v1_shadow_pass",
    "V2_CLASS4": "router_v2_class4_shadow_pass",
    "V6_GOLD_SEAM": "router_v6_gold_seam_watchlist",
}


def load_data() -> pd.DataFrame:
    path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    df = pd.read_csv(path)
    df["sp_decimal"] = pd.to_numeric(df["sp_decimal"], errors="coerce")
    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)
    # Router lane booleans
    for col in ROUTER_LANE_COLS.values():
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
        else:
            df[col] = False
    # Build composite router-qualified flag
    df["router_qualified"] = (
        df["router_v1_shadow_pass"] |
        df["router_v2_class4_shadow_pass"] |
        df["router_v6_gold_seam_watchlist"]
    )
    return df


def sr(grp: pd.DataFrame) -> float:
    if len(grp) == 0:
        return 0.0
    return round(grp["won"].sum() / len(grp) * 100, 1)


def frame(grp: pd.DataFrame) -> float:
    if len(grp) == 0:
        return 0.0
    return round(grp["placed"].sum() / len(grp) * 100, 1)


def roi(grp: pd.DataFrame) -> float | None:
    if len(grp) == 0:
        return None
    if "candidate_pl" not in grp.columns:
        return None
    pl = pd.to_numeric(grp["candidate_pl"], errors="coerce").sum()
    bets = len(grp)
    return round((pl / bets) * 100, 1)


def main():
    print("MIDPRICE ROUTER SUPPRESSION AUDIT V1")
    print("=" * 60)

    df = load_data()
    with_results = df[df["won"].notna()].copy()
    total_with_results = len(with_results)
    print(f"Total rows with results: {total_with_results}")

    # ── Universe partitions ───────────────────────────────────────────────────
    mid = with_results[
        (with_results["sp_decimal"] >= SP_LOW) &
        (with_results["sp_decimal"] <= SP_HIGH)
    ].copy()
    non_mid = with_results[
        (with_results["sp_decimal"] < SP_LOW) |
        (with_results["sp_decimal"] > SP_HIGH)
    ].copy()

    print(f"Mid-price (SP {SP_LOW}–{SP_HIGH}): n={len(mid)}  SR={sr(mid)}%  Frame={frame(mid)}%")
    print(f"Non-mid-price: n={len(non_mid)}  SR={sr(non_mid)}%  Frame={frame(non_mid)}%")

    # ── Router split within mid-price ─────────────────────────────────────────
    mid_qualified = mid[mid["router_qualified"]]
    mid_suppressed = mid[~mid["router_qualified"]]

    print(f"\nRouter-qualified (mid-price): n={len(mid_qualified)}  SR={sr(mid_qualified)}%  Frame={frame(mid_qualified)}%")
    print(f"Router-suppressed (mid-price): n={len(mid_suppressed)}  SR={sr(mid_suppressed)}%  Frame={frame(mid_suppressed)}%")

    # ── The money question ────────────────────────────────────────────────────
    suppressed_winners = int(mid_suppressed["won"].sum())
    suppressed_losers = int((~mid_suppressed["won"]).sum())
    suppressed_total = len(mid_suppressed)

    qualified_winners = int(mid_qualified["won"].sum())
    qualified_losers = int((~mid_qualified["won"]).sum())
    qualified_total = len(mid_qualified)

    # Coverage impact
    all_winners = int(with_results["won"].sum())
    pct_winners_lost = round(suppressed_winners / all_winners * 100, 1) if all_winners else 0
    pct_losers_removed = round(suppressed_losers / (len(with_results) - all_winners) * 100, 1)

    # Net effect simulation: if suppression had been active
    # Corpus becomes: all non-mid + mid_qualified only
    retained = pd.concat([non_mid, mid_qualified])
    net_sr = sr(retained)
    net_frame = frame(retained)
    net_n = len(retained)

    print(f"\nNET EFFECT IF SUPPRESSION ACTIVE:")
    print(f"  Retained: {net_n} rows (was {total_with_results})")
    print(f"  SR: {sr(with_results)}% → {net_sr}% ({net_sr - sr(with_results):+.1f}pp)")
    print(f"  Frame: {frame(with_results)}% → {net_frame}% ({net_frame - frame(with_results):+.1f}pp)")
    print(f"  Winners suppressed: {suppressed_winners} ({pct_winners_lost}% of all winners)")
    print(f"  Losers removed:     {suppressed_losers} ({pct_losers_removed}% of all losers)")

    # ── Per-lane breakdown ────────────────────────────────────────────────────
    lane_breakdown = []
    for lane_name, col in ROUTER_LANE_COLS.items():
        in_mid = mid[mid[col] == True]
        lane_breakdown.append({
            "lane": lane_name,
            "mid_price_n": len(in_mid),
            "mid_price_sr": sr(in_mid),
            "mid_price_frame": frame(in_mid),
            "wins": int(in_mid["won"].sum()),
        })

    # ── Tier breakdown of suppressed ─────────────────────────────────────────
    tier_suppressed = {}
    for tier, grp in mid_suppressed.groupby("tier"):
        tier_suppressed[str(tier)] = {
            "n": len(grp), "wins": int(grp["won"].sum()), "sr": sr(grp), "frame": frame(grp)
        }

    # ── Build result ──────────────────────────────────────────────────────────
    result = {
        "run_ts": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "sp_zone": f"{SP_LOW}–{SP_HIGH}",
        "total_corpus_with_results": total_with_results,
        "global_sr": sr(with_results),
        "global_frame": frame(with_results),
        "mid_price": {
            "n": len(mid), "sr": sr(mid), "frame": frame(mid),
            "winners": int(mid["won"].sum()), "losers": int((~mid["won"]).sum()),
        },
        "router_qualified": {
            "n": qualified_total, "sr": sr(mid_qualified), "frame": frame(mid_qualified),
            "winners": qualified_winners, "losers": qualified_losers,
        },
        "router_suppressed_advisory": {
            "n": suppressed_total, "sr": sr(mid_suppressed), "frame": frame(mid_suppressed),
            "winners": suppressed_winners, "losers": suppressed_losers,
        },
        "money_question": {
            "winners_suppressed": suppressed_winners,
            "pct_winners_lost": pct_winners_lost,
            "losers_removed": suppressed_losers,
            "pct_losers_removed": pct_losers_removed,
            "loser_to_winner_ratio_suppressed": round(suppressed_losers / suppressed_winners, 1) if suppressed_winners else None,
        },
        "net_effect_if_suppression_active": {
            "retained_n": net_n,
            "retained_sr": net_sr,
            "retained_frame": net_frame,
            "sr_delta": round(net_sr - sr(with_results), 1),
            "frame_delta": round(net_frame - frame(with_results), 1),
        },
        "per_lane_breakdown": lane_breakdown,
        "tier_breakdown_of_suppressed": tier_suppressed,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "staking_change": False,
            "router_change": False,
            "telegram_change": False,
            "classification": "ADVISORY_ONLY",
        },
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    json_path = REPORTS_DIR / "midprice_router_suppression_audit_latest.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = build_md(result)
    md_path = REPORTS_DIR / "midprice_router_suppression_audit_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return result


def build_md(r: dict) -> str:
    mq = r["money_question"]
    net = r["net_effect_if_suppression_active"]
    lines = [
        "# MIDPRICE ROUTER SUPPRESSION AUDIT V1",
        f"**Run:** {r['run_ts']}",
        f"**SP Zone:** {r['sp_zone']}",
        "",
        "---",
        "",
        "## The Money Question",
        "",
        "If we suppress SP 3.0–8.5 selections without router qualification,",
        "how many losers do we remove — and how many winners do we lose?",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total corpus (with results) | {r['total_corpus_with_results']} |",
        f"| Global SR | {r['global_sr']}% |",
        f"| Global Frame | {r['global_frame']}% |",
        "",
        "## Mid-Price Universe",
        "",
        "| Group | n | SR | Frame | Winners | Losers |",
        "|---|---|---|---|---|---|",
        f"| All mid-price | {r['mid_price']['n']} | {r['mid_price']['sr']}% | {r['mid_price']['frame']}% | {r['mid_price']['winners']} | {r['mid_price']['losers']} |",
        f"| Router-qualified | {r['router_qualified']['n']} | {r['router_qualified']['sr']}% | {r['router_qualified']['frame']}% | {r['router_qualified']['winners']} | {r['router_qualified']['losers']} |",
        f"| Router-suppressed (advisory) | {r['router_suppressed_advisory']['n']} | {r['router_suppressed_advisory']['sr']}% | {r['router_suppressed_advisory']['frame']}% | {r['router_suppressed_advisory']['winners']} | {r['router_suppressed_advisory']['losers']} |",
        "",
        "## Suppression Impact",
        "",
        "| Question | Answer |",
        "|---|---|",
        f"| Winners we would suppress | **{mq['winners_suppressed']}** ({mq['pct_winners_lost']}% of all winners) |",
        f"| Losers we would remove | **{mq['losers_removed']}** ({mq['pct_losers_removed']}% of all losers) |",
        f"| Loser:winner ratio (suppressed group) | **{mq['loser_to_winner_ratio_suppressed']}:1** |",
        "",
        "## Net Effect If Suppression Had Been Active",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---|---|---|",
        f"| n | {r['total_corpus_with_results']} | {net['retained_n']} | {net['retained_n'] - r['total_corpus_with_results']} |",
        f"| SR | {r['global_sr']}% | {net['retained_sr']}% | **{net['sr_delta']:+.1f}pp** |",
        f"| Frame | {r['global_frame']}% | {net['retained_frame']}% | **{net['frame_delta']:+.1f}pp** |",
        "",
        "## Router Lane Breakdown (Mid-Price Qualifiers)",
        "",
        "| Lane | n in mid-price | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for lane in r["per_lane_breakdown"]:
        lines.append(f"| {lane['lane']} | {lane['mid_price_n']} | {lane['mid_price_sr']}% | {lane['mid_price_frame']}% | {lane['wins']} |")

    lines += [
        "",
        "## Tier Breakdown of Suppressed Group",
        "",
        "| Tier | n | SR | Frame | Wins |",
        "|---|---|---|---|---|",
    ]
    for tier, v in sorted(r["tier_breakdown_of_suppressed"].items()):
        lines.append(f"| {tier} | {v['n']} | {v['sr']}% | {v['frame']}% | {v['wins']} |")

    lines += [
        "",
        "## Governance",
        "",
        "**This audit is ADVISORY ONLY. No changes made:**",
        "- Scoring: NO CHANGE",
        "- Model weights: NO CHANGE",
        "- Staking: NONE (paper only)",
        "- Router rules: NO CHANGE",
        "- Telegram format: NO CHANGE",
        "",
        "*MIDPRICE_ROUTER_SUPPRESSION_AUDIT_V1 — scripts/midprice_router_suppression_audit.py*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
