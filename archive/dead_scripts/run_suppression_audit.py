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
    "baseline_v1": {
        # Pre-calibration thresholds — kept for before/after comparison only
        "a_prob": 0.32, "a_gap": 0.08, "a_place": 0.52,
        "b_prob": 0.18, "b_gap": 0.03,
        "c_prob": 0.13, "c_gap": 0.02,
        "x_prob": 0.10, "x_longshot": 0.35,
        "x_strong_escape": False,  # escape hatch disabled
        "desc": "Pre-calibration baseline (b=0.18, no escape hatch)",
    },
    "calibrated_v1": {
        # Active thresholds after 2026-04-04 calibration
        "a_prob": 0.32, "a_gap": 0.08, "a_place": 0.52,
        "b_prob": 0.15, "b_gap": 0.03,
        "c_prob": 0.13, "c_gap": 0.02,
        "x_prob": 0.10, "x_longshot": 0.35,
        "x_strong_escape": True,   # escape: prob>=0.18 + place>=0.35 skips gap/longshot X
        "desc": "Calibrated v1 (b=0.15, strong-signal escape hatch active)",
    },
    "relaxed": {
        "a_prob": 0.26, "a_gap": 0.05, "a_place": 0.44,
        "b_prob": 0.15, "b_gap": 0.02,
        "c_prob": 0.10, "c_gap": 0.01,
        "x_prob": 0.08, "x_longshot": 0.50,
        "x_strong_escape": True,
        "desc": "Relaxed thresholds — more bets, lower bar",
    },
    "sqpe_direct": {
        "a_prob": 0.30, "a_gap": 0.06, "a_place": 0.0,
        "b_prob": 0.18, "b_gap": 0.02,
        "c_prob": 0.11, "c_gap": 0.01,
        "x_prob": 0.08, "x_longshot": 0.99,   # disable longshot X gate
        "x_strong_escape": False,
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

    # Strong-signal escape: horses with real edge bypass gap/longshot X gates.
    # macro_chaos_mode is always a hard block regardless of escape setting.
    use_escape = v.get("x_strong_escape", False)
    strong_escape = use_escape and (prob >= 0.18 and place >= 0.35)

    if (prob < v["x_prob"]
            or (gap < 0.015 and place < 0.40 and not strong_escape)
            or (longshot_trigger and not strong_escape)
            or chaos):
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


def _extract_top_pick(verdict: dict, sp_by_horse: dict | None = None) -> dict:
    """
    velo_verdicts is race-level: one row per race, with the top horse's summary
    fields as direct columns and full runner details in full_analysis (list).
    Returns a flat dict ready for classify().
    """
    fa = verdict.get("full_analysis") or []
    if isinstance(fa, str):
        fa = json.loads(fa)

    # Sort full_analysis runners by velo_prime_prob to find top + second
    runners = sorted(fa, key=lambda x: float(x.get("velo_prime_prob") or 0), reverse=True)
    top_runner = runners[0] if runners else {}
    second_prob = float(runners[1].get("velo_prime_prob") or 0) if len(runners) > 1 else 0.0
    top_prob = float(top_runner.get("velo_prime_prob") or 0)

    race_id   = verdict["race_id"]
    horse_id  = top_runner.get("horse_id") or verdict.get("top_rank_horse_id") or ""
    sp_key    = f"{race_id}:{horse_id}"
    sp_dec    = float((sp_by_horse or {}).get(sp_key) or 0)

    return {
        "race_id":            race_id,
        "horse_name":         top_runner.get("horse") or horse_id,
        "horse_id":           horse_id,
        "velo_prime_prob":    verdict.get("velo_prime_prob") or top_prob,
        "place_prob":         verdict.get("place_prob") or float(top_runner.get("place_prob") or 0),
        "improvement_score":  verdict.get("improvement_score") or float(top_runner.get("improvement_score") or 0),
        "longshot_prob":      verdict.get("longshot_prob") or float(top_runner.get("longshot_prob") or 0),
        "macro_chaos_mode":   verdict.get("macro_chaos_mode") or bool(top_runner.get("macro_chaos_mode")),
        "gap":                top_prob - second_prob,
        "sp_dec":             sp_dec,
        "stored_tier":        verdict.get("decision_tier"),
    }


def run_audit(days: int = 30, show_blocked: bool = False):
    print(f"\n{'='*65}")
    print(f"  VÉLØ SUPPRESSION AUDIT — last {days} days")
    print(f"{'='*65}\n")

    sb = get_client()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # velo_verdicts is race-level (one row per race / top selection).
    # full_analysis carries per-runner detail including second runner for gap calc.
    resp = sb.table("velo_verdicts") \
        .select("race_id,generated_at,decision_tier,velo_prime_prob,place_prob,"
                "improvement_score,longshot_prob,macro_chaos_mode,top_rank_horse_id,full_analysis") \
        .gte("generated_at", since) \
        .not_.is_("velo_prime_prob", "null") \
        .execute()

    verdicts = resp.data or []
    if not verdicts:
        print("No verdicts found in velo_verdicts for this period.")
        print("Check table name or date range.")
        return

    # Pull results for outcome mapping — runner_results has is_winner + sp_dec per horse
    result_resp = sb.table("runner_results") \
        .select("race_id,horse_id,position,is_winner,sp_dec") \
        .execute()

    # Build lookup: race_id → winner horse_id, and race_id+horse_id → sp_dec
    results_by_race: dict[str, dict] = {}
    sp_by_horse: dict[str, float] = {}   # key = race_id + ":" + horse_id
    for r in (result_resp.data or []):
        rid = r["race_id"]
        if r.get("is_winner"):
            results_by_race[rid] = {"winner_horse_id": r["horse_id"]}
        if r.get("sp_dec") and r.get("horse_id"):
            sp_by_horse[f"{rid}:{r['horse_id']}"] = float(r["sp_dec"])

    # Flatten to top-pick dicts (one per verdict row = one per race)
    top_picks = [_extract_top_pick(v, sp_by_horse) for v in verdicts]

    sp_coverage = sum(1 for p in top_picks if float(p.get("sp_dec") or 0) > 0)
    print(f"Loaded {len(top_picks)} race verdicts  |  results available: {len(results_by_race)}"
          f"  |  SP data: {sp_coverage}/{len(top_picks)} ({_pct(sp_coverage, len(top_picks))})")
    if sp_coverage < len(top_picks) * 0.5:
        print("  WARNING: SP coverage <50% — longshot trigger is SP-blind for missing races.")
        print("           This causes false X classifications on short-priced horses with high longshot_prob.")
    print()

    # Tier distribution comparison across all variants
    print(f"{'Variant':<22} {'A':>5} {'B':>5} {'C':>7} {'D':>7} {'X':>7} {'Act%':>8}  Description")
    print("-" * 80)

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
        print(f"{vname:<22} {counts['A']:>5} {counts['B']:>5} {counts['C']:>7} "
              f"{counts['D']:>7} {counts['X']:>7} {_pct(actionable, total):>8}  {vthresh['desc']}")
        detailed[vname] = picks_by_tier

    # Stored-tier vs re-classified comparison (shows drift from what was actually filed)
    stored_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "X": 0, "None": 0}
    for p in top_picks:
        t = p.get("stored_tier") or "None"
        stored_counts[t] = stored_counts.get(t, 0) + 1
    total = len(top_picks)
    act_stored = stored_counts.get("A", 0) + stored_counts.get("B", 0)
    print(f"\n{'stored_in_db':<22} {stored_counts.get('A',0):>5} {stored_counts.get('B',0):>5} "
          f"{stored_counts.get('C',0):>7} {stored_counts.get('D',0):>7} {stored_counts.get('X',0):>7} "
          f"{_pct(act_stored, total):>8}  Tiers actually written to velo_verdicts")

    # Outcome analysis (if results available)
    if results_by_race:
        print(f"\n{'─'*65}")
        print("OUTCOME ANALYSIS (where results available)")
        print(f"{'─'*65}")
        for vname, vthresh in VARIANTS.items():
            actionable = detailed[vname]["A"] + detailed[vname]["B"]
            if not actionable:
                continue
            wins = matched = 0
            for p in actionable:
                res = results_by_race.get(p.get("race_id"))
                if not res:
                    continue
                matched += 1
                if p.get("horse_id") == res.get("winner_horse_id"):
                    wins += 1
            print(f"  {vname:<22} actionable={len(actionable):>3}  matched={matched:>3}  wins={wins:>3}  hit%={_pct(wins, matched)}")

    # Blocked bet investigation: baseline_v1 (old) vs calibrated_v1 (new)
    if show_blocked:
        print(f"\n{'─'*65}")
        print("RESCUED RACES: baseline_v1 suppressed → calibrated_v1 fires")
        print(f"{'─'*65}")
        base_v  = VARIANTS["baseline_v1"]
        cal_v   = VARIANTS["calibrated_v1"]
        rescued = []
        for p in top_picks:
            base_tier = classify(p, base_v)
            cal_tier  = classify(p, cal_v)
            if base_tier in ("D", "X", "C") and cal_tier in ("A", "B"):
                res = results_by_race.get(p.get("race_id"))
                if res:
                    won = p.get("horse_id") == res.get("winner_horse_id")
                else:
                    won = "?"
                rescued.append({
                    "horse":      p.get("horse_name", ""),
                    "prob":       round(float(p.get("velo_prime_prob") or 0), 3),
                    "place":      round(float(p.get("place_prob") or 0), 3),
                    "gap":        round(float(p.get("gap") or 0), 3),
                    "longshot":   round(float(p.get("longshot_prob") or 0), 3),
                    "sp":         round(float(p.get("sp_dec") or 0), 1),
                    "chaos":      p.get("macro_chaos_mode"),
                    "base_tier":  base_tier,
                    "cal_tier":   cal_tier,
                    "won":        won,
                })

        print(f"  Total rescued races: {len(rescued)}")
        if rescued:
            wins_r = sum(1 for r in rescued if r["won"] is True)
            print(f"  Win hit rate (rescued): {_pct(wins_r, len(rescued))}")
        print()
        for row in rescued[:30]:
            won_marker = "WIN" if row["won"] is True else ("---" if row["won"] is False else "  ?")
            print(f"  {row['horse']:<30} prob={row['prob']:.3f} gap={row['gap']:.3f} "
                  f"place={row['place']:.3f} ls={row['longshot']:.3f} sp={row['sp']:>5.1f} "
                  f"{row['base_tier']}→{row['cal_tier']}  {won_marker}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",         type=int, default=30)
    parser.add_argument("--show-blocked", action="store_true")
    args = parser.parse_args()
    run_audit(days=args.days, show_blocked=args.show_blocked)
