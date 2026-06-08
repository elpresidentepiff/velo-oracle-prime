#!/usr/bin/env python3
"""
Race Shape Feature Builder V1

Computes race-level shape features from runner snapshots + results.
Research-only: no scoring integration, no model changes.

Features computed per race (from RACE_SHAPE_MODEL_V1.md):
  Field compression:
    field_size, top_pick_rank_gap, vp_spread_top3, vp_spread_field,
    contender_compression_score, favourite_vulnerability_score, top3_vp_spread
  Market structure:
    market_concentration_score, midprice_density, longshot_noise_ratio,
    sp_vp_rank_corr, winner_sp_rank, top_pick_is_favourite
  Data availability flags:
    class_drop_flag, distance_change_flag, going_soft_flag, draw_available
  Classification:
    race_shape_status: COMPRESSED / CLEAR_TOP / FAV_VULNERABLE / MIDPRICE_TRAP / CHAOTIC / UNKNOWN

Outputs:
  data/features/race_shape_features_latest.json
  data/reports/race_shape_features_latest.md

Usage:
    PYTHONPATH=. python scripts/build_race_shape_features.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIDPRICE_LOW = 3.0
MIDPRICE_HIGH = 8.5


def _load_snapshots(date_str: str) -> list[dict]:
    date_und = date_str.replace("-", "_")
    patterns = [
        str(ROOT / "data" / f"runner_snapshots_{date_und}_{date_und}_*.jsonl"),
        str(ROOT / "data" / f"runner_snapshots_{date_und}*.jsonl"),
    ]
    rows: list[dict] = []
    seen: set = set()
    for pattern in patterns:
        for fpath in glob.glob(pattern):
            if fpath in seen:
                continue
            seen.add(fpath)
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
    return rows


def _load_results(date_str: str) -> list[dict]:
    date_und = date_str.replace("-", "_")
    paths = [
        ROOT / "data" / f"results_{date_und}.json",
        ROOT / f"results_{date_und}.json",
    ]
    for p in paths:
        if p.exists():
            d = json.loads(p.read_text())
            return d.get("results", []) if isinstance(d, dict) else d
    return []


def _sp_to_dec(sp_str: str) -> float | None:
    """Convert fractional SP like '5/2' to decimal, or return float directly."""
    if not sp_str:
        return None
    s = str(sp_str).strip()
    try:
        return float(s)
    except ValueError:
        pass
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1]) + 1.0
            except (ValueError, ZeroDivisionError):
                pass
    return None


def _classify_shape(features: dict) -> str:
    vp_spread_top3 = features.get("vp_spread_top3", 1.0)
    vp_spread_field = features.get("vp_spread_field", 1.0)
    top_vp = features.get("top_vp", 0.0)
    rank_gap = features.get("top_pick_rank_gap", 1.0)
    midprice_density = features.get("midprice_density", 0.0)

    # CLEAR_TOP: dominant top pick with meaningful VP gap
    if top_vp >= 0.40 and rank_gap >= 0.15:
        return "CLEAR_TOP"

    # FAV_VULNERABLE: top pick VP too low to trust
    if top_vp < 0.20:
        return "FAV_VULNERABLE"

    # COMPRESSED: top 3 VP are nearly identical
    if vp_spread_top3 is not None and vp_spread_top3 < 0.04:
        return "COMPRESSED"

    # CHAOTIC: entire field has near-uniform VP (VP spreads very small)
    if vp_spread_field is not None and vp_spread_field < 0.08:
        return "CHAOTIC"

    # MIDPRICE_TRAP: many mid-priced runners, market fragmented
    if midprice_density >= 0.45:
        return "MIDPRICE_TRAP"

    return "UNKNOWN"


def compute_race_shape(race_id: str, snap_runners: list[dict], result_runners: list[dict], result_meta: dict) -> dict:
    """Compute race shape features for a single race."""
    # Sort snapshot runners by rank
    snaps = sorted(snap_runners, key=lambda r: r.get("rank", 99))

    # VP array (rank-ordered)
    vps = [float(r.get("velo_prime_prob", 0) or 0) for r in snaps]
    mds_list = [float(r.get("market_deception_score", 0) or 0) for r in snaps]

    n_snap = len(snaps)
    top_vp = vps[0] if vps else 0.0
    vp_rank1 = vps[1] if len(vps) >= 2 else None
    vp_rank2 = vps[2] if len(vps) >= 3 else None

    top_pick_rank_gap = (top_vp - vp_rank1) if vp_rank1 is not None else None
    vp_spread_top3 = (top_vp - vp_rank2) if vp_rank2 is not None else (top_vp - vp_rank1 if vp_rank1 is not None else None)
    vp_spread_field = (max(vps) - min(vps)) if len(vps) >= 2 else None

    # Contender compression: 1 - (vp_spread_top3 / vp_spread_field)
    # High value = top3 compressed relative to full field
    if vp_spread_top3 is not None and vp_spread_field and vp_spread_field > 0:
        contender_compression_score = round(1.0 - vp_spread_top3 / vp_spread_field, 4)
    else:
        contender_compression_score = None

    # Favourite vulnerability
    favourite_vulnerability_score = (
        top_vp < 0.30 and (top_pick_rank_gap is None or top_pick_rank_gap < 0.05)
    )

    # Market structure from result runners
    field_size = len(result_runners)
    sps = [_sp_to_dec(r.get("sp") or r.get("sp_dec", "")) for r in result_runners]
    sps = [s for s in sps if s is not None]

    midprice_count = sum(1 for s in sps if MIDPRICE_LOW <= s <= MIDPRICE_HIGH)
    longshot_count = sum(1 for s in sps if s > 10.0)
    midprice_density = round(midprice_count / field_size, 4) if field_size > 0 else 0.0
    longshot_noise_ratio = round(longshot_count / field_size, 4) if field_size > 0 else 0.0

    # Market concentration: SP of top pick
    top_snap = snaps[0] if snaps else {}
    top_sp = _sp_to_dec(str(top_snap.get("sp_dec", "") or ""))
    market_concentration_score = round(1.0 / top_sp, 4) if top_sp and top_sp > 0 else None

    # Is top pick the market favourite?
    top_pick_is_favourite = bool(top_snap.get("is_fav", False))

    # SP vs VP rank correlation (Spearman-like, simplified)
    sp_vp_rank_corr = None
    if snaps and sps and len(snaps) >= 3 and len(sps) == len(snaps):
        vp_ranks = list(range(len(snaps)))  # already sorted by VP rank
        sp_ranks = sorted(range(len(sps)), key=lambda i: sps[i])
        # simple rank agreement score
        matches = sum(1 for v, s in zip(vp_ranks, sp_ranks) if v == s)
        sp_vp_rank_corr = round(matches / len(snaps), 4)

    # Winner SP rank (from result)
    winner = next((r for r in result_runners if str(r.get("position", "")) == "1"), None)
    winner_sp = _sp_to_dec(winner.get("sp") or str(winner.get("sp_dec", ""))) if winner else None
    winner_sp_rank = None
    if winner_sp is not None and sps:
        sorted_sps = sorted(sps)
        try:
            winner_sp_rank = sorted_sps.index(winner_sp) + 1
        except ValueError:
            winner_sp_rank = None

    # Going flag
    going = result_meta.get("going", "") or ""
    going_soft_flag = going.lower() in {"soft", "heavy", "good to soft", "soft (heavy in places)"}

    # Draw available
    draw_available = any(str(r.get("draw", "")).strip() for r in result_runners)

    features: dict = {
        "race_id": race_id,
        "date": result_meta.get("date", ""),
        "course": result_meta.get("course", ""),
        "course_id": result_meta.get("course_id", ""),
        "off_time": result_meta.get("off", ""),
        "race_class": result_meta.get("class", ""),
        "dist": result_meta.get("dist", ""),
        "going": going,
        "field_size": field_size,
        "n_snap_runners": n_snap,
        "top_vp": round(top_vp, 6),
        "top_pick_rank_gap": round(top_pick_rank_gap, 6) if top_pick_rank_gap is not None else None,
        "vp_spread_top3": round(vp_spread_top3, 6) if vp_spread_top3 is not None else None,
        "vp_spread_field": round(vp_spread_field, 6) if vp_spread_field is not None else None,
        "contender_compression_score": contender_compression_score,
        "favourite_vulnerability_score": favourite_vulnerability_score,
        "top3_vp_spread": round(vp_spread_top3, 6) if vp_spread_top3 is not None else None,
        "market_concentration_score": market_concentration_score,
        "top_pick_is_favourite": top_pick_is_favourite,
        "sp_vp_rank_corr": sp_vp_rank_corr,
        "midprice_density": midprice_density,
        "midprice_count": midprice_count,
        "longshot_noise_ratio": longshot_noise_ratio,
        "longshot_count": longshot_count,
        "winner_sp": winner_sp,
        "winner_sp_rank": winner_sp_rank,
        "winner_in_midprice": (MIDPRICE_LOW <= winner_sp <= MIDPRICE_HIGH) if winner_sp else None,
        "going_soft_flag": going_soft_flag,
        "draw_available": draw_available,
        "class_drop_flag": None,
        "distance_change_flag": None,
    }
    features["race_shape_status"] = _classify_shape(features)
    return features


def build_features(date_str: str) -> list[dict]:
    print(f"[RaceShape] Loading snapshots for {date_str}...")
    snapshots = _load_snapshots(date_str)
    print(f"[RaceShape] Loading results for {date_str}...")
    results = _load_results(date_str)

    if not snapshots:
        print(f"[WARN] No snapshots found for {date_str}")
        return []
    if not results:
        print(f"[WARN] No results found for {date_str}")
        return []

    # Group snapshots by race_id
    snap_by_race: dict[str, list[dict]] = {}
    for row in snapshots:
        rid = row.get("race_id", "")
        if rid:
            snap_by_race.setdefault(rid, []).append(row)

    result_map = {r["race_id"]: r for r in results}

    features_list: list[dict] = []
    for race_id, result_meta in result_map.items():
        snap_runners = snap_by_race.get(race_id, [])
        result_runners = result_meta.get("runners", [])
        features = compute_race_shape(race_id, snap_runners, result_runners, result_meta)
        features_list.append(features)

    print(f"[RaceShape] Computed features for {len(features_list)} races")
    return features_list


def _write_md(features_list: list[dict], date_str: str) -> str:
    status_counts: dict[str, int] = {}
    for f in features_list:
        s = f.get("race_shape_status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1

    fav_vuln = sum(1 for f in features_list if f.get("favourite_vulnerability_score"))
    compressed = sum(1 for f in features_list if (f.get("vp_spread_top3") or 1.0) < 0.04)
    midprice_trap = sum(1 for f in features_list if (f.get("midprice_density") or 0) >= 0.45)
    winner_midprice = sum(1 for f in features_list if f.get("winner_in_midprice"))

    status_rows = "".join(f"| {k} | {v} |\n" for k, v in sorted(status_counts.items(), key=lambda x: -x[1]))

    race_rows = ""
    for f in sorted(features_list, key=lambda x: x.get("race_id", "")):
        race_rows += (
            f"| {f['race_id']} | {f.get('race_shape_status')} | "
            f"{f.get('field_size')} | "
            f"{f.get('vp_spread_top3', 'N/A'):.4f} | "
            f"{f.get('midprice_density', 0):.3f} | "
            f"{f.get('winner_sp', 'N/A')} | "
            f"{f.get('going', '')} |\n"
        )

    return f"""# Race Shape Features — {date_str}

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Races:** {len(features_list)}
**Status:** RESEARCH ONLY — no scoring integration

---

## Race Shape Status Distribution

| Status | Count |
|---|---|
{status_rows}
---

## Summary Statistics

| Metric | Count |
|---|---|
| FAV_VULNERABLE races | {fav_vuln} |
| COMPRESSED top3 VP (<0.04) | {compressed} |
| MIDPRICE_TRAP density (>=0.45) | {midprice_trap} |
| Winner in midprice zone (SP 3-8.5) | {winner_midprice} |

---

## Per-Race Table

| Race ID | Shape Status | Field Size | VP Spread Top3 | Midprice Density | Winner SP | Going |
|---|---|---|---|---|---|---|
{race_rows}
---

## Governance

```
No scoring changes.
No routing changes.
No staking changes.
Research artifact only — feeds MIDPRICE_HUNTER_V2_RESEARCH_PLAN.md protocol.
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Race Shape Features V1")
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    features_list = build_features(args.date)
    if not features_list:
        print("[WARN] No features computed — check inputs")
        sys.exit(1)

    out_dir_features = ROOT / "data" / "features"
    out_dir_reports = ROOT / "data" / "reports"
    out_dir_features.mkdir(parents=True, exist_ok=True)
    out_dir_reports.mkdir(parents=True, exist_ok=True)

    out_json = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "race_count": len(features_list),
        "features": features_list,
    }

    feat_path = out_dir_features / "race_shape_features_latest.json"
    feat_path.write_text(json.dumps(out_json, indent=2))
    print(f"[RaceShape] Written: {feat_path}")

    md_path = out_dir_reports / "race_shape_features_latest.md"
    md_path.write_text(_write_md(features_list, args.date))
    print(f"[RaceShape] Written: {md_path}")

    # Print status distribution
    status_counts: dict[str, int] = {}
    for f in features_list:
        s = f.get("race_shape_status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1
    print()
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
