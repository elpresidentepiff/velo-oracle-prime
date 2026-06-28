"""Paper-only champion scorer for New Build current cards.

This loads the New Build champion model and scores the current-card Passport
Feed without touching Live VELO, Shadow VELO, Telegram, staking, or live tables.
Missing current-card core fields are filled from the champion bundle medians and
reported as paper-read limitations.
"""
from __future__ import annotations

import csv as _csv
import json
import pickle
import re as _re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from new_build_velo.current_card_feed import (
    FEED_JSONL_PATH,
    REPORT_JSON_PATH as CURRENT_FEED_REPORT_JSON,
    build_current_card_feed,
)
from new_build_velo.spine import NEW_BUILD_ROOT, TRUST_POLICY, stable_id, utc_now


ROOT = Path(__file__).resolve().parents[1]
BHA_PERF_FIGURES_PATH = ROOT / "data" / "bha_perf_figures_latest.csv"
_BHA_PERF_NORM_RE = _re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
_BHA_PERF_FIG_RE = _re.compile(r"^([TAHSNM]):(.+)$")
PAPER_ROOT = NEW_BUILD_ROOT / "paper_predictions"
REPORT_ROOT = NEW_BUILD_ROOT / "reports"
PAPER_JSONL_PATH = PAPER_ROOT / "new_build_paper_predictions_latest.jsonl"
PAPER_REPORT_JSON_PATH = REPORT_ROOT / "new_build_paper_predictions_latest.json"
PAPER_REPORT_MD_PATH = REPORT_ROOT / "new_build_paper_predictions_latest.md"
FINAL_CARD_PAPER_JSONL_PATH = PAPER_ROOT / "new_build_paper_predictions_final_card_latest.jsonl"
FINAL_CARD_PAPER_REPORT_JSON_PATH = REPORT_ROOT / "new_build_paper_predictions_final_card_latest.json"
FINAL_CARD_PAPER_REPORT_MD_PATH = REPORT_ROOT / "new_build_paper_predictions_final_card_latest.md"
CHAMPION_REGISTRY_PATH = NEW_BUILD_ROOT / "models" / "champion" / "champion_registry.json"
INTENT_FEATURE_PATH = NEW_BUILD_ROOT / "training" / "intent_features.parquet"

RPR_ALLOWED_POLICY_KEYS = {"rpr_policy", "rp_rpr_velo_allowed", "rpr_feature_allowed"}
BANNED_SUBSTRINGS = ("rpr",)


def _assert_new_build_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"New Build writes are restricted to {allowed}: {resolved}")


def _write_json(path: Path, payload: Any) -> None:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_champion_bundle() -> tuple[dict[str, Any], dict[str, Any]]:
    registry = _read_json(CHAMPION_REGISTRY_PATH, {})
    model_path = registry.get("model_pkl")
    if not model_path:
        raise RuntimeError("Champion registry has no model_pkl.")
    path = Path(model_path)
    if not path.is_absolute():
        path = ROOT / path
    with path.open("rb") as handle:
        bundle = pickle.load(handle)
    return registry, bundle


def _bad_keys(row: dict[str, Any]) -> list[str]:
    bad = []
    for key in row:
        lowered = key.lower()
        if lowered in RPR_ALLOWED_POLICY_KEYS:
            continue
        if any(token in lowered for token in BANNED_SUBSTRINGS):
            bad.append(key)
    return bad


def _load_bha_perf_figures_lookup() -> dict[str, list[tuple[str, int | None]]]:
    if not BHA_PERF_FIGURES_PATH.exists():
        return {}
    lookup: dict[str, list[tuple[str, int | None]]] = {}
    try:
        with open(BHA_PERF_FIGURES_PATH, encoding="utf-8-sig", errors="replace") as fh:
            for row in _csv.DictReader(fh):
                raw = (row.get("Racehorse") or "").strip()
                norm = _BHA_PERF_NORM_RE.sub("", raw).lower().strip()
                if not norm:
                    continue
                figs: list[tuple[str, int | None]] = []
                for col in ["Latest", "2 runs ago", "3 runs ago", "4 runs ago", "5 runs ago", "6 runs ago"]:
                    m = _BHA_PERF_FIG_RE.match((row.get(col) or "").strip())
                    if not m:
                        continue
                    surf, val = m.group(1), m.group(2)
                    figs.append((surf, None if val == "x" else _to_int(val)))
                if figs:
                    lookup[norm] = figs
    except Exception:
        pass
    return lookup


def _bha_slope(values: list[int]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(values))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den if den else 0.0


def _bha_form_momentum(horse: str, lookup: dict[str, list[tuple[str, int | None]]]) -> dict[str, Any]:
    norm = _BHA_PERF_NORM_RE.sub("", (horse or "").strip()).lower().strip()
    figs = lookup.get(norm)
    if not figs:
        return {"bha_form_momentum": None, "bha_form_latest_fig": None, "bha_form_n": 0, "bha_form_flag": "NO_DATA"}
    nums_latest_first = [f for _, f in figs if f is not None and f > 0]
    if not nums_latest_first:
        return {"bha_form_momentum": None, "bha_form_latest_fig": None, "bha_form_n": 0, "bha_form_flag": "SPARSE"}
    nums_asc = list(reversed(nums_latest_first))
    slope = _bha_slope(nums_asc) if len(nums_asc) >= 2 else None
    if slope is None:
        flag = "SPARSE"
    elif slope > 5.0:
        flag = "ACCELERATING"
    elif slope > 2.0:
        flag = "PROGRESSIVE"
    elif slope >= -2.0:
        flag = "STABLE"
    elif slope >= -5.0:
        flag = "REGRESSING"
    else:
        flag = "DECLINING"
    return {
        "bha_form_momentum": round(slope, 2) if slope is not None else None,
        "bha_form_latest_fig": nums_latest_first[0],
        "bha_form_n": len(nums_asc),
        "bha_form_flag": flag,
    }


def _going_code(value: Any, default: float) -> float:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    mapping = {
        "heavy": 0.0,
        "soft": 1.0,
        "good to soft": 2.0,
        "good": 3.0,
        "good to firm": 4.0,
        "firm": 5.0,
        "standard": 6.0,
        "standard to slow": 7.0,
        "slow": 8.0,
    }
    for label, code in mapping.items():
        if label in raw:
            return code
    return default


def _actual_feature_map(row: dict[str, Any], medians: dict[str, float]) -> dict[str, float]:
    passport = row.get("passport_summary") or {}
    live_pp = row.get("passport_live_features") or {}
    field_size = _to_float(row.get("field_size"), None)
    draw = _to_float(row.get("draw"), None)
    official_rating = _to_float(row.get("official_rating"), None)

    def _pp(live_key: str, fallback: float | None) -> float | None:
        v = live_pp.get(live_key)
        return float(v) if v is not None else fallback

    feature_values = {
        "dist_f": _to_float(row.get("distance_furlongs"), None),
        "going_code": _going_code(row.get("going") or row.get("going_code_raw"), medians.get("going_code", 0.0)),
        "is_aw": 1.0 if str(row.get("surface") or "").lower() in {"aw", "all-weather", "all weather"} else 0.0,
        "field_size": field_size,
        "draw_num": draw,
        "draw_pct": draw / field_size if field_size and draw is not None else None,
        "age_num": _to_float(row.get("age"), None),
        "wgt_lbs": _to_float(row.get("weight_lbs"), None),
        "or_vs_field": 0.0,
        "official_rating": official_rating,
        "is_rated": 1.0 if official_rating is not None else 0.0,
        "pp_career_runs": _pp("pp_career_runs", _to_float(passport.get("career_runs"), None)),
        "pp_win_rate": _pp("pp_win_rate", _to_float(passport.get("win_rate"), None)),
        "pp_place_rate": _pp("pp_place_rate", _to_float(passport.get("place_rate"), None)),
        "pp_days_since_last": _pp("pp_days_since_last", _to_float(passport.get("days_since_last_run"), None)),
        "pp_layoff": _pp("pp_layoff", None),
        "pp_avg_sp_last5": _pp("pp_avg_sp_last5", _to_float(passport.get("avg_sp_last5"), None)),
        "pp_jockey_continuity": _pp("pp_jockey_continuity", 1.0 if passport.get("jockey_continuity") else 0.0),
        "pp_course_seen": _pp("pp_course_seen", medians.get("pp_course_seen", 0.0)),
        "pp_or_change_3": _pp("pp_or_change_3", _to_float(passport.get("or_change_last3"), None)),
        "pp_class_moved_up": _pp("pp_class_moved_up", 1.0 if str(passport.get("class_movement") or "").upper() == "UP" else 0.0),
        "pp_class_moved_down": _pp("pp_class_moved_down", 1.0 if str(passport.get("class_movement") or "").upper() == "DOWN" else 0.0),
    }
    # Fallback: reconstruct layoff from stored string flag when live_pp has no value
    if feature_values["pp_layoff"] is None:
        layoff = str(passport.get("layoff_flag") or "").upper()
        if layoff:
            feature_values["pp_layoff"] = 0.0 if layoff == "ACTIVE" else 1.0
    return feature_values


def _feature_row(row: dict[str, Any], feature_cols: list[str], medians: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    actual = _actual_feature_map(row, medians)
    missing = []
    out = {}
    for col in feature_cols:
        value = actual.get(col)
        if value is None:
            missing.append(col)
            value = medians.get(col, 0.0)
        out[col] = float(value)
    return out, missing


def _race_normalize(rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("race_id"))].append(row)
    for race_rows in grouped.values():
        race_rows.sort(key=lambda item: item["champion_probability"], reverse=True)
        for rank, row in enumerate(race_rows, start=1):
            row["champion_rank"] = rank


def _race_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("race_id"))].append(row)
    reports = []
    for race_rows in grouped.values():
        ranked = sorted(race_rows, key=lambda row: row["champion_probability"], reverse=True)
        missing = [row for row in race_rows if not row["passport_found"]]
        strongest_passport = max(
            (row for row in race_rows if row["passport_found"]),
            key=lambda row: row.get("passport_strength_score", -1),
            default=None,
        )
        strongest_intent = max(
            (row for row in race_rows if row.get("intent_score") is not None),
            key=lambda row: row.get("intent_score") or -1,
            default=None,
        )
        reports.append(
            {
                "race_id": ranked[0]["race_id"],
                "course": ranked[0]["course"],
                "off_time": ranked[0]["off_time"],
                "race_date": ranked[0]["race_date"],
                "race_title": ranked[0]["race_title"],
                "runner_count": len(race_rows),
                "passport_coverage": sum(1 for row in race_rows if row["passport_found"]),
                "top_3": [
                    {
                        "horse": row["horse"],
                        "rp_uid": row["rp_uid"],
                        "champion_probability": row["champion_probability"],
                        "champion_rank": row["champion_rank"],
                        "intent_score": row.get("intent_score"),
                        "reason_codes": row.get("reason_codes", [])[:8],
                    }
                    for row in ranked[:3]
                ],
                "strongest_passport_horse": _compact(strongest_passport),
                "strongest_intent_candidate": _compact(strongest_intent),
                "missing_data_warnings": [
                    f"{len(missing)} missing/unraced passport rows" if missing else None,
                    "Intent unavailable for current-card rows" if not strongest_intent else None,
                ],
                "unraced_new_horse_warnings": [_compact(row) for row in missing[:5]],
            }
        )
    for report in reports:
        report["missing_data_warnings"] = [item for item in report["missing_data_warnings"] if item]
    return sorted(reports, key=lambda row: (str(row["race_date"]), str(row["off_time"]), str(row["course"])))


def _compact(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "horse": row.get("horse"),
        "rp_uid": row.get("rp_uid"),
        "champion_probability": row.get("champion_probability"),
        "champion_rank": row.get("champion_rank"),
        "intent_score": row.get("intent_score"),
        "reason_codes": row.get("reason_codes", [])[:8],
        "missing_reason": row.get("missing_reason"),
    }


def _load_official_race_ids(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    data = _read_json(path, [])
    rows = data if isinstance(data, list) else data.get("verdicts") or data.get("races") or []
    return {str(row.get("race_id")) for row in rows if row.get("race_id") not in (None, "")}


def build_paper_predictions(
    *,
    execute: bool = False,
    refresh_feed: bool = True,
    racecard_path: Path | None = None,
    official_verdict_path: Path | None = None,
    final_card: bool = False,
) -> dict[str, Any]:
    if refresh_feed:
        feed_report = build_current_card_feed(execute=True, racecard_path=racecard_path)
    else:
        feed_report = _read_json(CURRENT_FEED_REPORT_JSON, {})
    feed_rows = _read_jsonl(FEED_JSONL_PATH)
    registry, bundle = _load_champion_bundle()
    model = bundle["model"]
    feature_cols = [str(col) for col in bundle["feature_cols"]]
    medians = {str(key): float(value) for key, value in dict(bundle["medians"]).items()}
    bad_keys = [bad for row in feed_rows for bad in _bad_keys(row)]

    matrix_rows = []
    missing_by_col: Counter[str] = Counter()
    missing_by_runner: dict[str, list[str]] = {}
    for row in feed_rows:
        features, missing = _feature_row(row, feature_cols, medians)
        matrix_rows.append(features)
        for col in missing:
            missing_by_col[col] += 1
        missing_by_runner[row["feed_row_id"]] = missing
    X = pd.DataFrame(matrix_rows, columns=feature_cols)
    probabilities = model.predict_proba(X)[:, 1] if len(X) else []

    paper_rows: list[dict[str, Any]] = []
    for row, probability in zip(feed_rows, probabilities):
        intent_score = None
        if row.get("intent_features_available"):
            intent_score = row.get("intent_score")
        paper_rows.append(
            {
                "prediction_id": stable_id(row.get("race_id"), row.get("rp_uid"), "new_build_paper"),
                "source": "new_build_paper_scorer_v1",
                "generated_at": utc_now(),
                "race_id": row.get("race_id"),
                "course": row.get("course"),
                "off_time": row.get("off_time"),
                "race_date": row.get("race_date"),
                "race_title": row.get("race_title"),
                "horse": row.get("horse"),
                "rp_uid": row.get("rp_uid"),
                "passport_found": row.get("passport_found"),
                "champion_probability": round(float(probability), 6),
                "champion_rank": None,
                "intent_score": intent_score,
                "intent_features_available": row.get("intent_features_available"),
                "missing_reason": row.get("missing_reason"),
                "reason_codes": row.get("reason_codes", []),
                "passport_strength_score": row.get("passport_strength_score"),
                "feature_missing_filled_from_median": missing_by_runner.get(row["feed_row_id"], []),
                "paper_only": True,
                "trust_policy": TRUST_POLICY,
                "velo_scoring_allowed": False,
                "live_velo_impact": False,
                "shadow_velo_impact": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
                "rpr_feature_allowed": False,
                "rp_rpr_velo_allowed": False,
            }
        )
    _race_normalize(paper_rows)

    # B-2 shadow signal: BHA form momentum (sidecar evidence — NOT in champion model feature matrix)
    _bha_lookup = _load_bha_perf_figures_lookup()
    for pr in paper_rows:
        pr.update(_bha_form_momentum(pr.get("horse") or "", _bha_lookup))

    intent_count = sum(1 for row in paper_rows if row["intent_features_available"])
    classification = "NEW_BUILD_PRE_RUN_BLOCKED" if bad_keys else "NEW_BUILD_PAPER_READY_NO_INTENT"
    if not bad_keys and intent_count:
        classification = "NEW_BUILD_PAPER_READY"
    official_race_ids = _load_official_race_ids(official_verdict_path)
    paper_race_ids = {str(row["race_id"]) for row in paper_rows}
    race_id_match = None
    missing_from_paper: list[str] = []
    extra_in_paper: list[str] = []
    if official_race_ids:
        missing_from_paper = sorted(official_race_ids - paper_race_ids)
        extra_in_paper = sorted(paper_race_ids - official_race_ids)
        race_id_match = not missing_from_paper and not extra_in_paper
        if final_card and not race_id_match:
            classification = "NEW_BUILD_FINAL_CARD_MISMATCH"
        elif final_card and feed_report.get("passport_coverage", {}).get("coverage_pct", 0.0) < 50.0:
            classification = "NEW_BUILD_FINAL_CARD_BRIDGE_LOW_COVERAGE"
        elif final_card and not bad_keys:
            classification = "NEW_BUILD_FINAL_CARD_PAPER_READY_BRIDGED"
    payload = {
        "generated_at": utc_now(),
        "classification": classification,
        "champion_name": registry.get("champion_name"),
        "champion_version": registry.get("champion_version"),
        "current_card_feed": {
            "classification": feed_report.get("classification"),
            "races_processed": feed_report.get("races_processed"),
            "runners_processed": feed_report.get("runners_processed"),
            "passport_coverage": feed_report.get("passport_coverage"),
            "missing_horse_count": feed_report.get("missing_horse_count"),
            "unraced_new_horse_count": feed_report.get("unraced_new_horse_count"),
            "rpr_violations": feed_report.get("rpr_violations"),
        },
        "paper_predictions_created": bool(paper_rows),
        "prediction_rows": len(paper_rows),
        "race_count": len({row["race_id"] for row in paper_rows}),
        "official_card_alignment": {
            "final_card_mode": final_card,
            "racecard_path": str(racecard_path) if racecard_path else None,
            "official_verdict_path": str(official_verdict_path) if official_verdict_path else None,
            "official_race_count": len(official_race_ids) if official_race_ids else None,
            "paper_race_count": len(paper_race_ids),
            "race_id_match": race_id_match,
            "missing_from_paper": missing_from_paper,
            "extra_in_paper": extra_in_paper,
        },
        "intent_current_card_coverage": {
            "found": intent_count,
            "total": len(paper_rows),
            "coverage_pct": round(intent_count / len(paper_rows) * 100, 2) if paper_rows else 0.0,
            "status": "AVAILABLE" if intent_count else "UNAVAILABLE_TODAY",
        },
        "feature_median_fill_counts": dict(missing_by_col),
        "rpr_violations": len(bad_keys),
        "rpr_violation_keys": sorted(set(bad_keys)),
        "race_reports": _race_reports(paper_rows),
        "rules": {
            "paper_only": True,
            "no_training": True,
            "no_live_engine": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "no_telegram": True,
            "no_staking": True,
            "no_live_table_writes": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        jsonl_path = FINAL_CARD_PAPER_JSONL_PATH if final_card else PAPER_JSONL_PATH
        report_json_path = FINAL_CARD_PAPER_REPORT_JSON_PATH if final_card else PAPER_REPORT_JSON_PATH
        report_md_path = FINAL_CARD_PAPER_REPORT_MD_PATH if final_card else PAPER_REPORT_MD_PATH
        _write_jsonl(jsonl_path, paper_rows)
        _write_json(report_json_path, payload)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    feed = payload["current_card_feed"]
    intent = payload["intent_current_card_coverage"]
    lines = [
        "# New Build Paper Predictions",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Classification**: `{payload['classification']}`",
        f"- **Champion**: `{payload.get('champion_version')}`",
        f"- **Paper predictions created**: `{payload['paper_predictions_created']}`",
        f"- **Races**: {payload['race_count']}",
        f"- **Runner predictions**: {payload['prediction_rows']}",
        f"- **Passport coverage**: {feed.get('passport_coverage', {}).get('found')} / {feed.get('passport_coverage', {}).get('total')} ({feed.get('passport_coverage', {}).get('coverage_pct')}%)",
        f"- **Missing/unraced horses**: {feed.get('missing_horse_count')}",
        f"- **Intent current-card coverage**: {intent['found']} / {intent['total']} ({intent['coverage_pct']}%) - `{intent['status']}`",
        f"- **RPR violations**: {payload['rpr_violations']}",
        f"- **Official race-id match**: `{payload.get('official_card_alignment', {}).get('race_id_match')}`",
        "",
        "## Median-Filled Champion Features",
        "| Feature | Runner rows filled |",
        "|---|---:|",
    ]
    for feature, count in sorted(payload["feature_median_fill_counts"].items()):
        lines.append(f"| `{feature}` | {count} |")
    lines += ["", "## Race Analyst Packet"]
    for race in payload["race_reports"][:80]:
        top3 = race["top_3"]
        lines += [
            "",
            f"### {race['race_date']} {race['course']} {race['off_time']}",
            f"- **Race**: {race.get('race_title')}",
            f"- **Top 3 paper**: " + ", ".join(
                f"{row['horse']} ({row['champion_probability']:.3f})" for row in top3
            ),
        ]
        strongest_passport = race.get("strongest_passport_horse")
        if strongest_passport:
            lines.append(f"- **Strongest passport horse**: {strongest_passport['horse']}")
        strongest_intent = race.get("strongest_intent_candidate")
        if strongest_intent:
            lines.append(f"- **Strongest intent candidate**: {strongest_intent['horse']}")
        else:
            lines.append("- **Strongest intent candidate**: unavailable today")
        if race.get("missing_data_warnings"):
            lines.append("- **Warnings**: " + "; ".join(race["missing_data_warnings"]))
    lines += [
        "",
        "## Boundaries",
        "- Paper-only intelligence. No betting instruction.",
        "- No Telegram, staking, live scoring table writes, or official-pick override.",
        "- Old Live VÉLØ and Shadow VÉLØ untouched.",
        "- RPR remains archive-only and is not a model input.",
    ]
    return "\n".join(lines)
