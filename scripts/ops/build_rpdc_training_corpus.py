#!/usr/bin/env python3
"""
Build a real training corpus joining RPDC tags/fields (data/rpdc_full_dump.json,
43,017 rows, Supabase runner_release_candidates) against actual race results
(data/results/rp_results_YYYY_MM_DD.json).

RPDC uses the old Racing-API-derived rac_/hrs_ ID scheme; local results files
use plain numeric RP IDs -- the same identity-scheme mismatch class as the
venue-code bugs fixed elsewhere this session. Rather than reconcile ID
schemes, this joins by (run_date, normalized horse name), the established
pattern already used by new_build_identity_bridge_v2.py for exactly this
kind of cross-source name matching.

RPDC has never been used as trained model features before -- only as a
crude RS>=1.5 threshold advisory gate. This is a genuine first attempt at
training a real classifier on the tag data.

Usage:
    python scripts/ops/build_rpdc_training_corpus.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RPDC_DUMP = ROOT / "data" / "rpdc_full_dump.json"
RESULTS_DIR = ROOT / "data" / "results"
OUTPUT = ROOT / "data" / "training" / "rpdc_training_corpus.jsonl"


def _norm(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"\s*\([a-z]{2,4}\)\s*$", "", n)
    n = re.sub(r"[^a-z0-9 ]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def load_results_index():
    """Return {(run_date, norm_name): {"win": 0/1, "position": str, "sp_dec": float}}"""
    index = {}
    files = sorted(RESULTS_DIR.glob("rp_results_*.json"))
    for f in files:
        m = re.search(r"rp_results_(\d{4})_(\d{2})_(\d{2})", f.name)
        if not m:
            continue
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        races = d.get("results", []) if isinstance(d, dict) else d
        if not isinstance(races, list):
            continue
        for race in races:
            if not isinstance(race, dict):
                continue
            for runner in race.get("runners", []):
                if runner.get("non_runner"):
                    continue
                name = _norm(runner.get("horse"))
                if not name:
                    continue
                pos = str(runner.get("position") or "")
                index[(date, name)] = {
                    "win": 1 if pos == "1" else 0,
                    "position": pos,
                    "sp_dec": runner.get("sp_dec"),
                }
    return index


def main():
    print("Loading results index (per-runner ground truth)...")
    results_index = load_results_index()
    print(f"  {len(results_index):,} (date, horse) result rows indexed")

    print("Loading RPDC dump...")
    rpdc_rows = json.loads(RPDC_DUMP.read_text())
    print(f"  {len(rpdc_rows):,} RPDC rows")

    matched = 0
    unmatched = 0
    out_rows = []
    for r in rpdc_rows:
        date = r.get("run_date")
        name = _norm(r.get("horse"))
        if not date or not name:
            unmatched += 1
            continue
        result = results_index.get((date, name))
        if result is None:
            unmatched += 1
            continue
        matched += 1
        out_rows.append({**r, "target": result["win"], "result_position": result["position"], "winner_sp_dec": result["sp_dec"]})

    print(f"\nMatched: {matched:,}  Unmatched: {unmatched:,} ({100*matched/(matched+unmatched):.1f}% match rate)")
    print(f"Win rate in matched corpus: {sum(r['target'] for r in out_rows)/len(out_rows)*100:.2f}%")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        for row in out_rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nWritten: {OUTPUT} ({len(out_rows):,} rows)")


if __name__ == "__main__":
    main()
