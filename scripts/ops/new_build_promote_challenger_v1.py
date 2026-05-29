"""
new_build_promote_challenger_v1.py
Promotes Challenger V1 (Core+Passport+Intent, 45 features) to champion.

Writes updated champion_registry.json. Does NOT touch live VELO, shadow,
Telegram, staking, or live tables. Paper scorer only.
"""
import json
import pickle
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "new_build" / "models" / "champion" / "champion_registry.json"
CHAMPION_MODEL_PKL = ROOT / "data" / "new_build" / "models" / "champion" / "champion_model.pkl"
CHALLENGER_V1_PKL = ROOT / "data" / "new_build" / "models" / "core_v0_or_passport_intent" / "model.pkl"

CORE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag", "official_rating", "is_rated",
]
PASSPORT_FEATURES = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]
INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score", "intent_trip_match", "intent_course_win_history",
    "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]


def promote(execute: bool = False) -> None:
    if not CHALLENGER_V1_PKL.exists():
        raise FileNotFoundError(f"Challenger V1 bundle not found: {CHALLENGER_V1_PKL}")

    with CHALLENGER_V1_PKL.open("rb") as f:
        bundle = pickle.load(f)

    assert isinstance(bundle, dict), "Bundle must be a dict"
    assert "model" in bundle and "feature_cols" in bundle and "medians" in bundle, \
        "Bundle missing model/feature_cols/medians"
    assert len(bundle["feature_cols"]) == 45, f"Expected 45 features, got {len(bundle['feature_cols'])}"

    print(f"Challenger V1 bundle verified: {len(bundle['feature_cols'])} features, {len(bundle['medians'])} medians")

    all_45 = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
    assert set(bundle["feature_cols"]) == set(all_45), \
        f"Feature mismatch: {set(bundle['feature_cols']) ^ set(all_45)}"
    print("Feature set verified: Core(19) + Passport(11) + Intent(15) = 45")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    existing_registry = {}
    if REGISTRY_PATH.exists():
        existing_registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    registry = {
        "generated_at": now,
        "champion_name": "core_v0_or_passport_intent",
        "champion_version": "Challenger_V1",
        "promoted_at": now,
        "promoted_from": "challenger",
        "dethroned_champion": existing_registry.get("champion_version", "Core_V0_OR_Passport_V1"),
        "promotion_reason": "CHALLENGER_V1_PROMOTED — held-out 2025 test: AUC +0.0047 / SR +0.0086 / Frame +0.0094 over champion",
        "classification": [
            "INTENT_SIGNAL_CONFIRMED",
            "CHALLENGER_V1_BEATS_CHAMPION_ON_UNSEEN_2025",
            "PROMOTE_TO_NEW_BUILD_CHAMPION",
            "CORE_PASSPORT_INTENT_45_FEATURES",
        ],
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "rpr_violation": False,
        "sp_violation": False,
        "model_pkl": "data/new_build/models/core_v0_or_passport_intent/model.pkl",
        "features_frozen": all_45,
        "feature_groups": {
            "core_v0": CORE_FEATURES,
            "or_layer": ["official_rating", "is_rated"],
            "passport_layer": PASSPORT_FEATURES,
            "intent_layer": INTENT_FEATURES,
        },
        "metrics_2025_unseen": {
            "auc": 0.6969,
            "brier": 0.0855,
            "sr": 0.2502,
            "frame": 0.5498,
            "races": 5775,
            "runners": 57221,
            "note": "held-out 2025 test set",
        },
        "prior_champion_metrics_2025_unseen": {
            "auc": 0.6922,
            "brier": 0.0862,
            "sr": 0.2416,
            "frame": 0.5404,
        },
        "deltas_2025_unseen": {
            "auc": round(0.6969 - 0.6922, 4),
            "brier": round(0.0855 - 0.0862, 4),
            "sr": round(0.2502 - 0.2416, 4),
            "frame": round(0.5498 - 0.5404, 4),
        },
        "intent_current_card_note": (
            "Intent features (15) are filled from training medians for current-card rows. "
            "Model will score on Core+Passport signals primarily. Intent median-fill is expected behavior."
        ),
        "paper_only": True,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
    }

    if not execute:
        print("DRY RUN — registry not written. Pass execute=True to apply.")
        print(f"Would write: {REGISTRY_PATH}")
        print(f"champion_version: {registry['champion_version']}")
        print(f"model_pkl: {registry['model_pkl']}")
        return

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Registry written: {REGISTRY_PATH}")

    # Also copy to champion_model.pkl for any consumers that use that path directly
    shutil.copy2(CHALLENGER_V1_PKL, CHAMPION_MODEL_PKL)
    print(f"champion_model.pkl updated: {CHAMPION_MODEL_PKL}")
    print(f"\nChallenger V1 is now champion. Model: {registry['model_pkl']}")
    print(f"Deltas vs prior champion: AUC +{registry['deltas_2025_unseen']['auc']} | SR +{registry['deltas_2025_unseen']['sr']} | Frame +{registry['deltas_2025_unseen']['frame']}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    promote(execute=args.execute)
