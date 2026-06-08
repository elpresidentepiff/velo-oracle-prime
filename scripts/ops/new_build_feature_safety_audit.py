#!/usr/bin/env python3
"""
new_build_feature_safety_audit.py
Classify every column in raceform_v17_features.parquet as safe/unsafe for Core V0.
Shadow only — no scoring.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

OUT_DIR = ROOT / "data" / "new_build" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLASSIFICATIONS = {
    # ── IDENTITY ─────────────────────────────────────────────────────────────
    "race_id":           ("IDENTITY", "race key"),
    "date":              ("IDENTITY", "race date"),
    "date_parsed":       ("IDENTITY", "parsed date"),
    "course":            ("IDENTITY", "course name"),
    "horse":             ("IDENTITY", "horse name"),
    "jockey":            ("IDENTITY", "jockey name"),
    "trainer":           ("IDENTITY", "trainer name"),
    "num":               ("IDENTITY", "cloth number"),
    "off":               ("IDENTITY", "race off time"),
    "race_name":         ("IDENTITY", "race name"),
    "pattern":           ("IDENTITY", "race pattern grade"),
    "rating_band":       ("IDENTITY", "rating band string"),
    "age_band":          ("IDENTITY", "age restriction string"),
    "sex_rest":          ("IDENTITY", "sex restriction string"),
    "owner":             ("IDENTITY", "owner name"),
    "sire":              ("IDENTITY", "sire name"),
    "dam":               ("IDENTITY", "dam name"),
    "damsire":           ("IDENTITY", "damsire name"),

    # ── TARGET ───────────────────────────────────────────────────────────────
    "pos":               ("TARGET", "finishing position — outcome label only"),
    "target":            ("TARGET", "pre-derived target flag"),
    "ovr_btn":           ("TARGET", "total lengths beaten — post-race"),
    "btn":               ("TARGET", "lengths beaten by winner — post-race"),

    # ── DROP — leakage / post-race ────────────────────────────────────────────
    "comment":           ("DROP_LEAKAGE", "post-race comment text — never available pre-race"),
    "time":              ("DROP_LEAKAGE", "race time in seconds — post-race result"),

    # ── ARCHIVE_ONLY — RPR boundary + prize ──────────────────────────────────
    "rpr":               ("ARCHIVE_ONLY", "RPR: archive-only boundary, never a model feature"),
    "rpr_num":           ("ARCHIVE_ONLY", "RPR numeric: archive-only boundary"),
    "rpr_vs_field":      ("ARCHIVE_ONLY", "RPR vs field: archive-only boundary"),
    "prize":             ("ARCHIVE_ONLY", "race prize money — race context, not horse feature"),

    # ── TIMESTAMP_UNKNOWN — TS may be post-race ──────────────────────────────
    "ts":                ("TIMESTAMP_UNKNOWN", "TS rating: requires race time to compute — post-race leakage risk"),
    "ts_num":            ("TIMESTAMP_UNKNOWN", "TS numeric: requires race time — post-race leakage risk"),

    # ── MARKET_ONLY — SP-derived, not for morning model ──────────────────────
    "sp":                ("MARKET_ONLY", "final SP — not available before race closes"),
    "sp_dec":            ("MARKET_ONLY", "SP decimal — final odds"),
    "log_sp":            ("MARKET_ONLY", "log SP — SP derived"),
    "implied_prob":      ("MARKET_ONLY", "market implied probability — SP derived"),
    "sp_rank":           ("MARKET_ONLY", "SP rank within race — requires all SPs"),
    "is_fav":            ("MARKET_ONLY", "favourite flag — market derived"),
    "runs_since_mkt_support": ("MARKET_ONLY", "runs since last market support — requires SP history"),
    "odds_resilience_score":  ("MARKET_ONLY", "odds resilience — SP movement derived"),
    "odds_contraction_score": ("MARKET_ONLY", "odds contraction — SP movement derived"),
    "decoy_support_flag":     ("MARKET_ONLY", "decoy support — SP pattern derived"),

    # ── KEEP_CORE_V0 — safe pre-race features ────────────────────────────────
    "type":              ("KEEP_CORE_V0", "race type: Flat/Hurdle/Chase/NHF"),
    "class_raw":         ("KEEP_CORE_V0", "raw class string"),
    "class_num":         ("KEEP_CORE_V0", "class numeric"),
    "dist":              ("KEEP_CORE_V0", "distance string"),
    "dist_f":            ("KEEP_CORE_V0", "distance in furlongs"),
    "going":             ("KEEP_CORE_V0", "going string"),
    "going_code":        ("KEEP_CORE_V0", "going numeric code"),
    "is_aw":             ("KEEP_CORE_V0", "all-weather flag"),
    "ran":               ("KEEP_CORE_V0", "field size from racecard"),
    "field_size":        ("KEEP_CORE_V0", "field size derived"),
    "draw":              ("KEEP_CORE_V0", "draw position"),
    "draw_num":          ("KEEP_CORE_V0", "draw numeric"),
    "draw_pct":          ("KEEP_CORE_V0", "draw percentile in race"),
    "age":               ("KEEP_CORE_V0", "age string"),
    "age_num":           ("KEEP_CORE_V0", "age numeric"),
    "sex":               ("KEEP_CORE_V0", "sex code"),
    "wgt":               ("KEEP_CORE_V0", "weight string"),
    "wgt_lbs":           ("KEEP_CORE_V0", "weight in lbs"),
    "hg":                ("KEEP_CORE_V0", "headgear code"),
    "or_rating":         ("KEEP_CORE_V0", "Official Rating — pre-race handicap mark"),
    "or_num":            ("KEEP_CORE_V0", "OR numeric — pre-race handicap mark"),
    "or_vs_field":       ("KEEP_CORE_V0", "OR vs field mean — pre-race relative mark"),
    "curr_or_minus_last_win_or": ("KEEP_CORE_V0", "OR drop since last win — handicap plot signal"),
    "curr_or_minus_best_or":     ("KEEP_CORE_V0", "OR vs career best — mark compression"),
    "mark_compression_score":    ("KEEP_CORE_V0", "mark compression score"),
    "runs_since_win":    ("KEEP_CORE_V0", "runs since last win"),
    "runs_since_place":  ("KEEP_CORE_V0", "runs since last place"),
    "release_window_score":  ("KEEP_CORE_V0", "release window / handicap drop signal"),
    "course_fit_score":      ("KEEP_CORE_V0", "course specialist fit score"),
    "going_fit_score":       ("KEEP_CORE_V0", "going preference fit score"),
    "distance_fit_score":    ("KEEP_CORE_V0", "distance fit score"),
    "quiet_run_score":       ("KEEP_CORE_V0", "quiet/prep run indicator"),
    "trainer_timing_score":  ("KEEP_CORE_V0", "trainer intent timing signal"),
    "jockey_switch_intent":  ("KEEP_CORE_V0", "jockey change intent signal"),
    "setup_run_flag":        ("KEEP_CORE_V0", "setup run flag"),
    "cash_run_flag":         ("KEEP_CORE_V0", "cash run flag"),
}


def run():
    print("Loading raceform_v17_features.parquet ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
    all_cols = list(df.columns)

    records = []
    unknown = []
    for col in all_cols:
        if col in CLASSIFICATIONS:
            cls, reason = CLASSIFICATIONS[col]
        else:
            cls, reason = "UNCLASSIFIED", "not in classification map — review needed"
            unknown.append(col)
        records.append({"column": col, "classification": cls, "reason": reason})

    # Also audit raceform_clean for any extra columns
    df_clean = pd.read_parquet(ROOT / "data" / "raceform_clean.parquet")
    for col in df_clean.columns:
        if col not in all_cols and col not in CLASSIFICATIONS:
            unknown.append(col)
            records.append({"column": col, "classification": "UNCLASSIFIED", "reason": "in raceform_clean only, not in v17"})
        elif col not in all_cols:
            cls, reason = CLASSIFICATIONS.get(col, ("UNCLASSIFIED", ""))
            records.append({"column": col, "classification": cls, "reason": f"raceform_clean only: {reason}"})

    # Counts
    from collections import Counter
    counts = Counter(r["classification"] for r in records)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "total_columns_audited": len(records),
        "summary": dict(counts),
        "unclassified": unknown,
        "columns": records,
    }

    (OUT_DIR / "historical_feature_safety_audit_latest.json").write_text(
        json.dumps(output, indent=2)
    )

    # MD report
    lines = [
        "# Historical Feature Safety Audit",
        f"Generated: {output['generated_at']}",
        "",
        "## Summary",
        "",
        "| Classification | Count |",
        "|---|---|",
    ]
    for cls, n in sorted(counts.items()):
        lines.append(f"| {cls} | {n} |")

    lines += ["", "## Column Classifications", ""]
    for cls in ["KEEP_CORE_V0", "MARKET_ONLY", "ARCHIVE_ONLY", "TIMESTAMP_UNKNOWN", "DROP_LEAKAGE", "TARGET", "IDENTITY", "UNCLASSIFIED"]:
        cols_in_cls = [r for r in records if r["classification"] == cls]
        if not cols_in_cls:
            continue
        lines.append(f"### {cls} ({len(cols_in_cls)})")
        lines.append("")
        lines.append("| Column | Reason |")
        lines.append("|---|---|")
        for r in cols_in_cls:
            lines.append(f"| `{r['column']}` | {r['reason']} |")
        lines.append("")

    if unknown:
        lines += ["", f"## ⚠ Unclassified columns ({len(unknown)})", ""]
        for u in unknown:
            lines.append(f"- `{u}`")

    (OUT_DIR / "historical_feature_safety_audit_latest.md").write_text("\n".join(lines))

    print(f"\nAudit complete. {len(records)} columns classified.")
    for cls, n in sorted(counts.items()):
        print(f"  {cls:<25} {n}")
    if unknown:
        print(f"\n  ⚠ UNCLASSIFIED: {unknown}")

    return output


if __name__ == "__main__":
    run()
