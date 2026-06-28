"""
Build Sigma Local Corpus
========================
Joins local sigma outcome files with local verdict JSON files to produce
a feature-rich training corpus for C-2 multi-model sigma and C-3 RPDC threshold
calibration.

Source A: data/sigma_results/sigma_results_YYYY_MM_DD.json  (outcomes per race)
Source B: data/velo_prime_verdicts_YYYY_MM_DD.json          (features per race)

Join key: race_id (1:1, sigma is top-pick only)

Output:
  data/training/sigma_local_corpus_latest.parquet
  data/training/sigma_local_corpus_latest.json   (manifest)

Safety: read-only from sources, writes only to data/training/.
No Supabase. No scoring change. No staking. Audit only.
"""
from __future__ import annotations

import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT_PARQUET = DATA / "training" / "sigma_local_corpus_latest.parquet"
OUT_MANIFEST = DATA / "training" / "sigma_local_corpus_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _v(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return default


def _float(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _bool_flag(v: Any) -> bool:
    return bool(v) and str(v).lower() not in {"false", "0", "none", "null"}


def load_date(sigma_path: Path, verdict_path: Path) -> list[dict]:
    sigma_data = json.loads(sigma_path.read_text(encoding="utf-8"))
    verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))

    date = sigma_data.get("date", "")
    if sigma_data.get("evaluated_count", 0) == 0:
        return []

    # Build verdict lookup by race_id
    verdict_by_race: dict[str, dict] = {}
    for v in verdict_data:
        rid = v.get("race_id")
        if rid:
            verdict_by_race[rid] = v

    rows = []
    for sigma_row in sigma_data.get("rows", []):
        race_id = sigma_row.get("race_id")
        outcome = sigma_row.get("outcome", "")
        verdict = verdict_by_race.get(race_id, {})
        top = verdict.get("top") or {}
        ss = verdict.get("signal_stack") or {}

        if not outcome or outcome in ("NO_RESULT", "NR"):
            continue

        row = {
            "date": date,
            "race_id": race_id,
            "course": sigma_row.get("course") or verdict.get("course"),
            "off_time": sigma_row.get("off") or verdict.get("off_time"),
            "horse": sigma_row.get("predicted") or top.get("horse"),
            # Outcome
            "won": outcome == "WIN",
            "placed": outcome in ("WIN", "PLACED"),
            "outcome": outcome,
            # Core VP signals
            "velo_prime_prob": _float(_v(sigma_row, "velo_prime_prob") or _v(top, "velo_prime_prob") or _v(ss, "vp")),
            "sqpe_v17_prob": _float(top.get("sqpe_v17_prob")),
            "sqpe_no_rpr_prob": _float(top.get("sqpe_no_rpr_shadow_prob")),
            "improvement_score": _float(top.get("improvement_score") or _v(ss, "improvement")),
            "market_deception_score": _float(top.get("market_deception_score") or _v(ss, "mds")),
            "place_prob": _float(top.get("place_prob") or _v(ss, "place_prob")),
            "comment_intel_score": _float(top.get("comment_intel_score")),
            "sp_dec": _float(top.get("sp_dec")),
            # Decision context
            "assigned_product": sigma_row.get("assigned_product") or top.get("assigned_product"),
            "confidence_level": top.get("confidence_level"),
            "tier": verdict.get("tier"),
            "prob_gap": _float(ss.get("prob_gap")),
            "ensemble_confidence": _float(ss.get("ensemble_confidence")),
            # Router
            "router_qualified": _bool_flag(ss.get("source") in {"B_QUALITY", "B_FOCUS"}),
            # Macro
            "macro_chaos": _bool_flag(top.get("chaos_bloom")),
            "macro_favourite_trap": top.get("macro_favourite_trap"),
            "macro_available": _bool_flag(top.get("macro_available")),
            # G-shadow
            "g_shadow_mode": _bool_flag(top.get("g_shadow_mode")),
            "g_shadow_multiplier": _float(top.get("g_shadow_multiplier")),
            # RPDC
            "rpdc_lookup_status": top.get("rpdc_lookup_status"),
            "rpdc_primary_tag": top.get("rpdc_primary_tag"),
            "rpdc_tags": json.dumps(top.get("rpdc_tags") or []),
            "rpdc_release_score": _float(top.get("rpdc_release_score")),
            "rpdc_cash_window": _bool_flag(top.get("rpdc_cash_window_flag")),
            "rpdc_tag_count": int(top.get("rpdc_tag_count") or 0),
            # BHA signals
            "bha_or_diff_flag": top.get("bha_or_diff_flag"),
            "bha_or_diff_magnitude": _float(top.get("bha_or_diff_magnitude")),
            "surf_traj_flag": top.get("surf_traj_flag"),
            "surf_traj_slope": _float(top.get("surf_traj_slope")),
            # Verdict source
            "verdict_found": bool(verdict),
        }
        rows.append(row)
    return rows


def build() -> dict:
    sigma_files = sorted(
        f for f in glob.glob(str(DATA / "sigma_results" / "sigma_results_2026_*.json"))
        if "_pre_backfill" not in f
    )

    all_rows: list[dict] = []
    dates_built: list[str] = []
    dates_skipped: list[str] = []

    for sf in sigma_files:
        sigma_path = Path(sf)
        sigma_data = json.loads(sigma_path.read_text(encoding="utf-8"))
        date = sigma_data.get("date", "")
        if sigma_data.get("evaluated_count", 0) == 0:
            dates_skipped.append(date)
            continue

        date_slug = date.replace("-", "_")
        verdict_path = DATA / f"velo_prime_verdicts_{date_slug}.json"
        if not verdict_path.exists():
            dates_skipped.append(date)
            continue

        rows = load_date(sigma_path, verdict_path)
        all_rows.extend(rows)
        dates_built.append(date)

    df = pd.DataFrame(all_rows)

    # Type coercion
    for col in ["velo_prime_prob", "sqpe_v17_prob", "improvement_score",
                "market_deception_score", "place_prob", "prob_gap",
                "ensemble_confidence", "g_shadow_multiplier"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["won", "placed", "router_qualified", "macro_chaos",
                "macro_available", "g_shadow_mode", "verdict_found"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    wins = int(df["won"].sum()) if "won" in df.columns else 0
    sr = round(wins / len(df) * 100, 1) if len(df) else 0.0

    manifest = {
        "generated_at": _utc_now(),
        "source": "local_sigma_results + local_verdict_json",
        "dates_built": len(dates_built),
        "dates_skipped": len(dates_skipped),
        "date_range": f"{dates_built[0]} to {dates_built[-1]}" if dates_built else "none",
        "total_rows": len(df),
        "wins": wins,
        "sr_pct": sr,
        "skipped_dates": dates_skipped,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = build()
    print(f"Built: {result['total_rows']} rows, {result['dates_built']} dates")
    print(f"Range: {result['date_range']}")
    print(f"SR: {result['sr_pct']}%  ({result['wins']} wins)")
    print(f"Skipped: {result['dates_skipped']}")
    print(f"Output: {OUT_PARQUET}")
