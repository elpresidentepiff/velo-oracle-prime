#!/usr/bin/env python3
"""
VÉLØ — Place stack shadow lane
===============================
Settles the place signal stacks against results every night, with real place
terms, and accumulates a forward ledger.

WHY THIS EXISTS
---------------
Nothing in this pipeline has ever settled a place leg. Every lane, card and
scorecard is scored on the win market, which is how a set of place stacks came
to carry documented evidence of "Frame=100%, E/W 1/4 ROI +170%" from a 28-race
sample while nobody could see what they were actually returning.

Two things justify a place product specifically. On 14,748 runners over
2026-05-20..09-02, backing everything returned -27.29% on the win market and
-18.56% on the place market: the place market is about nine points cheaper.
And the sidecars concentrate frame rate far harder than win rate — the ELITE
stack frames 64.1% against a 28.1% baseline while winning 37.5%. Whatever
these signals know, they know it about placing.

That is a reason to measure, not a reason to bet. As recalibrated, no stack
clears zero: ELITE -9.13%, STRONG -10.38%, BASE -15.90%. The two positive
cells are n=38 and n=28. This lane exists so that a year from now those
numbers come from a forward ledger instead of another retrospective sweep.

PLACE TERMS
-----------
Industry standard UK/IRE, derived per race from field size and whether the
race name contains handicap/nursery:

    <= 4 runners          no place market — selection recorded, not settled
    5 - 7                 2 places @ 1/4
    8 - 11                3 places @ 1/5   (and non-handicaps of any size)
    12 - 15 handicap      3 places @ 1/4
    16+ handicap          4 places @ 1/4

Settlement is 1pt on the place leg alone. This is a place lane, not each-way:
on the EW_CANDIDATE lane the place leg returned -1.51% while the win leg
returned +24.28%, so pairing the two legs blends a signal with its opposite
and reports the average. They are measured apart here.

CALIBRATION DRIFT
-----------------
The thresholds this depends on were set at a stated firing rate. The lane
asserts that rate every night and flags DRIFT when a signal fires at less than
half or more than double what it was calibrated to. That check is the whole
reason the previous thresholds could sit at 0.20% for months without anyone
noticing.

BOUNDARY
--------
Shadow only. No staking, no execution, no Supabase writes, no Telegram, no
promotion. Writes data/place_stack_shadow/ and appends one row per selection
to the forward ledger.

Usage:
    python scripts/ops/run_place_stack_shadow.py --date 2026-09-02
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT_DIR = ROOT / "data" / "place_stack_shadow"
LEDGER = OUT_DIR / "place_stack_shadow_ledger.csv"
RESULTS_DIR = ROOT / "data" / "results"

LEDGER_FIELDS = [
    "date", "race_id", "course", "off_time", "horse", "horse_id",
    "stack_label", "stack_status", "tier", "velo_prime_prob",
    "market_deception_score", "improvement_score", "place_prob",
    "field_size", "is_handicap", "places_paid", "place_fraction",
    "sp_dec", "finish_pos", "won", "placed", "win_pl", "place_pl",
]


def _norm(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"\([a-z]{2,3}\)", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def place_terms(field: int, handicap: bool) -> tuple[int, float]:
    if field <= 4:
        return 0, 0.0
    if field <= 7:
        return 2, 0.25
    if handicap and field >= 16:
        return 4, 0.25
    if handicap and field >= 12:
        return 3, 0.25
    return 3, 0.20


def load_results(date: str) -> dict:
    path = RESULTS_DIR / f"rp_results_{date.replace('-', '_')}.json"
    if not path.exists():
        raise FileNotFoundError(f"no parsed results for {date}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    races = payload if isinstance(payload, list) else (payload.get("results") or [])
    out = {}
    for r in races:
        if not isinstance(r, dict):
            continue
        runners = {}
        for run in (r.get("runners") or []):
            sp = run.get("sp_dec")
            if not sp or sp <= 1.0 or run.get("non_runner"):
                continue
            try:
                pos = int(run.get("position"))
            except (TypeError, ValueError):
                pos = 999
            runners[_norm(run.get("horse"))] = (float(sp), pos)
        if not runners:
            continue
        name = r.get("race_name") or ""
        out[str(r.get("race_id"))] = {
            "runners": runners,
            "course": r.get("course"),
            "off": r.get("off"),
            "handicap": bool(re.search(r"\b(handicap|h'cap|hcap|nursery)\b", name, re.I)),
            "field": len(runners),
        }
    return out


def load_snapshot(date: str) -> list[dict]:
    """Latest snapshot row per (race, horse) for the date."""
    tag = date.replace("-", "_")
    files = sorted((ROOT / "data").glob(f"runner_snapshots_{tag}_*.jsonl"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"no runner snapshots for {date}")
    best: dict[tuple[str, str], dict] = {}
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid, h = str(row.get("race_id") or ""), _norm(row.get("horse"))
            if rid and h:
                best[(rid, h)] = row
    return list(best.values())


def main() -> int:
    from velo.place_signal_classifier import (
        CALIBRATION_WINDOW, EXPECTED_FIRE_RATE, IMPROVE_HIGH_T, MDS_HIGH_T,
        VP30_T, classify,
    )

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()
    date = args.date

    results = load_results(date)
    snapshot = load_snapshot(date)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    fires = Counter()
    scored = 0
    for row in snapshot:
        rid = str(row.get("race_id") or "")
        race = results.get(rid)
        if not race:
            continue
        key = _norm(row.get("horse"))
        if key not in race["runners"]:
            continue
        scored += 1

        vp = row.get("velo_prime_prob")
        mds = row.get("market_deception_score")
        imp = row.get("improvement_score")
        if (vp or 0) >= VP30_T:
            fires["VP30"] += 1
        if (mds or 0) > MDS_HIGH_T:
            fires["MDS_HIGH"] += 1
        if (imp or 0) >= IMPROVE_HIGH_T:
            fires["IMPROVE_HIGH"] += 1

        sig = classify(
            velo_prime_prob=vp or 0.0,
            tier=str(row.get("tier") or ""),
            market_deception_score=mds or 0.0,
            improvement_score=imp or 0.0,
            place_prob=row.get("place_prob") or 0.0,
        )
        sp, pos = race["runners"][key]
        n_places, frac = place_terms(race["field"], race["handicap"])
        placed = n_places > 0 and pos <= n_places
        won = pos == 1
        rows.append({
            "date": date, "race_id": rid, "course": race["course"], "off_time": race["off"],
            "horse": row.get("horse"), "horse_id": row.get("horse_id"),
            "stack_label": sig.place_stack_label, "stack_status": sig.place_stack_status,
            "tier": row.get("tier"), "velo_prime_prob": vp,
            "market_deception_score": mds, "improvement_score": imp,
            "place_prob": row.get("place_prob"),
            "field_size": race["field"], "is_handicap": race["handicap"],
            "places_paid": n_places, "place_fraction": frac,
            "sp_dec": sp, "finish_pos": pos, "won": int(won), "placed": int(placed),
            "win_pl": round((sp - 1) if won else -1.0, 4),
            # A race with no place market cannot be settled on the place leg.
            # Recorded with a null rather than a zero, which would silently
            # dilute every average that follows.
            "place_pl": (round(((sp - 1) * frac) if placed else -1.0, 4)
                         if n_places > 0 else None),
        })

    if not rows:
        print(f"PLACE_STACK_SHADOW NO_SELECTIONS date={date} "
              f"(snapshot rows={len(snapshot)}, result races={len(results)})",
              file=sys.stderr)
        return 1

    # ── calibration drift ────────────────────────────────────────────────────
    drift = {}
    for sig_name, expected in EXPECTED_FIRE_RATE.items():
        actual = fires[sig_name] / scored if scored else 0.0
        state = "OK"
        if expected > 0 and (actual < expected / 2 or actual > expected * 2):
            state = "DRIFT"
        drift[sig_name] = {"expected": expected, "actual": round(actual, 5),
                           "fired": fires[sig_name], "state": state}

    # ── per-stack settlement ─────────────────────────────────────────────────
    by = defaultdict(list)
    for r in rows:
        by[r["stack_label"]].append(r)
    summary = {}
    for label, rs in by.items():
        settled = [r for r in rs if r["place_pl"] is not None]
        summary[label] = {
            "selections": len(rs),
            "place_settled": len(settled),
            "frame_rate": round(sum(r["placed"] for r in settled) / len(settled), 4) if settled else None,
            "win_rate": round(sum(r["won"] for r in rs) / len(rs), 4),
            "place_pl": round(sum(r["place_pl"] for r in settled), 3) if settled else None,
            "place_roi": round(sum(r["place_pl"] for r in settled) / len(settled), 4) if settled else None,
            "win_pl": round(sum(r["win_pl"] for r in rs), 3),
            "win_roi": round(sum(r["win_pl"] for r in rs) / len(rs), 4),
        }

    # ── append to the forward ledger (idempotent per date) ───────────────────
    existing = []
    if LEDGER.exists():
        with LEDGER.open(newline="", encoding="utf-8") as fh:
            existing = [r for r in csv.DictReader(fh) if r.get("date") != date]
    with LEDGER.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        w.writerows(existing)
        w.writerows({k: r.get(k) for k in LEDGER_FIELDS} for r in rows)

    # ── cumulative, straight off the ledger ──────────────────────────────────
    cum = defaultdict(lambda: {"n": 0, "settled": 0, "framed": 0, "place_pl": 0.0})
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            c = cum[r["stack_label"]]
            c["n"] += 1
            if r.get("place_pl") not in (None, ""):
                c["settled"] += 1
                c["framed"] += int(r["placed"] == "1")
                c["place_pl"] += float(r["place_pl"])

    payload = {
        "date": date, "generated_at": datetime.now(UTC).isoformat(),
        "status": "SHADOW_ONLY_NO_STAKING",
        "settlement": "1pt place leg at industry terms; win leg carried alongside, never blended",
        "thresholds": {"VP30_T": VP30_T, "MDS_HIGH_T": MDS_HIGH_T,
                       "IMPROVE_HIGH_T": IMPROVE_HIGH_T},
        "calibration_window": CALIBRATION_WINDOW,
        "calibration_drift": drift,
        "runners_scored": scored,
        "today": summary,
        "cumulative": {k: {"selections": v["n"], "place_settled": v["settled"],
                           "frame_rate": round(v["framed"] / v["settled"], 4) if v["settled"] else None,
                           "place_pl": round(v["place_pl"], 3),
                           "place_roi": round(v["place_pl"] / v["settled"], 4) if v["settled"] else None}
                       for k, v in sorted(cum.items())},
    }
    (OUT_DIR / f"place_stack_shadow_{date.replace('-', '_')}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "place_stack_shadow_latest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    print(f"PLACE_STACK_SHADOW date={date} runners={scored} selections={len(rows)}")
    print(f"\n  calibration (window {CALIBRATION_WINDOW}):")
    for k, v in drift.items():
        print(f"    {k:<14} expected {v['expected']:.2%}  actual {v['actual']:.2%}  {v['state']}")
    print(f"\n  {'stack':<26}{'n':>5}{'frame%':>9}{'place ROI':>11}{'win ROI':>10}")
    for label in sorted(summary, key=lambda k: -summary[k]["selections"]):
        s = summary[label]
        fr = f"{s['frame_rate']:.1%}" if s["frame_rate"] is not None else "-"
        pr = f"{s['place_roi']:+.2%}" if s["place_roi"] is not None else "-"
        print(f"  {label:<26}{s['selections']:>5}{fr:>9}{pr:>11}{s['win_roi']:>+10.2%}")
    print(f"\n  cumulative ledger ({sum(v['n'] for v in cum.values())} selections):")
    for label, v in sorted(payload["cumulative"].items(), key=lambda kv: -kv[1]["selections"]):
        fr = f"{v['frame_rate']:.1%}" if v["frame_rate"] is not None else "-"
        pr = f"{v['place_roi']:+.2%}" if v["place_roi"] is not None else "-"
        print(f"    {label:<26}{v['selections']:>5}  frame {fr:>7}  place ROI {pr:>9}")
    print(f"\n  ledger: {LEDGER}")

    if any(v["state"] == "DRIFT" for v in drift.values()):
        print("\n[WARN] a signal is firing far from its calibrated rate — thresholds "
              "may be stale. This is the check that was missing when MDS_HIGH sat "
              "at 0.20% for months.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
