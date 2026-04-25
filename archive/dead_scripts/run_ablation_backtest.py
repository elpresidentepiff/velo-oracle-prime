"""
VÉLØ Ablation Backtest
======================
Re-scores historical races in three ensemble modes using stored specialist
values from velo_verdicts.full_analysis. Joins against runner_results to
evaluate top-1 hit rate and other outcome metrics.

The point: do NOT use stored velo_prime_prob. Recompute from stored runner-level
specialist scores under each mode. This isolates the contribution of each
component set to actual predictive lift.

Modes
-----
  SQPE_ONLY       — only sqpe_v17_prob (pure baseline)
  SQPE_PLUS_PLACE — sqpe_v17_prob + place_prob (tests Place lift)
  FULL_MINUS_DEAD — live stack: sqpe + improvement + market_deception + longshot
                    (release_window + comment_intel already disabled)

Field name mapping (full_analysis → ensemble)
----------------------------------------------
  release_day_prob  → release_window_score  (raw specialist output, always disabled)
  longshot_prob     → longshot_score
  comment_intel_score → comment_intel_score (same key, always disabled)

Usage
-----
    python scripts/run_ablation_backtest.py --days 35
    python scripts/run_ablation_backtest.py --days 60 --verbose
    python scripts/run_ablation_backtest.py --days 7   # just latest week
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client

from src.intelligence.velo_prime_ensemble import (
    VeloPrimeEnsemble,
    ABLATION_SQPE_ONLY,
    ABLATION_SQPE_PLUS_PLACE,
    ABLATION_SQPE_PLUS_PLACE_PLUS_IMPROVE,
    ABLATION_SQPE_PLUS_PLACE_PLUS_MKT,
    ABLATION_SQPE_PLUS_PLACE_PLUS_LONG,
    ABLATION_FULL_MINUS_DEAD,
)

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

MODES = [
    ABLATION_SQPE_ONLY,
    ABLATION_SQPE_PLUS_PLACE,
    ABLATION_SQPE_PLUS_PLACE_PLUS_IMPROVE,
    ABLATION_SQPE_PLUS_PLACE_PLUS_MKT,
    ABLATION_SQPE_PLUS_PLACE_PLUS_LONG,
    ABLATION_FULL_MINUS_DEAD,
]

TIERS = ("A", "B", "C", "D", "X")


def _pct(n: int, d: int) -> str:
    return f"{n / d * 100:.1f}%" if d else "n/a"


def _synthesize_tier(top_prob: float, second_prob: float, place: float,
                     improve: float, chaos: bool, longshot: float) -> str:
    """Simplified decision tier re-sim matching calibrated thresholds (B=0.15, X escape)."""
    gap = top_prob - second_prob
    eff_conf = "high" if top_prob >= 0.45 else "normal" if top_prob >= 0.15 else "low"

    # X-CHAOS escape hatch: strong signal overrides gap/longshot X triggers
    x_escape = (top_prob >= 0.18 and place >= 0.35)

    if top_prob < 0.10 or chaos:
        return "X"
    if not x_escape and (gap < 0.015 and place < 0.40):
        return "X"
    if not x_escape and longshot >= 0.50 and top_prob < 0.25:
        return "X"
    if top_prob >= 0.32 and gap >= 0.08 and place >= 0.52:
        return "A"
    if top_prob >= 0.15 and gap >= 0.03 and eff_conf != "low":
        if place >= 0.45 or gap >= 0.08 or improve >= 0.18:
            return "B"
    if (top_prob >= 0.13 and gap >= 0.02) or (place >= 0.55 and top_prob >= 0.11):
        return "C"
    return "D"


def _rescore_race(runners: list[dict], mode: str) -> list[dict]:
    """
    Re-run VeloPrimeEnsemble on a set of stored runner dicts.

    Stored field names → ensemble field names:
      release_day_prob  → release_window_score
      longshot_prob     → longshot_score

    sp_dec is not stored in full_analysis so longshot SP-gate cannot apply.
    This means longshot is included unconditionally in FULL_MINUS_DEAD mode
    when a longshot_prob value exists — slight over-inclusion, noted in output.
    """
    ensemble_inputs = []
    for r in runners:
        ensemble_inputs.append({
            "horse":                 r.get("horse", r.get("horse_id", "unknown")),
            "race_id":               r.get("race_id", ""),
            "sqpe_v17_prob":         float(r.get("sqpe_v17_prob") or 0.0),
            "improvement_score":     r.get("improvement_score"),
            "release_window_score":  r.get("release_day_prob"),   # key mapping
            "market_deception_score": r.get("market_deception_score"),
            "place_prob":            r.get("place_prob"),
            "comment_intel_score":   r.get("comment_intel_score"),
            "longshot_score":        r.get("longshot_prob"),      # key mapping
            # sp_dec absent — longshot SP-gate not applied in backtest
            "sp_dec":                None,
            "is_fav":                bool(r.get("is_fav", False)),
        })

    ensemble = VeloPrimeEnsemble()
    preds = ensemble.predict_race(ensemble_inputs, macro_context=None, mode=mode)

    # Map back to runner dicts with rescore results
    results = []
    for pred in preds:
        results.append({
            "horse":          pred.horse,
            "horse_id":       next(
                (ei["race_id"] and r.get("horse_id") for r, ei in zip(runners, ensemble_inputs)
                 if ei["horse"] == pred.horse),
                None,
            ),
            "velo_prime_prob": pred.velo_prime_prob,
            "place_prob":      pred.place_prob,
            "improvement_score": pred.improvement_score,
            "macro_chaos_mode": False,
            "longshot_prob":   pred.longshot_score,
            "active_components": pred.active_components,
        })
    return results


def _rescore_race_with_horse_ids(runners: list[dict], mode: str) -> list[dict]:
    """Wrapper that preserves horse_id through the rescore."""
    horse_id_map = {
        r.get("horse", r.get("horse_id", "unknown")): r.get("horse_id")
        for r in runners
    }
    rescored = _rescore_race(runners, mode)
    for row in rescored:
        row["horse_id"] = horse_id_map.get(row["horse"])
    return rescored


def run_backtest(days: int = 35, verbose: bool = False):
    print(f"\n{'='*70}")
    print(f"  VÉLØ ABLATION BACKTEST — last {days} days")
    print(f"  Modes: {' | '.join(MODES)}")
    print(f"{'='*70}\n")

    sb = create_client(SB_URL, SB_KEY)
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")

    # -- Load verdicts ---------------------------------------------------------
    resp = (
        sb.table("velo_verdicts")
        .select("race_id,generated_at,engine_version,full_analysis")
        .gte("generated_at", since)
        .eq("engine_version", "velo_prime_v1")
        .not_.is_("full_analysis", "null")
        .execute()
    )
    verdicts = resp.data or []
    print(f"Verdicts loaded (velo_prime_v1): {len(verdicts)}")

    if not verdicts:
        print("  No velo_prime_v1 verdicts found in window. Exiting.")
        return

    # -- Load outcomes ---------------------------------------------------------
    race_ids = list({v["race_id"] for v in verdicts})
    # Batch runner_results queries (Supabase in() limit ~200)
    winners: dict[str, set[str]] = defaultdict(set)  # race_id → set of winning horse_ids
    batch_size = 150
    total_outcome_rows = 0
    for i in range(0, len(race_ids), batch_size):
        batch = race_ids[i:i + batch_size]
        res = (
            sb.table("runner_results")
            .select("race_id,horse_id,is_winner,sp_dec")
            .in_("race_id", batch)
            .eq("is_winner", True)
            .execute()
        )
        for row in (res.data or []):
            winners[row["race_id"]].add(row["horse_id"])
        total_outcome_rows += len(res.data or [])

    races_with_outcomes = len([rid for rid in race_ids if rid in winners])
    print(f"runner_results winner rows: {total_outcome_rows} "
          f"| races with outcomes: {races_with_outcomes}/{len(race_ids)}\n")

    # -- Rescore in each mode -------------------------------------------------
    # Results structure per mode:
    #   top1_hits, top1_total (races where we have outcomes)
    #   tier_dist, actionable_count
    #   winner_probs (velo_prime_prob of actual winner when known)
    mode_results: dict[str, dict] = {
        m: {
            "top1_hits": 0, "top1_total": 0,
            "tier_dist": Counter(),
            "actionable_count": 0,
            "winner_probs": [],
            "races_scored": 0,
            "active_components_sample": None,
        }
        for m in MODES
    }

    for verdict in verdicts:
        race_id = verdict["race_id"]
        fa = verdict.get("full_analysis") or []
        if isinstance(fa, str):
            fa = json.loads(fa)
        if not fa or not isinstance(fa, list) or len(fa) < 2:
            continue

        for mode in MODES:
            mr = mode_results[mode]
            try:
                rescored = _rescore_race_with_horse_ids(fa, mode)
            except Exception as e:
                if verbose:
                    print(f"  [WARN] rescore failed race={race_id} mode={mode}: {e}")
                continue

            if not rescored:
                continue

            mr["races_scored"] += 1
            if mr["active_components_sample"] is None:
                mr["active_components_sample"] = rescored[0].get("active_components", [])

            # Sort by velo_prime_prob desc (should already be sorted)
            rescored.sort(key=lambda x: x["velo_prime_prob"], reverse=True)
            top = rescored[0]
            second_prob = rescored[1]["velo_prime_prob"] if len(rescored) > 1 else 0.0

            # Tier re-simulation
            tier = _synthesize_tier(
                top_prob=top["velo_prime_prob"],
                second_prob=second_prob,
                place=float(top.get("place_prob") or 0),
                improve=float(top.get("improvement_score") or 0),
                chaos=bool(top.get("macro_chaos_mode", False)),
                longshot=float(top.get("longshot_prob") or 0),
            )
            mr["tier_dist"][tier] += 1
            if tier in ("A", "B"):
                mr["actionable_count"] += 1

            # Outcome evaluation
            race_winners = winners.get(race_id, set())
            if race_winners:
                mr["top1_total"] += 1
                top_horse_id = top.get("horse_id")
                if top_horse_id and top_horse_id in race_winners:
                    mr["top1_hits"] += 1
                # Winner's probability under this mode
                for runner in rescored:
                    if runner.get("horse_id") in race_winners:
                        mr["winner_probs"].append(runner["velo_prime_prob"])
                        break

    # -- Report ----------------------------------------------------------------
    print(f"{'-'*70}")
    print("ABLATION RESULTS")
    print(f"{'-'*70}\n")

    for mode in MODES:
        mr = mode_results[mode]
        races = mr["races_scored"]
        actionable = mr["actionable_count"]
        top1_hits = mr["top1_hits"]
        top1_total = mr["top1_total"]
        winner_probs = mr["winner_probs"]
        td = mr["tier_dist"]
        active = mr["active_components_sample"] or []

        print(f"  MODE: {mode}")
        print(f"  Active components: {', '.join(active)}")
        print(f"  Races scored:      {races}")

        # Tier distribution
        tier_str = "  ".join(f"{t}={td.get(t, 0)}" for t in TIERS)
        print(f"  Tier dist:         {tier_str}")
        print(f"  Actionable (A+B):  {actionable}/{races}  ({_pct(actionable, races)})")

        # Top-1 hit rate
        if top1_total:
            print(f"  Top-1 hit rate:    {top1_hits}/{top1_total}  ({_pct(top1_hits, top1_total)})")
        else:
            print(f"  Top-1 hit rate:    n/a — no outcome data")

        # Winner probability
        if winner_probs:
            avg_wp = sum(winner_probs) / len(winner_probs)
            print(f"  Avg winner prob:   {avg_wp:.4f}  (over {len(winner_probs)} races with outcomes)")

        print()

    # -- Comparison table ------------------------------------------------------
    print(f"{'-'*70}")
    print("COMPARISON")
    print(f"{'-'*70}")
    header = f"{'Mode':<20} {'Races':>7} {'Act%':>7} {'Top-1%':>8} {'AvgWinP':>9}"
    print(header)
    print("-" * len(header))
    for mode in MODES:
        mr = mode_results[mode]
        races = mr["races_scored"]
        act_pct = mr["actionable_count"] / races * 100 if races else 0
        top1_pct = mr["top1_hits"] / mr["top1_total"] * 100 if mr["top1_total"] else float("nan")
        avg_wp = (sum(mr["winner_probs"]) / len(mr["winner_probs"])) if mr["winner_probs"] else float("nan")
        top1_str = f"{top1_pct:.1f}%" if not math.isnan(top1_pct) else "n/a"
        wp_str = f"{avg_wp:.4f}" if not math.isnan(avg_wp) else "n/a"
        print(f"  {mode:<18} {races:>7} {act_pct:>6.1f}% {top1_str:>8} {wp_str:>9}")

    print(f"\n{'-'*70}")
    print("NOTES")
    print(f"{'-'*70}")
    print("  - release_day_prob (stored) = release_window_score (disabled) — raw specialist, not used")
    print("  - comment_intel_score (stored) = constant 0.0889 — raw specialist, not used")
    print("  - longshot SP-gate NOT applied in backtest (sp_dec not in full_analysis)")
    print("  - Tier re-sim uses calibrated thresholds: B>=0.15, X escape at prob>=0.18+place>=0.35")
    print("  - Top-1 hit rate requires runner_results rows — coverage depends on backfill status")
    print()


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Ablation Backtest")
    parser.add_argument("--days", type=int, default=35,
                        help="Number of days of history to score (default: 35)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-race warnings")
    args = parser.parse_args()
    run_backtest(days=args.days, verbose=args.verbose)


if __name__ == "__main__":
    main()
