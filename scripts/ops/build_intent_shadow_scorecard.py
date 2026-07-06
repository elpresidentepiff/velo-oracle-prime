#!/usr/bin/env python3
"""Score a current card with the CHAMPION_INTENT_SHADOW model — shadow only.

This is a research/observation lane. It never touches live scoring, never
authorises staking, and is not eligible for promotion. It exists purely to
accumulate day-after evidence for the Champion+Intent challenger
(data/new_build/models/core_v0_or_passport_intent/) so a real promotion
decision can eventually be made on canonical results, the same way Little
Lady Rock and other doctrine promotions were evaluated.

Feature sourcing, in priority order, per champion feature:
  1. Directly present / directly derivable from the current-card passport
     feed row (dist_f, going_code, is_aw, field_size, draw_num, draw_pct,
     age_num, wgt_lbs, official_rating, is_rated, or_vs_field, and all
     pp_* passport features).
  2. Intent features (mark_compression_score .. intent_top3_last6) from
     data/new_build/current_cards/current_card_intent_features_<date>.jsonl
     (Part B output).
  3. Doctrine features not locally computable from current-card + archive
     data (release_window_score, going_fit_score, distance_fit_score,
     quiet_run_score, trainer_timing_score, jockey_switch_intent,
     setup_run_flag, cash_run_flag) are filled with the model's own stored
     training medians — the identical missing-value convention the model
     was trained and evaluated under (see prep_and_train/score_on_test in
     new_build_intent_layer.py). This is not fabrication: it is the model's
     designed fallback, applied consistently and disclosed per-row via
     doctrine_features_median_filled=True.

No stake_authorised, no promotion_eligible, no dashboard_visible can ever be
set true by this script — enforced at the row-construction call site.
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODEL_DIR = ROOT / "data" / "new_build" / "models" / "core_v0_or_passport_intent"
CURRENT_CARDS = ROOT / "data" / "new_build" / "current_cards"
RPT_DIR = ROOT / "data" / "reports"

DOCTRINE_MEDIAN_FILL_FEATURES = [
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _going_code(going_str: str) -> float:
    g = str(going_str or "").strip().upper()
    if any(x in g for x in ("STANDARD", "FAST", "TAPETA", "POLYTRACK", "FIRM")):
        return 0.0
    if "HEAVY" in g or "VERY SOFT" in g:
        return 3.0
    if "SOFT" in g or "YIELD" in g:
        return 2.0
    return 1.0


def load_intent_rows(date_safe: str) -> dict[str, dict]:
    path = CURRENT_CARDS / f"current_card_intent_features_{date_safe}.jsonl"
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[str(row["horse_rp_uid"])] = row
    return rows


def build_feature_row(passport_row: dict, intent_row: dict | None, medians: dict[str, float],
                       race_avg_or: float | None) -> tuple[dict[str, float], bool]:
    or_val = passport_row.get("official_rating")
    or_val = float(or_val) if or_val not in (None, "") else None

    feat: dict[str, float] = {
        "dist_f": float(passport_row.get("distance_furlongs") or medians["dist_f"]),
        "going_code": _going_code(passport_row.get("going")),
        "is_aw": 1.0 if "polytrack" in str(passport_row.get("surface", "")).lower()
                 or "aw" in str(passport_row.get("course", "")).lower() else 0.0,
        "field_size": float(passport_row.get("field_size") or medians["field_size"]),
        "draw_num": float(passport_row.get("draw") or medians["draw_num"]),
        "age_num": float(passport_row.get("age") or medians["age_num"]),
        "wgt_lbs": float(passport_row.get("weight_lbs") or medians["wgt_lbs"]),
        "official_rating": or_val if or_val is not None else medians["official_rating"],
        "is_rated": 1.0 if or_val else 0.0,
    }
    field_size = feat["field_size"] or 1.0
    draw = feat["draw_num"]
    feat["draw_pct"] = draw / field_size if field_size else medians["draw_pct"]
    feat["or_vs_field"] = (or_val - race_avg_or) if (or_val is not None and race_avg_or is not None) else medians["or_vs_field"]

    pp = passport_row.get("passport_live_features") or {}
    for c in ("pp_career_runs", "pp_win_rate", "pp_place_rate", "pp_days_since_last", "pp_layoff",
              "pp_avg_sp_last5", "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
              "pp_class_moved_up", "pp_class_moved_down"):
        v = pp.get(c)
        feat[c] = float(v) if v is not None else medians[c]

    doctrine_median_filled = False
    for c in DOCTRINE_MEDIAN_FILL_FEATURES:
        feat[c] = medians[c]
        doctrine_median_filled = True

    intent_cols = [
        "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
        "runs_since_win", "runs_since_place", "runs_since_mkt_support", "odds_resilience_score",
        "intent_trip_match", "intent_course_win_history", "intent_going_match",
        "intent_class_drop_vs_best", "intent_run_after_break", "intent_sp_shortening",
        "intent_wins_last10", "intent_top3_last6",
    ]
    for c in intent_cols:
        v = intent_row.get(c) if intent_row else None
        feat[c] = float(v) if v is not None else medians[c]

    return feat, doctrine_median_filled


def run(*, target_date: str, execute: bool) -> dict[str, Any]:
    date_safe = target_date.replace("-", "_")
    feed_path = CURRENT_CARDS / f"current_card_passport_feed_{date_safe}.jsonl"
    passport_rows = [json.loads(l) for l in feed_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    intent_rows = load_intent_rows(date_safe)

    with (MODEL_DIR / "model.pkl").open("rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    medians = bundle["medians"]

    by_race: dict[str, list[dict]] = {}
    for row in passport_rows:
        by_race.setdefault(row["race_id"], []).append(row)

    scorecard_rows: list[dict] = []
    for race_id, runners in by_race.items():
        ors = [float(r["official_rating"]) for r in runners if r.get("official_rating") not in (None, "")]
        race_avg_or = sum(ors) / len(ors) if ors else None

        feat_rows = []
        meta_rows = []
        for r in runners:
            intent_row = intent_rows.get(str(r["rp_uid"]))
            feat, doctrine_filled = build_feature_row(r, intent_row, medians, race_avg_or)
            feat_rows.append([feat[c] for c in feature_cols])
            meta_rows.append((r, intent_row, doctrine_filled))

        import pandas as pd
        X = pd.DataFrame(feat_rows, columns=feature_cols)
        probs = model.predict_proba(X)[:, 1]

        ranked = sorted(zip(probs, meta_rows), key=lambda t: -t[0])
        for rank, (prob, (r, intent_row, doctrine_filled)) in enumerate(ranked, start=1):
            scorecard_rows.append({
                "race_id": race_id,
                "course": r["course"],
                "off_time": r["off_time"],
                "horse": r["horse"],
                "rp_uid": r["rp_uid"],
                "trainer": r.get("trainer"),
                "champion_intent_shadow_prob": round(float(prob), 6),
                "rank_in_race": rank,
                "top_pick_shadow": rank == 1,
                "passport_found": r.get("passport_found", False),
                "intent_history_runs_used": (intent_row or {}).get("history_runs_used", 0),
                "doctrine_features_median_filled": doctrine_filled,
                "model_label": "CHAMPION_INTENT_SHADOW",
                "model_verdict_basis": "INTENT_ADDS_SIGNAL (2025 unseen holdout, 4/4 promotion gates passed)",
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "learning_class": "SHADOW_INTENT_SIGNAL",
                "stake_authorised": False,
                "promotion_eligible": False,
                "dashboard_visible": False,
            })

    total = len(scorecard_rows)
    with_history = sum(1 for r in scorecard_rows if r["intent_history_runs_used"] > 0)
    median_filled = sum(1 for r in scorecard_rows if r["doctrine_features_median_filled"])

    summary = {
        "generated_at": _utc_now(),
        "target_date": target_date,
        "model_label": "CHAMPION_INTENT_SHADOW",
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "learning_class": "SHADOW_INTENT_SIGNAL",
        "stake_authorised": False,
        "promotion_eligible": False,
        "dashboard_visible": False,
        "races_scored": len(by_race),
        "runners_scored": total,
        "runners_with_intent_history": with_history,
        "runners_doctrine_median_filled": median_filled,
        "doctrine_median_fill_note": "release_window_score/going_fit_score/distance_fit_score/quiet_run_score/"
                                     "trainer_timing_score/jockey_switch_intent/setup_run_flag/cash_run_flag are "
                                     "not locally computable pre-race from current-card + archive data; every row "
                                     "uses the model's own stored training medians for these, its designed "
                                     "missing-value convention, not an invented signal.",
        "next_step": "Accumulate day-after canonical results against this scorecard across multiple race days "
                     "before any promotion review, same protocol as Little Lady Rock.",
    }

    if execute:
        RPT_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RPT_DIR / "july06_intent_shadow_scorecard.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(scorecard_rows[0].keys()))
            w.writeheader()
            w.writerows(scorecard_rows)

        md_path = RPT_DIR / "july06_intent_shadow_scorecard_summary.md"
        md_lines = [
            "# July 06 Intent Shadow Scorecard — CHAMPION_INTENT_SHADOW",
            f"Generated: {summary['generated_at']}",
            "",
            "**stake_authorised: false | promotion_eligible: false | dashboard_visible: false**",
            "",
            f"- Races scored: {summary['races_scored']}",
            f"- Runners scored: {summary['runners_scored']}",
            f"- Runners with local intent run-history: {summary['runners_with_intent_history']}",
            f"- Runners using median-filled doctrine features: {summary['runners_doctrine_median_filled']}",
            "",
            "## Top pick per race (shadow only, no stake)",
            "| Race | Course | Off | Top Pick | Prob | Intent history runs |",
            "|---|---|---|---|---|---|",
        ]
        for r in scorecard_rows:
            if r["top_pick_shadow"]:
                md_lines.append(
                    f"| {r['race_id']} | {r['course']} | {r['off_time']} | {r['horse']} | "
                    f"{r['champion_intent_shadow_prob']:.3f} | {r['intent_history_runs_used']} |"
                )
        md_lines += ["", f"Next step: {summary['next_step']}"]
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        audit_path = RPT_DIR / "july06_intent_shadow_audit.json"
        audit_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["csv_path"] = str(csv_path.relative_to(ROOT))
        summary["md_path"] = str(md_path.relative_to(ROOT))
        summary["audit_path"] = str(audit_path.relative_to(ROOT))

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Score current card with CHAMPION_INTENT_SHADOW (shadow only).")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    summary = run(target_date=args.date, execute=args.execute)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
