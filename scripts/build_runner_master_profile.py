#!/usr/bin/env python3
"""
BUILD_RUNNER_MASTER_PROFILE_V1

Combines all available data sources into a single runner-level truth table.
Historical rows = sigma training dataset enriched with JTC-D and RP data.

Data sources joined:
  1. sigma_2k_training_dataset_latest.parquet (1,521 rows — scored + results)
  2. Racing API racecard snapshot JSONs (horse_id → trainer_id/jockey_id)
  3. JTC-D lookup tables (shrinkage-adjusted, 10yr history)
  4. RP runner profile (colour card OR/TS/RPR where PDFs exist for that date)

Outputs:
  data/features/runner_master_profile_latest.parquet
  data/features/runner_master_profile_latest.json

Governance:
  NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
  Advisory only — shadow audit only, not wired to scoring

Usage:
  python scripts/build_runner_master_profile.py [--dry-run]
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workers.ingestion_spine.racingpost_pdf.normalize import normalize_horse_name

SIGMA = ROOT / "data" / "training" / "sigma_2k_training_dataset_latest.parquet"
RACECARDS_DIR = ROOT / "data"
JTCD_DIR = ROOT / "data" / "features" / "jtc_d"
RP_PROFILE = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
FEATURES_DIR = ROOT / "data" / "features"
FEATURES_DIR.mkdir(exist_ok=True)


def _build_global_bridge() -> dict[str, dict]:
    """
    Build horse_id → {trainer, trainer_id, jockey, jockey_id, trainer_rtf}
    from ALL available Racing API racecard snapshot JSONs.
    Latest racecard for each horse_id wins (iterates chronologically).
    """
    bridge: dict[str, dict] = {}
    json_files = sorted(
        list(RACECARDS_DIR.glob("racecards_*_standard.json")) +
        list(RACECARDS_DIR.glob("racecards_*.json"))
    )

    seen = set()
    for jf in json_files:
        if jf in seen:
            continue
        seen.add(jf)
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            racecards = data.get("racecards", data) if isinstance(data, dict) else data
            if not isinstance(racecards, list):
                continue
            for rc in racecards:
                for runner in rc.get("runners", []):
                    hid = runner.get("horse_id")
                    if not hid:
                        continue
                    bridge[hid] = {
                        "trainer": runner.get("trainer", ""),
                        "trainer_id": runner.get("trainer_id"),
                        "jockey": runner.get("jockey", ""),
                        "jockey_id": runner.get("jockey_id"),
                        "trainer_rtf": runner.get("trainer_rtf"),
                        "ofr_api": runner.get("ofr"),
                        "rpr_api": runner.get("rpr"),
                        "ts_api": runner.get("ts"),
                        "form_api": runner.get("form"),
                        "spotlight_api": runner.get("spotlight"),
                        "comment_api": runner.get("comment"),
                    }
        except Exception:
            continue

    return bridge


def _load_jtcd() -> dict[str, pd.DataFrame | None]:
    profiles = {}
    for name in ["trainer_course", "trainer_dist", "jockey_course",
                 "jockey_dist", "trainer_jockey"]:
        path = JTCD_DIR / f"{name}_profile.parquet"
        profiles[name] = pd.read_parquet(path) if path.exists() else None
    return profiles


def _build_jtcd_lookup(profiles: dict) -> dict:
    """Convert DataFrames to dicts for fast lookup."""
    lookups = {}
    for name, df in profiles.items():
        if df is None:
            lookups[name] = {}
            continue
        if name in ("trainer_course",):
            lookups[name] = {(r["trainer"].upper(), r["course"].upper()): r["jtc_signal"]
                             for _, r in df.iterrows() if r["trainer"] and r["course"]}
        elif name == "trainer_dist":
            lookups[name] = {(r["trainer"].upper(), str(r["dist_band"]).upper()): r["jtc_signal"]
                             for _, r in df.iterrows() if r["trainer"]}
        elif name == "jockey_course":
            lookups[name] = {(r["jockey"].upper(), r["course"].upper()): r["jtc_signal"]
                             for _, r in df.iterrows() if r["jockey"] and r["course"]}
        elif name == "jockey_dist":
            lookups[name] = {(r["jockey"].upper(), str(r["dist_band"]).upper()): r["jtc_signal"]
                             for _, r in df.iterrows() if r["jockey"]}
        elif name == "trainer_jockey":
            lookups[name] = {(r["trainer"].upper(), r["jockey"].upper()): r["jtc_signal"]
                             for _, r in df.iterrows() if r["trainer"] and r["jockey"]}
    return lookups


def _dist_band(dist_text: str) -> str:
    """Convert distance text (e.g. '6f', '1m2f') to canonical band."""
    import re
    t = (dist_text or "").lower().replace(" ", "")
    m = re.match(r"(?:(\d+)m)?(\d+(?:\.\d+)?f)?", t)
    if not m:
        return "unknown"
    miles = int(m.group(1) or 0)
    furlongs_raw = float((m.group(2) or "0f").replace("f", ""))
    total_f = miles * 8 + furlongs_raw
    bins = [(5.5, "5f"), (6.5, "6f"), (7.5, "7f"), (8.5, "8f"),
            (10.5, "9-10f"), (12.5, "11-12f"), (14.5, "13-14f"), (17.5, "15-17f")]
    for ceil, label in bins:
        if total_f < ceil:
            return label
    return "18f+"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("RUNNER MASTER PROFILE V1")
    print("=" * 60)

    # ── Load sigma ───────────────────────────────────────────────
    sigma = pd.read_parquet(SIGMA)
    sigma = sigma[sigma["result_matched"] == True].copy()
    print(f"Sigma (result_matched): {len(sigma):,} rows")
    print(f"Date range: {sigma['date'].min()} → {sigma['date'].max()}")

    # ── Build identity bridge (all 36 racecard snapshots) ────────
    bridge = _build_global_bridge()
    print(f"\nIdentity bridge: {len(bridge):,} horse_id entries")

    # ── Load JTC-D profiles ──────────────────────────────────────
    jtcd_dfs = _load_jtcd()
    lookups = _build_jtcd_lookup(jtcd_dfs)
    jtcd_loaded = sum(1 for v in jtcd_dfs.values() if v is not None)
    print(f"JTC-D profiles: {jtcd_loaded}/5 tables")

    # ── Load RP runner profile (for available dates) ─────────────
    rp_map: dict[tuple, dict] = {}
    if RP_PROFILE.exists():
        rp_df = pd.read_parquet(RP_PROFILE)
        for _, row in rp_df.iterrows():
            key = (str(row.get("race_date", "")), row.get("horse_id", ""))
            rp_map[key] = row.to_dict()
        print(f"RP runner profile: {len(rp_df):,} rows from {rp_df['race_date'].iloc[0] if len(rp_df) > 0 else 'n/a'}")
    else:
        print("RP runner profile: not available (run build_rp_runner_profile.py first)")

    # ── Enrich each sigma row ────────────────────────────────────
    print("\nEnriching sigma rows...")
    rows_out = []

    for _, row in sigma.iterrows():
        horse_id = row["horse_id"]
        course = str(row.get("course") or "")
        dist_text = str(row.get("distance", ""))
        dist_b = _dist_band(dist_text)
        date_str = str(row.get("date", ""))[:10]

        id_data = bridge.get(horse_id, {})
        trainer = str(id_data.get("trainer") or "")
        trainer_id = id_data.get("trainer_id")
        jockey = str(id_data.get("jockey") or "")
        jockey_id = id_data.get("jockey_id")

        # JTC-D lookups
        tc_key = (trainer.upper(), course.upper()) if trainer else ("", "")
        td_key = (trainer.upper(), dist_b.upper()) if trainer else ("", "")
        jc_key = (jockey.upper(), course.upper()) if jockey else ("", "")
        jd_key = (jockey.upper(), dist_b.upper()) if jockey else ("", "")
        tj_key = (trainer.upper(), jockey.upper()) if trainer and jockey else ("", "")

        trainer_course_sr = lookups["trainer_course"].get(tc_key)
        trainer_dist_sr = lookups["trainer_dist"].get(td_key)
        jockey_course_sr = lookups["jockey_course"].get(jc_key)
        jockey_dist_sr = lookups["jockey_dist"].get(jd_key)
        trainer_jockey_sr = lookups["trainer_jockey"].get(tj_key)

        # RP data (if available for this date)
        rp_key = (date_str, horse_id)
        rp = rp_map.get(rp_key, {})

        out = dict(row)
        out.update({
            "trainer": trainer,
            "trainer_id": trainer_id,
            "jockey": jockey,
            "jockey_id": jockey_id,
            "trainer_rtf": id_data.get("trainer_rtf"),
            "ofr_api": id_data.get("ofr_api"),
            "rpr_api": id_data.get("rpr_api"),
            "ts_api": id_data.get("ts_api"),
            "form_api": id_data.get("form_api"),
            "spotlight_api": id_data.get("spotlight_api") or id_data.get("comment_api"),
            # JTC-D signals
            "trainer_course_sr": trainer_course_sr,
            "trainer_dist_sr": trainer_dist_sr,
            "jockey_course_sr": jockey_course_sr,
            "jockey_dist_sr": jockey_dist_sr,
            "trainer_jockey_sr": trainer_jockey_sr,
            "dist_band": dist_b,
            # RP colour card fields (where available)
            "rp_current_or": rp.get("current_or"),
            "rp_current_ts": rp.get("current_ts"),
            "rp_current_rpr": rp.get("current_rpr"),
            "rp_form_figures": rp.get("form_figures"),
            "rp_days_since_run": rp.get("days_since_run"),
            "rp_course_winner": rp.get("course_winner"),
            "rp_dist_winner": rp.get("dist_winner"),
            "rp_cd_winner": rp.get("cd_winner"),
            "rp_trainer_course_sr": rp.get("trainer_course_sr"),
            "rp_jockey_course_sr": rp.get("jockey_course_sr"),
            "rp_horse_comment": rp.get("horse_comment"),
        })
        rows_out.append(out)

    master = pd.DataFrame(rows_out)

    # Coverage report
    id_cov = (master["trainer"] != "").mean()
    tc_cov = master["trainer_course_sr"].notna().mean()
    jc_cov = master["jockey_course_sr"].notna().mean()
    rp_cov = master["rp_current_or"].notna().mean()

    print(f"\nCoverage on {len(master):,} rows:")
    print(f"  trainer identity:      {id_cov:.1%}")
    print(f"  trainer_course_sr:     {tc_cov:.1%}")
    print(f"  jockey_course_sr:      {jc_cov:.1%}")
    print(f"  RP OR (same-day):      {rp_cov:.1%}")

    if args.dry_run:
        print("\nDRY RUN — no files written")
        show_cols = ["date", "horse", "course", "velo_prime_prob", "trainer",
                     "trainer_course_sr", "jockey_course_sr", "won"]
        print(master[show_cols].head(10).to_string())
        return

    # ── Write ────────────────────────────────────────────────────
    numeric_cols = ["trainer_course_sr", "trainer_dist_sr", "jockey_course_sr",
                    "jockey_dist_sr", "trainer_jockey_sr", "ofr_api", "rpr_api",
                    "ts_api", "trainer_rtf", "rp_current_or", "rp_current_ts",
                    "rp_current_rpr", "rp_days_since_run"]
    for c in numeric_cols:
        if c in master.columns:
            master[c] = pd.to_numeric(master[c], errors="coerce")

    str_cols = ["form_api", "spotlight_api", "trainer", "jockey",
                "trainer_id", "jockey_id", "dist_band", "rp_form_figures", "rp_horse_comment"]
    for c in str_cols:
        if c in master.columns:
            master[c] = master[c].astype(str).replace("None", "").replace("nan", "")

    parquet_path = FEATURES_DIR / "runner_master_profile_latest.parquet"
    master.to_parquet(parquet_path, index=False)
    print(f"\nWritten: {parquet_path}  ({len(master):,} rows, {len(master.columns)} columns)")

    json_path = FEATURES_DIR / "runner_master_profile_latest.json"
    summary = {
        "rows": len(master),
        "columns": list(master.columns),
        "date_range": {"min": str(master["date"].min()), "max": str(master["date"].max())},
        "coverage": {
            "trainer_identity": round(id_cov, 4),
            "trainer_course_sr": round(tc_cov, 4),
            "jockey_course_sr": round(jc_cov, 4),
            "rp_or_same_day": round(rp_cov, 4),
        },
        "governance": "NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_AUDIT_ONLY",
    }
    json_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Written: {json_path}")
    print(f"\nGovernance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | SHADOW_AUDIT_ONLY")

    return master


if __name__ == "__main__":
    main()
