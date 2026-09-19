#!/usr/bin/env python3
"""Disposable market-blind pairwise ranker with chronological holdout.

The ranker learns only from pre-off model/component scores. It never receives
prices, favourite flags, results-derived fields, or runner identity. Models are
held in memory, reported as analysis parameters, and never installed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.prime_component_mechanism_ablation import (  # noqa: E402
    fit_provider_beta,
    variant_metrics,
)
from scripts.analysis.prime_probability_calibration_challenger import (  # noqa: E402
    load_historical_races,
    paired_bootstrap,
    power_transform,
    provider_from_spec,
    split_chronologically,
)

CORE_FEATURES = (
    "sqpe_v17_prob",
    "improvement_score",
    "market_deception_score",
)
EXPANDED_FEATURES = CORE_FEATURES + (
    "place_prob",
    "longshot_prob",
    "spotlight_score",
    "nds_score",
)
FEATURE_SETS = {"core": CORE_FEATURES, "expanded": EXPANDED_FEATURES}
C_GRID = (0.01, 0.1, 1.0, 10.0)


def _numeric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def feature_matrix(race: dict[str, Any], features: tuple[str, ...]) -> np.ndarray:
    return np.asarray(
        [[_numeric(row.get(feature)) for feature in features] for row in race["source_field"]],
        dtype=float,
    )


def pairwise_training_data(
    races: list[dict[str, Any]],
    features: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    samples, labels = [], []
    for race in races:
        matrix = feature_matrix(race, features)
        winner = int(race["winner_index"])
        for loser in range(len(matrix)):
            if loser == winner:
                continue
            difference = matrix[winner] - matrix[loser]
            samples.extend((difference, -difference))
            labels.extend((1, 0))
    return np.asarray(samples, dtype=float), np.asarray(labels, dtype=int)


def fit_ranker(
    races: list[dict[str, Any]],
    features: tuple[str, ...],
    c_value: float,
):
    x_train, y_train = pairwise_training_data(races, features)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=c_value, solver="lbfgs", max_iter=2000, random_state=1981),
    )
    model.fit(x_train, y_train)
    return model


def ranker_provider(model, features: tuple[str, ...], gamma: float):
    def provider(race: dict[str, Any]) -> list[float]:
        scores = model.decision_function(feature_matrix(race, features))
        centred = gamma * (scores - np.max(scores))
        exponentiated = np.exp(np.clip(centred, -50.0, 0.0))
        probabilities = exponentiated / exponentiated.sum()
        return probabilities.tolist()

    return provider


def fit_gamma(
    races: list[dict[str, Any]],
    model,
    features: tuple[str, ...],
) -> tuple[float, float]:
    race_scores = [
        (
            model.decision_function(feature_matrix(race, features)),
            int(race["winner_index"]),
        )
        for race in races
    ]
    scored = []
    for index in range(151):
        gamma = index / 50
        losses = []
        for scores, winner in race_scores:
            centred = gamma * (scores - np.max(scores))
            exponentiated = np.exp(np.clip(centred, -50.0, 0.0))
            probabilities = exponentiated / exponentiated.sum()
            losses.append(-math.log(max(float(probabilities[winner]), 1e-12)))
        scored.append((sum(losses) / len(losses), abs(gamma - 1.0), gamma))
    loss, _distance, gamma = min(scored)
    return gamma, loss


def _coefficient_report(model, features: tuple[str, ...]) -> dict[str, float]:
    scaler = model.named_steps["standardscaler"]
    classifier = model.named_steps["logisticregression"]
    raw = classifier.coef_[0] / scaler.scale_
    return {feature: float(value) for feature, value in zip(features, raw, strict=True)}


def _feature_coverage(races: list[dict[str, Any]]) -> dict[str, float]:
    rows = [row for race in races for row in race["source_field"]]
    return {feature: sum(row.get(feature) is not None for row in rows) / len(rows) for feature in EXPANDED_FEATURES}


def run_ranker_challenger(
    races: list[dict[str, Any]],
    output_dir: Path,
    bootstrap_samples: int = 1000,
    source_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks = split_chronologically(races)
    train, calibration, test = blocks["train"], blocks["calibration"], blocks["test"]

    stored_g_raw = provider_from_spec({"kind": "temperature", "source": "g", "beta": 1.0})
    stored_g_beta, stored_g_train_loss = fit_provider_beta(train, stored_g_raw)

    def stored_g_provider(race: dict[str, Any]) -> list[float] | None:
        probabilities = stored_g_raw(race)
        return power_transform(probabilities, stored_g_beta) if probabilities is not None else None

    candidates: dict[str, dict[str, Any]] = {
        "stored_g": {
            "provider": stored_g_provider,
            "parameters": {"beta": stored_g_beta, "train_log_loss": stored_g_train_loss},
        }
    }
    for feature_label, features in FEATURE_SETS.items():
        for c_value in C_GRID:
            label = f"pairwise_{feature_label}_c{c_value:g}"
            model = fit_ranker(train, features, c_value)
            gamma, train_loss = fit_gamma(train, model, features)
            candidates[label] = {
                "provider": ranker_provider(model, features, gamma),
                "parameters": {
                    "feature_set": feature_label,
                    "features": list(features),
                    "c": c_value,
                    "gamma": gamma,
                    "train_log_loss": train_loss,
                    "coefficients": _coefficient_report(model, features),
                },
            }

    calibration_metrics = {
        label: variant_metrics(calibration, candidate["provider"])[0] for label, candidate in candidates.items()
    }
    selected = min(
        calibration_metrics,
        key=lambda label: (
            -calibration_metrics[label]["top1_accuracy"],
            -calibration_metrics[label]["mean_reciprocal_rank"],
            calibration_metrics[label]["multiclass_log_loss"],
            label,
        ),
    )

    test_metrics, test_rows = {}, {}
    for label, candidate in candidates.items():
        metrics, rows = variant_metrics(test, candidate["provider"])
        test_metrics[label], test_rows[label] = metrics, rows

    intervals = paired_bootstrap(test_rows[selected], test_rows["stored_g"], bootstrap_samples)
    selected_metrics, baseline_metrics = test_metrics[selected], test_metrics["stored_g"]
    if selected == "stored_g":
        readout = "STORED_G_REMAINS_RANKING_CHAMPION"
    elif (
        intervals.get("top1_accuracy", [0.0, 0.0])[0] > 0.0
        and selected_metrics["mean_reciprocal_rank"] > baseline_metrics["mean_reciprocal_rank"]
    ):
        readout = "MARKET_BLIND_RANKING_LIFT_CONFIRMED"
    elif (
        selected_metrics["mean_reciprocal_rank"] > baseline_metrics["mean_reciprocal_rank"]
        or selected_metrics["winner_pairwise_accuracy"] > baseline_metrics["winner_pairwise_accuracy"]
    ):
        readout = "PARTIAL_RANKING_LIFT_NOT_PROMOTABLE"
    else:
        readout = "CALIBRATION_SELECTION_DID_NOT_REPLICATE"

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "classification": "ANALYSIS_ONLY",
        "time_contract": "fit train, select calibration, evaluate untouched test; whole race days",
        "market_blind_contract": {
            "price_features_used": False,
            "favourite_flag_used": False,
            "runner_identity_used": False,
            "result_fields_used_as_features": False,
        },
        "source_diagnostics": source_diagnostics or {},
        "blocks": {
            name: {
                "races": len(block),
                "start": min(race["race_date"] for race in block),
                "end": max(race["race_date"] for race in block),
            }
            for name, block in blocks.items()
        },
        "feature_coverage_on_train": _feature_coverage(train),
        "fitted_on_train_only": {label: candidate["parameters"] for label, candidate in candidates.items()},
        "selected_on_calibration_only": {"variant": selected, "metrics": calibration_metrics},
        "untouched_test": test_metrics,
        "selected_vs_stored_g_bootstrap_95pct": intervals,
        "readout": {"status": readout, "selected_variant": selected},
        "safety": {
            "fitted_model_persisted": False,
            "live_state_written": False,
            "canonical_shadow_state_written": False,
            "supabase_writes": False,
            "production_model_weights_changed": False,
            "production_scoring_changed": False,
            "promotion_authorized": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prime_market_blind_ranker_challenger.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "disposable_ranker_parameters.json").write_text(
        json.dumps(
            {
                "classification": "DISPOSABLE_ANALYSIS_PARAMETERS_ONLY",
                "selected_variant": selected,
                "parameters": summary["fitted_on_train_only"],
                "model_object_persisted": False,
            },
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    with (output_dir / "holdout_ranker_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "variant",
            "races",
            "top1_accuracy",
            "top3_accuracy",
            "multiclass_log_loss",
            "multiclass_brier",
            "flat_stake_roi",
            "ece",
            "mean_winner_rank",
            "mean_reciprocal_rank",
            "winner_pairwise_accuracy",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label, metrics in test_metrics.items():
            writer.writerow({"variant": label, **{field: metrics.get(field) for field in fields[1:]}})

    markdown = [
        "# Prime Market-Blind Ranker Challenger",
        "",
        "- Classification: **ANALYSIS ONLY**",
        f"- Locked calibration selection: **{selected}**",
        f"- Holdout readout: **{readout}**",
        "- Prices, favourite flags, runner identity, and result fields were excluded from features.",
        "- No fitted model object was persisted or installed.",
        "",
        "## Untouched holdout",
        "",
        "| Variant | Top-1 | Top-3 | Log loss | Brier | MRR | Pairwise | ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in test_metrics.items():
        marker = " **← selected**" if label == selected else ""
        markdown.append(
            f"| {label}{marker} | {metrics['top1_accuracy']:.2%} | {metrics['top3_accuracy']:.2%} | "
            f"{metrics['multiclass_log_loss']:.4f} | {metrics['multiclass_brier']:.4f} | "
            f"{metrics['mean_reciprocal_rank']:.4f} | {metrics['winner_pairwise_accuracy']:.2%} | "
            f"{metrics['flat_stake_roi']:.2%} |"
        )
    markdown.extend(
        [
            "",
            "## Interpretation",
            "",
            "The early block alone fitted all coefficients and probability scaling. The middle block locked the "
            "candidate and hyperparameters. The final block was then evaluated once. This is a supervised "
            "ranking experiment, not a production model, promotion, or RL policy.",
        ]
    )
    (output_dir / "prime_market_blind_ranker_challenger.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
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
    summary = run_ranker_challenger(races, args.output_dir, args.bootstrap_samples, diagnostics)
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
