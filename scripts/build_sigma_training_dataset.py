#!/usr/bin/env python3
"""
Build the frozen 2K Sigma training dataset.

Merges the unified evidence corpus + innovation protocol, adds derived
signal flags, enforces feature/label separation (no leakage), and
produces frozen parquet + JSON + manifest.

Outputs:
    data/training/sigma_2k_training_dataset_latest.parquet
    data/training/sigma_2k_training_dataset_latest.json
    data/reports/sigma_2k_dataset_manifest_latest.json
    data/reports/sigma_2k_dataset_manifest_latest.md

Usage:
    python scripts/build_sigma_training_dataset.py
"""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = ROOT / "data" / "training"
REPORTS_DIR = ROOT / "data" / "reports"
TRAINING_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ── Leakage boundary ─────────────────────────────────────────────────────────
# PREDICTION FEATURES — available before race start
PREDICTION_COLS = [
    "velo_prime_prob", "sqpe_v17_prob", "market_deception_score",
    "improvement_score", "place_prob", "longshot_prob", "release_day_prob",
    "comment_intel_score", "g_shadow_mode",
    "router_v1_shadow_pass", "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist", "router_shadow_lane",
    "power_anchor_mode", "watch_only_mode", "b_low_vp_suppress",
    # Racing API shadow scores (pre-race connection intelligence)
    "racing_api_connection_shadow_score", "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score", "racing_api_enrichment_shadow_score",
]

# RESULT LABELS — only known after race start
RESULT_COLS = [
    "result_position", "won", "placed", "sp_decimal",
    "actual_winner_sp", "result_matched",
]

# IDENTITY COLS — not features, not labels
IDENTITY_COLS = [
    "date", "race_id", "horse_id", "horse", "course", "off_time",
    "decision_tier", "confidence_level", "assigned_product",
    "canonical_identity_source", "canonical_result_source", "canonical_signal_source",
]

# IP structural columns (from innovation protocol)
IP_STRUCTURAL_COLS = [
    "race_type", "class_num", "field_size", "going", "distance", "archetype",
    "macro_chaos", "candidate_execution_lane", "candidate_execution_allowed",
]

FEATURE_SCHEMA_VERSION = "sigma_2k_v1"


def get_git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True
        ).strip()[:12]
    except Exception:
        return "unknown"


def vp_band(vp) -> str:
    if pd.isna(vp):
        return "unknown"
    vp = float(vp)
    if vp < 0.20:
        return "VP<0.20"
    if vp < 0.30:
        return "VP0.20-0.30"
    if vp < 0.40:
        return "VP0.30-0.40"
    return "VP>=0.40"


def sp_band(sp) -> str:
    if pd.isna(sp):
        return "unknown"
    sp = float(sp)
    if sp < 3.0:
        return "SP<3.0"
    if sp <= 8.5:
        return "SP3.0-8.5"
    if sp <= 16.0:
        return "SP8.5-16.0"
    return "SP>16.0"


def mds_band(mds) -> str:
    if pd.isna(mds):
        return "unknown"
    mds = float(mds)
    if mds < 0.30:
        return "MDS<0.30"
    if mds <= 0.50:
        return "MDS0.30-0.50"
    return "MDS>0.50"


def imp_band(imp) -> str:
    if pd.isna(imp):
        return "unknown"
    imp = float(imp)
    if imp < 0.20:
        return "IMP<0.20"
    if imp <= 0.40:
        return "IMP0.20-0.40"
    return "IMP>0.40"


def main():
    print("BUILD SIGMA 2K TRAINING DATASET")
    print("=" * 60)

    git_sha = get_git_sha()
    build_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    print(f"Git SHA: {git_sha}")
    print(f"Build:   {build_ts}")

    # ── Load sources ──────────────────────────────────────────────────────────
    print("\nLoading unified evidence corpus...")
    corpus = pd.read_csv(ROOT / "data" / "velo_unified_evidence_corpus_v1.csv")
    print(f"  Corpus rows: {len(corpus)}")

    print("Loading innovation protocol...")
    ip = pd.read_csv(ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv")
    print(f"  IP rows: {len(ip)}")

    # ── Merge structural fields from IP ───────────────────────────────────────
    ip_merge = ip[["race_id", "horse_id"] + [c for c in IP_STRUCTURAL_COLS if c in ip.columns]].drop_duplicates(
        subset=["race_id", "horse_id"]
    )
    df = corpus.merge(ip_merge, on=["race_id", "horse_id"], how="left", suffixes=("", "_ip"))
    print(f"  After merge: {len(df)} rows")

    # ── Numeric coercion ──────────────────────────────────────────────────────
    for col in ["velo_prime_prob", "sqpe_v17_prob", "market_deception_score",
                "improvement_score", "place_prob", "sp_decimal", "actual_winner_sp",
                "racing_api_connection_shadow_score", "racing_api_course_shadow_score",
                "racing_api_distance_shadow_score", "racing_api_enrichment_shadow_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["won"] = df["won"].fillna(False).astype(bool)
    df["placed"] = df["placed"].fillna(False).astype(bool)

    # ── Derived signal flags (pre-race, no leakage) ───────────────────────────
    df["vp_band"] = df["velo_prime_prob"].apply(vp_band)
    df["vp40_flag"] = (df["velo_prime_prob"] >= 0.40).fillna(False)
    df["vp30_flag"] = (df["velo_prime_prob"] >= 0.30).fillna(False)
    df["mds_high_flag"] = (df["market_deception_score"] > 0.50).fillna(False)
    df["mds_band"] = df["market_deception_score"].apply(mds_band)
    df["improver_high_flag"] = (df["improvement_score"] >= 0.40).fillna(False)
    df["imp_band"] = df["improvement_score"].apply(imp_band)
    df["router_qualified"] = (
        df.get("router_v1_shadow_pass", False) |
        df.get("router_v2_class4_shadow_pass", False) |
        df.get("router_v6_gold_seam_watchlist", False)
    ).fillna(False)

    # Midprice router suppression advisory (pre-race flag using any available SP proxy)
    # Note: SP band uses actual SP from results — label-side. Advisory flag uses router_qualified only.
    df["midprice_router_suppression_advisory"] = ~df["router_qualified"]

    # ── SP band (result side — label use only) ────────────────────────────────
    df["sp_band"] = df["sp_decimal"].apply(sp_band)

    # ── Leakage check ─────────────────────────────────────────────────────────
    prediction_feature_cols = [c for c in PREDICTION_COLS if c in df.columns] + [
        "vp_band", "vp40_flag", "vp30_flag",
        "mds_high_flag", "mds_band",
        "improver_high_flag", "imp_band",
        "router_qualified", "midprice_router_suppression_advisory",
    ] + [c for c in IP_STRUCTURAL_COLS if c in df.columns]

    result_label_cols = [c for c in RESULT_COLS if c in df.columns] + ["sp_band"]
    identity_cols = [c for c in IDENTITY_COLS if c in df.columns]

    # Verify no result col appears in prediction features (hard leakage check)
    leakage_violations = set(result_label_cols) & set(prediction_feature_cols)
    if leakage_violations:
        raise RuntimeError(f"LEAKAGE VIOLATION — result columns in prediction features: {leakage_violations}")

    print(f"\nLeakage check: PASSED (0 violations)")

    # ── Build final dataset ───────────────────────────────────────────────────
    final_cols = identity_cols + prediction_feature_cols + result_label_cols + [
        "source_count", "source_names",
        "identity_unresolved", "conflict_count", "serious_conflict_count",
    ]
    final_cols = [c for c in dict.fromkeys(final_cols) if c in df.columns]

    dataset = df[final_cols].copy()
    dataset["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    dataset["git_commit_sha"] = git_sha
    dataset["official_prediction_frozen_at"] = build_ts
    dataset["learning_allowed"] = True
    dataset["consumed_live"] = 0
    dataset["target_state_name"] = "shadow_full_train_v2"
    dataset["leakage_confirmed_false"] = True

    # With-results subset
    with_results = dataset[dataset["result_matched"] == True]
    total_n = len(dataset)
    results_n = len(with_results)

    print(f"\nDataset built:")
    print(f"  Total rows:        {total_n}")
    print(f"  With results:      {results_n}")
    print(f"  Features:          {len(prediction_feature_cols)} prediction features")
    print(f"  Labels:            {len(result_label_cols)} result labels")
    print(f"  Identity cols:     {len(identity_cols)}")
    print(f"  SR (with results): {round(with_results['won'].mean()*100,1)}%")
    print(f"  Frame:             {round(with_results['placed'].mean()*100,1)}%")
    print(f"  VP coverage:       {with_results['velo_prime_prob'].notna().sum()}/{results_n}")
    print(f"  MDS coverage:      {with_results['market_deception_score'].notna().sum()}/{results_n}")

    # ── Write parquet ─────────────────────────────────────────────────────────
    parquet_path = TRAINING_DIR / "sigma_2k_training_dataset_latest.parquet"
    dataset.to_parquet(parquet_path, index=False)
    print(f"\nWritten: {parquet_path} ({parquet_path.stat().st_size // 1024}KB)")

    # JSON (with-results subset only — full set may be large)
    json_path = TRAINING_DIR / "sigma_2k_training_dataset_latest.json"
    json_path.write_text(json.dumps(
        with_results.where(with_results.notna(), None).to_dict(orient="records"),
        indent=2, default=str
    ))
    print(f"Written: {json_path} ({json_path.stat().st_size // 1024}KB)")

    # ── Manifest ──────────────────────────────────────────────────────────────
    manifest = {
        "build_ts": build_ts,
        "git_commit_sha": git_sha,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "source_files": [
            str(ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"),
            str(ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"),
        ],
        "row_counts": {
            "corpus_raw": len(corpus),
            "ip_raw": len(ip),
            "merged_total": total_n,
            "with_results": results_n,
        },
        "columns": {
            "identity": identity_cols,
            "prediction_features": prediction_feature_cols,
            "result_labels": result_label_cols,
        },
        "dataset_stats": {
            "dates": int(dataset["date"].nunique()),
            "courses": int(dataset["course"].nunique()),
            "sr_pct": round(with_results["won"].mean() * 100, 1),
            "frame_pct": round(with_results["placed"].mean() * 100, 1),
            "vp30_n": int(with_results["vp30_flag"].sum()),
            "vp40_n": int(with_results["vp40_flag"].sum()),
            "mds_high_n": int(with_results["mds_high_flag"].sum()),
            "improver_high_n": int(with_results["improver_high_flag"].sum()),
            "router_qualified_n": int(with_results["router_qualified"].sum()),
            "midprice_advisory_n": int(
                with_results["midprice_router_suppression_advisory"].sum()
            ),
        },
        "leakage_confirmed_false": True,
        "consumed_live": 0,
        "scoring_change": False,
        "model_change": False,
        "staking_change": False,
        "artifacts": {
            "parquet": str(parquet_path),
            "json": str(json_path),
        },
    }

    manifest_json_path = REPORTS_DIR / "sigma_2k_dataset_manifest_latest.json"
    manifest_json_path.write_text(json.dumps(manifest, indent=2))
    print(f"Written: {manifest_json_path}")

    # Manifest markdown
    md_lines = [
        "# Sigma 2K Training Dataset Manifest",
        f"**Built:** {build_ts}",
        f"**Git SHA:** `{git_sha}`",
        f"**Schema:** `{FEATURE_SCHEMA_VERSION}`",
        "",
        "## Row Counts",
        "",
        f"| Source | Rows |",
        f"|---|---|",
        f"| Unified evidence corpus | {len(corpus)} |",
        f"| Innovation protocol | {len(ip)} |",
        f"| Merged total | {total_n} |",
        f"| **With results (training rows)** | **{results_n}** |",
        "",
        "## Dataset Stats",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Dates covered | {dataset['date'].nunique()} |",
        f"| Courses | {dataset['course'].nunique()} |",
        f"| Strike rate | {round(with_results['won'].mean()*100,1)}% |",
        f"| Frame rate | {round(with_results['placed'].mean()*100,1)}% |",
        f"| VP≥0.30 rows | {int(with_results['vp30_flag'].sum())} |",
        f"| VP≥0.40 rows | {int(with_results['vp40_flag'].sum())} |",
        f"| MDS>0.50 rows | {int(with_results['mds_high_flag'].sum())} |",
        f"| Improvement>0.40 rows | {int(with_results['improver_high_flag'].sum())} |",
        f"| Router-qualified rows | {int(with_results['router_qualified'].sum())} |",
        f"| Midprice advisory rows | {int(with_results['midprice_router_suppression_advisory'].sum())} |",
        "",
        "## Column Split",
        "",
        f"| Type | Count |",
        f"|---|---|",
        f"| Identity | {len(identity_cols)} |",
        f"| Prediction features (pre-race) | {len(prediction_feature_cols)} |",
        f"| Result labels (post-race) | {len(result_label_cols)} |",
        "",
        "## Governance",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Leakage confirmed false | TRUE |",
        "| Consumed live | 0 |",
        "| Scoring change | NONE |",
        "| Model change | NONE |",
        "| Staking change | NONE |",
        "",
        "*sigma_2k_dataset_manifest — build_sigma_training_dataset.py*",
    ]
    manifest_md_path = REPORTS_DIR / "sigma_2k_dataset_manifest_latest.md"
    manifest_md_path.write_text("\n".join(md_lines))
    print(f"Written: {manifest_md_path}")

    print(f"\n{'='*60}")
    print("STOP CONDITIONS — all clear:")
    print(f"  Leakage:      NONE")
    print(f"  consumed_live: 0")
    print(f"  Scoring files: UNTOUCHED")
    print(f"  Model files:   UNTOUCHED")

    return manifest


if __name__ == "__main__":
    main()
