"""
VÉLØ Suppression Audit
=======================
Runs recent scored races through three threshold variants and shows
exactly how many bets each tier fires + what the current thresholds are blocking.

Usage (inside Docker):
    python scripts/run_suppression_audit.py --days 30
    python scripts/run_suppression_audit.py --days 7 --show-blocked

Reads from Supabase: velo_verdicts (predictions) + race_results (outcomes)
Outputs: tier counts, suppression breakdown, ROI by tier
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")


def get_client():
    return create_client(SB_URL, SB_KEY)


# ── Threshold variants ────────────────────────────────────────────────────────

VARIANTS = {
    "current_prod": {
        "a_prob": 0.32, "a_gap": 0.08, "a_place": 0.52,
        "b_prob": 0.18, "b_gap": 0.03,
        "c_prob": 0.13, "c_gap": 0.02,
        "x_prob": 0.10, "x_longshot": 0.35,
        "desc": "Current production thresholds",
    },
    "relaxed": {
        "a_prob": 0.26, "a_gap": 0.05, "a_place": 0.44,
        "b_prob": 0.15, "b_gap": 0.02,
        "c_prob": 0.10, "c_gap": 0.01,
        "x_prob": 0.08, "x_longshot": 0.50,
        "desc": "Relaxed thresholds — more bets, lower bar",
    },
    "sqpe_direct": {
        "a_prob": 0.30, "a_gap": 0.06, "a_place": 0.0,
        "b_prob": 0.18, "b_gap": 0.02,
        "c_prob": 0.11, "c_gap": 0.01,
        "x_prob": 0.08, "x_longshot": 0.99,   # disable longshot X gate
        "desc": "SQPE-direct — no place floor, longshot gate disabled",
    },
}


def classify(p: dict, v: dict) -> str:
    prob    = float(p.get("velo_prime_prob") or 0)
    place   = float(p.get("place_prob") or 0)
    improve = float(p.get("improvement_score") or 0)
    longshot = float(p.get("longshot_prob") or 0)
    sp_dec  = float(p.get("sp_dec") or 0)
    chaos   = bool(p.get("macro_chaos_mode") or False)
    gap     = float(p.get("gap") or 0)   # pre-computed second_prob gap

    longshot_trigger = longshot > v["x_longshot"] and sp_dec >= 10.0

    if prob < v["x_prob"] or (gap < 0.015 and place < 0.40) or longshot_trigger or chaos:
        return "X"
    if prob >= v["a_prob"] and gap >= v["a_gap"] and place >= v["a_place"]:
        return "A"
    if prob >= v["b_prob"] and gap >= v["b_gap"]:
        if place >= 0.45 or gap >= 0.08 or improve >= 0.18:
            return "B"
    if (prob >= v["c_prob"] and gap >= v["c_gap"]) or (place >= 0.55 and prob >= 0.11):
        return "C"
    return "D"


def _pct(n, d):
    return f"{n/d*100:.1f}%" if d else "0%"


def run_audit(days: int = 30, show_blocked: bool = False):
    print(f"\n{'='*65}")
    print(f"  VÉLØ SUPPRESSION AUDIT — last {days} days")
    print(f"{'='*65}\n")

    sb = get_client()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Pull verdicts
    resp = sb.table("velo_verdicts") \
        .select("race_id,horse_name,velo_prime_prob,place_prob,improvement_score,"
                "longshot_prob,sp_dec,macro_chaos_mode,confidence_level,"
                "release_day_prob,market_deception_score") \
        .gte("created_at", since) \
        .execute()

    verdicts = resp.data or []
    if not verdicts:
        print("No verdicts found in velo_verdicts for this period.")
        print("Check table name or date range.")
        return

    # Pull results for outcome mapping
    result_resp = sb.table("race_results") \
        .select("race_id,winner_horse_name,top4_horse_names") \
        .gte("race_date", since) \
        .execute()

    results_by_race: dict[str, dict] = {}
    for r in (result_resp.data or []):
        results_by_race[r["race_id"]] = r

    # Need gap — compute per race
    races: dict[str, list] = {}
    for v in verdicts:
        races.setdefault(v["race_id"], []).append(v)

    for race_id, runners in races.items():
        sorted_r = sorted(runners, key=lambda x: float(x.get("velo_prime_prob") or 0), reverse=True)
        top_prob = float(sorted_r[0].get("velo_prime_prob") or 0) if sorted_r else 0
        second_prob = float(sorted_r[1].get("velo_prime_prob") or 0) if len(sorted_r) > 1 else 0
        for r in runners:
            r["gap"] = top_prob - second_prob if float(r.get("velo_prime_prob") or 0) == top_prob else 0

    print(f"Loaded {len(verdicts)} runner predictions across {len(races)} races\n")

    # Only analyze top pick per race
    top_picks = [sorted(runners, key=lambda x: float(x.get("velo_prime_prob") or 0), reverse=True)[0]
                 for runners in races.values()]

    print(f"{'Variant':<20} {'A':>5} {'B':>5} {'C':>7} {'D':>7} {'X':>7} {'Act%':>8}  Description")
    print("-" * 75)

    detailed: dict[str, list] = {}
    for vname, vthresh in VARIANTS.items():
        counts = {"A": 0, "B": 0, "C": 0, "D": 0, "X": 0}
        picks_by_tier: dict[str, list] = {"A": [], "B": [], "C": [], "D": [], "X": []}
        for p in top_picks:
            tier = classify(p, vthresh)
            counts[tier] += 1
            picks_by_tier[tier].append(p)

        total = sum(counts.values())
        actionable = counts["A"] + counts["B"]
        print(f"{vname:<20} {counts['A']:>5} {counts['B']:>5} {counts['C']:>7} "
              f"{counts['D']:>7} {counts['X']:>7} {_pct(actionable, total):>8}  {vthresh['desc']}")
        detailed[vname] = picks_by_tier

    # Outcome analysis (if results available)
    if results_by_race:
        print(f"\n{'─'*65}")
        print("OUTCOME ANALYSIS (where results available)")
        print(f"{'─'*65}")
        for vname, vthresh in VARIANTS.items():
            a_picks = detailed[vname]["A"]
            b_picks = detailed[vname]["B"]
            actionable = a_picks + b_picks
            if not actionable:
                continue
            wins = 0
            for p in actionable:
                res = results_by_race.get(p.get("race_id"), {})
                winner = (res.get("winner_horse_name") or "").lower()
                if p.get("horse_name", "").lower() == winner:
                    wins += 1
            print(f"  {vname:<20} actionable={len(actionable):>3}  wins={wins:>3}  hit={_pct(wins, len(actionable))}")

    # Blocked bet investigation
    if show_blocked:
        print(f"\n{'─'*65}")
        print("BETS FIRED BY current_prod vs sqpe_direct (differences)")
        print(f"{'─'*65}")
        prod_v   = VARIANTS["current_prod"]
        direct_v = VARIANTS["sqpe_direct"]
        unblocked = []
        for p in top_picks:
            prod_tier   = classify(p, prod_v)
            direct_tier = classify(p, direct_v)
            if prod_tier in ("D", "X", "C") and direct_tier in ("A", "B"):
                res = results_by_race.get(p.get("race_id"), {})
                winner = (res.get("winner_horse_name") or "").lower()
                won = p.get("horse_name", "").lower() == winner
                unblocked.append({
                    "horse": p.get("horse_name"),
                    "prob":  round(float(p.get("velo_prime_prob") or 0), 3),
                    "place": round(float(p.get("place_prob") or 0), 3),
                    "gap":   round(float(p.get("gap") or 0), 3),
                    "longshot": round(float(p.get("longshot_prob") or 0), 3),
                    "sp":    round(float(p.get("sp_dec") or 0), 1),
                    "chaos": p.get("macro_chaos_mode"),
                    "prod_tier":   prod_tier,
                    "direct_tier": direct_tier,
                    "won": won if res else "?",
                })
        print(f"  Races blocked by PROD but would fire under SQPE_DIRECT: {len(unblocked)}")
        for row in unblocked[:20]:
            won_marker = "✓WIN" if row["won"] is True else ("✗" if row["won"] is False else "?")
            print(f"  {row['horse']:<28} prob={row['prob']:.3f} gap={row['gap']:.3f} "
                  f"place={row['place']:.3f} longshot={row['longshot']:.3f} sp={row['sp']:>6.1f} "
                  f"prod={row['prod_tier']} → direct={row['direct_tier']}  {won_marker}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",         type=int, default=30)
    parser.add_argument("--show-blocked", action="store_true")
    args = parser.parse_args()
    run_audit(days=args.days, show_blocked=args.show_blocked)
