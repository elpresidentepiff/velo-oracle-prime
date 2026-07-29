#!/usr/bin/env python3
"""
Catch up Playbook G's LIVE state (data/sentient_state.json) from its
2026-04-25 freeze point to the present, using real historical verdicts +
sigma results, now that the doctrines_fired-discarding bug is fixed.

Uses the real SentientLoopbackEngine.observe_race_outcome() for every race
so ALL pillars (races observed, emotion_laws/pain_rules, house_behaviour_map,
appetite_state, doctrine_strengths) evolve through their actual logic, not a
partial hand-rolled update.

Ground truth for win/loss comes directly from sigma's own already-reconciled
`outcome` field (WIN/PLACED/MISS) rather than re-deriving it, since sigma is
the system's own result-reconciliation truth layer.

Usage:
    python scripts/ops/catchup_playbook_g_live_state.py            # dry run
    python scripts/ops/catchup_playbook_g_live_state.py --execute
"""
import argparse
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine  # noqa: E402

LIVE_STATE = ROOT / "data" / "sentient_state.json"
FREEZE_DATE = _date(2026, 4, 25)


def _date_tag_from_filename(path: Path) -> _date | None:
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", path.name)
    if not m:
        return None
    return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def load_pairs():
    verdict_files = {}
    for p in (ROOT / "data").glob("velo_prime_verdicts_*.json"):
        d = _date_tag_from_filename(p)
        if d:
            verdict_files[d] = p
    sigma_files = {}
    for p in (ROOT / "data" / "sigma_results").glob("sigma_results_*.json"):
        d = _date_tag_from_filename(p)
        if d:
            sigma_files[d] = p
    dates = sorted(d for d in (set(verdict_files) & set(sigma_files)) if d > FREEZE_DATE)
    return [(d, verdict_files[d], sigma_files[d]) for d in dates]


def build_events(verdict_path: Path, sigma_path: Path):
    """Return list of (race_data, prediction, actual_result) tuples for this date."""
    try:
        verdicts = json.loads(verdict_path.read_text())
    except Exception:
        return []
    try:
        sigma = json.loads(sigma_path.read_text())
    except Exception:
        return []

    row_by_race = {}
    for row in sigma.get("rows", []):
        rid = str(row.get("race_id") or "")
        if rid:
            row_by_race[rid] = row

    events = []
    if not isinstance(verdicts, list):
        return events
    for race in verdicts:
        rid = str(race.get("race_id") or "")
        top = race.get("top") or {}
        row = row_by_race.get(rid)
        if row is None or not top:
            continue

        pick_name = top.get("horse") or row.get("predicted") or ""
        outcome = row.get("outcome")
        winner_sp = float(row.get("winner_sp") or 0.0)
        # Ground truth from sigma's own reconciled outcome, not re-derived.
        if outcome == "WIN":
            winner_name = pick_name
        else:
            winner_name = row.get("actual_name") or "__no_match__"

        race_data = {
            "race_id": rid,
            "mpi": float(top.get("mpi") or 0) * (100 if abs(top.get("mpi") or 0) <= 1 else 1),
            "chaos_bloom": float(top.get("chaos_bloom") or 0) * (100 if abs(top.get("chaos_bloom") or 0) <= 1 else 1),
            "story_anchor": "favourite" if winner_sp <= 3.0 else "non-favourite",
            "power_anchor": pick_name,
            "runners": [],
        }
        prediction = {
            "power_anchor": pick_name,
            "confidence": float(top.get("velo_prime_prob") or 0),
            "doctrines_fired": top.get("doctrines_fired") or [],
        }
        actual_result = {
            "winner": winner_name,
            "favourite_won": winner_sp <= 3.0,
            "winner_profile": {},
            "sp": winner_sp,
        }
        events.append((race_data, prediction, actual_result))
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    pairs = load_pairs()
    print(f"Dates after freeze ({FREEZE_DATE}) with usable verdict+sigma pairs: {len(pairs)}")

    total_races = 0
    for d, vp, sp in pairs:
        total_races += len(build_events(vp, sp))
    print(f"Total races to replay: {total_races}")

    if not args.execute:
        before = json.loads(LIVE_STATE.read_text())
        print(f"\nLIVE before: races_observed={before.get('total_races_observed')} "
              f"last_updated={before.get('last_updated')} "
              f"pain_rules={len(before.get('emotion_laws', {}).get('pain_rules', []))}")
        print("\nDRY RUN — no writes. Pass --execute to actually run the engine and save.")
        return

    import shutil
    backup = LIVE_STATE.with_name(f"sentient_state_backup_pre_catchup_{_date.today().isoformat().replace('-', '')}.json")
    shutil.copyfile(LIVE_STATE, backup)
    print(f"Backup written: {backup}")

    engine = SentientLoopbackEngine(state_file=str(LIVE_STATE), disable_cloud_backup=True)
    before_races = engine.state.get("total_races_observed")
    processed = 0
    for d, vp, sp in pairs:
        for race_data, prediction, actual_result in build_events(vp, sp):
            engine.observe_race_outcome(race_data, prediction, actual_result)
            processed += 1
    print(f"Replayed {processed} races across {len(pairs)} dates.")

    after = json.loads(LIVE_STATE.read_text())
    print(f"\nLIVE races_observed: {before_races} -> {after.get('total_races_observed')}")
    print(f"LIVE last_updated: {after.get('last_updated')}")
    print(f"LIVE pain_rules: {len(after.get('emotion_laws', {}).get('pain_rules', []))}")
    print("\nDoctrine strengths after catch-up:")
    for k, v in sorted(after.get("doctrine_strengths", {}).items(), key=lambda x: -x[1]):
        print(f"  {k:20s} {v:.4f}")


if __name__ == "__main__":
    main()
