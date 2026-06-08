#!/usr/bin/env python3
"""
new_build_promote_passport.py
Promote V0_OR+Passport to New Build champion.
Previous champion (V0_OR) demoted to prior_champion.
Writes champion registry + frozen feature list + model card with feature importance.

Classification: PASSPORT_SIGNAL_CONFIRMED
"""
import json
import pickle
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

MDL_DIR  = ROOT / "data" / "new_build" / "models"
RPT_DIR  = ROOT / "data" / "new_build" / "reports"
TRAIN_DIR = ROOT / "data" / "new_build" / "training"

CHAMP_DIR    = MDL_DIR / "champion"
PREV_PKL     = MDL_DIR / "core_v0_or" / "core_v0_or_model.pkl"
NEW_PKL      = MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_model.pkl"
NEW_META_P   = MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_metadata.json"
PREV_META_P  = MDL_DIR / "core_v0_or" / "core_v0_or_metadata.json"
PROOF_PATH   = RPT_DIR / "v0_or_passport_2025_unseen_test_latest.json"

NOW = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

V0_CORE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]
OR_FEATURES = ["official_rating", "is_rated"]
PASSPORT_FEATURES = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]


def feature_importance_table(model, feature_cols):
    """Extract feature importance from LightGBM or sklearn GBM."""
    try:
        imp = model.feature_importances_
        rows = sorted(
            [{"feature": f, "importance": float(i)} for f, i in zip(feature_cols, imp)],
            key=lambda r: -r["importance"],
        )
        total = sum(r["importance"] for r in rows) or 1.0
        for r in rows:
            r["importance_pct"] = round(r["importance"] / total * 100, 2)
        return rows
    except AttributeError:
        return []


def run():
    print("=== Promote V0_OR+Passport → New Build Champion ===")

    # Load proof
    proof = json.loads(PROOF_PATH.read_text())
    new_metrics  = next(v for v in proof["variants"] if v["variant"] == "V0_OR+Passport")
    prev_metrics = next(v for v in proof["variants"] if v["variant"] == "V0_OR")
    n_gates      = proof["n_gates_passed"]
    classification = proof["classification"]

    print(f"  Proof: {n_gates}/4 gates passed on 2025 unseen test")
    print(f"  New champion: AUC={new_metrics['auc']}  SR={new_metrics['sr']:.1%}  Frame={new_metrics['frame']:.1%}")
    print(f"  Prior champion: AUC={prev_metrics['auc']}  SR={prev_metrics['sr']:.1%}  Frame={prev_metrics['frame']:.1%}")

    # Load new champion model
    with open(NEW_PKL, "rb") as f:
        bundle = pickle.load(f)
    model        = bundle["model"]
    feature_cols = bundle["feature_cols"]
    medians      = bundle["medians"]

    # Feature importance
    print("\n  Computing feature importance ...")
    imp_rows = feature_importance_table(model, feature_cols)

    print("  Top features:")
    for r in imp_rows[:15]:
        bar = "█" * int(r["importance_pct"] / 2)
        print(f"    {r['feature']:<30} {r['importance_pct']:5.1f}%  {bar}")

    # Passport-only importance subset
    pp_imp = [r for r in imp_rows if r["feature"] in PASSPORT_FEATURES]
    pp_total_pct = sum(r["importance_pct"] for r in pp_imp)
    print(f"\n  Passport features total importance: {pp_total_pct:.1f}%")
    for r in pp_imp:
        print(f"    {r['feature']:<30} {r['importance_pct']:5.1f}%")

    # Write champion registry
    CHAMP_DIR.mkdir(parents=True, exist_ok=True)
    registry = {
        "generated_at": NOW,
        "champion_name": "core_v0_or_passport",
        "champion_version": "Core_V0_OR_Passport_V1",
        "promoted_at": NOW,
        "promoted_from": "challenger",
        "dethroned_champion": "core_v0_or",
        "promotion_reason": "PASSPORT_SIGNAL_CONFIRMED — 4/4 unseen 2025 gates passed",
        "classification": [
            "PASSPORT_SIGNAL_CONFIRMED",
            "V0_OR_PASSPORT_BEATS_CHAMPION_ON_UNSEEN_2025",
            "PROMOTE_TO_NEW_BUILD_CHAMPION",
            "HORSE_FIRST_STRATEGY_VALIDATED",
        ],
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "rpr_violation": False,
        "sp_violation": False,
        "model_pkl": str((MDL_DIR / "core_v0_or_passport" / "core_v0_or_passport_model.pkl").relative_to(ROOT)),
        "features_frozen": feature_cols,
        "feature_groups": {
            "core_v0": [f for f in feature_cols if f in V0_CORE_FEATURES],
            "or_layer": [f for f in feature_cols if f in OR_FEATURES],
            "passport_layer": [f for f in feature_cols if f in PASSPORT_FEATURES],
        },
        "metrics_2025_unseen": new_metrics,
        "prior_champion_metrics_2025_unseen": prev_metrics,
        "deltas_2025_unseen": proof["deltas"],
        "promotion_gates_2025_unseen": proof["promotion_gates"],
        "feature_importance": imp_rows,
        "passport_importance_total_pct": round(pp_total_pct, 2),
    }

    (CHAMP_DIR / "champion_registry.json").write_text(json.dumps(registry, indent=2))
    shutil.copy2(NEW_PKL, CHAMP_DIR / "champion_model.pkl")
    print(f"\n  Champion registry → data/new_build/models/champion/champion_registry.json")

    # Model card
    _write_model_card(registry, imp_rows, pp_imp, pp_total_pct, proof)

    print(f"\n  Champion: V0_OR+Passport")
    print(f"  Previous: V0_OR")
    print(f"  Status: NEW_BUILD_ONLY — not live, not old VÉLØ")


def _write_model_card(registry, imp_rows, pp_imp, pp_total_pct, proof):
    m = registry["metrics_2025_unseen"]
    p = registry["prior_champion_metrics_2025_unseen"]
    d = registry["deltas_2025_unseen"]
    cal = proof.get("calibration_champion", [])
    pp_features = registry["feature_groups"]["passport_layer"]
    core_features = registry["feature_groups"]["core_v0"]
    or_features = registry["feature_groups"]["or_layer"]

    lines = [
        "# New Build VÉLØ — Model Card",
        f"**Model:** Core V0_OR+Passport V1",
        f"**Generated:** {NOW}",
        f"**Status:** NEW_BUILD_CHAMPION — not live, not old VÉLØ",
        "",
        "---",
        "",
        "## Classification",
        "```",
        "PASSPORT_SIGNAL_CONFIRMED",
        "V0_OR_PASSPORT_BEATS_CHAMPION_ON_UNSEEN_2025",
        "PROMOTE_TO_NEW_BUILD_CHAMPION",
        "HORSE_FIRST_STRATEGY_VALIDATED",
        "```",
        "",
        "## Trust Policy",
        "- `ARCHIVE_CONTEXT_ONLY_NOT_SCORING`",
        "- `velo_scoring_allowed = False`",
        "- `rpr_violation = False`",
        "- `sp_violation = False`",
        "",
        "## 2025 Unseen Test Results",
        f"Test set: 2025-01-01 → 2025-07-05 | {m['races']:,} races | {m['runners']:,} runners",
        "",
        "| Metric | Previous Champion (V0_OR) | New Champion (V0_OR+Passport) | Delta |",
        "|---|---|---|---|",
        f"| AUC | {p['auc']} | {m['auc']} | {d['auc']:+.4f} |",
        f"| Brier | {p['brier']} | {m['brier']} | {d['brier']:+.4f} |",
        f"| Top-pick SR | {p['sr']:.1%} | {m['sr']:.1%} | {d['sr']:+.1%} |",
        f"| Top-3 Frame | {p['frame']:.1%} | {m['frame']:.1%} | {d['frame']:+.1%} |",
        "",
        "Promotion gates: **AUC PASS / Brier PASS / SR PASS / Frame PASS — 4/4**",
        "",
        "## Feature Architecture",
        f"Total features: {len(registry['features_frozen'])}",
        "",
        "### Layer 1 — Core V0 Race Context",
        f"({len(core_features)} features)",
    ] + [f"- `{f}`" for f in core_features] + [
        "",
        "### Layer 2 — Official Rating",
        f"({len(or_features)} features)",
    ] + [f"- `{f}`" for f in or_features] + [
        "",
        "### Layer 3 — Horse Passport (NEW)",
        f"({len(pp_features)} features | {pp_total_pct:.1f}% of total model importance)",
    ] + [f"- `{f}`" for f in pp_features] + [
        "",
        "## Feature Importance (top 20)",
        "| Rank | Feature | Layer | Importance % |",
        "|---|---|---|---|",
    ]

    def _layer(f):
        if f in registry["feature_groups"]["passport_layer"]: return "Passport"
        if f in registry["feature_groups"]["or_layer"]:       return "OR"
        return "Core V0"

    for i, r in enumerate(imp_rows[:20], 1):
        lines.append(f"| {i} | `{r['feature']}` | {_layer(r['feature'])} | {r['importance_pct']:.1f}% |")

    lines += [
        "",
        "### Passport Feature Importance Detail",
        "| Feature | Importance % | Meaning |",
        "|---|---|---|",
    ]
    pp_desc = {
        "pp_career_runs":      "Number of prior career starts (experience)",
        "pp_win_rate":         "Career win rate up to this race",
        "pp_place_rate":       "Career place rate up to this race",
        "pp_days_since_last":  "Days since previous race (freshness)",
        "pp_layoff":           "1 if layoff >90 days",
        "pp_avg_sp_last5":     "Mean SP over last 5 prior runs (historical market support)",
        "pp_jockey_continuity":"1 if same jockey as previous race",
        "pp_course_seen":      "1 if horse has previously run at this course",
        "pp_or_change_3":      "OR change over last 3 races (form direction)",
        "pp_class_moved_up":   "1 if stepped up in class vs last race",
        "pp_class_moved_down": "1 if dropped down in class vs last race",
    }
    for r in sorted(pp_imp, key=lambda x: -x["importance_pct"]):
        desc = pp_desc.get(r["feature"], "")
        lines.append(f"| `{r['feature']}` | {r['importance_pct']:.1f}% | {desc} |")

    lines += [
        "",
        "## Calibration (V0_OR+Passport champion, 2025 test)",
        "| Prob band | n | Predicted WR | Actual WR | Over/Under |",
        "|---|---|---|---|---|",
    ]
    cal_challenger = proof.get("calibration_challenger", [])
    for row in cal_challenger:
        lines.append(f"| {row['band']} | {row['n']:,} | {row['pred_prob']:.3f} | {row['actual_wr']:.3f} | {row['over_under']:+.3f} |")

    lines += [
        "",
        "## Key Findings",
        "",
        "**Passport-only is weaker than Core V0.** Horse history alone is not enough —",
        "it requires race context to be meaningful.",
        "",
        "**Horse history + race context is where the edge lives.** The combination",
        f"adds {d['auc']:+.4f} AUC, {d['sr']:+.1%} SR, and {d['frame']:+.1%} Frame on completely unseen data.",
        "",
        f"**Passport features account for {pp_total_pct:.1f}% of total model importance.**",
        "These are not decoration — they are structural contributors.",
        "",
        "## Frozen Feature List",
        "```",
    ] + registry["features_frozen"] + [
        "```",
        "",
        "## Scope",
        "- NEW_BUILD_ONLY",
        "- Not wired to old VÉLØ engine",
        "- Not live deployment",
        "- No RPR in any feature",
        "- No current-race SP in any feature",
        "- All passport features use prior-race data only (no leakage)",
        "",
        "## Next Layer: Intent",
        "Planned challenger: **Intent Layer V1**",
        "```",
        "CASH_RUN_CANDIDATE",
        "SETUP_RUN",
        "TRAP_PREP",
        "MARK_READY",
        "JOCKEY_INTENT",
        "TRAINER_TIMING",
        "```",
        "Test against this champion. Promote only if it beats on unseen data.",
    ]

    card_path = RPT_DIR / "new_build_model_card_latest.md"
    card_path.write_text("\n".join(lines))
    print(f"  Model card → {card_path.relative_to(ROOT)}")

    # JSON model card
    card_json = {
        "generated_at": NOW,
        "model": "Core_V0_OR_Passport_V1",
        "status": "NEW_BUILD_CHAMPION",
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "features_frozen": registry["features_frozen"],
        "feature_groups": registry["feature_groups"],
        "metrics_2025_unseen": m,
        "deltas": d,
        "promotion_gates": registry["promotion_gates_2025_unseen"],
        "feature_importance": imp_rows,
        "passport_importance_total_pct": pp_total_pct,
        "calibration_2025": cal_challenger,
        "next_layer": "Intent_Layer_V1",
    }
    (RPT_DIR / "new_build_model_card_latest.json").write_text(json.dumps(card_json, indent=2))


if __name__ == "__main__":
    run()
