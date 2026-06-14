"""
Builds a doctrine-vs-market scorecard for audit/dashboard use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.monitoring.doctrine_scorecard import build_scorecard


def _load_input(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            return pd.read_json(path, lines=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and "rows" in data:
            return pd.DataFrame(data["rows"])
        raise ValueError(f"Unexpected JSON structure in {path}")
    raise ValueError(f"Unsupported input format: {suffix}")


def _normalise_corpus(df: pd.DataFrame) -> pd.DataFrame:
    """Map innovation protocol corpus columns to scorecard expected schema.

    The velo_innovation_protocol corpus uses different column names than the
    scorecard primitives expect. This layer translates without dropping data.

    Column mappings:
      won (bool)       -> outcome ("WIN" / "LOSS")
      confidence       -> confidence_level
      model_probability -> velo_prime_prob
      placed (bool)    -> placed_outcome ("PLACED" / "")

    Missing columns (0% live coverage — documented in investor brief):
      cash_run_flag, setup_run_flag, decoy_support_flag
      market_deception_score
    These remain absent — the scorecard will correctly report 0% gate progress.
    """
    df = df.copy()

    # outcome: derived from won/placed boolean columns
    if "outcome" not in df.columns:
        if "won" in df.columns:
            df["outcome"] = df["won"].map(lambda v: "WIN" if bool(v) else "LOSS")
        elif "result_position" in df.columns:
            df["outcome"] = df["result_position"].map(
                lambda v: "WIN" if str(v).strip() == "1" else "LOSS"
            )

    # confidence_level: map from 'confidence' column
    if "confidence_level" not in df.columns and "confidence" in df.columns:
        df["confidence_level"] = df["confidence"].str.strip().str.upper()

    # velo_prime_prob: map from model_probability
    if "velo_prime_prob" not in df.columns and "model_probability" in df.columns:
        df["velo_prime_prob"] = pd.to_numeric(df["model_probability"], errors="coerce")

    # decision_tier: alias from tier
    if "decision_tier" not in df.columns and "tier" in df.columns:
        df["decision_tier"] = df["tier"]

    # Confidence band expected rates for the innovation corpus
    # HIGH / MEDIUM / LOW map to known audit baselines from the evidence corpus
    CONF_EXPECTED = {"HIGH": 30.8, "MEDIUM": 37.5, "LOW": 19.6}
    if "confidence_expected_win_rate_pct" not in df.columns and "confidence_level" in df.columns:
        df["confidence_expected_win_rate_pct"] = df["confidence_level"].map(CONF_EXPECTED)

    return df


def _as_markdown(scorecard: dict) -> str:
    gate = scorecard["gate_progress"]
    tier_a = scorecard["tier_a"]
    decoy = scorecard["decoy_interception"]
    edge = scorecard["doctrine_vs_market"]
    conf = scorecard["confidence_reliability"]
    lines = [
        "# Doctrine vs Market Scorecard",
        "",
        "## Gate Progress",
        f"- Flag-bearing races: **{gate['flagged_races']} / {gate['target']}** ({gate['completion_pct']}%)",
        f"- Remaining to gate: **{gate['remaining']}**",
        f"- cash/setup/decoy support: {gate['cash_run_races']} / {gate['setup_run_races']} / {gate['decoy_support_races']}",
        "",
        "## Tier A Strike",
        f"- Sample size: **{tier_a['sample_size']}**",
        f"- Wins: **{tier_a['wins']}**",
        f"- Strike rate: **{tier_a['strike_rate_pct']}%**",
        "",
        "## Decoy Interception",
        f"- Threshold: **MDS >= {decoy['threshold']}**",
        f"- Interceptions: **{decoy['interceptions']} / {decoy['sample_size']}**",
        f"- Interception rate: **{decoy['interception_rate_pct']}%**",
        "",
        "## Doctrine vs Market",
        f"- Doctrine win rate: **{edge['doctrine_win_rate_pct']}%**",
    ]
    if edge["market_win_rate_pct"] is None:
        lines.append("- Market win rate: **N/A** (market column not available)")
    else:
        lines.extend(
            [
                f"- Market win rate: **{edge['market_win_rate_pct']}%**",
                f"- Edge: **{edge['edge_pct_points']} pp**",
            ]
        )
    lines.append("")
    lines.append("## Confidence Reliability")
    if not conf["bands"]:
        lines.append("- No confidence bands available")
    else:
        for band in conf["bands"]:
            lines.append(
                f"- {band['label']}: actual **{band['actual_win_rate_pct']}%** vs expected "
                f"**{band['expected_win_rate_pct']}%** (|error| {band['absolute_error_pct_points']} pp)"
            )
        lines.append(f"- Mean absolute error: **{conf['mean_abs_error_pct_points']} pp**")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build doctrine-vs-market scorecard")
    parser.add_argument("--input", required=True, help="Input .csv, .json, or .jsonl file")
    parser.add_argument(
        "--output-json",
        default="data/doctrine_market_scorecard_latest.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        default="data/doctrine_market_scorecard_latest.md",
        help="Output markdown path",
    )
    parser.add_argument("--gate-target", type=int, default=100)
    parser.add_argument("--mds-threshold", type=float, default=0.5)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = _load_input(input_path)
    df = _normalise_corpus(df)
    scorecard = build_scorecard(df, gate_target=args.gate_target, mds_threshold=args.mds_threshold)
    scorecard["meta"] = {
        "input_path": str(input_path),
        "rows": len(df),
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "gate_flags_live_coverage": "0%_EXPECTED — cash/setup/decoy flags not yet in live corpus",
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    output_md.write_text(_as_markdown(scorecard), encoding="utf-8")
    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
