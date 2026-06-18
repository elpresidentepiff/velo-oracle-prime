#!/usr/bin/env python3
"""
VFU-25: Identity Resolution + SP Repair Sprint

Builds a horse_id resolution map for the 1,977 NAME_ONLY rows in the
VFU-11 sigma master ledger using 4 local data sources.

Sources (priority order — first writer wins):
  1. VFU-21 current-era ledger     (already-resolved current rows)
  2. Runner snapshots              (86 files, May 20 – Jun 17)
  3. Racing Post results           (rp_results, May 23 – Jun 17)
  4. Acca lane reports             (Mar 27 – Jun 4, includes May 8-17 gap)

Output (READ-ONLY reference documents — VFU-11 ledger is NOT mutated):
  data/reports/vfu_25_identity_resolution_map.jsonl   — row-level matches
  data/reports/vfu_25_resolution_summary.json         — stats + source breakdown

Governance:
  blocked_from_live_use = True
  No canonical VFU-11 ledger mutation
  No Horse Passport mutation
  No Supabase writes  |  No Telegram  |  No model promotion
  No VP threshold change  |  No live scoring change
"""

from __future__ import annotations

import glob
import json
import pathlib
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

VFU25_VERSION = "VFU_25_IDENTITY_RESOLUTION_V1"

LEDGER_PATH = REPORTS / "vfu_11_sigma_master_ledger.jsonl"
VFU21_PATH  = REPORTS / "vfu_21_pick_sp_backfill_ledger.jsonl"

# Minimum confidence level to include in the resolution map
CONFIDENCE_THRESHOLD = "MEDIUM"  # CONFIRMED > HIGH > MEDIUM > LOW


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(name: str) -> str:
    """Normalise horse name for matching."""
    return (name or "").strip().lower()


def _load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ── Source builders ───────────────────────────────────────────────────────────

def _build_lookup_from_vfu21(path: pathlib.Path) -> dict:
    """(norm_name, race_date) → (horse_id, sp_dec, source, confidence)"""
    lookup: dict = {}
    for row in _load_jsonl(path):
        name = _norm(row.get("horse_name", ""))
        hid  = row.get("horse_id")
        date = row.get("race_date", "")
        sp   = row.get("pick_sp")
        if name and hid and date:
            k = (name, date)
            if k not in lookup:
                lookup[k] = (hid, sp, "vfu21_ledger", "CONFIRMED")
    return lookup


def _build_lookup_from_snapshots(data_dir: pathlib.Path) -> dict:
    """(norm_name, race_date) → (horse_id, sp_dec, source, confidence)"""
    lookup: dict = {}
    snap_files = sorted(glob.glob(str(data_dir / "runner_snapshots_*.jsonl")))
    for sf in snap_files:
        with open(sf, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                name = _norm(row.get("horse", ""))
                hid  = row.get("horse_id")
                date = row.get("race_date", "")
                sp   = row.get("sp_dec")
                if name and hid and date:
                    k = (name, date)
                    if k not in lookup:
                        lookup[k] = (hid, sp, "runner_snapshot", "HIGH")
    return lookup


def _build_lookup_from_rp_results(data_dir: pathlib.Path) -> dict:
    """(norm_name, race_date) → (horse_id, sp_dec, source, confidence)"""
    lookup: dict = {}
    rp_files = sorted(glob.glob(str(data_dir / "results" / "rp_results_*.json")))
    for rf in rp_files:
        with open(rf, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            continue
        date = d.get("date", "")
        for race in d.get("results", []):
            for rn in race.get("runners", []):
                name = _norm(rn.get("horse", ""))
                hid  = rn.get("horse_id")
                sp   = rn.get("sp_dec")
                if name and hid and date:
                    k = (name, date)
                    if k not in lookup:
                        lookup[k] = (hid, sp, "rp_results", "HIGH")
    return lookup


def _build_lookup_from_acca_lane(data_dir: pathlib.Path) -> dict:
    """(norm_name, race_date) → (horse_id, sp_dec, source, confidence)"""
    lookup: dict = {}
    lane_files = sorted(glob.glob(str(data_dir / "acca_lane_report_*.json")))
    for lf in lane_files:
        with open(lf, encoding="utf-8") as fh:
            d = json.load(fh)
        date = d.get("date", "")
        if not date:
            continue
        for section in ("candidates", "trap_legs", "cashrun_legs", "winners",
                        "sidecar_picks", "acca_picks"):
            for entry in d.get(section, []):
                name = _norm(entry.get("horse", ""))
                hid  = entry.get("horse_id")
                sp   = entry.get("sp_dec", entry.get("sp"))
                if name and hid and date:
                    k = (name, date)
                    if k not in lookup:
                        lookup[k] = (str(hid), sp, "acca_lane", "MEDIUM")
    return lookup


def build_combined_lookup(data_dir: pathlib.Path, vfu21_path: pathlib.Path) -> dict:
    """
    Combine all 4 sources into one lookup.
    Priority: vfu21 > snapshots > rp_results > acca_lane.
    Returns {(norm_name, race_date): (horse_id, sp_dec, source, confidence)}.
    """
    lookup: dict = {}

    # Apply in reverse priority order so higher-priority sources overwrite
    for src_lookup in [
        _build_lookup_from_acca_lane(data_dir),
        _build_lookup_from_rp_results(data_dir),
        _build_lookup_from_snapshots(data_dir),
        _build_lookup_from_vfu21(vfu21_path),
    ]:
        lookup.update(src_lookup)

    return lookup


# ── Resolution engine ─────────────────────────────────────────────────────────

def resolve_ledger_rows(
    ledger: list[dict],
    lookup: dict,
) -> tuple[list[dict], list[dict]]:
    """
    For each NAME_ONLY row in ledger, attempt resolution.
    Returns (resolved_rows, unresolved_rows).
    """
    resolved: list[dict] = []
    unresolved: list[dict] = []

    for row in ledger:
        # Only target rows missing horse_id with a known horse_name
        if row.get("horse_id") or not row.get("horse_name"):
            continue

        name = _norm(row.get("horse_name", ""))
        date = row.get("race_date", "")

        match = lookup.get((name, date))
        if match:
            horse_id, sp_dec, source, confidence = match
            resolved_row: dict = {
                "ledger_id":   row.get("ledger_id"),
                "horse_name":  row.get("horse_name"),
                "race_date":   date,
                "race_id":     row.get("race_id"),
                "course":      row.get("course"),
                "era_bucket":  row.get("era_bucket"),
                "outcome":     row.get("outcome"),
                # Resolution result
                "resolved_horse_id":     horse_id,
                "resolved_sp_dec":       sp_dec,
                "resolution_source":     source,
                "resolution_confidence": confidence,
                # SP repair: only populate if currently null
                "pick_sp_was_null":      row.get("pick_sp") is None,
                "pick_sp_repaired":      sp_dec if row.get("pick_sp") is None and sp_dec else None,
                "existing_pick_sp":      row.get("pick_sp"),
                # Governance
                "blocked_from_live_use": True,
                "human_review_required": True,
                "resolution_version":    VFU25_VERSION,
            }
            resolved.append(resolved_row)
        else:
            unresolved.append({
                "ledger_id":  row.get("ledger_id"),
                "horse_name": row.get("horse_name"),
                "race_date":  date,
                "era_bucket": row.get("era_bucket"),
                "reason":     "NO_SOURCE_COVERAGE",
            })

    return resolved, unresolved


def build_stats(
    ledger: list[dict],
    resolved: list[dict],
    unresolved: list[dict],
) -> dict:
    name_only = [r for r in ledger if not r.get("horse_id") and r.get("horse_name")]
    total_name_only = len(name_only)
    total_resolved  = len(resolved)

    source_dist   = Counter(r["resolution_source"] for r in resolved)
    conf_dist     = Counter(r["resolution_confidence"] for r in resolved)
    era_dist_res  = Counter(r["era_bucket"] for r in resolved)
    era_dist_unres = Counter(r["era_bucket"] for r in unresolved)
    sp_repaired   = sum(1 for r in resolved if r["pick_sp_repaired"] is not None)

    unres_dates = sorted({r["race_date"] for r in unresolved if r.get("race_date")})

    current_name_only = [r for r in name_only if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]
    current_resolved  = [r for r in resolved if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]

    return {
        "total_ledger_rows":             len(ledger),
        "total_name_only":               total_name_only,
        "total_resolved":                total_resolved,
        "total_unresolved":              len(unresolved),
        "resolution_rate_pct":           round(total_resolved / total_name_only * 100, 1) if total_name_only else 0,
        "current_era_name_only":         len(current_name_only),
        "current_era_resolved":          len(current_resolved),
        "current_era_resolution_pct":    round(len(current_resolved) / len(current_name_only) * 100, 1) if current_name_only else 0,
        "sp_repairs":                    sp_repaired,
        "source_distribution":           dict(source_dist),
        "confidence_distribution":       dict(conf_dist),
        "era_distribution_resolved":     dict(era_dist_res),
        "era_distribution_unresolved":   dict(era_dist_unres),
        "unresolved_date_range":         {"first": unres_dates[0] if unres_dates else None,
                                          "last": unres_dates[-1] if unres_dates else None},
        "unresolved_date_count":         len(unres_dates),
        "unresolved_gap_note": (
            "Unresolved rows are primarily May 8-19 — no local snapshot or results "
            "files cover this window. Irreducible gap without additional source import."
        ),
    }


def main() -> None:
    print(f"VFU-25: Identity Resolution Sprint — {_utc_now()}")

    ledger = _load_jsonl(LEDGER_PATH)
    print(f"Loaded VFU-11 ledger: {len(ledger)} rows")

    print("Building combined lookup from 4 sources...")
    lookup = build_combined_lookup(DATA, VFU21_PATH)
    print(f"  Lookup size: {len(lookup):,} (name, date) pairs")

    resolved, unresolved = resolve_ledger_rows(ledger, lookup)
    stats = build_stats(ledger, resolved, unresolved)

    print(f"\n  NAME_ONLY rows:  {stats['total_name_only']:,}")
    print(f"  Resolved:        {stats['total_resolved']:,} ({stats['resolution_rate_pct']}%)")
    print(f"  Unresolved:      {stats['total_unresolved']:,}")
    print(f"  SP repairs:      {stats['sp_repairs']}")
    print(f"  Source dist:     {stats['source_distribution']}")
    print(f"  Confidence dist: {stats['confidence_distribution']}")
    print(f"\n  Current era:     {stats['current_era_resolved']}/{stats['current_era_name_only']} resolved ({stats['current_era_resolution_pct']}%)")
    print(f"  Unresolved gap:  {stats['unresolved_date_range']['first']} – {stats['unresolved_date_range']['last']} ({stats['unresolved_date_count']} dates, no local source)")

    REPORTS.mkdir(parents=True, exist_ok=True)

    # Write resolution map
    map_path = REPORTS / "vfu_25_identity_resolution_map.jsonl"
    with open(map_path, "w", encoding="utf-8") as fh:
        for row in resolved:
            fh.write(json.dumps(row) + "\n")
    print(f"\nWritten: {map_path.name}  ({len(resolved)} rows)")

    # Write summary
    summary = {
        "vfu": "VFU-25",
        "version": VFU25_VERSION,
        "generated_at": _utc_now(),
        "stats": stats,
        "blocked_from_live_use": True,
        "paper_only": True,
        "no_supabase_writes": True,
        "no_telegram": True,
        "no_model_promotion": True,
        "no_vp_threshold_change": True,
        "no_live_scoring_change": True,
        "vfu11_ledger_mutated": False,
        "horse_passport_mutated": False,
        "classifications": [
            "VFU_25_IDENTITY_RESOLUTION_COMPLETE",
            "VFU11_LEDGER_NOT_MUTATED",
            "HORSE_PASSPORT_NOT_MUTATED",
            "BLOCKED_FROM_LIVE_USE",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM",
            "NO_MODEL_PROMOTION",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
        ],
    }
    summ_path = REPORTS / "vfu_25_resolution_summary.json"
    summ_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Written: {summ_path.name}")
    print(f"Classification: VFU_25_IDENTITY_RESOLUTION_COMPLETE")


if __name__ == "__main__":
    main()
