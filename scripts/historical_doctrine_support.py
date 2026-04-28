from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Sequence

from app.services.v17_feature_extractor import DEFAULTS as V17_DEFAULTS

HISTORICAL_DOCTRINE_CONTRACT = "HISTORICAL_DOCTRINE_FEATURES_V1"
DOCTRINE_SOURCE = "prior_only_raceform_history"
DOCTRINE_CUTOFF_RULE = "prior_race_date_lt_current_race_date"
DISTANCE_PARSER_VERSION = "HISTORICAL_DISTANCE_FIX_V1"

DOCTRINE_FEATURE_NAMES = [
    "runs_since_win",
    "runs_since_place",
    "runs_since_mkt_support",
    "curr_or_minus_last_win_or",
    "curr_or_minus_best_or",
    "mark_compression_score",
    "release_window_score",
    "course_fit_score",
    "going_fit_score",
    "distance_fit_score",
    "quiet_run_score",
    "trainer_timing_score",
    "jockey_switch_intent",
    "odds_resilience_score",
    "odds_contraction_score",
    "decoy_support_flag",
    "setup_run_flag",
    "cash_run_flag",
]


def parse_date_ymd(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_position(value: Any) -> int | None:
    if value in (None, "", "-", "–"):
        return None
    match = re.search(r"(\d+)", str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def parse_sp_decimal(value: Any) -> float | None:
    if value in (None, "", "-", "–"):
        return None
    text = str(value).strip().upper().rstrip("F").rstrip("J").strip()
    if text in ("EVENS", "EVS"):
        return 2.0
    frac = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", text)
    if frac:
        return float(frac.group(1)) / float(frac.group(2)) + 1.0
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number > 1.0 else number + 1.0


def going_bucket(going_str: Any) -> int:
    text = str(going_str or "").strip().upper()
    if any(token in text for token in ["STANDARD", "FAST", "TAPETA", "POLYTRACK"]):
        return 0
    if "HEAVY" in text or "VERY SOFT" in text:
        return 3
    if "SOFT" in text or "YIELD" in text:
        return 2
    return 1


def parse_distance_metric(value: Any) -> float | None:
    if value in (None, "", "-", "–"):
        return None
    direct = safe_float(value)
    if direct is not None:
        return direct
    text = str(value).strip().lower()
    total = 0.0
    miles = re.search(r"(\d+(?:\.\d+)?)m", text)
    furlongs = re.search(r"(\d+(?:\.\d+)?)f", text)
    yards = re.search(r"(\d+)y", text)
    if miles:
        total += float(miles.group(1)) * 8.0
    if furlongs:
        total += float(furlongs.group(1))
    if yards:
        total += float(yards.group(1)) / 220.0
    return total if total > 0 else None


def historical_distance_feature_value(distance_f: Any, distance_label: Any = None) -> float:
    numeric = safe_float(distance_f)
    if numeric is not None:
        return numeric
    parsed = parse_distance_metric(distance_label)
    if parsed is not None:
        return parsed
    return 16.0


def rows_strictly_before(rows: Sequence[dict[str, Any]], race_date: str | None) -> list[dict[str, Any]]:
    current_dt = parse_date_ymd(race_date)
    if current_dt is None:
        return []
    output: list[dict[str, Any]] = []
    for row in rows:
        row_dt = parse_date_ymd(row.get("date"))
        if row_dt is None:
            continue
        if row_dt < current_dt:
            output.append(row)
    output.sort(key=lambda item: str(item.get("date") or ""))
    return output


def compute_doctrine_features_from_prior_history(
    *,
    horse_prior_rows: Sequence[dict[str, Any]],
    trainer_prior_rows: Sequence[dict[str, Any]],
    race_context: dict[str, Any],
) -> dict[str, Any]:
    features = {name: float(V17_DEFAULTS[name]) for name in DOCTRINE_FEATURE_NAMES}
    current_sp = safe_float(race_context.get("sp_dec")) or 10.0
    current_or = safe_float(race_context.get("or_num"))
    current_jockey = str(race_context.get("jockey") or "")
    current_course = str(race_context.get("course") or "")
    current_going_bucket = going_bucket(race_context.get("going"))
    current_distance = parse_distance_metric(race_context.get("distance_metric"))
    is_fav = bool(race_context.get("is_fav"))

    if not horse_prior_rows:
        features["_coverage"] = {
            "prior_run_count": 0,
            "prior_1_plus": False,
            "prior_3_plus": False,
            "trainer_prior_run_count": len(trainer_prior_rows),
        }
        return features

    positions = [parse_position(row.get("pos")) for row in horse_prior_rows]
    wins = [int(pos == 1) for pos in positions]
    places = [int(pos in (1, 2, 3)) for pos in positions]
    sps = [parse_sp_decimal(row.get("sp")) for row in horse_prior_rows]
    ors = [safe_float(row.get("or_rating")) for row in horse_prior_rows]
    ovr_btns = [safe_float(row.get("ovr_btn")) or 0.0 for row in horse_prior_rows]
    jockeys = [str(row.get("jockey") or "") for row in horse_prior_rows]
    courses = [str(row.get("course") or "") for row in horse_prior_rows]
    goings = [going_bucket(row.get("going")) for row in horse_prior_rows]
    distances = [parse_distance_metric(row.get("dist")) for row in horse_prior_rows]
    market_support = [int((sps[idx] or 99.0) < 3.5) for idx in range(len(horse_prior_rows))]

    def runs_since_last(flags: Sequence[int]) -> float:
        for idx in range(len(flags) - 1, -1, -1):
            if flags[idx]:
                return float(len(flags) - 1 - idx)
        return float(len(flags))

    features["runs_since_win"] = runs_since_last(wins)
    features["runs_since_place"] = runs_since_last(places)
    features["runs_since_mkt_support"] = runs_since_last(market_support)

    valid_ors = [value for value in ors if value is not None]
    if valid_ors and current_or is not None:
        best_or = max(valid_ors)
        last_win_or = None
        for idx in range(len(wins) - 1, -1, -1):
            if wins[idx] and ors[idx] is not None:
                last_win_or = ors[idx]
                break
        if last_win_or is not None:
            delta = current_or - last_win_or
            features["curr_or_minus_last_win_or"] = float(delta)
        features["curr_or_minus_best_or"] = float(current_or - best_or)
        if best_or > 0:
            features["mark_compression_score"] = float((best_or - current_or) / best_or)

    rsw = features["runs_since_win"]
    mc = features["mark_compression_score"]
    if 3.0 <= rsw <= 10.0 and mc > 0.05:
        features["release_window_score"] = float(min(1.0, mc * 5.0))

    same_course = [(wins[idx], places[idx]) for idx in range(len(horse_prior_rows)) if courses[idx] == current_course]
    same_going = [(wins[idx], places[idx]) for idx in range(len(horse_prior_rows)) if goings[idx] == current_going_bucket]
    same_distance = [
        (wins[idx], places[idx])
        for idx in range(len(horse_prior_rows))
        if current_distance is not None
        and distances[idx] is not None
        and abs(distances[idx] - current_distance) <= current_distance * 0.2
    ]

    if same_course:
        features["course_fit_score"] = float(sum(win + place for win, place in same_course) / len(same_course))
    if same_going:
        features["going_fit_score"] = float(sum(win + place for win, place in same_going) / len(same_going))
    if same_distance:
        features["distance_fit_score"] = float(sum(win + place for win, place in same_distance) / len(same_distance))

    if ovr_btns and ovr_btns[-1] > 12.0:
        features["quiet_run_score"] = float(min(1.0, (ovr_btns[-1] - 12.0) / 20.0))

    if trainer_prior_rows:
        trainer_wins = sum(1 for row in trainer_prior_rows if parse_position(row.get("pos")) == 1)
        trainer_starts = len(trainer_prior_rows)
        if trainer_starts > 0:
            features["trainer_timing_score"] = float(trainer_wins / trainer_starts)

    if jockeys and current_jockey and jockeys[-1] and jockeys[-1] != current_jockey:
        features["jockey_switch_intent"] = 1.0

    recent_sps = [sp for sp in sps[-3:] if sp is not None]
    if len(recent_sps) >= 2:
        mean_sp = sum(recent_sps) / len(recent_sps)
        variance = sum((sp - mean_sp) ** 2 for sp in recent_sps) / len(recent_sps)
        features["odds_resilience_score"] = float(math.sqrt(variance))

    valid_sps = [sp for sp in sps if sp is not None]
    if valid_sps:
        last_sp = valid_sps[-1]
        if last_sp > 0:
            features["odds_contraction_score"] = float((last_sp - current_sp) / last_sp)

    if is_fav and features["trainer_timing_score"] < 0.08:
        features["decoy_support_flag"] = 1.0
    if ovr_btns and ovr_btns[-1] > 15.0:
        features["setup_run_flag"] = 1.0
    if (
        features["trainer_timing_score"] > 0.15
        and 3.0 <= features["runs_since_win"] <= 6.0
        and features["mark_compression_score"] > 0.0
    ):
        features["cash_run_flag"] = 1.0

    features["_coverage"] = {
        "prior_run_count": len(horse_prior_rows),
        "prior_1_plus": len(horse_prior_rows) >= 1,
        "prior_3_plus": len(horse_prior_rows) >= 3,
        "trainer_prior_run_count": len(trainer_prior_rows),
    }
    return features


def build_prior_history_context(
    horse_id: str,
    horse_name: str,
    race_date: str,
    *,
    race_context: dict[str, Any],
    horse_history_rows: Sequence[dict[str, Any]] | None = None,
    trainer_history_rows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    horse_prior_rows = rows_strictly_before(horse_history_rows or [], race_date)
    trainer_prior_rows = rows_strictly_before(trainer_history_rows or [], race_date)
    doctrine = compute_doctrine_features_from_prior_history(
        horse_prior_rows=horse_prior_rows,
        trainer_prior_rows=trainer_prior_rows,
        race_context=race_context,
    )
    return {
        "horse_id": horse_id,
        "horse_name": horse_name,
        "race_date": race_date,
        "contract": HISTORICAL_DOCTRINE_CONTRACT,
        "source": DOCTRINE_SOURCE,
        "cutoff_rule": DOCTRINE_CUTOFF_RULE,
        "doctrine_features": {name: doctrine[name] for name in DOCTRINE_FEATURE_NAMES},
        "coverage": doctrine.get("_coverage", {}),
    }
