"""
SQPE - Sub-Quadratic Prediction Engine

Purpose: ML-powered win probability engine with signal convergence analysis

The SQPE is the core intelligence layer that generates calibrated win probabilities
using a trained GradientBoosting model, with optional signal convergence adjustments.

Key Concepts:
- ML Core: GradientBoosting classifier with isotonic calibration
- TimeSeriesSplit: Prevents lookahead bias in training
- Signal convergence: Multi-factor validation (optional adjustment layer)
- Persistence: Save/load trained models

Author: VÉLØ Oracle Team
Version: 2.0 (ML-based)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.model_selection import TimeSeriesSplit


# ============================================================================
# ML Core Constants
# ============================================================================

SQPE_MODEL_FILENAME = "sqpe_model.pkl"
SQPE_CALIBRATOR_FILENAME = "sqpe_calibrator.pkl"
SQPE_META_FILENAME = "sqpe_meta.json"


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class SQPEConfig:
    """
    Configuration for the Sub-Quadratic Probability Engine.

    Attributes:
        n_estimators: Number of boosting stages.
        learning_rate: Shrinkage applied at each boosting step.
        max_depth: Max depth of individual trees.
        min_samples_leaf: Min samples per leaf node.
        time_splits: Number of folds for TimeSeriesSplit.
        calibration_method: 'sigmoid' or 'isotonic'.
        random_state: RNG seed.
        convergence_threshold: Minimum convergence score for signal analysis.
        min_confidence: Minimum confidence for strong signal classification.
        longshot_threshold: Odds threshold for longshot classification.
    """

    n_estimators: int = 400
    learning_rate: float = 0.05
    max_depth: int = 3
    min_samples_leaf: int = 40
    time_splits: int = 5
    calibration_method: str = "isotonic"
    random_state: int = 42
    
    # Signal analysis parameters (legacy compatibility)
    convergence_threshold: float = 0.6
    min_confidence: float = 0.5
    longshot_threshold: float = 10.0


# ============================================================================
# Signal Analysis (Legacy Support)
# ============================================================================

class SignalStrength(Enum):
    """Signal strength classification"""
    STRONG = "strong"          # High confidence, multiple factors align
    MODERATE = "moderate"      # Some factors align
    WEAK = "weak"              # Single factor or contradictory
    NOISE = "noise"            # No clear signal


@dataclass
class SQPESignal:
    """SQPE analysis result for a single runner"""
    runner_id: str
    horse_name: str
    
    # Core probabilities
    p_benter: float           # ML model probability
    p_public: float           # Market probability
    edge: float               # p_benter - p_public
    
    # Signal components
    rating_signal: float      # Strength from ratings (0-1)
    form_signal: float        # Strength from recent form (0-1)
    class_signal: float       # Strength from class/quality (0-1)
    market_signal: float      # Strength from market movement (0-1)
    
    # Convergence analysis
    convergence_score: float  # How many signals agree (0-1)
    signal_strength: SignalStrength
    
    # Final ranking
    sqpe_score: float         # Combined score for ranking
    confidence: float         # Confidence in prediction (0-1)
    
    # Metadata
    odds: float
    is_longshot: bool         # odds > 10.0


# ============================================================================
# ML Core Engine
# ============================================================================

class _MLCore:
    """
    Internal ML core for SQPE.
    
    Handles GradientBoosting training, calibration, and persistence.
    Not exposed in public API - accessed only through SQPEEngine.
    """
    
    def __init__(self, config: SQPEConfig) -> None:
        self.config = config
        self._model: Optional[GradientBoostingClassifier] = None
        self._calibrator: Optional[CalibratedClassifierCV] = None
        self._feature_names: Optional[List[str]] = None
        self._fitted: bool = False
        self._cv_metrics: Optional[dict] = None
    
    @property
    def is_fitted(self) -> bool:
        return self._fitted
    
    @property
    def cv_metrics(self) -> Optional[dict]:
        return self._cv_metrics
    
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        time_order: Optional[Iterable[int]] = None,
    ) -> None:
        """Train the ML model with TimeSeriesSplit validation."""
        if time_order is not None:
            X = X.loc[time_order]
            y = y.loc[time_order]
        
        self._feature_names = list(X.columns)
        
        base_model = GradientBoostingClassifier(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            min_samples_leaf=self.config.min_samples_leaf,
            random_state=self.config.random_state,
        )
        
        # TimeSeriesSplit cross-validation
        tscv = TimeSeriesSplit(n_splits=self.config.time_splits)
        log_losses: List[float] = []
        briers: List[float] = []
        
        X_values = X.values
        y_values = y.values
        
        for train_idx, val_idx in tscv.split(X_values):
            X_train, X_val = X_values[train_idx], X_values[val_idx]
            y_train, y_val = y_values[train_idx], y_values[val_idx]
            
            fold_model = GradientBoostingClassifier(
                n_estimators=self.config.n_estimators,
                learning_rate=self.config.learning_rate,
                max_depth=self.config.max_depth,
                min_samples_leaf=self.config.min_samples_leaf,
                random_state=self.config.random_state,
            )
            fold_model.fit(X_train, y_train)
            proba_val = fold_model.predict_proba(X_val)[:, 1]
            
            log_losses.append(log_loss(y_val, proba_val, eps=1e-15))
            briers.append(brier_score_loss(y_val, proba_val))
        
        self._cv_metrics = {
            "log_loss_mean": float(np.mean(log_losses)),
            "log_loss_std": float(np.std(log_losses)),
            "brier_mean": float(np.mean(briers)),
            "brier_std": float(np.std(briers)),
        }
        
        # Fit final model on full data
        base_model.fit(X_values, y_values)
        
        # Wrap with calibrator
        calibrator = CalibratedClassifierCV(
            base_model,
            method=self.config.calibration_method,
            cv="prefit",
        )
        calibrator.fit(X_values, y_values)
        
        self._model = base_model
        self._calibrator = calibrator
        self._fitted = True
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated win probabilities."""
        if not self._fitted or self._calibrator is None:
            raise RuntimeError("ML core not fitted. Call fit() first.")
        
        X = X[self._feature_names]  # type: ignore[index]
        proba = self._calibrator.predict_proba(X.values)[:, 1]  # type: ignore[union-attr]
        return np.clip(proba, 1e-6, 1 - 1e-6)
    
    def save(self, directory: Path) -> None:
        """Persist model to disk."""
        if not self._fitted:
            raise RuntimeError("ML core not fitted. Cannot save.")
        
        directory.mkdir(parents=True, exist_ok=True)
        
        joblib.dump(self._model, directory / SQPE_MODEL_FILENAME)
        joblib.dump(self._calibrator, directory / SQPE_CALIBRATOR_FILENAME)
        
        meta = {
            "feature_names": self._feature_names,
            "config": self.config.__dict__,
            "cv_metrics": self._cv_metrics,
        }
        (directory / SQPE_META_FILENAME).write_text(pd.Series(meta).to_json())
    
    @classmethod
    def load(cls, directory: Path, config: SQPEConfig) -> "_MLCore":
        """Load model from disk."""
        model = joblib.load(directory / SQPE_MODEL_FILENAME)
        calibrator = joblib.load(directory / SQPE_CALIBRATOR_FILENAME)
        meta = pd.read_json((directory / SQPE_META_FILENAME).read_text(), typ="series")
        
        core = cls(config)
        core._model = model
        core._calibrator = calibrator
        core._feature_names = list(meta["feature_names"])
        core._cv_metrics = dict(meta.get("cv_metrics", {}))
        core._fitted = True
        return core


# ============================================================================
# Unified SQPE Engine (Public API)
# ============================================================================

class SQPEEngine:
    """
    Sub-Quadratic Probability Engine (Unified ML + Signal Analysis)
    
    Primary Responsibilities:
        - Generate calibrated win probabilities via ML core
        - Provide signal convergence analysis for validation
        - Persist and load trained models
        - Maintain backward compatibility with existing code
    
    Public API:
        - fit(X, y): Train the ML model
        - predict_proba(X): Get calibrated win probabilities
        - analyze_runner(runner, p_benter, p_public): Signal analysis
        - analyze_race(runners, p_dict, p_public_dict): Full race analysis
        - save(directory): Persist model
        - load(directory): Load model
    """
    
    def __init__(self, config: Optional[SQPEConfig] = None) -> None:
        """
        Initialize SQPE engine.
        
        Args:
            config: Configuration object. Uses defaults if None.
        """
        self.config = config or SQPEConfig()
        self._ml_core = _MLCore(self.config)
        self._fitted: bool = False
    
    # -------------------------------------------------------------------------
    # Core ML API
    # -------------------------------------------------------------------------
    
    @property
    def is_fitted(self) -> bool:
        """Check if model is trained."""
        return self._ml_core.is_fitted
    
    @property
    def cv_metrics(self) -> Optional[dict]:
        """Return cross-validation metrics if available."""
        return self._ml_core.cv_metrics
    
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        time_order: Optional[Iterable[int]] = None,
    ) -> None:
        """
        Train the SQPE model with TimeSeriesSplit validation.
        
        Args:
            X: Runner-level feature matrix.
            y: Binary Series (1 = winner, 0 = loser).
            time_order: Optional ordering index for TimeSeriesSplit.
        """
        self._ml_core.fit(X, y, time_order)
        self._fitted = True
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict calibrated win probabilities for each runner.
        
        Args:
            X: Runner-level features with same columns as training.
        
        Returns:
            Array of shape (n_samples,) with calibrated win probabilities.
        """
        return self._ml_core.predict_proba(X)
    
    # -------------------------------------------------------------------------
    # Signal Analysis API (Legacy Compatibility)
    # -------------------------------------------------------------------------
    
    def calculate_rating_signal(self, runner: pd.Series) -> float:
        """Calculate signal strength from ratings."""
        ratings = []
        if pd.notna(runner.get('or_int')): ratings.append(runner['or_int'])
        if pd.notna(runner.get('rpr_int')): ratings.append(runner['rpr_int'])
        if pd.notna(runner.get('ts_int')): ratings.append(runner['ts_int'])
        
        if not ratings:
            return 0.0
        
        avg_rating = np.mean(ratings)
        normalized = np.clip(avg_rating / 140.0, 0, 1)
        
        if len(ratings) > 1:
            std = np.std(ratings)
            consistency = 1.0 - np.clip(std / 20.0, 0, 1)
            normalized *= (1.0 + 0.2 * consistency)
        
        return np.clip(normalized, 0, 1)
    
    def calculate_form_signal(self, runner: pd.Series) -> float:
        """Calculate signal strength from recent form."""
        if pd.notna(runner.get('pos_int')) and runner['pos_int'] <= 3:
            return 0.7
        return 0.3
    
    def calculate_class_signal(self, runner: pd.Series) -> float:
        """Calculate signal strength from class/quality."""
        if pd.notna(runner.get('class')):
            try:
                class_val = int(runner['class'])
                return np.clip((8 - class_val) / 7.0, 0, 1)
            except:
                pass
        return 0.5
    
    def calculate_market_signal(self, runner: pd.Series) -> float:
        """Calculate signal strength from market behavior."""
        if pd.notna(runner.get('sp_decimal')):
            p_market = 1.0 / runner['sp_decimal']
            return np.clip(p_market * 2.0, 0, 1)
        return 0.0
    
    def calculate_convergence(self, signals: List[float]) -> float:
        """Calculate convergence score from multiple signals."""
        if not signals:
            return 0.0
        std = np.std(signals)
        return 1.0 - np.clip(std, 0, 1)
    
    def classify_signal_strength(
        self,
        convergence: float,
        confidence: float
    ) -> SignalStrength:
        """Classify overall signal strength."""
        if convergence >= self.config.convergence_threshold and confidence >= self.config.min_confidence:
            return SignalStrength.STRONG
        elif convergence >= 0.4 and confidence >= 0.3:
            return SignalStrength.MODERATE
        elif convergence >= 0.2:
            return SignalStrength.WEAK
        else:
            return SignalStrength.NOISE
    
    def calculate_sqpe_score(
        self,
        edge: float,
        convergence: float,
        confidence: float,
        is_longshot: bool
    ) -> float:
        """Calculate final SQPE score for ranking."""
        score = edge * convergence * confidence
        if is_longshot:
            score *= 0.7
        return score
    
    def analyze_runner(
        self,
        runner: pd.Series,
        p_benter: float,
        p_public: float
    ) -> SQPESignal:
        """
        Analyze a single runner and generate SQPE signal.
        
        Args:
            runner: Runner data (pandas Series)
            p_benter: ML model probability
            p_public: Market probability
        
        Returns:
            SQPESignal object with full analysis
        """
        rating_signal = self.calculate_rating_signal(runner)
        form_signal = self.calculate_form_signal(runner)
        class_signal = self.calculate_class_signal(runner)
        market_signal = self.calculate_market_signal(runner)
        
        signals = [rating_signal, form_signal, class_signal, market_signal]
        convergence = self.calculate_convergence(signals)
        confidence = np.mean(signals)
        
        edge = p_benter - p_public
        odds = runner.get('sp_decimal', 0)
        is_longshot = odds > self.config.longshot_threshold
        
        signal_strength = self.classify_signal_strength(convergence, confidence)
        sqpe_score = self.calculate_sqpe_score(edge, convergence, confidence, is_longshot)
        
        return SQPESignal(
            runner_id=f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}",
            horse_name=runner.get('horse', 'Unknown'),
            p_benter=p_benter,
            p_public=p_public,
            edge=edge,
            rating_signal=rating_signal,
            form_signal=form_signal,
            class_signal=class_signal,
            market_signal=market_signal,
            convergence_score=convergence,
            signal_strength=signal_strength,
            sqpe_score=sqpe_score,
            confidence=confidence,
            odds=odds,
            is_longshot=is_longshot
        )
    
    def analyze_race(
        self,
        runners: pd.DataFrame,
        p_benter_dict: Dict[str, float],
        p_public_dict: Dict[str, float]
    ) -> List[SQPESignal]:
        """
        Analyze all runners in a race.
        
        Args:
            runners: DataFrame of runners in race
            p_benter_dict: Dict mapping runner_id to ML probability
            p_public_dict: Dict mapping runner_id to public probability
        
        Returns:
            List of SQPESignal objects, sorted by sqpe_score (descending)
        """
        signals = []
        
        for idx, runner in runners.iterrows():
            runner_id = f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}"
            p_benter = p_benter_dict.get(runner_id, 0.0)
            p_public = p_public_dict.get(runner_id, 0.0)
            
            signal = self.analyze_runner(runner, p_benter, p_public)
            signals.append(signal)
        
        signals.sort(key=lambda x: x.sqpe_score, reverse=True)
        return signals
    
    def filter_strong_signals(self, signals: List[SQPESignal]) -> List[SQPESignal]:
        """Filter to only strong signals."""
        return [s for s in signals if s.signal_strength == SignalStrength.STRONG]
    
    def get_top_opportunities(
        self,
        signals: List[SQPESignal],
        top_n: int = 3
    ) -> List[SQPESignal]:
        """Get top N opportunities by SQPE score."""
        return signals[:top_n]
    
    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------
    
    def save(self, directory: Path) -> None:
        """
        Persist model, calibrator, and metadata to directory.
        
        Args:
            directory: Target directory. Created if not exists.
        """
        self._ml_core.save(directory)
    
    @classmethod
    def load(cls, directory: Path) -> "SQPEEngine":
        """
        Load a previously saved SQPEEngine from disk.
        
        Args:
            directory: Directory containing saved model files.
        
        Returns:
            Loaded SQPEEngine instance.
        """
        meta = pd.read_json((directory / SQPE_META_FILENAME).read_text(), typ="series")
        config = SQPEConfig(**meta["config"])
        
        engine = cls(config=config)
        engine._ml_core = _MLCore.load(directory, config)
        engine._fitted = True
        return engine


# Backward compatibility alias
SQPE = SQPEEngine

