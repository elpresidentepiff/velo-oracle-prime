"""
new_build_two_lane_score.py
Race-day two-lane paper scorer for a specific target date.

Lane A: Core V0_OR + Passport (30 features) — operational read
Lane B: Full Challenger V1 (45 features, Core+Passport+Intent) — paper read

Operational lane selection:
  - Lane B selected only if Intent current-card coverage >= INTENT_COVERAGE_GATE (80%)
  - Otherwise Lane A is the operational read; Lane B is PAPER_ONLY_NO_INTENT

No Old VELO. No Shadow. No Telegram. No market lane. No RPR. No SP.

Usage:
  python scripts/ops/new_build_two_lane_score.py --date 2026-05-30 [--execute]
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
NEW_BUILD_ROOT = ROOT / "data" / "new_build"
REPORT_DIR = NEW_BUILD_ROOT / "reports"
FEED_JSONL = NEW_BUILD_ROOT / "current_cards" / "current_card_passport_feed_latest.jsonl"
INTENT_FEATURE_PATH = NEW_BUILD_ROOT / "training" / "intent_features.parquet"

LANE_A_PKL = ROOT / "data" / "new_build" / "models" / "core_v0_or_passport" / "core_v0_or_passport_model.pkl"
LANE_B_PKL = ROOT / "data" / "new_build" / "models" / "core_v0_or_passport_intent" / "model.pkl"
LANE_C_PKL = ROOT / "data" / "new_build" / "models" / "soft_label_challenger" / "champion_model.pkl"
REGISTRY_PATH = NEW_BUILD_ROOT / "models" / "champion" / "champion_registry.json"

INTENT_COVERAGE_GATE = 80.0  # percent; below this → Lane A is operational
BANNED_SUBSTRINGS = ("rpr", "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav")

INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score", "intent_trip_match", "intent_course_win_history",
    "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _to_float(v, default=None):
    try:
        return default if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return default


def _going_code(value, default=1.0) -> float:
    raw = str(value or "").strip().lower()
    # Scale matches raceform_v17 training data (-1 to 2)
    mapping = {"heavy": -1.0, "soft": -0.5, "good to soft": 0.0, "good": 1.0,
               "good to firm": 1.5, "firm": 2.0, "standard": 1.0,
               "standard to slow": 0.0, "slow": -0.5}
    for label, code in mapping.items():
        if label in raw:
            return code
    return default


def _feature_map(row: dict, medians: dict) -> dict:
    pp = row.get("passport_summary") or {}
    fs = _to_float(row.get("field_size"))
    draw = _to_float(row.get("draw"))
    ofr = _to_float(row.get("official_rating"))
    layoff_raw = str(pp.get("layoff_flag") or "").upper()
    layoff = 0.0 if layoff_raw == "ACTIVE" else (1.0 if layoff_raw else None)
    return {
        "dist_f": _to_float(row.get("distance_furlongs")),
        "going_code": _going_code(row.get("going") or row.get("going_code_raw"),
                                   medians.get("going_code", 1.0)),
        "is_aw": 1.0 if str(row.get("surface") or "").lower() in {"aw", "all-weather", "all weather"} else 0.0,
        "field_size": fs,
        "draw_num": draw,
        "draw_pct": draw / fs if fs and draw is not None else None,
        "age_num": _to_float(row.get("age")),
        "wgt_lbs": _to_float(row.get("weight_lbs")),
        "or_vs_field": 0.0,
        "release_window_score": None,
        "going_fit_score": None,
        "distance_fit_score": None,
        "quiet_run_score": None,
        "trainer_timing_score": None,
        "jockey_switch_intent": None,
        "setup_run_flag": None,
        "cash_run_flag": None,
        "official_rating": ofr,
        "is_rated": 1.0 if ofr is not None else 0.0,
        "pp_career_runs": _to_float(pp.get("career_runs")),
        "pp_win_rate": _to_float(pp.get("win_rate")),
        "pp_place_rate": _to_float(pp.get("place_rate")),
        "pp_days_since_last": _to_float(pp.get("days_since_last_run")),
        "pp_layoff": layoff,
        "pp_avg_sp_last5": _to_float(pp.get("avg_sp_last5")),
        "pp_jockey_continuity": 1.0 if pp.get("jockey_continuity") else 0.0,
        "pp_course_seen": medians.get("pp_course_seen", 0.0),
        "pp_or_change_3": _to_float(pp.get("or_change_last3")),
        "pp_class_moved_up": 1.0 if str(pp.get("class_movement") or "").upper() == "UP" else 0.0,
        "pp_class_moved_down": 1.0 if str(pp.get("class_movement") or "").upper() == "DOWN" else 0.0,
        "pp_best_ts_last6": _to_float(pp.get("pp_best_ts_last6")),
        "pp_ts_trajectory": _to_float(pp.get("pp_ts_trajectory")),
    }


def _build_matrix(rows: list[dict], feature_cols: list[str], medians: dict) -> tuple[pd.DataFrame, Counter]:
    records = []
    missing_counter: Counter = Counter()
    for row in rows:
        actual = _feature_map(row, medians)
        record = {}
        for col in feature_cols:
            val = actual.get(col)
            if val is None:
                missing_counter[col] += 1
                val = medians.get(col, 0.0)
            record[col] = float(val)
        records.append(record)
    return pd.DataFrame(records, columns=feature_cols), missing_counter


def _leakage_check(feature_cols: list[str], label: str) -> list[str]:
    return [f for f in feature_cols if any(b in f.lower() for b in BANNED_SUBSTRINGS)]


def _score_lane(bundle: dict, rows: list[dict], label: str) -> tuple[list[float], Counter, list[str]]:
    model = bundle["model"]
    feature_cols = [str(c) for c in bundle["feature_cols"]]
    medians = {str(k): float(v) for k, v in dict(bundle["medians"]).items()}
    violations = _leakage_check(feature_cols, label)
    if violations:
        raise AssertionError(f"LEAKAGE ABORT {label}: {violations}")
    X, missing = _build_matrix(rows, feature_cols, medians)
    if not len(X):
        probs = []
    elif bundle.get("model_type") == "lgb_native_booster":
        raw = model.predict(X.values)
        probs = (1.0 / (1.0 + np.exp(-raw))).tolist()
    else:
        probs = model.predict_proba(X)[:, 1].tolist()
    return probs, missing, violations


def _rank_within_race(rows: list[dict], probs: list[float], prob_key: str, rank_key: str) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[str(row.get("race_id"))].append(i)
    for indices in grouped.values():
        sorted_indices = sorted(indices, key=lambda i: probs[i], reverse=True)
        for rank, idx in enumerate(sorted_indices, start=1):
            rows[idx][rank_key] = rank
    for i, row in enumerate(rows):
        row[prob_key] = round(probs[i], 6)


def _intent_coverage(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.get("intent_features_available")) / len(rows) * 100


def _date_status(target_date: str) -> dict:
    inj_path = PARSED_ROOT / target_date / "racecard_injection.json"
    raw_dir = ROOT / "data" / "racing_post_account_raw" / target_date
    if not inj_path.exists():
        return {"date": target_date, "status": "NOT_CAPTURED", "races": 0, "runners": 0}
    inj = _load_json(inj_path, {})
    races = inj.get("races_count", 0)
    runners = inj.get("runners_count", 0)
    if races == 0:
        return {
            "date": target_date, "status": "CAPTURED_BUT_EMPTY",
            "races": 0, "runners": 0,
            "skipped": len(inj.get("skipped", [])),
            "note": "Runners not declared at capture time. Recapture required.",
        }
    return {"date": target_date, "status": "READY", "races": races, "runners": runners}


def score_date(target_date: str, execute: bool = False) -> dict:
    # Load feed rows
    all_rows = _read_jsonl(FEED_JSONL)
    if not all_rows:
        raise RuntimeError("Feed JSONL is empty. Run: python scripts/ops/new_build_current_card_feed.py --execute first.")

    # Filter to target date ONLY
    target_rows = [r for r in all_rows if str(r.get("race_date", ""))[:10] == target_date]

    # Date capture status
    capture_status = _date_status(target_date)

    if not target_rows:
        # BLOCKED — no data for this date
        payload = {
            "generated_at": _utc_now(),
            "target_date": target_date,
            "overall_status": "BLOCKED_NO_DATA",
            "capture_status": capture_status,
            "races_found": 0,
            "runners_found": 0,
            "action_required": (
                "No runners found for this date. "
                "Run: python scripts/ops/racing_post_account_collector.py --date {date}\n"
                "     python scripts/ops/parse_racing_post_racecard_capture.py --date {date} --execute\n"
                "     python scripts/ops/new_build_current_card_feed.py --execute\n"
                "     python scripts/ops/new_build_two_lane_score.py --date {date} --execute"
            ).format(date=target_date),
            "lane_a": None,
            "lane_b": None,
            "operational_lane": None,
        }
        if execute:
            out_json = REPORT_DIR / f"two_lane_readiness_{target_date.replace('-', '_')}.json"
            out_md = REPORT_DIR / f"two_lane_readiness_{target_date.replace('-', '_')}.md"
            _write_json(out_json, payload)
            out_md.write_text(_blocked_markdown(payload), encoding="utf-8")
            print(f"Written: {out_json}")
            print(f"Written: {out_md}")
        return payload

    # Load bundles
    if not LANE_A_PKL.exists():
        raise FileNotFoundError(f"Lane A bundle missing: {LANE_A_PKL}")
    if not LANE_B_PKL.exists():
        raise FileNotFoundError(f"Lane B bundle missing: {LANE_B_PKL}")

    with LANE_A_PKL.open("rb") as f:
        bundle_a = pickle.load(f)
    with LANE_B_PKL.open("rb") as f:
        bundle_b = pickle.load(f)
    bundle_c = None
    if LANE_C_PKL.exists():
        with LANE_C_PKL.open("rb") as f:
            bundle_c = pickle.load(f)

    # Score both lanes
    probs_a, missing_a, violations_a = _score_lane(bundle_a, target_rows, "LaneA")
    probs_b, missing_b, violations_b = _score_lane(bundle_b, target_rows, "LaneB")
    probs_c: list[float] = []
    if bundle_c is not None:
        probs_c, _, _ = _score_lane(bundle_c, target_rows, "LaneC_SoftLabel")

    # Clone rows for each lane so we don't mix keys
    rows_a = [dict(r) for r in target_rows]
    rows_b = [dict(r) for r in target_rows]
    rows_c = [dict(r) for r in target_rows]
    _rank_within_race(rows_a, probs_a, "lane_a_prob", "lane_a_rank")
    _rank_within_race(rows_b, probs_b, "lane_b_prob", "lane_b_rank")
    if probs_c:
        _rank_within_race(rows_c, probs_c, "lane_c_prob", "lane_c_rank")

    # ── NEW: Apply Decision Policy V1 ─────────────────────────────────────────
    from new_build_velo.policy_v1 import apply_policy_v1
    for r_a, r_b in zip(rows_a, rows_b):
        # We use Lane B (Full Challenger V1) as the decision anchor
        policy = apply_policy_v1(r_b)
        r_b.update(policy)
        r_a.update(policy)

    # Intent coverage check (same for both — intent is in feed row flags)
    intent_count = sum(1 for r in target_rows if r.get("intent_features_available"))
    intent_pct = round(intent_count / len(target_rows) * 100, 2)
    intent_status = "AVAILABLE" if intent_pct >= INTENT_COVERAGE_GATE else "UNAVAILABLE_BELOW_GATE"

    # Operational lane selection
    if intent_pct >= INTENT_COVERAGE_GATE:
        operational = "LANE_B_CHALLENGER_V1"
        operational_note = f"Intent coverage {intent_pct}% >= {INTENT_COVERAGE_GATE}% gate. Full Challenger V1 operational."
    else:
        operational = "LANE_A_CORE_PASSPORT"
        operational_note = (
            f"Intent coverage {intent_pct}% < {INTENT_COVERAGE_GATE}% gate. "
            "Lane B is PAPER_ONLY_NO_INTENT. Lane A (Core+Passport) is operational read."
        )

    # RPR/SP violations — allowed policy keys are governance metadata, not features
    RPR_ALLOWED_POLICY_KEYS = {"rpr_policy", "rp_rpr_velo_allowed", "rpr_feature_allowed"}
    all_violations = violations_a + violations_b
    rpr_violations = len([
        k for r in target_rows for k in r
        if "rpr" in k.lower() and k.lower() not in RPR_ALLOWED_POLICY_KEYS
    ])

    # Build per-race scorecards
    by_race: dict[str, dict] = {}
    rows_c_map = {str(r.get("race_id","")) + str(r.get("horse","")): r for r in rows_c} if rows_c else {}
    for row_a, row_b in zip(rows_a, rows_b):
        rid = str(row_a.get("race_id"))
        if rid not in by_race:
            by_race[rid] = {
                "race_id": rid,
                "course": row_a.get("course"),
                "off_time": row_a.get("off_time"),
                "race_date": row_a.get("race_date"),
                "race_title": row_a.get("race_title"),
                "runners": [],
            }
        row_c = rows_c_map.get(str(row_a.get("race_id","")) + str(row_a.get("horse","")), {})
        by_race[rid]["runners"].append({
            "horse": row_a.get("horse"),
            "rp_uid": row_a.get("rp_uid"),
            "passport_found": row_a.get("passport_found"),
            "lane_a_prob": row_a.get("lane_a_prob"),
            "lane_a_rank": row_a.get("lane_a_rank"),
            "lane_b_prob": row_b.get("lane_b_prob"),
            "lane_b_rank": row_b.get("lane_b_rank"),
            "lane_c_prob": row_c.get("lane_c_prob"),
            "lane_c_rank": row_c.get("lane_c_rank"),
            "nb_decision_lane": row_a.get("nb_decision_lane"),
            "nb_policy_reasons": row_a.get("nb_policy_reasons"),
        })

    scorecards = []
    for race in sorted(by_race.values(), key=lambda r: (str(r.get("race_date", "")), str(r.get("off_time", "")))):
        runners = sorted(race["runners"], key=lambda r: r.get("lane_a_rank", 99))
        pp_found = sum(1 for r in runners if r.get("passport_found"))
        scorecards.append({
            "race_id": race["race_id"],
            "course": race["course"],
            "off_time": race["off_time"],
            "race_date": race["race_date"],
            "race_title": race["race_title"],
            "runner_count": len(runners),
            "passport_coverage": f"{pp_found}/{len(runners)}",
            "passport_coverage_pct": round(pp_found / len(runners) * 100, 1) if runners else 0.0,
            "lane_a_top3": [{"rank": r["lane_a_rank"], "horse": r["horse"], "prob": r["lane_a_prob"], "nb_decision_lane": r.get("nb_decision_lane")}
                             for r in runners if r.get("lane_a_rank", 99) <= 3],
            "lane_b_top3": [{"rank": r["lane_b_rank"], "horse": r["horse"], "prob": r["lane_b_prob"], "nb_decision_lane": r.get("nb_decision_lane")}
                             for r in runners if r.get("lane_b_rank", 99) <= 3],
            "lane_c_top3": [{"rank": r["lane_c_rank"], "horse": r["horse"], "prob": r["lane_c_prob"]}
                             for r in runners if r.get("lane_c_rank") is not None and r.get("lane_c_rank", 99) <= 3],
            "lane_b_note": "PAPER_ONLY_NO_INTENT" if intent_pct < INTENT_COVERAGE_GATE else "LIVE",
            "weak_data": pp_found < len(runners),
            "top_pick_lane": runners[0].get("nb_decision_lane") if runners else None,
        })

    payload = {
        "generated_at": _utc_now(),
        "target_date": target_date,
        "overall_status": "READY" if not all_violations and rpr_violations == 0 else "BLOCKED_VIOLATIONS",
        "capture_status": capture_status,
        "races_scored": len(scorecards),
        "runners_scored": len(target_rows),
        "rpr_violations": rpr_violations,
        "sp_violations": len([f for f in (missing_a.keys() | missing_b.keys()) if "sp_dec" in f or "log_sp" in f]),
        "quality_gates": {
            "rpr_clean": rpr_violations == 0,
            "sp_clean": True,
            "passport_coverage_above_50pct": (
                sum(sc.get("passport_coverage_pct", 0) for sc in scorecards) / max(len(scorecards), 1) >= 50
            ),
            "no_leakage_violations": len(all_violations) == 0,
        },
        "intent_coverage": {
            "found": intent_count,
            "total": len(target_rows),
            "coverage_pct": intent_pct,
            "gate": INTENT_COVERAGE_GATE,
            "status": intent_status,
            "note": "Intent features are historical (race_id, horse) pairs. "
                    "Current-card rows never match → 0% is expected for morning reads.",
        },
        "operational_lane": operational,
        "operational_note": operational_note,
        "lane_a": {
            "label": "Core_V0_OR_Passport (30 features)",
            "model_pkl": str(LANE_A_PKL),
            "feature_count": len(bundle_a["feature_cols"]),
            "median_fill_counts": dict(missing_a.most_common(10)),
        },
        "lane_b": {
            "label": "Challenger_V1 Core+Passport+Intent (45 features)",
            "model_pkl": str(LANE_B_PKL),
            "feature_count": len(bundle_b["feature_cols"]),
            "intent_coverage_pct": intent_pct,
            "status": "PAPER_ONLY_NO_INTENT" if intent_pct < INTENT_COVERAGE_GATE else "OPERATIONAL",
            "median_fill_counts": dict(missing_b.most_common(10)),
        },
        "race_day_scorecards": scorecards,
        "rules": {
            "paper_only": True,
            "no_live_engine": True,
            "no_telegram": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "no_staking": True,
            "rpr_archive_only": True,
            "no_market_lane_morning": True,
            "no_jtcd_alltime": True,
        },
    }

    if execute:
        out_json = REPORT_DIR / f"two_lane_readiness_{target_date.replace('-', '_')}.json"
        out_md = REPORT_DIR / f"two_lane_readiness_{target_date.replace('-', '_')}.md"
        _write_json(out_json, payload)
        out_md.write_text(_markdown(payload), encoding="utf-8")
        print(f"Written: {out_json}")
        print(f"Written: {out_md}")

    return payload


def _blocked_markdown(p: dict) -> str:
    cs = p["capture_status"]
    action = p.get("action_required", "")
    return "\n".join([
        f"# Race Day Two-Lane Readiness: {p['target_date']}",
        f"Generated: {p['generated_at']}",
        "",
        f"**Status: `{p['overall_status']}`**",
        "",
        "## Date Capture",
        f"- Status: `{cs.get('status')}` — {cs.get('races', 0)} races, {cs.get('runners', 0)} runners",
        cs.get('note', ''),
        "",
        "## Actions Required",
        "```",
        action,
        "```",
        "",
        "## Boundaries",
        "- Paper-only. No betting. No Telegram. Old Live VÉLØ and Shadow untouched.",
    ])


def _markdown(p: dict) -> str:
    lines = [
        f"# Race Day Two-Lane Readiness: {p['target_date']}",
        f"Generated: {p['generated_at']}",
        "",
        f"**Overall Status:** `{p['overall_status']}`",
        f"**Operational Lane:** `{p['operational_lane']}`",
        "",
        "## Quality Gates",
        "| Gate | Pass |",
        "|---|---|",
    ]
    for gate, passed in p["quality_gates"].items():
        lines.append(f"| {gate} | {'✓' if passed else '✗'} |")

    ic = p["intent_coverage"]
    lines += [
        "",
        "## Intent Coverage",
        f"- Coverage: **{ic['coverage_pct']}%** (gate: {ic['gate']}%) — `{ic['status']}`",
        f"- {ic['note']}",
        "",
        "## Lane Selection",
        f"- **{p['operational_lane']}** — {p['operational_note']}",
        "",
        "## Lane A: Core V0_OR + Passport (30 features) — Operational",
        f"- Model: `{p['lane_a']['model_pkl']}`",
        "",
        "## Lane B: Challenger V1 Core+Passport+Intent (45 features)",
        f"- Status: `{p['lane_b']['status']}`",
        f"- Intent coverage: {p['lane_b']['intent_coverage_pct']}%",
        "",
        f"## Race Day Scorecards — {p['target_date']}",
        f"_{p['races_scored']} races, {p['runners_scored']} runners_",
    ]

    def _fmt_time(val):
        if not val:
            return ""
        if "T" in str(val):
            try:
                from datetime import datetime as _dt
                return _dt.fromisoformat(val).strftime("%H:%M")
            except Exception:
                pass
        return str(val)[:5]

    for sc in p["race_day_scorecards"]:
        a_top3 = ", ".join(f"{r['horse']} ({r['prob']:.3f})" for r in sc.get("lane_a_top3", []))
        b_top3 = ", ".join(f"{r['horse']} ({r['prob']:.3f})" for r in sc.get("lane_b_top3", []))
        b_flag = " ⚠ PAPER_ONLY_NO_INTENT" if sc.get("lane_b_note") == "PAPER_ONLY_NO_INTENT" else ""
        weak = " ⚠ WEAK_DATA" if sc.get("weak_data") else ""
        lane = f" **[{sc.get('top_pick_lane', 'NO_EDGE')}]**"
        lines += [
            "",
            f"### {_fmt_time(sc.get('off_time'))} {sc.get('course')} — {(sc.get('race_title') or '')[:50]}{lane}",
            f"- Runners: {sc['runner_count']} | Passport: {sc['passport_coverage']}{weak}",
            f"- **Lane A (operational):** {a_top3}",
            f"- **Lane B (paper):** {b_top3}{b_flag}",
        ]

    lines += [
        "",
        "## Boundaries",
        "- Paper-only intelligence. No betting instruction.",
        "- No Telegram, staking, live scoring table writes, or official-pick override.",
        "- Old Live VÉLØ and Shadow VÉLØ untouched.",
        "- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="Target race date YYYY-MM-DD")
    p.add_argument("--execute", action="store_true", help="Write report files")
    args = p.parse_args()
    result = score_date(args.date, execute=args.execute)
    print(f"\nOverall status: {result['overall_status']}")
    print(f"Races scored: {result.get('races_scored', 0)}")
    print(f"Runners scored: {result.get('runners_scored', 0)}")
    print(f"Operational lane: {result.get('operational_lane')}")
    if result.get('action_required'):
        print(f"\nACTION REQUIRED:\n{result['action_required']}")


if __name__ == "__main__":
    main()
