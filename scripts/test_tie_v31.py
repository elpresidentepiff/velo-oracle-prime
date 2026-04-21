#!/usr/bin/env python3.11
"""Quick test of TIE v3.1 gate with specialist signal requirement."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intelligence.tie_v3_gate import TIEv3Gate

gate = TIEv3Gate()

tests = [
    {
        "name": "Plot Horse (3 mech + 3 spec) — should UPGRADE",
        "tier": "C",
        "features": {
            "days_since_run": 28, "class_delta": -1, "runs_since_win": 8,
            "headgear_run": 1, "spotlight_score": 0.8, "handicap_plot_score": 1.0,
        },
    },
    {
        "name": "Mechanical Only (5 mech + 0 spec) — should NOT upgrade",
        "tier": "C",
        "features": {
            "days_since_run": 20, "class_delta": 0, "runs_since_win": 7,
            "runs_since_place": 3, "sp_dec": 5.0, "sp_rank": 2, "is_fav": False,
        },
    },
    {
        "name": "Minimal Plot (2 mech + 1 spec) — should UPGRADE at threshold 3",
        "tier": "C",
        "features": {
            "days_since_run": 21, "class_delta": 0,
            "handicap_plot_score": 0.95,
        },
    },
    {
        "name": "Wind Surgery + Class Drop (2 mech + 1 spec) — should UPGRADE",
        "tier": "D",
        "features": {
            "days_since_run": 35, "class_delta": -2,
            "wind_surgery_run": 1,
        },
    },
    {
        "name": "Stale Horse (0 signals) — should NOT fire",
        "tier": "C",
        "features": {
            "days_since_run": 90, "class_delta": 1, "runs_since_win": 20,
        },
    },
]

print("=" * 80)
print("  TIE v3.1 GATE TEST — Specialist Signal Requirement")
print("=" * 80)

all_pass = True
for t in tests:
    result = gate.evaluate(t["features"], current_tier=t["tier"])
    fires = result.fires
    upgrade = result.tier_upgrade
    signals = result.signals_found

    expected_fire = "UPGRADE" in t["name"] or "should UPGRADE" in t["name"]
    actual_fire = fires and upgrade is not None

    status = "PASS" if expected_fire == actual_fire else "FAIL"
    if status == "FAIL":
        all_pass = False

    print(f"\n  [{status}] {t['name']}")
    print(f"    Signals: {len(signals)} → {signals}")
    print(f"    Fires: {fires}  Upgrade: {upgrade}  Reason: {result.reason}")

print("\n" + "=" * 80)
print(f"  RESULT: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
print("=" * 80)
