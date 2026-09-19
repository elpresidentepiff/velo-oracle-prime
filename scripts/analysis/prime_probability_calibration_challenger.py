#!/usr/bin/env python3
"""Leak-free chronological probability calibration challenger.

Fits simple race-normalised transforms on an early block, selects challengers
on a later calibration block, then evaluates an untouched final holdout. The
separate market track uses only races with complete late pre-off prices.

This is analysis only. It never changes production scoring, models, weights,
or canonical state. All artifacts go beneath an explicit ``--output-dir``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.playbook_g_full_field_benchmark import (  # noqa: E402
    EPSILON,
    _find_result,
    _fresh_engine,
    _norm_off,
    _replay_race,
    _result_lookup,
    evaluate_field,
    select_latest_pre_off_fields,
)

ProbabilityProvider = Callable[[dict[str, Any]], list[float] | None]


def power_transform(probabilities: list[float], beta: float) -> list[float]:
    """Apply a race-level power/temperature transform and renormalise."""
    powered = [max(float(probability), EPSILON) ** beta for probability in probabilities]
    total = sum(powered)
    return [value / total for value in powered]


def geometric_blend(model: list[float], market: list[float], alpha: float) -> list[float]:
    """Geometrically pool model and market probabilities inside one race."""
    pooled = [
        max(model_prob, EPSILON) ** (1.0 - alpha) * max(market_prob, EPSILON) ** alpha
        for model_prob, market_prob in zip(model, market, strict=True)
    ]
    total = sum(pooled)
    return [value / total for value in pooled]


def _source_probabilities(race: dict[str, Any], source: str) -> list[float] | None:
    values = [runner.get(f"{source}_prob") for runner in race["runners"]]
    if not values or any(value is None for value in values):
        return None
    probabilities = [max(float(value), 0.0) for value in values]
    total = sum(probabilities)
    return [value / total for value in probabilities] if total > 0.0 else None


def provider_from_spec(spec: dict[str, Any]) -> ProbabilityProvider:
    kind = spec["kind"]
    source = spec.get("source", "base")
    beta = float(spec.get("beta", 1.0))
    alpha = float(spec.get("alpha", 0.0))

    def provider(race: dict[str, Any]) -> list[float] | None:
        if kind == "market":
            return _source_probabilities(race, "market")
        model = _source_probabilities(race, source)
        if model is None:
            return None
        calibrated = power_transform(model, beta)
        if kind == "temperature":
            return calibrated
        if kind == "market_blend":
            market = _source_probabilities(race, "market")
            return geometric_blend(calibrated, market, alpha) if market is not None else None
        raise ValueError(f"Unsupported probability specification: {kind}")

    return provider


def _ece(rows: list[dict[str, Any]], bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    observations = [item for row in rows for item in row["observations"]]
    curve = []
    ece = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [
            (probability, won)
            for probability, won in observations
            if lower <= probability < upper or (index == bins - 1 and probability == 1.0)
        ]
        if not bucket:
            continue
        predicted = statistics.fmean(probability for probability, _won in bucket)
        observed = statistics.fmean(won for _probability, won in bucket)
        weight = len(bucket) / len(observations)
        ece += weight * abs(predicted - observed)
        curve.append(
            {
                "bucket": f"{lower:.1f}-{upper:.1f}",
                "n": len(bucket),
                "predicted_mean": predicted,
                "observed_rate": observed,
            }
        )
    return ece, curve


def score_variant(
    races: list[dict[str, Any]],
    provider: ProbabilityProvider,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for race in races:
        probabilities = provider(race)
        if probabilities is None:
            continue
        winner = int(race["winner_index"])
        order = sorted(range(len(probabilities)), key=lambda index: probabilities[index], reverse=True)
        top = order[0]
        winner_sp = float(race["winner_sp"])
        rows.append(
            {
                "race_id": race["race_id"],
                "race_date": race["race_date"],
                "course": race.get("course"),
                "off_time": race.get("off_time"),
                "winner_name": race.get("winner_name"),
                "top_name": race["runners"][top].get("horse"),
                "won": top == winner,
                "top3": winner in order[:3],
                "log_loss": -math.log(max(probabilities[winner], EPSILON)),
                "brier": sum(
                    (probability - (1.0 if index == winner else 0.0)) ** 2
                    for index, probability in enumerate(probabilities)
                ),
                "pnl": winner_sp - 1.0 if top == winner else -1.0,
                "observations": [
                    (probability, int(index == winner)) for index, probability in enumerate(probabilities)
                ],
            }
        )
    if not rows:
        return {}, []
    ece, curve = _ece(rows)
    return {
        "races": len(rows),
        "top1_accuracy": statistics.fmean(float(row["won"]) for row in rows),
        "top3_accuracy": statistics.fmean(float(row["top3"]) for row in rows),
        "multiclass_log_loss": statistics.fmean(row["log_loss"] for row in rows),
        "multiclass_brier": statistics.fmean(row["brier"] for row in rows),
        "flat_stake_roi": statistics.fmean(row["pnl"] for row in rows),
        "flat_stake_profit": sum(row["pnl"] for row in rows),
        "ece": ece,
        "calibration_curve": curve,
    }, rows


def split_chronologically(
    races: list[dict[str, Any]],
    train_fraction: float = 0.5,
    calibration_fraction: float = 0.25,
) -> dict[str, list[dict[str, Any]]]:
    """Split whole race days; no day may cross a boundary."""
    dates = sorted({str(race["race_date"]) for race in races})
    if len(dates) < 3:
        raise ValueError("At least three distinct race dates are required")
    train_end = max(1, min(len(dates) - 2, int(len(dates) * train_fraction)))
    calibration_end = max(
        train_end + 1,
        min(len(dates) - 1, int(len(dates) * (train_fraction + calibration_fraction))),
    )
    date_sets = {
        "train": set(dates[:train_end]),
        "calibration": set(dates[train_end:calibration_end]),
        "test": set(dates[calibration_end:]),
    }
    return {
        name: [race for race in races if str(race["race_date"]) in block_dates]
        for name, block_dates in date_sets.items()
    }


def _mean_log_loss(races: list[dict[str, Any]], provider: ProbabilityProvider) -> float:
    losses = []
    for race in races:
        probabilities = provider(race)
        if probabilities is not None:
            losses.append(-math.log(max(probabilities[int(race["winner_index"])], EPSILON)))
    return statistics.fmean(losses) if losses else math.inf


def fit_beta(races: list[dict[str, Any]], source: str) -> tuple[float, float]:
    scored = []
    for index in range(201):
        beta = index / 100
        spec = {"kind": "temperature", "source": source, "beta": beta}
        scored.append((_mean_log_loss(races, provider_from_spec(spec)), abs(beta - 1.0), beta))
    loss, _distance, beta = min(scored)
    return beta, loss


def fit_alpha(races: list[dict[str, Any]], source: str, beta: float) -> tuple[float, float]:
    scored = []
    for index in range(101):
        alpha = index / 100
        spec = {"kind": "market_blend", "source": source, "beta": beta, "alpha": alpha}
        scored.append((_mean_log_loss(races, provider_from_spec(spec)), abs(alpha), alpha))
    loss, _distance, alpha = min(scored)
    return alpha, loss


def _select_on_calibration(
    races: list[dict[str, Any]],
    specifications: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, dict[str, Any]]]:
    metrics = {
        label: score_variant(races, provider_from_spec(specification))[0]
        for label, specification in specifications.items()
    }
    selected = min(
        metrics,
        key=lambda label: (
            metrics[label].get("multiclass_log_loss", math.inf),
            metrics[label].get("multiclass_brier", math.inf),
            label,
        ),
    )
    return selected, metrics


def paired_bootstrap(
    challenger_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    samples: int,
) -> dict[str, list[float]]:
    if not challenger_rows or samples <= 0:
        return {}
    baseline_by_id = {row["race_id"]: row for row in baseline_rows}
    pairs = [(row, baseline_by_id[row["race_id"]]) for row in challenger_rows if row["race_id"] in baseline_by_id]
    if len(pairs) != len(challenger_rows):
        return {}
    rng = random.Random(1981)
    deltas = {"top1_accuracy": [], "multiclass_log_loss": [], "multiclass_brier": [], "flat_stake_roi": []}
    for _ in range(samples):
        sample = [pairs[rng.randrange(len(pairs))] for _index in range(len(pairs))]
        deltas["top1_accuracy"].append(statistics.fmean(float(a["won"]) - float(b["won"]) for a, b in sample))
        deltas["multiclass_log_loss"].append(statistics.fmean(a["log_loss"] - b["log_loss"] for a, b in sample))
        deltas["multiclass_brier"].append(statistics.fmean(a["brier"] - b["brier"] for a, b in sample))
        deltas["flat_stake_roi"].append(statistics.fmean(a["pnl"] - b["pnl"] for a, b in sample))
    intervals = {}
    for metric, values in deltas.items():
        values.sort()
        intervals[metric] = [
            values[max(0, int(0.025 * (len(values) - 1)))],
            values[min(len(values) - 1, int(0.975 * (len(values) - 1)))],
        ]
    return intervals


def load_historical_races(
    data_dir: Path,
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reuse strict pre-off selection and the benchmark's day-level state boundary."""
    selected, selection_diagnostics = select_latest_pre_off_fields(data_dir, start_date, end_date)
    race_dates = {str(field[0].get("race_date") or "") for field in selected.values() if field}
    result_lookup = _result_lookup(data_dir, race_dates)
    engine = _fresh_engine()
    selected_by_date: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for field in selected.values():
        selected_by_date[str(field[0].get("race_date") or "")].append(field)

    evaluated = []
    skipped = defaultdict(int)
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
        for race in sorted(day_races, key=lambda item: _norm_off(item.get("off_time"))):
            _replay_race(engine, race)
    return evaluated, {"selection": selection_diagnostics, "skipped": dict(skipped)}


def _block_summary(races: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({str(race["race_date"]) for race in races})
    return {
        "races": len(races),
        "dates": len(dates),
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "complete_market_races": sum(_source_probabilities(race, "market") is not None for race in races),
    }


def run_challenger(
    races: list[dict[str, Any]],
    output_dir: Path,
    bootstrap_samples: int = 1000,
    source_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks = split_chronologically(races)
    train, calibration, test = blocks["train"], blocks["calibration"], blocks["test"]

    base_beta, base_train_loss = fit_beta(train, "base")
    g_beta, g_train_loss = fit_beta(train, "g")
    model_specs = {
        "raw_base": {"kind": "temperature", "source": "base", "beta": 1.0},
        "base_temperature": {"kind": "temperature", "source": "base", "beta": base_beta},
        "g_temperature": {"kind": "temperature", "source": "g", "beta": g_beta},
    }
    selected_model, model_calibration_metrics = _select_on_calibration(calibration, model_specs)

    market_train = [race for race in train if _source_probabilities(race, "market") is not None]
    market_calibration = [race for race in calibration if _source_probabilities(race, "market") is not None]
    market_test = [race for race in test if _source_probabilities(race, "market") is not None]
    if not market_train or not market_calibration or not market_test:
        raise ValueError("Every chronological block requires complete-price market races")
    base_alpha, base_blend_train_loss = fit_alpha(market_train, "base", base_beta)
    g_alpha, g_blend_train_loss = fit_alpha(market_train, "g", g_beta)
    market_specs = {
        "late_market": {"kind": "market"},
        "base_late_market_blend": {
            "kind": "market_blend",
            "source": "base",
            "beta": base_beta,
            "alpha": base_alpha,
        },
        "g_late_market_blend": {
            "kind": "market_blend",
            "source": "g",
            "beta": g_beta,
            "alpha": g_alpha,
        },
    }
    selected_market, market_calibration_metrics = _select_on_calibration(market_calibration, market_specs)

    model_test_metrics, model_test_rows = {}, {}
    for label, specification in model_specs.items():
        metrics, rows = score_variant(test, provider_from_spec(specification))
        model_test_metrics[label], model_test_rows[label] = metrics, rows
    market_test_metrics, market_test_rows = {}, {}
    for label, specification in market_specs.items():
        metrics, rows = score_variant(market_test, provider_from_spec(specification))
        market_test_metrics[label], market_test_rows[label] = metrics, rows

    selected_model_metrics = model_test_metrics[selected_model]
    raw_base_metrics = model_test_metrics["raw_base"]
    if selected_model == "raw_base":
        model_readout = "RAW_BASE_REMAINS_CHAMPION"
    elif float(model_specs[selected_model].get("beta", 1.0)) <= 0.01:
        model_readout = "COLLAPSES_TO_UNIFORM_NO_RANKING_VALUE"
    elif (
        selected_model_metrics["multiclass_log_loss"] < raw_base_metrics["multiclass_log_loss"]
        and selected_model_metrics["multiclass_brier"] < raw_base_metrics["multiclass_brier"]
    ):
        model_readout = "CALIBRATION_CHALLENGER_BEATS_RAW_BASE_ON_HOLDOUT"
    else:
        model_readout = "CALIBRATION_SELECTION_DID_NOT_REPLICATE"

    selected_market_metrics = market_test_metrics[selected_market]
    late_market_metrics = market_test_metrics["late_market"]
    if selected_market == "late_market":
        market_readout = "LATE_MARKET_REMAINS_CHAMPION"
    elif (
        selected_market_metrics["multiclass_log_loss"] < late_market_metrics["multiclass_log_loss"]
        and selected_market_metrics["multiclass_brier"] < late_market_metrics["multiclass_brier"]
    ):
        market_readout = "BLEND_BEATS_LATE_MARKET_ON_HOLDOUT_PROPER_SCORES"
    else:
        market_readout = "MARKET_BLEND_SELECTION_DID_NOT_REPLICATE"

    uniform_test = {
        "races": len(test),
        "multiclass_log_loss": statistics.fmean(math.log(len(race["runners"])) for race in test),
        "multiclass_brier": statistics.fmean(1.0 - 1.0 / len(race["runners"]) for race in test),
    }
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "classification": "ANALYSIS_ONLY",
        "time_contract": "whole-day chronological train/calibration/test; final test untouched until lock",
        "market_contract": "latest strictly pre-off snapshot prices only; late-clock, not morning",
        "source_diagnostics": source_diagnostics or {},
        "blocks": {name: _block_summary(block) for name, block in blocks.items()},
        "fitted_on_train_only": {
            "base_beta": base_beta,
            "g_beta": g_beta,
            "base_alpha_to_late_market": base_alpha,
            "g_alpha_to_late_market": g_alpha,
            "train_objectives": {
                "base_temperature_log_loss": base_train_loss,
                "g_temperature_log_loss": g_train_loss,
                "base_market_blend_log_loss": base_blend_train_loss,
                "g_market_blend_log_loss": g_blend_train_loss,
            },
        },
        "selected_on_calibration_only": {
            "model_track": selected_model,
            "late_market_track": selected_market,
            "model_metrics": model_calibration_metrics,
            "late_market_metrics": market_calibration_metrics,
        },
        "untouched_test": {
            "model_track": model_test_metrics,
            "late_market_track": market_test_metrics,
            "uniform": uniform_test,
        },
        "readout": {
            "model_track": model_readout,
            "late_market_track": market_readout,
            "selected_model": selected_model,
            "selected_late_market": selected_market,
        },
        "paired_bootstrap_95pct": {
            "selected_model_minus_raw_base": paired_bootstrap(
                model_test_rows[selected_model], model_test_rows["raw_base"], bootstrap_samples
            ),
            "selected_market_minus_late_market": paired_bootstrap(
                market_test_rows[selected_market], market_test_rows["late_market"], bootstrap_samples
            ),
        },
        "safety": {
            "live_state_written": False,
            "canonical_shadow_state_written": False,
            "supabase_writes": False,
            "model_weights_changed": False,
            "production_scoring_changed": False,
            "promotion_authorized": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prime_probability_calibration_challenger.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    parameters = {
        "classification": "DISPOSABLE_ANALYSIS_PARAMETERS_ONLY",
        "model_specifications": model_specs,
        "late_market_specifications": market_specs,
        "selected_model": selected_model,
        "selected_late_market": selected_market,
    }
    (output_dir / "disposable_calibration_parameters.json").write_text(
        json.dumps(parameters, indent=2, allow_nan=False), encoding="utf-8"
    )

    selected_rows = {row["race_id"]: row for row in model_test_rows[selected_model]}
    base_rows = {row["race_id"]: row for row in model_test_rows["raw_base"]}
    selected_market_rows = {row["race_id"]: row for row in market_test_rows[selected_market]}
    late_market_rows = {row["race_id"]: row for row in market_test_rows["late_market"]}
    with (output_dir / "holdout_race_scores.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "race_date",
            "race_id",
            "course",
            "off_time",
            "winner_name",
            "raw_base_log_loss",
            "selected_model_log_loss",
            "raw_base_brier",
            "selected_model_brier",
            "late_market_log_loss",
            "selected_market_log_loss",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for race_id in sorted(selected_rows, key=lambda key: (selected_rows[key]["race_date"], key)):
            chosen, base = selected_rows[race_id], base_rows[race_id]
            market, market_chosen = late_market_rows.get(race_id), selected_market_rows.get(race_id)
            writer.writerow(
                {
                    "race_date": chosen["race_date"],
                    "race_id": race_id,
                    "course": chosen["course"],
                    "off_time": chosen["off_time"],
                    "winner_name": chosen["winner_name"],
                    "raw_base_log_loss": base["log_loss"],
                    "selected_model_log_loss": chosen["log_loss"],
                    "raw_base_brier": base["brier"],
                    "selected_model_brier": chosen["brier"],
                    "late_market_log_loss": market["log_loss"] if market else None,
                    "selected_market_log_loss": market_chosen["log_loss"] if market_chosen else None,
                }
            )

    def metric_row(label: str, metrics: dict[str, Any]) -> str:
        return (
            f"| {label} | {metrics.get('races', 0)} | {metrics.get('top1_accuracy', 0):.2%} | "
            f"{metrics.get('multiclass_log_loss', 0):.4f} | {metrics.get('multiclass_brier', 0):.4f} | "
            f"{metrics.get('flat_stake_roi', 0):.2%} | {metrics.get('ece', 0):.4f} |"
        )

    markdown = [
        "# Prime Probability Calibration Challenger",
        "",
        "- Classification: **ANALYSIS ONLY**",
        f"- Model readout: **{model_readout}**",
        f"- Late-market readout: **{market_readout}**",
        f"- Locked model selection: **{selected_model}**",
        f"- Locked late-market selection: **{selected_market}**",
        "- Market timing: **late pre-off snapshots only; not morning prices**",
        "",
        "## Chronological blocks",
        "",
        "| Block | Dates | Range | Races | Complete market |",
        "|---|---:|---|---:|---:|",
    ]
    for name in ("train", "calibration", "test"):
        block = summary["blocks"][name]
        markdown.append(
            f"| {name} | {block['dates']} | {block['start']} to {block['end']} | "
            f"{block['races']} | {block['complete_market_races']} |"
        )
    markdown.extend(
        [
            "",
            "## Untouched test: model track",
            "",
            "| Variant | Races | Top-1 | Log loss | Brier | Flat ROI | ECE |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, metrics in model_test_metrics.items():
        markdown.append(metric_row(label, metrics))
    markdown.extend(
        [
            "",
            "## Untouched test: complete late-market races",
            "",
            "| Variant | Races | Top-1 | Log loss | Brier | Flat ROI | ECE |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, metrics in market_test_metrics.items():
        markdown.append(metric_row(label, metrics))
    markdown.extend(
        [
            "",
            "## Interpretation",
            "",
            "Parameters were fitted on the early block, variants were selected on the middle block, and the "
            "final block was evaluated only after both were locked. This artifact is evidence, not a promotion "
            "or a live-scoring change.",
        ]
    )
    (output_dir / "prime_probability_calibration_challenger.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    args = parser.parse_args()

    races, diagnostics = load_historical_races(args.data_dir, args.start_date, args.end_date)
    summary = run_challenger(races, args.output_dir, args.bootstrap_samples, diagnostics)
    print(
        json.dumps(
            {
                "blocks": summary["blocks"],
                "readout": summary["readout"],
                "output_dir": str(args.output_dir.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
