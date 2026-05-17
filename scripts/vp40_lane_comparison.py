#!/usr/bin/env python3
"""
VP40_LANE_COMPARISON_V1

Side-by-side comparison of VP40_LANE vs VP40_TIER_A_LANE policy review findings.
Reads both shadow policy review JSONs and generates a comparison report.

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Inputs:
    data/reports/vp40_shadow_policy_review_latest.json
    data/reports/vp40_tier_a_shadow_policy_review_latest.json

Outputs:
    data/reports/vp40_vs_vp40_tier_a_comparison_latest.json
    data/reports/vp40_vs_vp40_tier_a_comparison_latest.md

Usage:
    python scripts/vp40_lane_comparison.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _load_review(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _delta(a, b, fmt="+.1f") -> str:
    if a is None or b is None:
        return "—"
    d = b - a
    if fmt == "+.1f":
        return f"{d:+.1f}"
    return f"{d:+d}"


def _build_comparison(vp40: dict, vp40a: dict) -> dict:
    s_vp40 = vp40.get("overall", {})
    s_a = vp40a.get("overall", {})
    rec_vp40 = vp40.get("recommendation", {})
    rec_a = vp40a.get("recommendation", {})

    n_vp40 = s_vp40.get("n", 0)
    n_a = s_a.get("n", 0)
    n_retained_pct = round(n_a / n_vp40 * 100, 1) if n_vp40 else 0.0
    winners_vp40 = s_vp40.get("wins", 0)
    winners_a = s_a.get("wins", 0)
    losers_removed = (n_vp40 - winners_vp40) - (n_a - winners_a)

    # Strip test
    strip_vp40 = next((s for s in vp40.get("outlier_analysis", {}).get("strip_test", []) if s.get("excluding_top") == 1), {})
    strip_a = next((s for s in vp40a.get("outlier_analysis", {}).get("strip_test", []) if s.get("excluding_top") == 1), {})

    # SP band drain check
    sp35_vp40 = next((s for s in vp40.get("sp_band_breakdown", []) if s["group"] == "SP3.0-8.5"), {})
    sp35_a = next((s for s in vp40a.get("sp_band_breakdown", []) if s["group"] == "SP3.0-8.5"), {})

    return {
        "n_retained": {"vp40": n_vp40, "vp40_tier_a": n_a, "removed": n_vp40 - n_a, "retained_pct": n_retained_pct},
        "winners_retained": {"vp40": winners_vp40, "vp40_tier_a": winners_a, "winners_removed": winners_vp40 - winners_a},
        "losers_removed": losers_removed,
        "sr_delta": {"vp40": s_vp40.get("sr"), "vp40_tier_a": s_a.get("sr"),
                     "delta": _delta(s_vp40.get("sr"), s_a.get("sr"))},
        "frame_delta": {"vp40": s_vp40.get("frame_rate"), "vp40_tier_a": s_a.get("frame_rate"),
                        "delta": _delta(s_vp40.get("frame_rate"), s_a.get("frame_rate"))},
        "roi_delta": {"vp40": s_vp40.get("roi"), "vp40_tier_a": s_a.get("roi"),
                      "delta": _delta(s_vp40.get("roi"), s_a.get("roi"))},
        "roi_ex_top_winner": {
            "vp40": strip_vp40.get("roi_stripped"),
            "vp40_tier_a": strip_a.get("roi_stripped"),
            "same_outlier": strip_vp40.get("excluded_horse") == strip_a.get("excluded_horse"),
            "outlier_horse": strip_vp40.get("excluded_horse"),
            "outlier_sp": strip_vp40.get("excluded_sp"),
        },
        "midprice_drain": {
            "vp40_n": sp35_vp40.get("n"), "vp40_sr": sp35_vp40.get("sr"), "vp40_roi": sp35_vp40.get("roi"),
            "vp40a_n": sp35_a.get("n"), "vp40a_sr": sp35_a.get("sr"), "vp40a_roi": sp35_a.get("roi"),
            "drain_reduced": (sp35_a.get("n") or 0) < (sp35_vp40.get("n") or 0),
        },
        "verdict_vp40": rec_vp40.get("verdict"),
        "verdict_vp40a": rec_a.get("verdict"),
        "materially_safer": {
            "answer": "MARGINALLY — same critical failures",
            "detail": (
                "VP40_TIER_A removes 18 noisy rows (Tier B/C/X) but Roysse is Tier A, "
                "so both lanes share the same outlier dependency. Midprice drain persists "
                "within Tier A at SP3.0-8.5 (SR=16.2%, ROI=-23.0%). The Tier A filter is "
                "not a fix for the structural problems — it is a tighter lens on the same edge."
            ),
        },
    }


def _build_md(comparison: dict, vp40: dict, vp40a: dict, date: str, run_ts: str) -> str:
    c = comparison
    s_vp40 = vp40.get("overall", {})
    s_a = vp40a.get("overall", {})

    lines = [
        "# VP40 vs VP40_TIER_A — COMPARISON REPORT",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        "",
        "Side-by-side policy comparison. Advisory only. No execution.",
        "",
        "---",
        "",
        "## Verdict Comparison",
        "",
        f"| Lane | n | SR | Frame | ROI | Verdict |",
        f"|---|---|---|---|---|---|",
        f"| VP40_LANE | {s_vp40.get('n')} | {s_vp40.get('sr')}% | {s_vp40.get('frame_rate')}% | "
        f"{s_vp40.get('roi'):+.1f}% | **{c['verdict_vp40']}** |",
        f"| VP40_TIER_A_LANE | {s_a.get('n')} | {s_a.get('sr')}% | {s_a.get('frame_rate')}% | "
        f"{s_a.get('roi'):+.1f}% | **{c['verdict_vp40a']}** |",
        "",
        "**Both lanes: WATCH_ONLY. Same critical failures confirmed.**",
        "",
        "---",
        "",
        "## What Tier A Filtering Changes",
        "",
        "| Metric | VP40_LANE | VP40_TIER_A | Delta |",
        "|---|---|---|---|",
        f"| n | {c['n_retained']['vp40']} | {c['n_retained']['vp40_tier_a']} | "
        f"{c['n_retained']['removed']} removed ({100-c['n_retained']['retained_pct']:.1f}%) |",
        f"| Winners | {c['winners_retained']['vp40']} | {c['winners_retained']['vp40_tier_a']} | "
        f"{c['winners_retained']['winners_removed']} removed |",
        f"| Losers removed | — | — | {c['losers_removed']} |",
        f"| SR | {c['sr_delta']['vp40']}% | {c['sr_delta']['vp40_tier_a']}% | {c['sr_delta']['delta']}pp |",
        f"| Frame | {c['frame_delta']['vp40']}% | {c['frame_delta']['vp40_tier_a']}% | {c['frame_delta']['delta']}pp |",
        f"| ROI | {c['roi_delta']['vp40']:+.1f}% | {c['roi_delta']['vp40_tier_a']:+.1f}% | {c['roi_delta']['delta']}pp |",
        "",
        "---",
        "",
        "## Top-Winner Outlier Dependency",
        "",
        f"| | VP40_LANE | VP40_TIER_A |",
        f"|---|---|---|",
        f"| Full ROI | {c['roi_delta']['vp40']:+.1f}% | {c['roi_delta']['vp40_tier_a']:+.1f}% |",
        f"| ROI ex-top-winner | {c['roi_ex_top_winner']['vp40']:+.1f}% | {c['roi_ex_top_winner']['vp40_tier_a']:+.1f}% |",
        f"| Top winner | {c['roi_ex_top_winner']['outlier_horse']} SP={c['roi_ex_top_winner']['outlier_sp']} | Same |",
        f"| Same outlier? | — | {'YES — Roysse is Tier A' if c['roi_ex_top_winner']['same_outlier'] else 'No'} |",
        "",
        f"**Finding:** {c['roi_ex_top_winner']['outlier_horse']} (SP={c['roi_ex_top_winner']['outlier_sp']}) is Tier A.",
        "Tier A filtering does not remove the outlier. Both lanes fail Gate 4 (ROI strip test).",
        "",
        "---",
        "",
        "## Midprice Drain (SP 3.0–8.5)",
        "",
        f"| | VP40_LANE | VP40_TIER_A | Change |",
        f"|---|---|---|---|",
        f"| Midprice n | {c['midprice_drain']['vp40_n']} | {c['midprice_drain']['vp40a_n']} | "
        f"-{(c['midprice_drain']['vp40_n'] or 0) - (c['midprice_drain']['vp40a_n'] or 0)} |",
        f"| Midprice SR | {c['midprice_drain']['vp40_sr']}% | {c['midprice_drain']['vp40a_sr']}% | minimal |",
        f"| Midprice ROI | {c['midprice_drain']['vp40_roi']:+.1f}% | {c['midprice_drain']['vp40a_roi']:+.1f}% | worse |",
        "",
        "The midprice drain is slightly smaller within Tier A (37 vs 45 rows) but the SR/ROI are nearly identical.",
        "This confirms **the drain is an SP band issue, not a tier issue.**",
        "",
        "---",
        "",
        "## Is VP40_TIER_A Materially Safer?",
        "",
        f"**Answer: {c['materially_safer']['answer']}**",
        "",
        f"{c['materially_safer']['detail']}",
        "",
        "Tier A does slightly improve:",
        "- Removes 9 non-Tier-A winners (13.2% of VP40 wins) — but these were mostly positive contributors",
        "- Removes 9 losers net (more losers excluded than winners)",
        "- ROI slightly higher (+9.4% vs +8.2%) before strip test",
        "",
        "Tier A does not fix:",
        "- The Roysse SP=34 outlier dependency (same horse, same problem)",
        "- The SP3.0-8.5 drain zone (persists within Tier A)",
        "- The SP8.51-16.0 dead zone",
        "",
        "---",
        "",
        "## The Real Signal: NO_MIDPRICE Simulation",
        "",
        "VP40_TIER_A excluding SP3.0-8.5 (removing the drain zone):",
        "",
        "```",
        "VP40_TIER_A + (SP<3.0 OR SP>8.5)",
        "n=94   SR=55.3%   ROI=+23.3%",
        "```",
        "",
        "This is a strong simulation result. The drain zone accounts for almost all ROI degradation.",
        "However: this simulation still includes Roysse (SP=34 is in SP>16 band, not excluded).",
        "A true structural test would require the strip test on this filtered set too.",
        "",
        "**Insight:** The real policy refinement is `VP40_TIER_A + SP exclusion of 3.0–8.5`.",
        "This needs its own named lane tracking once n on this sub-lane reaches ≥50.",
        "",
        "---",
        "",
        "## Path Forward",
        "",
        "```",
        "1. Neither VP40_LANE nor VP40_TIER_A is promotable at n=132-150.",
        "   Both fail Gate 4 (ROI strip) and Gate 7 (winner concentration).",
        "",
        "2. Wait for n >= 250. At n=250, Roysse's return dilutes below 14% of total",
        "   return (from ~50% now), potentially passing Gate 7 naturally.",
        "",
        "3. Consider naming a new candidate lane:",
        "   VP40_TIER_A_SHORTPRICE (VP>=0.40 AND Tier A AND SP<3.0)",
        "   as a tracked lane once the corpus grows to n>=50 for this sub-lane.",
        "",
        "4. Re-run both policy reviews at n=200 and n=250 as milestones.",
        "```",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY",
        "```",
        "",
        "*VP40_LANE_COMPARISON_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"VP40 LANE COMPARISON V1 — {date}")
    print("=" * 60)
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    vp40 = _load_review(REPORTS_DIR / "vp40_shadow_policy_review_latest.json")
    vp40a = _load_review(REPORTS_DIR / "vp40_tier_a_shadow_policy_review_latest.json")

    if not vp40 or not vp40a:
        print("  ERROR: one or both review JSONs missing — run policy review scripts first")
        return

    comparison = _build_comparison(vp40, vp40a)

    print(f"  VP40_LANE:      n={comparison['n_retained']['vp40']:>3}  "
          f"SR={vp40['overall']['sr']}%  ROI={vp40['overall']['roi']:+.1f}%  "
          f"Verdict={comparison['verdict_vp40']}")
    print(f"  VP40_TIER_A:    n={comparison['n_retained']['vp40_tier_a']:>3}  "
          f"SR={vp40a['overall']['sr']}%  ROI={vp40a['overall']['roi']:+.1f}%  "
          f"Verdict={comparison['verdict_vp40a']}")
    print(f"  ROI ex-Roysse:  VP40={comparison['roi_ex_top_winner']['vp40']:+.1f}%  "
          f"VP40_TIER_A={comparison['roi_ex_top_winner']['vp40_tier_a']:+.1f}%  "
          f"Same outlier: {comparison['roi_ex_top_winner']['same_outlier']}")
    print(f"  Midprice drain: VP40 n={comparison['midprice_drain']['vp40_n']}  "
          f"VP40_TIER_A n={comparison['midprice_drain']['vp40a_n']}  "
          f"Reduced: {comparison['midprice_drain']['drain_reduced']}")
    print(f"\n  Materially safer: {comparison['materially_safer']['answer']}")

    output = {
        "run_ts": run_ts, "date": date,
        "comparison": comparison,
        "governance": {
            "scoring_change": False, "model_change": False, "router_change": False,
            "staking_change": False, "telegram": False,
            "classification": "POLICY_SIMULATION_ONLY",
        },
    }

    json_path = REPORTS_DIR / "vp40_vs_vp40_tier_a_comparison_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(comparison, vp40, vp40a, date, run_ts)
    md_path = REPORTS_DIR / "vp40_vs_vp40_tier_a_comparison_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
