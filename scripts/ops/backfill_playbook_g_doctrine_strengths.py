#!/usr/bin/env python3
"""
Backfill Playbook G's doctrine_strengths in the SHADOW state only.

Root cause: scripts/playbook_g_shadow_adapter.py hardcoded
"doctrines_fired": [] for every replayed event since it was written, so
doctrine_strengths never moved off its 1.0 default despite total_races_observed
climbing to 938+ via the other (unaffected) update pillars. The real
doctrines_fired data was never lost -- it's stored per-race in the local
data/velo_prime_verdicts_YYYY_MM_DD.json backups (top.doctrines_fired),
just never read by the adapter. Supabase's persisted full_analysis does NOT
carry this field, so this local-file backfill is the only path.

This script ONLY rewrites doctrine_strengths in data/sentient_state_shadow.json.
It does not touch total_races_observed, pain_rules, house_behaviour_map, or
appetite_state (those already accumulated correctly on the nights they ran).
It never touches data/sentient_state.json (the live file).

Usage:
    python scripts/ops/backfill_playbook_g_doctrine_strengths.py            # dry run
    python scripts/ops/backfill_playbook_g_doctrine_strengths.py --execute
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHADOW_STATE = ROOT / "data" / "sentient_state_shadow.json"


def _date_tag_from_filename(path: Path) -> str:
    m = re.search(r"(\d{4}_\d{2}_\d{2})", path.name)
    return m.group(1) if m else ""


def load_pairs():
    """Yield (date_tag, verdict_path, sigma_path) for every date with both files."""
    verdict_files = {
        _date_tag_from_filename(p): p
        for p in (ROOT / "data").glob("velo_prime_verdicts_*.json")
    }
    sigma_files = {
        _date_tag_from_filename(p): p
        for p in (ROOT / "data" / "sigma_results").glob("sigma_results_*.json")
    }
    for date_tag in sorted(set(verdict_files) & set(sigma_files)):
        yield date_tag, verdict_files[date_tag], sigma_files[date_tag]


def replay_date(verdict_path: Path, sigma_path: Path) -> list[tuple[list[str], float]]:
    """Return [(doctrines_fired, correct), ...] for every race in this date with both a
    verdict top-pick and a sigma outcome."""
    try:
        verdicts = json.loads(verdict_path.read_text())
    except Exception:
        return []
    try:
        sigma = json.loads(sigma_path.read_text())
    except Exception:
        return []

    outcome_by_race = {}
    for row in sigma.get("rows", []):
        rid = str(row.get("race_id") or "")
        if rid:
            outcome_by_race[rid] = row.get("outcome")

    events = []
    if not isinstance(verdicts, list):
        return events
    for race in verdicts:
        rid = str(race.get("race_id") or "")
        top = race.get("top") or {}
        doctrines = top.get("doctrines_fired") or []
        if not doctrines:
            continue
        outcome = outcome_by_race.get(rid)
        if outcome is None:
            continue
        correct = 1.0 if outcome == "WIN" else 0.0
        events.append((doctrines, correct))
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    state = json.loads(SHADOW_STATE.read_text())
    strengths = dict(state.get("doctrine_strengths", {}))
    before = dict(strengths)

    total_events = 0
    dates_used = 0
    dates_skipped = []

    for date_tag, verdict_path, sigma_path in load_pairs():
        events = replay_date(verdict_path, sigma_path)
        if not events:
            dates_skipped.append(date_tag)
            continue
        dates_used += 1
        for doctrines, correct in events:
            for doctrine in doctrines:
                if doctrine in strengths:
                    current = strengths[doctrine]
                    strengths[doctrine] = 0.9 * current + 0.1 * correct
                    total_events += 1

    print(f"Dates with usable verdict+sigma pairs: {dates_used}")
    print(f"Dates skipped (no doctrines_fired or no outcome match): {len(dates_skipped)}")
    print(f"Doctrine-strength updates applied: {total_events}")
    print()
    print(f"{'Doctrine':30s} {'Before':>10s} {'After':>10s}")
    for k in sorted(strengths, key=lambda d: -strengths[d]):
        print(f"{k:30s} {before.get(k, 1.0):10.4f} {strengths[k]:10.4f}")

    if not args.execute:
        print("\nDRY RUN — no file written. Pass --execute to write to sentient_state_shadow.json.")
        return

    state["doctrine_strengths"] = strengths
    SHADOW_STATE.write_text(json.dumps(state, indent=2))
    print(f"\nWROTE updated doctrine_strengths to {SHADOW_STATE}")


if __name__ == "__main__":
    main()
