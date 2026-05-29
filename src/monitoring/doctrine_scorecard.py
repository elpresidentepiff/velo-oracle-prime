"""
Doctrine-vs-market scorecard primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

WIN_OUTCOMES = {"WIN"}
NON_LOSS_OUTCOMES = {"WIN", "PLACED"}
FLAG_COLUMNS = ("cash_run_flag", "setup_run_flag", "decoy_support_flag")


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _outcome(value: Any) -> str:
    return str(value or "").strip().upper()


def _tier(value: Any) -> str:
    tier = str(value or "").strip().upper()
    if tier in {"A", "A-STRIKE"}:
        return "A-STRIKE"
    return tier


@dataclass
class GateProgress:
    target: int
    flagged_races: int
    cash_run_races: int
    setup_run_races: int
    decoy_support_races: int

    @property
    def completion_pct(self) -> float:
        if self.target <= 0:
            return 0.0
        return round((self.flagged_races / self.target) * 100, 1)

    @property
    def remaining(self) -> int:
        return max(self.target - self.flagged_races, 0)


def compute_gate_progress(df: pd.DataFrame, target: int = 100) -> GateProgress:
    if df.empty:
        return GateProgress(target, 0, 0, 0, 0)

    flags = pd.DataFrame({col: df.get(col, False).map(_to_bool) for col in FLAG_COLUMNS})
    flagged = flags.any(axis=1)
    return GateProgress(
        target=target,
        flagged_races=int(flagged.sum()),
        cash_run_races=int(flags["cash_run_flag"].sum()),
        setup_run_races=int(flags["setup_run_flag"].sum()),
        decoy_support_races=int(flags["decoy_support_flag"].sum()),
    )


def compute_tier_a_strike(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"sample_size": 0, "wins": 0, "strike_rate_pct": 0.0}

    tier_a = df[df.get("decision_tier", "").map(_tier) == "A-STRIKE"].copy()
    if tier_a.empty:
        return {"sample_size": 0, "wins": 0, "strike_rate_pct": 0.0}

    wins = tier_a["outcome"].map(_outcome).isin(WIN_OUTCOMES).sum()
    return {
        "sample_size": int(len(tier_a)),
        "wins": int(wins),
        "strike_rate_pct": round((wins / len(tier_a)) * 100, 1),
    }


def compute_decoy_interception_rate(df: pd.DataFrame, mds_threshold: float = 0.5) -> dict[str, Any]:
    if df.empty:
        return {"sample_size": 0, "interceptions": 0, "interception_rate_pct": 0.0, "threshold": mds_threshold}

    mds = pd.to_numeric(df.get("market_deception_score"), errors="coerce")
    decoy_sample = df[mds >= mds_threshold].copy()
    if decoy_sample.empty:
        return {"sample_size": 0, "interceptions": 0, "interception_rate_pct": 0.0, "threshold": mds_threshold}

    interceptions = decoy_sample["outcome"].map(_outcome).isin(NON_LOSS_OUTCOMES).sum()
    return {
        "sample_size": int(len(decoy_sample)),
        "interceptions": int(interceptions),
        "interception_rate_pct": round((interceptions / len(decoy_sample)) * 100, 1),
        "threshold": mds_threshold,
    }


def compute_doctrine_vs_market_edge(df: pd.DataFrame) -> dict[str, Any]:
    doctrine_win_rate = 0.0
    if not df.empty:
        doctrine_wins = df["outcome"].map(_outcome).isin(WIN_OUTCOMES).sum()
        doctrine_win_rate = round((doctrine_wins / len(df)) * 100, 1)

    market_col: pd.Series | None = None
    if "market_top_pick_won" in df.columns:
        market_col = df["market_top_pick_won"].map(_to_bool)
    elif "market_top_pick_outcome" in df.columns:
        market_col = df["market_top_pick_outcome"].map(_outcome).isin(WIN_OUTCOMES)

    if market_col is None:
        return {
            "sample_size": int(len(df)),
            "doctrine_win_rate_pct": doctrine_win_rate,
            "market_win_rate_pct": None,
            "edge_pct_points": None,
            "note": "market_top_pick_won or market_top_pick_outcome not present",
        }

    market_win_rate = round(float(market_col.mean() * 100), 1) if len(market_col) else 0.0
    return {
        "sample_size": int(len(df)),
        "doctrine_win_rate_pct": doctrine_win_rate,
        "market_win_rate_pct": market_win_rate,
        "edge_pct_points": round(doctrine_win_rate - market_win_rate, 1),
    }


def compute_confidence_reliability(df: pd.DataFrame) -> dict[str, Any]:
    expected = {"HIGH": 0.31, "MEDIUM": 0.30, "LOW": 0.20}
    conf = df.get("confidence_level")
    if conf is None or df.empty:
        return {"bands": [], "mean_abs_error_pct_points": None}

    bands: list[dict[str, Any]] = []
    errors: list[float] = []
    for label in ("HIGH", "MEDIUM", "LOW"):
        group = df[conf.astype(str).str.upper() == label]
        if group.empty:
            continue
        actual = group["outcome"].map(_outcome).isin(WIN_OUTCOMES).mean()
        error_pct = abs(actual - expected[label]) * 100
        errors.append(error_pct)
        bands.append(
            {
                "label": label,
                "sample_size": int(len(group)),
                "expected_win_rate_pct": round(expected[label] * 100, 1),
                "actual_win_rate_pct": round(actual * 100, 1),
                "absolute_error_pct_points": round(error_pct, 1),
            }
        )

    return {
        "bands": bands,
        "mean_abs_error_pct_points": round(sum(errors) / len(errors), 1) if errors else None,
    }


def build_scorecard(df: pd.DataFrame, gate_target: int = 100, mds_threshold: float = 0.5) -> dict[str, Any]:
    gate = compute_gate_progress(df, target=gate_target)
    return {
        "gate_progress": {
            "target": gate.target,
            "flagged_races": gate.flagged_races,
            "cash_run_races": gate.cash_run_races,
            "setup_run_races": gate.setup_run_races,
            "decoy_support_races": gate.decoy_support_races,
            "completion_pct": gate.completion_pct,
            "remaining": gate.remaining,
        },
        "tier_a": compute_tier_a_strike(df),
        "decoy_interception": compute_decoy_interception_rate(df, mds_threshold=mds_threshold),
        "doctrine_vs_market": compute_doctrine_vs_market_edge(df),
        "confidence_reliability": compute_confidence_reliability(df),
    }
