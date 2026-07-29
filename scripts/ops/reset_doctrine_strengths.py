#!/usr/bin/env python3
"""
reset_doctrine_strengths.py — One-time doctrine strength reset (2026-07-28)

Why: LAY_THE_STORY and SHADOW_TRACKING collapsed to ~0.08 because the
STRONG_DOCTRINES discount in _g_shadow_adjustment() fired on EVERY race
(when strength < 0.5) and added the doctrine to doctrines_fired. The
loopback EMA then penalised those doctrines on every loss (~74% of races),
trapping them near zero. The ensemble fix (principled firing conditions)
stops future collapse, but the state still holds corrupt history.

Reset: all doctrine_strengths set to 0.5 (neutral — no discount applied).
Backup written before any change.

Usage: PYTHONPATH=. python scripts/ops/reset_doctrine_strengths.py --execute
"""
from __future__ import annotations
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESET_VALUE = 0.5
REASON = (
    "reset_2026-07-28: doctrine fired on every race when strength<0.5 "
    "(death-spiral). Ensemble fix adds principled firing conditions. "
    "Strengths reset to 0.5 (neutral) for clean re-learning."
)


def reset_file(state_path: Path, dry_run: bool) -> None:
    if not state_path.exists():
        print(f"  [SKIP] {state_path} does not exist")
        return

    state = json.loads(state_path.read_text())
    doctrines = state.get("doctrine_strengths", {})
    old_values = dict(doctrines)

    if not dry_run:
        backup = state_path.with_suffix(f".pre_doctrine_reset_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(state_path, backup)
        print(f"  Backup: {backup}")

    new_values = {k: RESET_VALUE for k in doctrines}
    # ENGINE_SUPREMACY never fires, keep it at 1.0 to flag it's inert
    if "ENGINE_SUPREMACY" in new_values:
        new_values["ENGINE_SUPREMACY"] = 1.0

    state["doctrine_strengths"] = new_values
    state["doctrine_reset_log"] = state.get("doctrine_reset_log", [])
    state["doctrine_reset_log"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": REASON,
        "before": old_values,
        "after": new_values,
    })

    print(f"\n  {'DRY RUN — ' if dry_run else ''}{state_path.name}:")
    for k in old_values:
        print(f"    {k}: {old_values[k]:.6g} → {new_values[k]}")

    if not dry_run:
        state_path.write_text(json.dumps(state, indent=2))
        print(f"  Written.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually write; default is dry-run")
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        print("DRY RUN — pass --execute to write")

    for name in ["sentient_state.json", "sentient_state_shadow.json"]:
        reset_file(ROOT / "data" / name, dry_run)

    if dry_run:
        print("\nRe-run with --execute to apply.")


if __name__ == "__main__":
    main()
