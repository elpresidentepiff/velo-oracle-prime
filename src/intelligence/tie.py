# src/intelligence/tie.py
"""
TIE - Trainer Intent Engine

Purpose: Quantify trainer intent - "they're here to win"

The TIE analyzes trainer behavior patterns, jockey changes, rest patterns,
and class movements to detect when a trainer is targeting a specific race.

This is the ML-based production version using logistic regression to learn
intent patterns from historical data.

Key Concepts:
- Trainer statistics: Win rates, recent form, track/distance specialization
- Rest patterns: Freshened vs too quick turnaround
- Jockey upgrade/downgrade signals
- Class movement analysis
- Intent scoring: 0-1 probability that this is a targeted run

Author: VÉLØ Oracle Team
Version: 2.0 (ML-based)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


@dataclass
class TIEConfig:
    """
    Configuration for Trainer Intent Engine.

    The engine predicts an 'intent score' representing the
    probability that a given runner is being targeted to run to peak.
    """

    min_trainer_runs: int = 50         # minimum history for stable stats
    lookback_days: int = 90           # window for recent form
    regularization_c: float = 0.5     # strength of L2 penalty
    random_state: int = 42


class TrainerIntentEngine:
    """
    Trainer Intent Engine (TIE) - ML-based version.

    Responsibilities:
        - Build trainer-level statistics from historical runners.
        - Construct intent features for (trainer, runner, race).
        - Train a logistic model to detect 'high intent' patterns.
        - Score live runners with an intent_score in [0, 1].

    'High intent' label can be:
        - y_intent = 1 when trainer + runner conditions match known
          profitable targeting patterns (e.g. big class drop + rest + jockey upgrade
          + trainer profitable in that niche).
        - Otherwise y_intent = 0.

    You control the labelling logic upstream; this engine just learns the pattern.
    """

    def __init__(self, config: Optional[TIEConfig] = None) -> None:
        self.config = config or TIEConfig()
        self._model: Optional[LogisticRegression] = None
        self._feature_columns: Optional[list[str]] = None
        self._fitted: bool = False

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(
        self,
        X: pd.DataFrame,
        y_intent: pd.Series,
    ) -> None:
        """
        Fit the intent classifier.

        Args:
            X: Feature matrix at runner level. Must already contain all relevant
               trainer/runner features (see build_runner_features()).
            y_intent: Binary Series: 1 = high intent, 0 = normal/low intent.
        """
        self._feature_columns = list(X.columns)

        model = LogisticRegression(
            C=self.config.regularization_c,
            penalty="l2",
            solver="liblinear",
            random_state=self.config.random_state,
        )
        model.fit(X.values, y_intent.values)

        self._model = model
        self._fitted = True

    def predict_intent_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict trainer intent scores in [0, 1].

        Args:
            X: Runner-level feature matrix with same columns as used in training.

        Returns:
            ndarray of shape (n_samples,) with intent scores.
        """
        self._ensure_fitted()

        X = X[self._feature_columns]  # type: ignore[index]
        proba = self._model.predict_proba(X.values)[:, 1]  # type: ignore[union-attr]
        return np.clip(proba, 1e-6, 1 - 1e-6)

    # -------------------------------------------------------------------------
    # Feature construction helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def build_trainer_stats(
        history: pd.DataFrame,
        date_col: str = "race_date",
        trainer_col: str = "trainer",
        won_col: str = "won",
    ) -> pd.DataFrame:
        """
        Build aggregated trainer stats from historical runs.

        Expects history with at least:
            - race_date (datetime)
            - trainer
            - won (0/1)

        Returns a DataFrame indexed by trainer with columns like:
            - trainer_runs
            - trainer_win_rate
            - trainer_recent_runs
            - trainer_recent_win_rate
        """
        df = history.copy()
        df[date_col] = pd.to_datetime(df[date_col])

        # Overall stats
        grp = df.groupby(trainer_col)
        overall = grp[won_col].agg(["count", "mean"]).rename(
            columns={"count": "trainer_runs", "mean": "trainer_win_rate"}
        )

        # Recent stats (last N days from max date)
        max_date = df[date_col].max()
        cutoff = max_date - pd.Timedelta(days=90)
        recent = (
            df[df[date_col] >= cutoff]
            .groupby(trainer_col)[won_col]
            .agg(["count", "mean"])
            .rename(
                columns={
                    "count": "trainer_recent_runs",
                    "mean": "trainer_recent_win_rate",
                }
            )
        )

        stats = overall.join(recent, how="left").fillna(
            {"trainer_recent_runs": 0, "trainer_recent_win_rate": 0.0}
        )

        return stats

    @staticmethod
    def build_runner_features(
        runners: pd.DataFrame,
        trainer_stats: pd.DataFrame,
        *,
        trainer_col: str = "trainer",
        days_since_run_col: str = "days_since_run",
        class_change_col: str = "class_delta",
        jockey_change_col: str = "jockey_change_rank",
    ) -> pd.DataFrame:
        """
        Build TIE feature frame for runners.

        Expects:
            runners with columns:
                - trainer
                - days_since_run
                - class_delta (negative = class drop)
                - jockey_change_rank (positive = upgrade)
            trainer_stats as produced by build_trainer_stats().

        Returns:
            DataFrame with engineered columns suitable for TIE.fit().
        """
        df = runners.copy()

        df = df.merge(
            trainer_stats,
            how="left",
            left_on=trainer_col,
            right_index=True,
        )

        # Handle trainers with no history
        df["trainer_runs"] = df["trainer_runs"].fillna(0)
        df["trainer_win_rate"] = df["trainer_win_rate"].fillna(0.0)
        df["trainer_recent_runs"] = df["trainer_recent_runs"].fillna(0)
        df["trainer_recent_win_rate"] = df["trainer_recent_win_rate"].fillna(0.0)

        # Simple transformations / caps
        df["trainer_runs_clipped"] = df["trainer_runs"].clip(0, 200)
        df["trainer_recent_runs_clipped"] = df["trainer_recent_runs"].clip(0, 50)

        # Normalise some numeric fields
        for col in [days_since_run_col, class_change_col, jockey_change_col]:
            if col in df.columns:
                df[col] = df[col].fillna(0).clip(-60, 365)

        feature_cols = [
            "trainer_runs_clipped",
            "trainer_win_rate",
            "trainer_recent_runs_clipped",
            "trainer_recent_win_rate",
        ]

        if days_since_run_col in df.columns:
            feature_cols.append(days_since_run_col)
        if class_change_col in df.columns:
            feature_cols.append(class_change_col)
        if jockey_change_col in df.columns:
            feature_cols.append(jockey_change_col)

        return df[feature_cols]

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _ensure_fitted(self) -> None:
        if not self._fitted or self._model is None:
            raise RuntimeError("TrainerIntentEngine is not fitted. Call .fit() first.")


# Backward compatibility alias
TIE = TrainerIntentEngine

