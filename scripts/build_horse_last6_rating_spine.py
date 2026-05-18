#!/usr/bin/env python3
"""RP_LAST6_RATING_SPINE_V1 — extracts last-6 OR/TS/RPR arrays and derives rating trend features.

Source : data/raceform_v17_features.parquet (1.7M rows, 2015-01-01 to 2025-07-05)
Targets: data/features/runner_master_profile_latest.parquet (1,310 sigma rows)
         + today's racecard (data/racecards_YYYY_MM_DD_standard.json)
Output : data/features/horse_last6_rating_spine.parquet

Raceform gap warning: Aug 2025 – Feb 2026 not covered. For March-May 2026 sigma rows
the last-6 arrays reflect pre-Aug 2025 history only.

Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_ONLY
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RACEFORM_PATH     = ROOT / "data" / "raceform_v17_features.parquet"
MASTER_PATH       = ROOT / "data" / "features" / "runner_master_profile_latest.parquet"
RACECARD_DIR      = ROOT / "data"
OUTPUT_PATH       = ROOT / "data" / "features" / "horse_last6_rating_spine.parquet"


# ─── Name normalization ────────────────────────────────────────────────────────

_COUNTRY_RE = re.compile(r'\s*\([^)]*\)\s*$')

def normalize_name(name: str) -> str:
    """Strip trailing country code suffixes and lowercase. 'Abduction (GB)' → 'abduction'."""
    return _COUNTRY_RE.sub('', str(name).strip()).strip().lower()


# ─── Position parsing ──────────────────────────────────────────────────────────

def parse_pos(pos_str) -> Optional[int]:
    """Return int finishing position, or None for PU/F/U/DSQ/RR/CO etc."""
    if pos_str is None:
        return None
    if isinstance(pos_str, float) and np.isnan(pos_str):
        return None
    try:
        return int(str(pos_str).strip())
    except (ValueError, TypeError):
        return None


# ─── Slope ────────────────────────────────────────────────────────────────────

def linear_slope(values: list) -> Optional[float]:
    """Slope over time for a newest-first list of floats.

    x=0 assigned to oldest, x=n-1 to newest → positive slope = improving trend.
    Requires ≥2 non-null values.
    """
    n = len(values)
    pts = [(n - 1 - i, v) for i, v in enumerate(values)
           if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if len(pts) < 2:
        return None
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    return float(np.polyfit(xs, ys, 1)[0])


# ─── Flag derivation ──────────────────────────────────────────────────────────

def _clean(vals: list) -> list:
    return [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]


def derive_flags(
    ts_vals: list,
    rpr_vals: list,
    ts_slope: Optional[float],
    or_slope: Optional[float],
    rpr_slope: Optional[float],
    n_runs: int,
) -> tuple[bool, bool, bool]:
    """Returns (rating_rebound_flag, silent_improver_flag, exposed_regression_flag)."""

    # rating_rebound_flag — TS shows V-shape: dip in mid-sequence then recovery
    rating_rebound = False
    ts_clean = _clean(ts_vals)
    if len(ts_clean) >= 4:
        recent_avg = float(np.mean(ts_clean[:2]))
        mid_section = ts_clean[1:-1]   # exclude most-recent and oldest
        mid_min = float(min(mid_section)) if mid_section else recent_avg
        early_avg = float(np.mean(ts_clean[2:])) if len(ts_clean) > 2 else recent_avg
        # Rebound: recent avg above the mid-sequence trough AND above early average
        if recent_avg > mid_min and recent_avg >= early_avg:
            rating_rebound = True

    # silent_improver_flag — TS improving while OR flat/falling
    # Horse running better than handicap mark suggests; handicapper hasn't caught up
    silent_improver = False
    if ts_slope is not None and or_slope is not None:
        if ts_slope >= 1.5 and or_slope <= 0.0:
            silent_improver = True

    # exposed_regression_flag — both RPR and TS declining over ≥3 runs
    exposed_regression = False
    if rpr_slope is not None and ts_slope is not None and n_runs >= 3:
        if rpr_slope <= -1.5 and ts_slope <= -1.5:
            exposed_regression = True

    return rating_rebound, silent_improver, exposed_regression


# ─── Core feature extractor ───────────────────────────────────────────────────

def _null_row() -> dict:
    return {
        "last6_runs":            0,
        "last_6_or":             "[]",
        "last_6_ts":             "[]",
        "last_6_rpr":            "[]",
        "last_6_pos":            "[]",
        "last_6_sp":             "[]",
        "last_6_course":         "[]",
        "last_6_distance":       "[]",
        "last_6_going":          "[]",
        "or_slope_6":            None,
        "ts_slope_6":            None,
        "rpr_slope_6":           None,
        "or_peak_6":             None,
        "ts_peak_recent":        None,
        "rpr_peak_recent":       None,
        "or_drop_from_peak":     None,
        "ts_vs_or_gap":          None,
        "rating_rebound_flag":   False,
        "silent_improver_flag":  False,
        "exposed_regression_flag": False,
    }


def extract_last6_features(runs: list[dict], cutoff_date: date) -> dict:
    """Given runs sorted newest-first, return last-6 feature dict for cutoff_date."""
    eligible = [r for r in runs if r["date"] < cutoff_date]
    last6 = eligible[:6]
    n = len(last6)

    if n == 0:
        return _null_row()

    # Raw arrays (index 0 = most recent)
    or_vals  = [r.get("or_num")    for r in last6]
    ts_vals  = [r.get("ts_num")    for r in last6]
    rpr_vals = [r.get("rpr_num")   for r in last6]
    pos_vals = [r.get("pos_int")   for r in last6]
    sp_vals  = [r.get("sp_dec")    for r in last6]
    crs_vals = [r.get("course")    for r in last6]
    dst_vals = [r.get("dist_f")    for r in last6]
    gng_vals = [r.get("going_code")for r in last6]

    # Slopes
    or_slope  = linear_slope(or_vals)
    ts_slope  = linear_slope(ts_vals)
    rpr_slope = linear_slope(rpr_vals)

    # Peak values across the window
    or_clean  = _clean(or_vals)
    ts_clean  = _clean(ts_vals)
    rpr_clean = _clean(rpr_vals)

    or_peak  = float(max(or_clean))  if or_clean  else None
    ts_peak  = float(max(ts_clean))  if ts_clean  else None
    rpr_peak = float(max(rpr_clean)) if rpr_clean else None

    # Current (most recent) values
    current_or  = next((v for v in or_vals  if v is not None), None)
    current_ts  = next((v for v in ts_vals  if v is not None), None)

    # Derived scalar metrics
    or_drop = (or_peak - current_or) if (or_peak is not None and current_or is not None) else None
    ts_or_gap = (current_ts - current_or) if (current_ts is not None and current_or is not None) else None

    # Flags
    rebound, improver, regression = derive_flags(
        ts_vals, rpr_vals, ts_slope, or_slope, rpr_slope, n
    )

    return {
        "last6_runs":              n,
        "last_6_or":               json.dumps(or_vals),
        "last_6_ts":               json.dumps(ts_vals),
        "last_6_rpr":              json.dumps(rpr_vals),
        "last_6_pos":              json.dumps(pos_vals),
        "last_6_sp":               json.dumps(sp_vals),
        "last_6_course":           json.dumps(crs_vals),
        "last_6_distance":         json.dumps(dst_vals),
        "last_6_going":            json.dumps(gng_vals),
        "or_slope_6":              or_slope,
        "ts_slope_6":              ts_slope,
        "rpr_slope_6":             rpr_slope,
        "or_peak_6":               or_peak,
        "ts_peak_recent":          ts_peak,
        "rpr_peak_recent":         rpr_peak,
        "or_drop_from_peak":       or_drop,
        "ts_vs_or_gap":            ts_or_gap,
        "rating_rebound_flag":     rebound,
        "silent_improver_flag":    improver,
        "exposed_regression_flag": regression,
    }


# ─── Raceform lookup builder ──────────────────────────────────────────────────

def build_raceform_lookup(path: Path) -> dict[str, list[dict]]:
    """Load raceform parquet and build {horse_normalized: [runs newest-first]}."""
    print(f"Loading raceform: {path}")
    cols = ["horse", "date", "or_num", "ts_num", "rpr_num", "pos",
            "sp_dec", "course", "dist_f", "going_code"]
    df = pd.read_parquet(path, columns=cols)
    print(f"  {len(df):,} rows")

    df["horse_norm"] = df["horse"].apply(normalize_name)
    df["date"]       = pd.to_datetime(df["date"]).dt.date
    df["pos_int"]    = df["pos"].apply(parse_pos)

    # Sort newest-first within each horse (stable)
    df = df.sort_values(["horse_norm", "date"], ascending=[True, False])

    keep_cols = ["date", "or_num", "ts_num", "rpr_num", "pos_int",
                 "sp_dec", "course", "dist_f", "going_code"]
    lookup: dict[str, list[dict]] = {}
    for horse_norm, grp in df.groupby("horse_norm", sort=False):
        lookup[horse_norm] = grp[keep_cols].to_dict("records")

    print(f"  {len(lookup):,} unique horses indexed")
    return lookup


# ─── Target collection ────────────────────────────────────────────────────────

def load_sigma_targets(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  WARNING: {path} not found — skipping sigma targets")
        return []
    df = pd.read_parquet(path, columns=["horse", "date", "race_id"])
    print(f"  Sigma: {len(df):,} rows")
    targets = []
    for _, row in df.iterrows():
        d = row["date"]
        targets.append({
            "horse":   str(row["horse"]),
            "date":    pd.to_datetime(d).date() if not isinstance(d, date) else d,
            "race_id": str(row.get("race_id", "")),
            "source":  "sigma",
        })
    return targets


def load_racecard_targets(racecard_dir: Path, today: date) -> list[dict]:
    """Load today's racecard horses for live daily use."""
    # Try standard filename patterns
    date_str_dash = today.strftime("%Y_%m_%d")
    date_str_iso  = today.strftime("%Y-%m-%d")
    candidates = [
        racecard_dir / f"racecards_{date_str_dash}_standard.json",
        racecard_dir / f"racecards_{date_str_iso}_standard.json",
        racecard_dir / f"racecards_{date_str_dash}.json",
        racecard_dir / f"racecards_{date_str_iso}.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            # API format: data['racecards'] list
            racecards = (data.get("racecards") or
                         (data if isinstance(data, list) else
                          data.get("races", data.get("data", []))))
            targets = []
            for race in racecards:
                race_id = race.get("race_id", "")
                course  = race.get("course", "")
                for runner in race.get("runners", []):
                    name = runner.get("horse", runner.get("horse_name", ""))
                    if name:
                        targets.append({
                            "horse":   str(name),
                            "date":    today,
                            "race_id": race_id,
                            "course":  course,
                            "source":  "racecard",
                        })
            print(f"  Racecard: {len(targets)} runners from {path.name}")
            return targets
        except Exception as e:
            print(f"  WARNING: Failed to load {path.name}: {e}")
    print(f"  No racecard found for {today}")
    return []


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"\nRP_LAST6_RATING_SPINE_V1 — {today}")
    print("=" * 62)

    # 1. Build raceform lookup
    lookup = build_raceform_lookup(RACEFORM_PATH)

    # 2. Collect targets
    print("\nCollecting targets...")
    targets = load_sigma_targets(MASTER_PATH) + load_racecard_targets(RACECARD_DIR, today)

    # Deduplicate on (horse_norm, date) — sigma rows win (source = sigma first)
    seen: set[tuple] = set()
    unique_targets: list[dict] = []
    for t in targets:
        key = (normalize_name(t["horse"]), t["date"])
        if key not in seen:
            seen.add(key)
            unique_targets.append(t)
    print(f"  Unique (horse, date) pairs: {len(unique_targets):,}")

    # 3. Extract features
    print("\nExtracting last-6 features...")
    rows = []
    found = 0
    not_found = 0

    for t in unique_targets:
        horse_norm = normalize_name(t["horse"])
        cutoff     = t["date"]

        if horse_norm in lookup:
            features = extract_last6_features(lookup[horse_norm], cutoff)
            found += 1
        else:
            features = _null_row()
            not_found += 1

        rows.append({
            "horse":     t["horse"],
            "horse_norm": horse_norm,
            "race_date": cutoff,
            "race_id":   t.get("race_id", ""),
            "source":    t.get("source", ""),
            **features,
        })

    cov = found / len(unique_targets) * 100 if unique_targets else 0
    print(f"  Found: {found:,} | Not found: {not_found:,} | Coverage: {cov:.1f}%")

    # 4. Build dataframe
    out = pd.DataFrame(rows)

    # ── Stats ─────────────────────────────────────────────────────────────────
    print("\n--- Feature Coverage ---")
    scalar_cols = [
        ("or_slope_6",         "OR slope"),
        ("ts_slope_6",         "TS slope"),
        ("rpr_slope_6",        "RPR slope"),
        ("or_drop_from_peak",  "OR drop from peak"),
        ("ts_vs_or_gap",       "TS vs OR gap"),
        ("or_peak_6",          "OR peak"),
        ("ts_peak_recent",     "TS peak"),
        ("rpr_peak_recent",    "RPR peak"),
    ]
    for col, label in scalar_cols:
        n_valid = out[col].notna().sum()
        pct = n_valid / len(out) * 100
        print(f"  {label:<22}: {n_valid:4d}/{len(out)} ({pct:.1f}%)")

    print()
    for flag in ["rating_rebound_flag", "silent_improver_flag", "exposed_regression_flag"]:
        n_flag = int(out[flag].sum())
        pct = n_flag / len(out) * 100
        print(f"  {flag:<30}: {n_flag:4d} ({pct:.1f}%)")

    print("\n--- Slope Distributions (non-null) ---")
    for col in ["or_slope_6", "ts_slope_6", "rpr_slope_6"]:
        s = out[col].dropna()
        if len(s):
            print(f"  {col}: n={len(s)} mean={s.mean():.2f} "
                  f"p25={s.quantile(0.25):.2f} p75={s.quantile(0.75):.2f} "
                  f"min={s.min():.2f} max={s.max():.2f}")

    # Sigma-only flag hit rates (exclude racecard targets)
    sigma_only = out[out["source"] == "sigma"]
    if len(sigma_only):
        print(f"\n--- Flag hit rates (sigma, n={len(sigma_only)}) ---")
        for flag in ["rating_rebound_flag", "silent_improver_flag", "exposed_regression_flag"]:
            n = int(sigma_only[flag].sum())
            print(f"  {flag}: {n} ({n/len(sigma_only)*100:.1f}%)")

    # 5. Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved:  {OUTPUT_PATH}")
    print(f"Shape:  {out.shape}")

    # JSON summary
    summary = {
        "generated":              today.isoformat(),
        "source":                 "raceform_v17_features.parquet",
        "raceform_date_range":    "2015-01-01 to 2025-07-05",
        "raceform_gap_warning":   (
            "Aug 2025 – Feb 2026 not covered. "
            "For March-May 2026 sigma rows, last-6 uses pre-Aug 2025 history only."
        ),
        "total_unique_targets":   len(unique_targets),
        "found_in_raceform":      found,
        "not_found":              not_found,
        "coverage_pct":           round(cov, 1),
        "rows":                   len(out),
        "columns":                list(out.columns),
        "slope_interpretation": {
            "or_slope_6":  "positive = OR rising (handicapper catching up); negative = OR falling (potentially well-weighted)",
            "ts_slope_6":  "positive = horse's performance (TS) improving over last 6",
            "rpr_slope_6": "positive = RPR improving",
            "or_drop_from_peak": "or_peak - current_or; positive = below peak weight (possibly well-handicapped)",
            "ts_vs_or_gap": "current_ts - current_or; positive = TS above OR (running beyond handicap mark)",
        },
        "flag_rules": {
            "rating_rebound_flag":   "TS shows V-shape: dip in mid-sequence then recent recovery",
            "silent_improver_flag":  "ts_slope >= 1.5 AND or_slope <= 0.0 (TS improving, OR not catching up)",
            "exposed_regression_flag": "rpr_slope <= -1.5 AND ts_slope <= -1.5 AND n_runs >= 3",
        },
        "governance":             "NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_ONLY",
    }
    summary_path = OUTPUT_PATH.with_suffix(".json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {summary_path}")

    print("\nRP_LAST6_RATING_SPINE_V1 complete.")
    print("Governance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_ONLY")


if __name__ == "__main__":
    main()
