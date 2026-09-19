#!/usr/bin/env python3
"""Chronological full-field ablation of the Prime probability mechanisms.

Reconstructs component mixtures from stored pre-off runner snapshots, fits one
scalar temperature per variant on the early block, selects on the middle block,
and evaluates the locked choice on the untouched final block. Analysis only:
no live score, model, weight, state, or gate is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.prime_probability_calibration_challenger import (  # noqa: E402
    load_historical_races,
    paired_bootstrap,
    power_transform,
    provider_from_spec,
    score_variant,
    split_chronologically,
)

ProbabilityProvider = Callable[[dict[str, Any]], list[float] | None]

WEIGHTS = {
    "sqpe_v17_prob": 0.45,
    "improvement_score": 0.12,
    "market_deception_score": 0.10,
}
COMPONENT_VARIANTS = {
    "sqpe_only": ("sqpe_v17_prob",),
    "sqpe_plus_improvement": ("sqpe_v17_prob", "improvement_score"),
    "sqpe_plus_mds": ("sqpe_v17_prob", "market_deception_score"),
    "sqpe_plus_improvement_mds": (
        "sqpe_v17_prob",
        "improvement_score",
        "market_deception_score",
    ),
}


def component_provider(components: tuple[str, ...]) -> ProbabilityProvider:
    """Reconstruct the production weighted-average pattern, then race-normalise."""

    def provider(race: dict[str, Any]) -> list[float] | None:
        raw = []
        for row in race.get("source_field", []):
            available = [name for name in components if row.get(name) is not None]
            total_weight = sum(WEIGHTS[name] for name in available)
            if total_weight <= 0.0:
                return None
            raw.append(sum(WEIGHTS[name] * float(row[name]) for name in available) / total_weight)
        total = sum(max(value, 0.0) for value in raw)
        return [max(value, 0.0) / total for value in raw] if total > 0.0 else None

    return provider


def calibrated_provider(provider: ProbabilityProvider, beta: float) -> ProbabilityProvider:
    def calibrated(race: dict[str, Any]) -> list[float] | None:
        probabilities = provider(race)
        return power_transform(probabilities, beta) if probabilities is not None else None

    return calibrated


def fit_provider_beta(races: list[dict[str, Any]], provider: ProbabilityProvider) -> tuple[float, float]:
    scored = []
    for index in range(201):
        beta = index / 100
        losses = []
        transformed = calibrated_provider(provider, beta)
        for race in races:
            probabilities = transformed(race)
            if probabilities is not None:
                losses.append(-math.log(max(probabilities[int(race["winner_index"])], 1e-12)))
        loss = statistics.fmean(losses) if losses else math.inf
        scored.append((loss, abs(beta - 1.0), beta))
    loss, _distance, beta = min(scored)
    return beta, loss


def _raw_providers() -> dict[str, ProbabilityProvider]:
    providers = {
        "stored_base": provider_from_spec({"kind": "temperature", "source": "base", "beta": 1.0}),
        "stored_g": provider_from_spec({"kind": "temperature", "source": "g", "beta": 1.0}),
    }
    providers.update({label: component_provider(components) for label, components in COMPONENT_VARIANTS.items()})
    return providers


def ranking_metrics(races: list[dict[str, Any]], provider: ProbabilityProvider) -> dict[str, Any]:
    ranks = []
    percentiles = []
    for race in races:
        probabilities = provider(race)
        if probabilities is None:
            continue
        order = sorted(range(len(probabilities)), key=lambda index: probabilities[index], reverse=True)
        rank = order.index(int(race["winner_index"])) + 1
        ranks.append(rank)
        percentiles.append((len(order) - rank) / max(1, len(order) - 1))
    return (
        {
            "mean_winner_rank": statistics.fmean(ranks),
            "median_winner_rank": statistics.median(ranks),
            "mean_reciprocal_rank": statistics.fmean(1.0 / rank for rank in ranks),
            "winner_pairwise_accuracy": statistics.fmean(percentiles),
        }
        if ranks
        else {}
    )


def variant_metrics(
    races: list[dict[str, Any]],
    provider: ProbabilityProvider,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics, rows = score_variant(races, provider)
    metrics.update(ranking_metrics(races, provider))
    return metrics, rows


def component_diagnostics(races: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for race in races for row in race.get("source_field", [])]
    diagnostics = {}
    for field in WEIGHTS:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        constant_races = 0
        eligible_races = 0
        for race in races:
            race_values = [row.get(field) for row in race.get("source_field", [])]
            if race_values and all(value is not None for value in race_values):
                eligible_races += 1
                constant_races += len({round(float(value), 12) for value in race_values}) == 1
        diagnostics[field] = {
            "row_coverage": len(values) / len(rows) if rows else 0.0,
            "mean": statistics.fmean(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "zero_rate": statistics.fmean(float(value == 0.0) for value in values) if values else None,
            "constant_within_race_rate": constant_races / eligible_races if eligible_races else None,
        }
    return diagnostics


def market_disagreement(races: list[dict[str, Any]], model: ProbabilityProvider) -> dict[str, Any]:
    market = provider_from_spec({"kind": "market"})
    counts = {
        "complete_market_races": 0,
        "same_pick": 0,
        "same_pick_wins": 0,
        "different_pick": 0,
        "model_pick_wins": 0,
        "market_pick_wins": 0,
        "neither_pick_wins": 0,
    }
    for race in races:
        model_probabilities, market_probabilities = model(race), market(race)
        if model_probabilities is None or market_probabilities is None:
            continue
        counts["complete_market_races"] += 1
        model_top = max(range(len(model_probabilities)), key=model_probabilities.__getitem__)
        market_top = max(range(len(market_probabilities)), key=market_probabilities.__getitem__)
        winner = int(race["winner_index"])
        if model_top == market_top:
            counts["same_pick"] += 1
            counts["same_pick_wins"] += model_top == winner
        else:
            counts["different_pick"] += 1
            if model_top == winner:
                counts["model_pick_wins"] += 1
            elif market_top == winner:
                counts["market_pick_wins"] += 1
            else:
                counts["neither_pick_wins"] += 1
    return counts


def _field_band(race: dict[str, Any]) -> str:
    size = len(race["runners"])
    if size <= 7:
        return "small_3_7"
    if size <= 11:
        return "medium_8_11"
    return "large_12_plus"


def run_ablation(
    races: list[dict[str, Any]],
    output_dir: Path,
    bootstrap_samples: int = 1000,
    source_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks = split_chronologically(races)
    train, calibration, test = blocks["train"], blocks["calibration"], blocks["test"]
    raw_providers = _raw_providers()

    fitted = {}
    calibrated = {}
    for label, provider in raw_providers.items():
        beta, train_loss = fit_provider_beta(train, provider)
        fitted[label] = {"beta": beta, "train_log_loss": train_loss}
        calibrated[label] = calibrated_provider(provider, beta)

    calibration_metrics = {label: variant_metrics(calibration, provider)[0] for label, provider in calibrated.items()}
    selected = min(
        calibration_metrics,
        key=lambda label: (
            calibration_metrics[label]["multiclass_log_loss"],
            calibration_metrics[label]["multiclass_brier"],
            label,
        ),
    )

    test_metrics, test_rows = {}, {}
    for label, provider in calibrated.items():
        metrics, rows = variant_metrics(test, provider)
        test_metrics[label], test_rows[label] = metrics, rows

    selected_metrics = test_metrics[selected]
    current_metrics = test_metrics["stored_g"]
    if selected == "stored_g":
        mechanism_readout = "STORED_G_REMAINS_COMPONENT_CHAMPION"
    elif selected == "sqpe_only":
        mechanism_readout = "SPECIALISTS_DILUTE_SQPE_RANKING"
    elif (
        selected_metrics["multiclass_log_loss"] < current_metrics["multiclass_log_loss"]
        and selected_metrics["multiclass_brier"] < current_metrics["multiclass_brier"]
    ):
        mechanism_readout = "RECONSTRUCTED_SUBSET_BEATS_STORED_G_ON_HOLDOUT"
    else:
        mechanism_readout = "CALIBRATION_SELECTION_DID_NOT_REPLICATE"

    field_bands = {}
    for band in ("small_3_7", "medium_8_11", "large_12_plus"):
        subset = [race for race in test if _field_band(race) == band]
        field_bands[band] = {
            "races": len(subset),
            "selected": variant_metrics(subset, calibrated[selected])[0],
            "stored_g": variant_metrics(subset, calibrated["stored_g"])[0],
            "market_disagreement": market_disagreement(subset, calibrated[selected]),
        }

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "classification": "ANALYSIS_ONLY",
        "time_contract": "fit train, select calibration, evaluate untouched test; whole race days",
        "reconstruction_contract": (
            "stored pre-off component scores and production weights; reconstructed variants exclude macro modifiers"
        ),
        "source_diagnostics": source_diagnostics or {},
        "blocks": {
            name: {
                "races": len(block),
                "start": min(race["race_date"] for race in block),
                "end": max(race["race_date"] for race in block),
            }
            for name, block in blocks.items()
        },
        "component_diagnostics_on_test": component_diagnostics(test),
        "fitted_on_train_only": fitted,
        "selected_on_calibration_only": {
            "variant": selected,
            "metrics": calibration_metrics,
        },
        "untouched_test": test_metrics,
        "readout": {
            "mechanism": mechanism_readout,
            "selected_variant": selected,
        },
        "selected_vs_stored_g_bootstrap_95pct": paired_bootstrap(
            test_rows[selected], test_rows["stored_g"], bootstrap_samples
        ),
        "market_disagreement_on_test": market_disagreement(test, calibrated[selected]),
        "field_size_bands": field_bands,
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
    (output_dir / "prime_component_mechanism_ablation.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "disposable_component_parameters.json").write_text(
        json.dumps(
            {
                "classification": "DISPOSABLE_ANALYSIS_PARAMETERS_ONLY",
                "weights_read_from_production": WEIGHTS,
                "component_variants": COMPONENT_VARIANTS,
                "fitted_beta": {label: values["beta"] for label, values in fitted.items()},
                "selected_variant": selected,
            },
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    with (output_dir / "holdout_variant_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
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
        "# Prime Component Mechanism Ablation",
        "",
        "- Classification: **ANALYSIS ONLY**",
        f"- Locked selection: **{selected}**",
        f"- Holdout readout: **{mechanism_readout}**",
        "- Reconstruction excludes macro modifiers; stored Base/G remain direct comparison anchors.",
        "",
        "## Untouched holdout",
        "",
        "| Variant | Top-1 | Top-3 | Log loss | Brier | ROI | Winner rank | Pairwise |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in test_metrics.items():
        markdown.append(
            f"| {label} | {metrics['top1_accuracy']:.2%} | {metrics['top3_accuracy']:.2%} | "
            f"{metrics['multiclass_log_loss']:.4f} | {metrics['multiclass_brier']:.4f} | "
            f"{metrics['flat_stake_roi']:.2%} | {metrics['mean_winner_rank']:.2f} | "
            f"{metrics['winner_pairwise_accuracy']:.2%} |"
        )
    disagreement = summary["market_disagreement_on_test"]
    markdown.extend(
        [
            "",
            "## Model versus late market",
            "",
            f"On {disagreement['different_pick']} disagreements, the model pick won "
            f"{disagreement['model_pick_wins']} and the market pick won {disagreement['market_pick_wins']}; "
            f"neither won {disagreement['neither_pick_wins']}.",
            "",
            "## Interpretation",
            "",
            "Every beta was fitted on the early block, the variant was selected on the middle block, and the "
            "final block was opened only after lock. These counterfactuals diagnose score composition; they do "
            "not authorize a live weight change or model promotion.",
        ]
    )
    (output_dir / "prime_component_mechanism_ablation.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
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
    summary = run_ablation(races, args.output_dir, args.bootstrap_samples, diagnostics)
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
