#!/usr/bin/env python3.11
"""
TIE v3 Threshold Sweep
======================
Simulates the TIE v3 gate at different MIN_SIGNALS_FOR_UPGRADE thresholds
against historical verdict data to find the optimal upgrade point.

The gate now has 10 possible signals:
  Tier 1 (Mechanical):
    1. rested_and_fit
    2. class_drop_or_same
    3. win_withheld
    4. in_form_placed_recently
    5. trainer_timing_pattern
    6. market_mid_range_support
  Tier 3 (Specialist):
    7. first_time_headgear
    8. first_run_since_wind_surgery
    9. high_spotlight_conviction
    10. handicap_plot_active

With MIN_SIGNALS=4, a horse needs 4 of 10 signals to upgrade.
This sweep tests thresholds 2-6 to find the sweet spot.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.intelligence.tie_v3_gate import TIEv3Gate


def build_synthetic_scenarios():
    """
    Build realistic test scenarios based on the 1,107-race forensic audit.
    Each scenario represents a horse archetype with known features.
    """
    scenarios = []

    # ── ARCHETYPE 1: Classic Plot Horse ──────────────────────────────────────
    # Dropped in class, rested, near winning mark, first-time headgear
    # This is the horse VÉLØ should be screaming about
    scenarios.append({
        "name": "Plot Horse (Classic)",
        "expected_tier": "B",  # Should upgrade from C
        "should_fire": True,
        "features": {
            "days_since_run": 28,           # rested_and_fit ✓
            "class_delta": -1,              # class_drop_or_same ✓
            "runs_since_win": 8,            # win_withheld ✓
            "runs_since_place": 3,          # in_form_placed_recently ✓
            "trainer_timing_score": 0.6,    # trainer_timing_pattern ✓
            "sp_dec": 6.0,
            "sp_rank": 3,
            "is_fav": False,                # market_mid_range_support ✓
            "headgear_run": 1,              # first_time_headgear ✓
            "wind_surgery_run": 0,
            "spotlight_score": 0.8,         # high_spotlight_conviction ✓
            "handicap_plot_score": 1.0,     # handicap_plot_active ✓
        },
    })

    # ── ARCHETYPE 2: Education Run → Release ─────────────────────────────────
    # Horse that's been setup, now back with gear change and plot
    scenarios.append({
        "name": "Education → Release",
        "expected_tier": "B",
        "should_fire": True,
        "features": {
            "days_since_run": 21,           # rested_and_fit ✓
            "class_delta": 0,               # class_drop_or_same ✓
            "runs_since_win": 10,           # win_withheld ✓
            "runs_since_place": 5,          # NOT in_form_placed_recently
            "trainer_timing_score": 0.3,    # NOT trainer_timing_pattern
            "sp_dec": 8.0,
            "sp_rank": 5,
            "is_fav": False,
            "headgear_run": 1,              # first_time_headgear ✓
            "wind_surgery_run": 0,
            "spotlight_score": 0.75,        # high_spotlight_conviction ✓
            "handicap_plot_score": 0.95,    # handicap_plot_active ✓
        },
    })

    # ── ARCHETYPE 3: Wind Surgery Return ─────────────────────────────────────
    # First run back after wind op, trainer has timed it
    scenarios.append({
        "name": "Wind Surgery Return",
        "expected_tier": "B",
        "should_fire": True,
        "features": {
            "days_since_run": 35,           # rested_and_fit ✓
            "class_delta": -2,              # class_drop_or_same ✓
            "runs_since_win": 12,           # win_withheld ✓
            "runs_since_place": 6,          # NOT in_form_placed_recently
            "trainer_timing_score": 0.55,   # trainer_timing_pattern ✓
            "sp_dec": 10.0,
            "sp_rank": 4,
            "is_fav": False,                # market_mid_range_support ✓
            "headgear_run": 0,
            "wind_surgery_run": 1,          # first_run_since_wind_surgery ✓
            "spotlight_score": 0.5,         # NOT high_spotlight_conviction
            "handicap_plot_score": 0.7,     # NOT handicap_plot_active
        },
    })

    # ── ARCHETYPE 4: Mechanical Only (No Specialist Signals) ─────────────────
    # Good form horse but no gear/plot/spotlight signals
    scenarios.append({
        "name": "Mechanical Only (No Specialist)",
        "expected_tier": "C",  # Should NOT upgrade at threshold 4
        "should_fire": False,
        "features": {
            "days_since_run": 20,           # rested_and_fit ✓
            "class_delta": 0,               # class_drop_or_same ✓
            "runs_since_win": 7,            # win_withheld ✓
            "runs_since_place": 3,          # in_form_placed_recently ✓
            "trainer_timing_score": 0.4,    # NOT trainer_timing_pattern
            "sp_dec": 5.0,
            "sp_rank": 2,
            "is_fav": False,                # market_mid_range_support ✓ (rank 2, sp > 3)
            "headgear_run": 0,
            "wind_surgery_run": 0,
            "spotlight_score": 0.3,
            "handicap_plot_score": 0.5,
        },
    })

    # ── ARCHETYPE 5: False Positive — Stale Horse ───────────────────────────
    # Long absent, no real signals, should NOT fire
    scenarios.append({
        "name": "False Positive (Stale)",
        "expected_tier": "C",
        "should_fire": False,
        "features": {
            "days_since_run": 90,           # NOT rested_and_fit (too long)
            "class_delta": 1,               # NOT class_drop_or_same (up in class)
            "runs_since_win": 20,           # NOT win_withheld (too long)
            "runs_since_place": 8,          # NOT in_form_placed_recently
            "trainer_timing_score": 0.2,    # NOT trainer_timing_pattern
            "sp_dec": 20.0,
            "sp_rank": 8,
            "is_fav": False,
            "headgear_run": 0,
            "wind_surgery_run": 0,
            "spotlight_score": 0.2,
            "handicap_plot_score": 0.1,
        },
    })

    # ── ARCHETYPE 6: Spotlight Darling ───────────────────────────────────────
    # Strong spotlight + plot but weak mechanical signals
    scenarios.append({
        "name": "Spotlight Darling (Weak Mechanical)",
        "expected_tier": "B",
        "should_fire": True,
        "features": {
            "days_since_run": 10,           # NOT rested_and_fit (too fresh)
            "class_delta": 1,               # NOT class_drop_or_same
            "runs_since_win": 3,            # NOT win_withheld
            "runs_since_place": 1,          # in_form_placed_recently ✓
            "trainer_timing_score": 0.6,    # trainer_timing_pattern ✓
            "sp_dec": 4.0,
            "sp_rank": 3,
            "is_fav": False,                # market_mid_range_support ✓
            "headgear_run": 1,              # first_time_headgear ✓
            "wind_surgery_run": 0,
            "spotlight_score": 0.85,        # high_spotlight_conviction ✓
            "handicap_plot_score": 0.95,    # handicap_plot_active ✓
        },
    })

    # ── ARCHETYPE 7: B-Tier Already (Should NOT Upgrade) ────────────────────
    # Already B-tier, gate should not upgrade further
    scenarios.append({
        "name": "Already B-Tier",
        "expected_tier": "B",
        "should_fire": False,  # Gate only upgrades C→B or D→C
        "features": {
            "days_since_run": 21,
            "class_delta": -1,
            "runs_since_win": 8,
            "runs_since_place": 2,
            "trainer_timing_score": 0.7,
            "sp_dec": 3.5,
            "sp_rank": 2,
            "is_fav": False,
            "headgear_run": 1,
            "wind_surgery_run": 0,
            "spotlight_score": 0.9,
            "handicap_plot_score": 1.0,
        },
    })

    # ── ARCHETYPE 8: Marginal Plot (2 signals) ──────────────────────────────
    # Only 2 signals — should only fire at threshold 2
    scenarios.append({
        "name": "Marginal (2 Signals Only)",
        "expected_tier": "C",
        "should_fire": False,
        "features": {
            "days_since_run": 21,           # rested_and_fit ✓
            "class_delta": 0,               # class_drop_or_same ✓
            "runs_since_win": 3,            # NOT win_withheld
            "runs_since_place": 6,          # NOT in_form_placed_recently
            "trainer_timing_score": 0.2,    # NOT trainer_timing_pattern
            "sp_dec": 12.0,
            "sp_rank": 7,
            "is_fav": False,
            "headgear_run": 0,
            "wind_surgery_run": 0,
            "spotlight_score": 0.3,
            "handicap_plot_score": 0.4,
        },
    })

    return scenarios


def run_sweep():
    """Run the threshold sweep and print results."""
    scenarios = build_synthetic_scenarios()
    gate = TIEv3Gate()

    print("=" * 80)
    print("  TIE v3 THRESHOLD SWEEP — 10 Signals, Thresholds 2-6")
    print("=" * 80)

    # First, show signal counts for each scenario
    print("\n  SIGNAL INVENTORY PER SCENARIO:")
    print("  " + "-" * 76)
    for sc in scenarios:
        signals = gate._collect_signals(sc["features"])
        print(f"  {sc['name']:<35s}  signals={len(signals):2d}  [{', '.join(signals)}]")
    print()

    # Sweep thresholds
    thresholds = [2, 3, 4, 5, 6]
    results = {}

    for threshold in thresholds:
        upgrades = 0
        correct_fires = 0
        false_positives = 0
        missed = 0

        for sc in scenarios:
            signals = gate._collect_signals(sc["features"])
            n = len(signals)

            # Simulate gate at this threshold
            would_fire = n >= threshold and sc.get("features", {}).get("sp_dec", 0) > 0

            # For B-tier horses, gate doesn't upgrade (only C→B, D→C)
            current_tier = "C"  # Default test tier
            if sc["name"] == "Already B-Tier":
                current_tier = "B"
                would_fire = False  # Gate only upgrades C/D

            if would_fire:
                upgrades += 1
                if sc["should_fire"]:
                    correct_fires += 1
                else:
                    false_positives += 1
            else:
                if sc["should_fire"]:
                    missed += 1

        precision = correct_fires / upgrades if upgrades > 0 else 0
        recall = correct_fires / sum(1 for s in scenarios if s["should_fire"]) if any(s["should_fire"] for s in scenarios) else 0

        results[threshold] = {
            "upgrades": upgrades,
            "correct": correct_fires,
            "false_pos": false_positives,
            "missed": missed,
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0,
        }

    # Print sweep results
    print("  THRESHOLD SWEEP RESULTS:")
    print("  " + "-" * 76)
    print(f"  {'Threshold':<12s} {'Upgrades':<10s} {'Correct':<10s} {'FP':<6s} {'Missed':<8s} {'Precision':<11s} {'Recall':<10s} {'F1':<8s}")
    print("  " + "-" * 76)

    for t in thresholds:
        r = results[t]
        marker = " ← CURRENT" if t == 4 else ""
        print(
            f"  {t:<12d} {r['upgrades']:<10d} {r['correct']:<10d} {r['false_pos']:<6d} "
            f"{r['missed']:<8d} {r['precision']:<11.2%} {r['recall']:<10.2%} {r['f1']:<8.3f}{marker}"
        )

    print("  " + "-" * 76)

    # Recommendation
    best_t = max(results, key=lambda t: results[t]["f1"])
    print(f"\n  RECOMMENDATION: MIN_SIGNALS_FOR_UPGRADE = {best_t}")
    print(f"  F1 = {results[best_t]['f1']:.3f}  Precision = {results[best_t]['precision']:.2%}  Recall = {results[best_t]['recall']:.2%}")

    # Liberal vs Conservative analysis
    print("\n  STRATEGIC ANALYSIS:")
    print("  " + "-" * 76)
    print(f"  Threshold 2: VERY LIBERAL — {results[2]['upgrades']} upgrades, {results[2]['false_pos']} false positives")
    print(f"               Risk: noise from marginal horses, dilutes A/B tier quality")
    print(f"  Threshold 3: LIBERAL — {results[3]['upgrades']} upgrades, {results[3]['false_pos']} false positives")
    print(f"               Best for: catching plot horses with specialist signals")
    print(f"  Threshold 4: MODERATE (current) — {results[4]['upgrades']} upgrades, {results[4]['false_pos']} false positives")
    print(f"               Safe but misses some genuine plot horses")
    print(f"  Threshold 5: CONSERVATIVE — {results[5]['upgrades']} upgrades, {results[5]['false_pos']} false positives")
    print(f"               Only fires on stacked conviction (multiple specialist signals)")
    print(f"  Threshold 6: FORTRESS — {results[6]['upgrades']} upgrades, {results[6]['false_pos']} false positives")
    print(f"               Almost never fires, defeats the purpose of TIE")

    # Specialist signal impact
    print("\n  SPECIALIST SIGNAL IMPACT:")
    print("  " + "-" * 76)
    specialist_signals = ["first_time_headgear", "first_run_since_wind_surgery",
                          "high_spotlight_conviction", "handicap_plot_active"]
    for sc in scenarios:
        signals = gate._collect_signals(sc["features"])
        spec_count = sum(1 for s in signals if s in specialist_signals)
        mech_count = len(signals) - spec_count
        print(f"  {sc['name']:<35s}  mechanical={mech_count}  specialist={spec_count}  total={len(signals)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_sweep()
