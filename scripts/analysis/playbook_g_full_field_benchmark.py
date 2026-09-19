#!/usr/bin/env python3
"""Chronological, full-field Playbook G benchmark.

This is an analysis-only harness. It reads historical runner snapshots and
settled RP results, evaluates the base field before outcomes are observed,
applies Playbook G counterfactually to every runner, renormalises the field,
and only then evolves a fresh disposable state for the next race day.

It never writes data/sentient_state.json or data/sentient_state_shadow.json.
All output goes to an explicit --output-dir.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTAMINATED_RUN_MARKERS = {"32cc27f9", "847964a6"}
LONDON = ZoneInfo("Europe/London")
EPSILON = 1e-12


def _norm_name(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(
        r"\s*\((gb|ire|fr|usa|ger|ity|aus|nz|saf|jpn|can|spa|swe|den|nor|bel|hol|pol|cze|hun|brz|arg|chi|uae|qat|ksa|tur)\)\s*$",
        "",
        text,
    )
    return re.sub(r"[^a-z0-9]", "", text)


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _settled_decimal(value: Any) -> float | None:
    number = _safe_float(value)
    if number is not None:
        return number if number > 1.0 else None
    text = str(value or "").strip().lower()
    if text in {"evens", "evensf", "evs", "evsf", "even", "evenf"}:
        return 2.0
    cleaned = re.sub(r"[^0-9./]", "", text)
    try:
        if "/" in cleaned:
            numerator, denominator = cleaned.split("/", 1)
            number = float(numerator) / float(denominator) + 1.0
        else:
            number = float(cleaned)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return number if math.isfinite(number) and number > 1.0 else None


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LONDON)
    return parsed


def _off_datetime(race_date: str, off_time: Any) -> datetime | None:
    match = re.fullmatch(r"\s*(\d{1,2})[.:](\d{2})\s*", str(off_time or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour < 11:
        hour += 12
    try:
        return datetime.fromisoformat(f"{race_date}T{hour:02d}:{minute:02d}:00").replace(tzinfo=LONDON)
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def select_latest_pre_off_fields(
    data_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Select one latest, strictly pre-off, complete snapshot run per race."""
    run_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    diagnostics = defaultdict(int)

    for path in sorted(data_dir.glob("runner_snapshots_*.jsonl")):
        diagnostics["snapshot_files_seen"] += 1
        for row in _read_jsonl(path):
            diagnostics["snapshot_rows_seen"] += 1
            race_date = str(row.get("race_date") or "")
            if start_date and race_date < start_date:
                continue
            if end_date and race_date > end_date:
                continue
            run_id = str(row.get("run_id") or path.stem)
            if any(marker in run_id for marker in CONTAMINATED_RUN_MARKERS):
                diagnostics["rows_contaminated_run"] += 1
                continue
            if row.get("live_scoring_changed") is True:
                diagnostics["rows_live_scoring_changed"] += 1
                continue
            race_id = str(row.get("race_id") or "")
            if not race_id or not race_date:
                diagnostics["rows_missing_identity"] += 1
                continue
            run_groups[(race_id, run_id)].append(row)

    eligible_by_race: dict[str, list[tuple[datetime, list[dict[str, Any]]]]] = defaultdict(list)
    for (race_id, _run_id), rows in run_groups.items():
        diagnostics["candidate_race_runs"] += 1
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("horse_id") or _norm_name(row.get("horse")))
            if key:
                unique[key] = row
        field = list(unique.values())
        if len(field) < 3:
            diagnostics["race_runs_too_small"] += 1
            continue
        created = _parse_created_at(field[0].get("created_at"))
        off = _off_datetime(str(field[0].get("race_date") or ""), field[0].get("off_time"))
        if created is None or off is None:
            diagnostics["race_runs_missing_exact_time"] += 1
            continue
        if created >= off:
            diagnostics["race_runs_post_off"] += 1
            continue
        eligible_by_race[race_id].append((created, field))

    selected: dict[str, list[dict[str, Any]]] = {}
    for race_id, candidates in eligible_by_race.items():
        candidates.sort(key=lambda item: item[0])
        selected[race_id] = candidates[-1][1]
        diagnostics["races_selected"] += 1
        diagnostics["superseded_pre_off_runs"] += max(0, len(candidates) - 1)
    return selected, dict(diagnostics)


def _load_results_file(data_dir: Path, race_date: str) -> list[dict[str, Any]]:
    tag = race_date.replace("-", "_")
    candidates = [
        data_dir / "results" / f"rp_results_{tag}.json",
        data_dir / f"results_{tag}.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("results", []) if isinstance(payload, dict) else payload
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _norm_off(value: Any) -> str:
    text = str(value or "").strip().replace(":", ".")
    match = re.fullmatch(r"(\d{1,2})\.(\d{2})", text)
    if not match:
        return text
    return f"{int(match.group(1))}.{match.group(2)}"


def _result_lookup(data_dir: Path, race_dates: set[str]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for race_date in sorted(race_dates):
        for race in _load_results_file(data_dir, race_date):
            race_id = str(race.get("race_id") or race.get("id") or "")
            if race_id:
                lookup[f"id:{race_id}"] = race
            course = _norm_name(race.get("course") or race.get("venue"))
            off = _norm_off(race.get("off") or race.get("off_time"))
            if course and off:
                lookup[f"fallback:{race_date}:{course}:{off}"] = race
    return lookup


def _find_result(field: list[dict[str, Any]], lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    first = field[0]
    race_id = str(first.get("race_id") or "")
    direct = lookup.get(f"id:{race_id}")
    if direct:
        return direct
    key = (
        f"fallback:{first.get('race_date')}:{_norm_name(first.get('course'))}:"
        f"{_norm_off(first.get('off_time'))}"
    )
    return lookup.get(key)


def _winner_facts(result: dict[str, Any]) -> dict[str, Any] | None:
    runners = [r for r in (result.get("runners") or []) if isinstance(r, dict)]
    winners = [r for r in runners if str(r.get("position") or "").strip() == "1"]
    winner = winners[0] if len(winners) == 1 else {}
    winner_id = str(
        winner.get("horse_rp_uid")
        or winner.get("horse_id")
        or result.get("winner_rp_uid")
        or result.get("winner_id")
        or ""
    )
    winner_name = str(winner.get("horse") or result.get("winner_horse") or result.get("winner_name") or "")
    winner_sp = _settled_decimal(winner.get("sp_dec") or winner.get("sp") or result.get("winner_sp"))
    if not (winner_id or winner_name) or winner_sp is None:
        return None

    priced = []
    for runner in runners:
        if runner.get("non_runner"):
            continue
        sp = _settled_decimal(runner.get("sp_dec") or runner.get("sp"))
        if sp is not None:
            priced.append((sp, runner))
    favourite = min(priced, key=lambda item: item[0])[1] if priced else {}
    favourite_id = str(favourite.get("horse_rp_uid") or favourite.get("horse_id") or "")
    favourite_name = _norm_name(favourite.get("horse"))
    favourite_won = bool(
        (winner_id and favourite_id and winner_id == favourite_id)
        or (winner_name and favourite_name and _norm_name(winner_name) == favourite_name)
    )

    profile: dict[str, Any] = {}
    style = winner.get("running_style") or winner.get("run_style")
    if style:
        profile["running_style"] = style
    try:
        if winner.get("draw") not in (None, ""):
            profile["draw"] = int(str(winner["draw"]).strip())
    except (TypeError, ValueError):
        pass
    for field_name in ("was_hidden_improver", "late_money"):
        if field_name in winner:
            profile[field_name] = bool(winner[field_name])

    return {
        "winner_id": winner_id,
        "winner_name": winner_name,
        "winner_sp": winner_sp,
        "favourite_won": favourite_won,
        "winner_profile": profile,
    }


def _winner_index(field: list[dict[str, Any]], facts: dict[str, Any]) -> int | None:
    id_matches = []
    name_matches = []
    for index, row in enumerate(field):
        horse_id = str(row.get("horse_id") or "")
        if facts["winner_id"] and horse_id and horse_id == facts["winner_id"]:
            id_matches.append(index)
        if facts["winner_name"] and _norm_name(row.get("horse")) == _norm_name(facts["winner_name"]):
            name_matches.append(index)
    matches = id_matches or name_matches
    return matches[0] if len(matches) == 1 else None


def _normalise_probabilities(values: list[float | None]) -> list[float] | None:
    clean = [max(0.0, value or 0.0) for value in values]
    total = sum(clean)
    if total <= 0.0:
        return None
    return [value / total for value in clean]


def _production_g_adjustment(
    row: dict[str, Any],
    state: dict[str, Any],
    is_favourite: bool,
) -> tuple[float, list[str]]:
    from src.intelligence import velo_prime_ensemble as ensemble

    previous_state = ensemble._G_STATE
    ensemble._G_STATE = state
    try:
        multiplier, _flags, doctrines, _pain_horse = ensemble._g_shadow_adjustment(
            market_deception_score=_safe_float(row.get("market_deception_score")),
            is_fav=is_favourite,
            sp_dec=_safe_float(row.get("sp_dec")),
            horse_id=str(row.get("horse_id") or ""),
            doctrine_strengths=state.get("doctrine_strengths", {}),
            appetite_state=state.get("appetite_state", {}),
            emotion_laws=state.get("emotion_laws", {}),
        )
    finally:
        ensemble._G_STATE = previous_state
    return float(multiplier), list(doctrines)


def _field_favourite_indexes(field: list[dict[str, Any]]) -> set[int]:
    prices = [(_safe_float(row.get("sp_dec")), index) for index, row in enumerate(field)]
    prices = [(price, index) for price, index in prices if price is not None and price > 1.0]
    if not prices:
        return set()
    minimum = min(price for price, _index in prices)
    return {index for price, index in prices if price == minimum}


def evaluate_field(
    field: list[dict[str, Any]],
    result: dict[str, Any],
    state: dict[str, Any],
    adjuster: Callable[[dict[str, Any], dict[str, Any], bool], tuple[float, list[str]]] = _production_g_adjustment,
) -> dict[str, Any] | None:
    facts = _winner_facts(result)
    if facts is None:
        return None
    winner_index = _winner_index(field, facts)
    if winner_index is None:
        return None

    base = _normalise_probabilities([
        _safe_float(row.get("velo_prime_prob") or row.get("g_base_prob")) for row in field
    ])
    if base is None:
        return None

    favourites = _field_favourite_indexes(field)
    multipliers: list[float] = []
    doctrines: list[list[str]] = []
    for index, row in enumerate(field):
        multiplier, fired = adjuster(row, state, index in favourites)
        multipliers.append(multiplier)
        doctrines.append(fired)
    adjusted = _normalise_probabilities([
        prob * mult for prob, mult in zip(base, multipliers, strict=True)
    ])
    if adjusted is None:
        return None

    market_prices = [_settled_decimal(row.get("sp_dec")) for row in field]
    market = (
        _normalise_probabilities([1.0 / price for price in market_prices])
        if all(price is not None for price in market_prices)
        else None
    )

    base_order = sorted(range(len(field)), key=lambda idx: base[idx], reverse=True)
    g_order = sorted(range(len(field)), key=lambda idx: adjusted[idx], reverse=True)
    base_top = base_order[0]
    g_top = g_order[0]
    winner_sp = facts["winner_sp"]

    runners = []
    for index, row in enumerate(field):
        runners.append({
            "horse": row.get("horse"),
            "horse_id": row.get("horse_id"),
            "base_prob": base[index],
            "g_prob": adjusted[index],
            "market_prob": market[index] if market is not None else None,
            "g_multiplier": multipliers[index],
            "doctrines_fired": doctrines[index],
            "is_winner": index == winner_index,
        })

    evaluated = {
        "race_id": str(field[0].get("race_id") or ""),
        "race_date": str(field[0].get("race_date") or ""),
        "course": field[0].get("course"),
        "off_time": field[0].get("off_time"),
        "field_size": len(field),
        "winner_index": winner_index,
        "winner_name": facts["winner_name"],
        "winner_sp": winner_sp,
        "base_top_index": base_top,
        "g_top_index": g_top,
        "base_top_name": field[base_top].get("horse"),
        "g_top_name": field[g_top].get("horse"),
        "base_won": base_top == winner_index,
        "g_won": g_top == winner_index,
        "base_top3": winner_index in base_order[:3],
        "g_top3": winner_index in g_order[:3],
        "pick_changed": base_top != g_top,
        "base_log_loss": -math.log(max(base[winner_index], EPSILON)),
        "g_log_loss": -math.log(max(adjusted[winner_index], EPSILON)),
        "base_brier": sum((prob - (1.0 if index == winner_index else 0.0)) ** 2 for index, prob in enumerate(base)),
        "g_brier": sum((prob - (1.0 if index == winner_index else 0.0)) ** 2 for index, prob in enumerate(adjusted)),
        "base_pnl": winner_sp - 1.0 if base_top == winner_index else -1.0,
        "g_pnl": winner_sp - 1.0 if g_top == winner_index else -1.0,
        "base_top_doctrines": doctrines[base_top],
        "winner_facts": facts,
        "runners": runners,
        "source_field": field,
    }
    if market is not None:
        market_order = sorted(range(len(field)), key=lambda idx: market[idx], reverse=True)
        market_top = market_order[0]
        evaluated.update({
            "market_top_index": market_top,
            "market_top_name": field[market_top].get("horse"),
            "market_won": market_top == winner_index,
            "market_top3": winner_index in market_order[:3],
            "market_log_loss": -math.log(max(market[winner_index], EPSILON)),
            "market_brier": sum(
                (prob - (1.0 if index == winner_index else 0.0)) ** 2
                for index, prob in enumerate(market)
            ),
            "market_pnl": winner_sp - 1.0 if market_top == winner_index else -1.0,
        })
    return evaluated


def _ece(races: list[dict[str, Any]], probability_key: str, bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    observations = []
    for race in races:
        for runner in race["runners"]:
            probability = runner.get(probability_key)
            if probability is not None:
                observations.append((float(probability), int(runner["is_winner"])))
    if not observations:
        return math.nan, []
    curve = []
    ece = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [(prob, won) for prob, won in observations if lower <= prob < upper or (index == bins - 1 and prob == 1.0)]
        if not bucket:
            continue
        predicted = statistics.fmean(prob for prob, _won in bucket)
        observed = statistics.fmean(won for _prob, won in bucket)
        weight = len(bucket) / len(observations)
        ece += weight * abs(predicted - observed)
        curve.append({
            "bucket": f"{lower:.1f}-{upper:.1f}",
            "n": len(bucket),
            "predicted_mean": predicted,
            "observed_rate": observed,
        })
    return ece, curve


def _variant_metrics(races: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    races = [race for race in races if f"{prefix}_won" in race]
    n = len(races)
    if not n:
        return {}
    ece, curve = _ece(races, f"{prefix}_prob")
    return {
        "races": n,
        "top1_accuracy": statistics.fmean(float(race[f"{prefix}_won"]) for race in races),
        "top3_accuracy": statistics.fmean(float(race[f"{prefix}_top3"]) for race in races),
        "multiclass_log_loss": statistics.fmean(race[f"{prefix}_log_loss"] for race in races),
        "multiclass_brier": statistics.fmean(race[f"{prefix}_brier"] for race in races),
        "flat_stake_roi": statistics.fmean(race[f"{prefix}_pnl"] for race in races),
        "flat_stake_profit": sum(race[f"{prefix}_pnl"] for race in races),
        "ece": ece,
        "calibration_curve": curve,
    }


def _paired_bootstrap(races: list[dict[str, Any]], samples: int) -> dict[str, list[float]]:
    if not races or samples <= 0:
        return {}
    rng = random.Random(1981)
    deltas = {"top1_accuracy": [], "multiclass_log_loss": [], "multiclass_brier": [], "flat_stake_roi": []}
    for _ in range(samples):
        sample = [races[rng.randrange(len(races))] for _index in range(len(races))]
        deltas["top1_accuracy"].append(
            statistics.fmean(float(race["g_won"]) - float(race["base_won"]) for race in sample)
        )
        deltas["multiclass_log_loss"].append(
            statistics.fmean(race["g_log_loss"] - race["base_log_loss"] for race in sample)
        )
        deltas["multiclass_brier"].append(
            statistics.fmean(race["g_brier"] - race["base_brier"] for race in sample)
        )
        deltas["flat_stake_roi"].append(
            statistics.fmean(race["g_pnl"] - race["base_pnl"] for race in sample)
        )

    intervals = {}
    for metric, values in deltas.items():
        values.sort()
        low = values[max(0, int(0.025 * (len(values) - 1)))]
        high = values[min(len(values) - 1, int(0.975 * (len(values) - 1)))]
        intervals[metric] = [low, high]
    return intervals


def _fresh_engine():
    from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

    engine = object.__new__(SentientLoopbackEngine)
    engine.state_file = "DISPOSABLE_ANALYSIS_ONLY"
    engine.disable_cloud_backup = True
    engine.state = engine._initialize_state()
    engine._save_state = lambda: None
    return engine


def _identity_pair(top: dict[str, Any], facts: dict[str, Any]) -> tuple[str, str] | None:
    top_id = str(top.get("horse_id") or "")
    winner_id = str(facts.get("winner_id") or "")
    if top_id and winner_id:
        return top_id, winner_id
    top_name = str(top.get("horse") or "")
    winner_name = str(facts.get("winner_name") or "")
    if top_name and winner_name:
        return top_name, winner_name
    return None


def _replay_race(engine, race: dict[str, Any]) -> bool:
    top_index = race["base_top_index"]
    top = race["source_field"][top_index]
    facts = race["winner_facts"]
    identities = _identity_pair(top, facts)
    if identities is None:
        return False
    predicted, actual = identities
    engine.observe_race_outcome(
        {
            "race_id": race["race_id"],
            "mpi": float(race["runners"][top_index]["base_prob"]) * 100.0,
            "chaos_bloom": 0.0,
            "story_anchor": "favourite" if facts["favourite_won"] else "non-favourite",
            "power_anchor": predicted,
            "runners": [],
        },
        {
            "power_anchor": predicted,
            "confidence": float(race["runners"][top_index]["base_prob"]),
            "doctrines_fired": race["base_top_doctrines"],
        },
        {
            "winner": actual,
            "sp": facts["winner_sp"],
            "favourite_won": facts["favourite_won"],
            "winner_profile": facts["winner_profile"],
        },
    )
    return True


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_races_observed": state.get("total_races_observed", 0),
        "doctrine_strengths": state.get("doctrine_strengths", {}),
        "appetite_state": state.get("appetite_state", {}),
        "structural_weights": state.get("structural_weights", {}),
        "emotion_rule_counts": {
            key: len(value) for key, value in (state.get("emotion_laws") or {}).items()
        },
    }


def _promotion_readout(races: list[dict[str, Any]], base: dict[str, Any], g: dict[str, Any]) -> str:
    changes = sum(int(race["pick_changed"]) for race in races)
    if len(races) < 200:
        return "INSUFFICIENT_RACES"
    if changes < 50:
        return "INSUFFICIENT_PICK_CHANGES"
    if (
        g["top1_accuracy"] <= base["top1_accuracy"]
        and g["multiclass_log_loss"] >= base["multiclass_log_loss"]
        and g["multiclass_brier"] >= base["multiclass_brier"]
    ):
        return "G_HARMS_FORECAST"
    if (
        g["top1_accuracy"] > base["top1_accuracy"]
        and g["multiclass_log_loss"] < base["multiclass_log_loss"]
        and g["multiclass_brier"] < base["multiclass_brier"]
    ):
        return "PROMISING_SHADOW_ONLY"
    return "NO_CLEAR_EDGE"


def run_benchmark(
    data_dir: Path,
    output_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    bootstrap_samples: int = 1000,
) -> dict[str, Any]:
    selected, selection_diagnostics = select_latest_pre_off_fields(data_dir, start_date, end_date)
    race_dates = {str(field[0].get("race_date") or "") for field in selected.values() if field}
    result_lookup = _result_lookup(data_dir, race_dates)
    engine = _fresh_engine()

    selected_by_date: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for field in selected.values():
        selected_by_date[str(field[0].get("race_date") or "")].append(field)

    evaluated: list[dict[str, Any]] = []
    skipped = defaultdict(int)
    replayed = 0
    for race_date in sorted(selected_by_date):
        day_races = []
        for field in sorted(selected_by_date[race_date], key=lambda rows: _norm_off(rows[0].get("off_time"))):
            result = _find_result(field, result_lookup)
            if result is None:
                skipped["result_not_found"] += 1
                continue
            race = evaluate_field(field, result, engine.state)
            if race is None:
                skipped["field_or_winner_not_evaluable"] += 1
                continue
            evaluated.append(race)
            day_races.append(race)

        # Critical time boundary: the whole day is scored before any result from
        # that day is allowed to evolve state.
        for race in sorted(day_races, key=lambda item: _norm_off(item.get("off_time"))):
            replayed += int(_replay_race(engine, race))

    base_metrics = _variant_metrics(evaluated, "base")
    g_metrics = _variant_metrics(evaluated, "g")
    market_metrics = _variant_metrics(evaluated, "market")
    market_races = [race for race in evaluated if "market_won" in race]
    base_on_market_races = _variant_metrics(market_races, "base")
    g_on_market_races = _variant_metrics(market_races, "g")
    paired_intervals = _paired_bootstrap(evaluated, bootstrap_samples)
    pick_changes = sum(int(race["pick_changed"]) for race in evaluated)
    changed_wins = sum(int(race["g_won"]) for race in evaluated if race["pick_changed"])
    changed_base_wins = sum(int(race["base_won"]) for race in evaluated if race["pick_changed"])

    current_state_summary = None
    current_state_path = data_dir / "sentient_state.json"
    if current_state_path.exists():
        try:
            current_state_summary = _state_summary(json.loads(current_state_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            current_state_summary = None

    uniform_metrics = {
        "races": len(evaluated),
        "multiclass_log_loss": (
            statistics.fmean(math.log(race["field_size"]) for race in evaluated)
            if evaluated else None
        ),
        "multiclass_brier": (
            statistics.fmean(1.0 - (1.0 / race["field_size"]) for race in evaluated)
            if evaluated else None
        ),
    }
    base_worse_than_uniform = bool(
        evaluated
        and base_metrics["multiclass_log_loss"] > uniform_metrics["multiclass_log_loss"]
        and base_metrics["multiclass_brier"] > uniform_metrics["multiclass_brier"]
    )
    market_dominates_same_races = bool(
        market_races
        and market_metrics["top1_accuracy"] > g_on_market_races["top1_accuracy"]
        and market_metrics["multiclass_log_loss"] < g_on_market_races["multiclass_log_loss"]
        and market_metrics["multiclass_brier"] < g_on_market_races["multiclass_brier"]
    )
    significant_g_metrics = [
        metric for metric, (low, high) in paired_intervals.items()
        if (metric in {"multiclass_log_loss", "multiclass_brier"} and high < 0)
        or (metric in {"top1_accuracy", "flat_stake_roi"} and low > 0)
    ]

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "classification": "ANALYSIS_ONLY",
        "data_dir": str(data_dir.resolve()),
        "date_range": {"start": start_date, "end": end_date},
        "time_contract": "latest snapshot strictly before exact race off; no date-only fallback",
        "state_contract": "fresh state; evaluate complete day before replaying that day's outcomes",
        "selection_diagnostics": selection_diagnostics,
        "skipped": dict(skipped),
        "races_evaluated": len(evaluated),
        "runner_rows_evaluated": sum(race["field_size"] for race in evaluated),
        "outcomes_replayed": replayed,
        "pick_changes": pick_changes,
        "pick_change_rate": pick_changes / len(evaluated) if evaluated else 0.0,
        "changed_pick_base_wins": changed_base_wins,
        "changed_pick_g_wins": changed_wins,
        "base": base_metrics,
        "playbook_g": g_metrics,
        "market_implied": market_metrics,
        "same_race_market_comparison": {
            "races": len(market_races),
            "base": base_on_market_races,
            "playbook_g": g_on_market_races,
            "market_implied": market_metrics,
        },
        "uniform_probability_baseline": uniform_metrics,
        "delta_g_minus_base": {
            key: g_metrics.get(key, math.nan) - base_metrics.get(key, math.nan)
            for key in ("top1_accuracy", "top3_accuracy", "multiclass_log_loss", "multiclass_brier", "flat_stake_roi", "ece")
        } if evaluated else {},
        "paired_bootstrap_95pct_delta_intervals": paired_intervals,
        "promotion_readout": _promotion_readout(evaluated, base_metrics, g_metrics) if evaluated else "NO_EVIDENCE",
        "forecast_truth_readout": {
            "base_vs_uniform": (
                "BASE_WORSE_THAN_UNIFORM_PROPER_SCORES"
                if base_worse_than_uniform else "BASE_BEATS_UNIFORM_ON_AT_LEAST_ONE_PROPER_SCORE"
            ),
            "g_statistically_clear_metrics": significant_g_metrics,
            "g_selection_evidence": (
                "INSUFFICIENT_PICK_CHANGES" if pick_changes < 50 else "SELECTION_SAMPLE_REVIEWABLE"
            ),
            "market_same_race": (
                "MARKET_DOMINATES_TOP1_LOGLOSS_BRIER"
                if market_dominates_same_races else "MARKET_NOT_DOMINANT_ON_ALL_CORE_METRICS"
            ),
        },
        "clean_shadow_state_summary": _state_summary(engine.state),
        "current_state_summary_read_only": current_state_summary,
        "safety": {
            "live_state_written": False,
            "canonical_shadow_state_written": False,
            "supabase_writes": False,
            "model_weights_changed": False,
            "production_scoring_changed": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "playbook_g_full_field_benchmark.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "clean_shadow_state.json").write_text(
        json.dumps(engine.state, indent=2, allow_nan=False), encoding="utf-8"
    )

    with (output_dir / "race_level_counterfactuals.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "race_date", "race_id", "course", "off_time", "field_size", "winner_name", "winner_sp",
            "base_top_name", "g_top_name", "market_top_name", "pick_changed", "base_won", "g_won", "market_won",
            "base_log_loss", "g_log_loss", "market_log_loss", "base_brier", "g_brier", "market_brier",
            "base_pnl", "g_pnl", "market_pnl",
        ])
        writer.writeheader()
        for race in evaluated:
            writer.writerow({key: race.get(key) for key in writer.fieldnames})

    md = [
        "# Playbook G Full-Field Benchmark",
        "",
        "- Classification: **ANALYSIS ONLY**",
        f"- Races: **{len(evaluated)}**; runners: **{summary['runner_rows_evaluated']}**",
        f"- Pick changes: **{pick_changes} ({summary['pick_change_rate']:.1%})**",
        f"- Readout: **{summary['promotion_readout']}**",
        f"- Calibration truth: **{summary['forecast_truth_readout']['base_vs_uniform']}**",
        "",
        "## Metrics",
        "",
        "| Variant | N races | Top-1 | Top-3 | Log loss | Brier | Flat ROI | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in (("Base", base_metrics), ("Playbook G", g_metrics), ("Market implied", market_metrics)):
        md.append(
            f"| {label} | {metrics.get('races', 0)} | {metrics.get('top1_accuracy', 0):.2%} | "
            f"{metrics.get('top3_accuracy', 0):.2%} | "
            f"{metrics.get('multiclass_log_loss', 0):.4f} | {metrics.get('multiclass_brier', 0):.4f} | "
            f"{metrics.get('flat_stake_roi', 0):.2%} | {metrics.get('ece', 0):.4f} |"
        )
    md.extend([
        "",
        "## Uniform probability check",
        "",
        f"Uniform field probabilities: log loss **{uniform_metrics['multiclass_log_loss']:.4f}**, "
        f"Brier **{uniform_metrics['multiclass_brier']:.4f}**. Lower is better.",
        "",
        f"## Same-race market comparison ({len(market_races)} races)",
        "",
        "| Variant | Top-1 | Log loss | Brier | Flat ROI | ECE |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for label, metrics in (
        ("Base", base_on_market_races),
        ("Playbook G", g_on_market_races),
        ("Market implied", market_metrics),
    ):
        md.append(
            f"| {label} | {metrics.get('top1_accuracy', 0):.2%} | "
            f"{metrics.get('multiclass_log_loss', 0):.4f} | {metrics.get('multiclass_brier', 0):.4f} | "
            f"{metrics.get('flat_stake_roi', 0):.2%} | {metrics.get('ece', 0):.4f} |"
        )
    md.extend([
        "",
        "## Safety and interpretation",
        "",
        "The harness selects the latest snapshot strictly before exact off time, evaluates every runner, "
        "renormalises probabilities inside each race, and evolves a fresh disposable state only after the "
        "entire day's forecasts have been evaluated. It does not authorize promotion or change live scoring.",
    ])
    (output_dir / "playbook_g_full_field_benchmark.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    args = parser.parse_args()

    summary = run_benchmark(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(json.dumps({
        "races_evaluated": summary["races_evaluated"],
        "pick_changes": summary["pick_changes"],
        "promotion_readout": summary["promotion_readout"],
        "output_dir": str(args.output_dir.resolve()),
    }, indent=2))
    return 0 if summary["races_evaluated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
