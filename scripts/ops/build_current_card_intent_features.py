#!/usr/bin/env python3
"""Build current-card Intent Layer features for a single race day.

Shadow-only research artifact. Does not touch live scoring.

Formulas for the GROUP A features (mark_compression_score,
curr_or_minus_last_win_or, curr_or_minus_best_or, runs_since_win,
runs_since_place, runs_since_mkt_support, odds_resilience_score) are ported
from app/services/v17_feature_extractor.py's pure numeric logic. That module
was written to call the (now decommissioned) Racing API; this script never
imports it and never calls any live API. All per-run history instead comes
from the local race_shape/form_history_*.json archive, which stores each
horse's own results as scraped off their Racing Post profile page.

GROUP B features (intent_trip_match, intent_course_win_history,
intent_going_match, intent_run_after_break, intent_sp_shortening,
intent_wins_last10, intent_top3_last6) are ported from
new_build_intent_features.py's per-horse logic.

intent_class_drop_vs_best is NOT computed: the local race_shape archive has
no race-class field (only or_rating), so there is no faithful source for it.
It is emitted as null with reason "NO_CLASS_FIELD_IN_LOCAL_ARCHIVE" rather
than approximated from OR, to avoid fabricating a feature.

Leakage rule: only runs with race_date strictly before the target card date
are used. Today's own SP/result/is_fav are never read.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
OUT_DIR = ROOT / "data" / "new_build" / "current_cards"
RPT_DIR = ROOT / "data" / "new_build" / "reports"

GROUP_A = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score",
]
GROUP_B = [
    "intent_trip_match", "intent_course_win_history", "intent_going_match",
    "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]
ALL_INTENT = GROUP_A + GROUP_B

BANNED_LEAKAGE_FIELDS = {
    "sp_dec", "rpr", "rpr_num", "is_fav", "sp_rank", "implied_prob", "pos",
    "odds_contraction_score", "decoy_support_flag",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _going_bucket(going_str: str) -> int:
    g = str(going_str or "").strip().upper()
    if any(x in g for x in ("STANDARD", "FAST", "TAPETA", "POLYTRACK", "GD-FM", "FIRM")):
        return 0
    if "HEAVY" in g or "VERY SOFT" in g or g == "HVY":
        return 3
    if "SOFT" in g or "YIELD" in g or g in ("SFT", "GS", "SFT-HVY"):
        return 2
    return 1


def _parse_dist_f(dist_str: str) -> float | None:
    """Parse RP-style distance strings ('2m4f', '7f', '1m') to furlongs."""
    if not dist_str:
        return None
    s = str(dist_str).strip().lower()
    m = re.match(r"^(?:(\d+)m)?(?:(\d+(?:\.\d+)?)f)?$", s)
    if not m or (not m.group(1) and not m.group(2)):
        return None
    miles = float(m.group(1) or 0)
    furlongs = float(m.group(2) or 0)
    return miles * 8.0 + furlongs


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        v = float(str(val).strip())
        return v if v == v else None  # nan check
    except (ValueError, TypeError):
        return None


def load_run_history() -> dict[str, list[dict]]:
    """Load all local per-run history, grouped by horse_rp_uid, deduped, sorted by date."""
    by_horse: dict[str, list[dict]] = {}
    seen: set[tuple] = set()
    for f in sorted(glob.glob(str(RACE_SHAPE_DIR / "form_history_*.json"))):
        if "latest" in f:
            continue
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for run in data.get("runs", []):
            uid = run.get("horse_rp_uid")
            if uid is None:
                continue
            uid = str(uid)
            key = (uid, run.get("race_date"), run.get("course_rp_uid"), run.get("position"), run.get("sp_raw"))
            if key in seen:
                continue
            seen.add(key)
            by_horse.setdefault(uid, []).append(run)
    for uid in by_horse:
        by_horse[uid].sort(key=lambda r: r.get("race_date") or "")
    return by_horse


def compute_features(runs: list[dict], *, target_date: str, today_course: str, today_dist_f: float | None,
                      today_going: str, today_or: float | None) -> dict[str, Any]:
    """Compute the 15 intent features for one runner, as-of target_date (exclusive)."""
    hist = [r for r in runs if (r.get("race_date") or "9999") < target_date]
    result: dict[str, Any] = {c: None for c in ALL_INTENT}
    result["history_runs_used"] = len(hist)
    result["intent_class_drop_vs_best"] = None  # never computed; see module docstring
    if not hist:
        return result

    n = len(hist)
    wins = [1 if str(r.get("position")) == "1" else 0 for r in hist]
    places = [1 if str(r.get("position")) in ("1", "2", "3") else 0 for r in hist]
    sps = [_safe_float(r.get("sp_dec")) for r in hist]
    mkt_support = [1 if (sps[i] is not None and sps[i] < 3.5) else 0 for i in range(n)]
    ors = [_safe_float(r.get("or_rating")) for r in hist]
    goings_bkt = [_going_bucket(r.get("going")) for r in hist]
    dists_f = [_parse_dist_f(r.get("distance")) for r in hist]
    courses = [str(r.get("course_key") or r.get("course_name") or "") for r in hist]
    dates = [r.get("race_date") for r in hist]

    def runs_since_last(flags: list[int]) -> int:
        for i in range(len(flags) - 1, -1, -1):
            if flags[i]:
                return len(flags) - 1 - i
        return len(flags)

    result["runs_since_win"] = float(runs_since_last(wins))
    result["runs_since_place"] = float(runs_since_last(places))
    result["runs_since_mkt_support"] = float(runs_since_last(mkt_support))

    valid_ors = [o for o in ors if o is not None]
    last_win_idx = next((i for i in range(n - 1, -1, -1) if wins[i] and ors[i] is not None), None)
    if valid_ors and today_or is not None:
        best_or = max(valid_ors)
        result["curr_or_minus_best_or"] = today_or - best_or
        if best_or > 0:
            result["mark_compression_score"] = (best_or - today_or) / best_or
        if last_win_idx is not None:
            result["curr_or_minus_last_win_or"] = today_or - ors[last_win_idx]

    recent_sps = [s for s in sps[-3:] if s is not None]
    if len(recent_sps) >= 2:
        mean = sum(recent_sps) / len(recent_sps)
        var = sum((s - mean) ** 2 for s in recent_sps) / len(recent_sps)
        result["odds_resilience_score"] = float(var ** 0.5)

    # GROUP B
    last_win_dist = next((dists_f[i] for i in range(n - 1, -1, -1) if wins[i] and dists_f[i] is not None), None)
    last_win_going = next((goings_bkt[i] for i in range(n - 1, -1, -1) if wins[i]), None)
    if last_win_dist is not None and today_dist_f is not None:
        result["intent_trip_match"] = float(abs(last_win_dist - today_dist_f) < 0.5)
    if last_win_going is not None:
        result["intent_going_match"] = float(_going_bucket(today_going) == last_win_going)

    course_wins = sum(1 for i in range(n) if wins[i] and courses[i] and today_course and courses[i] == today_course)
    result["intent_course_win_history"] = float(course_wins)

    layoff_run = 0
    prev_date = None
    for i in range(n):
        d = dates[i]
        if prev_date and d:
            try:
                gap = (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(prev_date, "%Y-%m-%d")).days
            except ValueError:
                gap = 0
            if gap > 90:
                layoff_run = 1
            elif layoff_run > 0:
                layoff_run += 1
        prev_date = d
    result["intent_run_after_break"] = float(layoff_run) if layoff_run > 0 else None

    valid_sps_tail3 = [s for s in sps[-3:] if s is not None]
    valid_sps_tail6 = [s for s in sps[-6:] if s is not None]
    if len(valid_sps_tail3) >= 2 and len(valid_sps_tail6) >= 3:
        avg3 = sum(valid_sps_tail3) / len(valid_sps_tail3)
        avg6 = sum(valid_sps_tail6) / len(valid_sps_tail6)
        result["intent_sp_shortening"] = float(avg3 < avg6)

    if n >= 3:
        result["intent_wins_last10"] = float(sum(wins[-10:]))
    if n >= 2:
        result["intent_top3_last6"] = float(sum(places[-6:]))

    return result


def build(*, standard_cache: Path, target_date: str, execute: bool) -> dict[str, Any]:
    std = json.loads(standard_cache.read_text(encoding="utf-8"))
    races = std if isinstance(std, list) else std.get("races", [])
    run_history = load_run_history()

    rows: list[dict[str, Any]] = []
    coverage_counts = {c: 0 for c in ALL_INTENT}
    join_hits = 0

    for race in races:
        race_id = str(race.get("race_id") or "")
        course = race.get("course")
        off_time = race.get("race_time") or race.get("off_time")
        for runner in race.get("runners", []):
            uid = str(runner.get("horse_id") or "")
            horse = runner.get("horse") or runner.get("horse_name")
            today_or = _safe_float(runner.get("official_rating") or runner.get("ofr"))
            today_dist_f = _parse_dist_f(race.get("distance") or race.get("dist"))
            today_going = race.get("going") or ""
            course_key = re.sub(r"[^a-z0-9]+", "-", str(course or "").lower()).strip("-")

            runs = run_history.get(uid, [])
            if runs:
                join_hits += 1
            feats = compute_features(
                runs, target_date=target_date, today_course=course_key,
                today_dist_f=today_dist_f, today_going=today_going, today_or=today_or,
            )

            row = {
                "race_id": race_id,
                "course": course,
                "off_time": off_time,
                "horse": horse,
                "horse_rp_uid": uid,
                "target_date": target_date,
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "learning_class": "SHADOW_INTENT_SIGNAL",
                **feats,
            }
            rows.append(row)
            for c in ALL_INTENT:
                if row.get(c) is not None:
                    coverage_counts[c] += 1

    total = len(rows)
    full_rows = sum(
        1 for r in rows
        if all(r.get(c) is not None for c in ALL_INTENT if c != "intent_class_drop_vs_best")
    )
    partial_rows = sum(1 for r in rows if r["history_runs_used"] > 0) - full_rows

    # leakage check: assert no banned field ever set on a row
    leakage_hits = [k for r in rows for k in r if k in BANNED_LEAKAGE_FIELDS]

    audit = {
        "generated_at": _utc_now(),
        "target_date": target_date,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "learning_class": "SHADOW_INTENT_SIGNAL",
        "total_runners": total,
        "runners_with_any_local_history": join_hits,
        "runners_full_feature_coverage": full_rows,
        "runners_partial_feature_coverage": max(partial_rows, 0),
        "runners_no_local_history": total - join_hits,
        "join_failure_rate_pct": round((total - join_hits) / total * 100, 2) if total else 0.0,
        "null_rate_pct_by_feature": {
            c: round((1 - coverage_counts[c] / total) * 100, 2) if total else 100.0
            for c in ALL_INTENT
        },
        "intent_class_drop_vs_best_note": "Not computed: local race_shape archive has no race-class field, only or_rating. Emitted as null rather than approximated.",
        "leakage_check": "PASS" if not leakage_hits else "FAIL",
        "leakage_hits": leakage_hits,
        "source": "data/race_shape/form_history_*.json (local per-run archive from Racing Post profile captures)",
        "as_of_rule": "Only runs with race_date strictly before target_date are used; today's own SP/result/is_fav never read.",
        "formula_provenance": "GROUP A (mark_compression_score, curr_or_minus_last_win_or, curr_or_minus_best_or, "
                               "runs_since_win, runs_since_place, runs_since_mkt_support, odds_resilience_score) "
                               "ported from app/services/v17_feature_extractor.py pure numeric logic "
                               "(no import, no live API call). GROUP B ported from new_build_intent_features.py.",
    }

    if execute:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        RPT_DIR.mkdir(parents=True, exist_ok=True)
        safe_date = target_date.replace("-", "_")
        out_path = OUT_DIR / f"current_card_intent_features_{safe_date}.jsonl"
        out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        audit_path = RPT_DIR / f"current_card_intent_features_{safe_date}_audit.json"
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        audit["output_path"] = str(out_path.relative_to(ROOT))
        audit["audit_path"] = str(audit_path.relative_to(ROOT))

    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build current-card Intent Layer features (shadow-only).")
    parser.add_argument("--standard-cache", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD target card date")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    audit = build(standard_cache=Path(args.standard_cache), target_date=args.date, execute=args.execute)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
