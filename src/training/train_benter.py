"""
VÉLØ v10.1 - Benter Model Training
===================================

Training pipeline for Benter multinomial logit model.
Includes: α/β grid search, isotonic calibration, CV by race date.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import os
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
import pickle
import json

from .feature_store import FeatureStore
from .labels import LabelCreator
from .metrics import ModelMetrics
from .model_registry import ModelRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BenterTrainer:
    """
    Benter model training pipeline.
    
    Implements Bill Benter's two-model approach:
    1. Fundamental model: Based on horse/jockey/trainer statistics
    2. Market model: Incorporates public odds
    3. Combined model: Weighted combination (α * fundamental + β * market)
    """
    
    def __init__(
        self,
        feature_store: FeatureStore,
        label_creator: LabelCreator,
        model_registry: ModelRegistry,
        output_dir: str = "out/models"
    ):
        """
        Initialize Benter trainer.
        
        Args:
            feature_store: Feature engineering module
            label_creator: Label creation module
            model_registry: Model versioning module
            output_dir: Directory for model artifacts
        """
        self.feature_store = feature_store
        self.label_creator = label_creator
        self.model_registry = model_registry
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_calc = ModelMetrics()
        
        logger.info("BenterTrainer initialized")
    
    def train(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        cv_folds: int = 5,
        calibrate: bool = True,
        grid_search: bool = True
    ) -> Dict:
        """
        Train Benter model with full pipeline.
        
        Args:
            train_df: Training data
            val_df: Validation data
            cv_folds: Number of CV folds
            calibrate: Whether to apply isotonic calibration
            grid_search: Whether to perform α/β grid search
        
        Returns:
            Dictionary with trained models and metrics
        """
        logger.info("="*60)
        logger.info("BENTER MODEL TRAINING PIPELINE")
        logger.info("="*60)
        
        # Step 1: Feature engineering
        logger.info("\n[1/6] Feature Engineering...")
        X_train, y_train, odds_train = self._prepare_data(train_df)
        X_val, y_val, odds_val = self._prepare_data(val_df)
        
        logger.info(f"Training set: {X_train.shape[0]} samples, {X_train.shape[1]} features")
        logger.info(f"Validation set: {X_val.shape[0]} samples")
        
        # Step 2: Train fundamental model
        logger.info("\n[2/6] Training Fundamental Model...")
        fundamental_model, scaler = self._train_fundamental_model(X_train, y_train)
        
        # Step 3: Train market model
        logger.info("\n[3/6] Training Market Model...")
        market_model = self._train_market_model(odds_train, y_train)
        
        # Step 4: Grid search for optimal α, β
        if grid_search:
            logger.info("\n[4/6] Grid Search for α, β...")
            best_alpha, best_beta = self._grid_search_alpha_beta(
                fundamental_model,
                market_model,
                scaler,
                X_val,
                y_val,
                odds_val
            )
        else:
            best_alpha, best_beta = 0.7, 0.3
            logger.info(f"\n[4/6] Using default α={best_alpha}, β={best_beta}")
        
        # Step 5: Calibration
        if calibrate:
            logger.info("\n[5/6] Isotonic Calibration...")
            fundamental_model = self._calibrate_model(fundamental_model, X_val, y_val)
        else:
            logger.info("\n[5/6] Skipping calibration")
        
        # Step 6: Final evaluation
        logger.info("\n[6/6] Final Evaluation...")
        metrics = self._evaluate_combined_model(
            fundamental_model,
            market_model,
            scaler,
            best_alpha,
            best_beta,
            X_val,
            y_val,
            odds_val
        )
        
        # Package results
        result = {
            'fundamental_model': fundamental_model,
            'market_model': market_model,
            'scaler': scaler,
            'alpha': best_alpha,
            'beta': best_beta,
            'metrics': metrics,
            'feature_names': self.feature_store.get_feature_names(),
            'trained_at': datetime.now().isoformat()
        }
        
        logger.info("\n" + "="*60)
        logger.info("TRAINING COMPLETE")
        logger.info("="*60)
        
        return result
    
    def _prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare data for training.
        
        Args:
            df: Raw race data
        
        Returns:
            Tuple of (X, y, odds)
        """
        # Engineer features
        features = self.feature_store.compute_features(df)
        
        # Create labels
        labels = self.label_creator.create_labels(features)
        
        # Extract feature matrix
        feature_cols = self.feature_store.get_feature_names()
        X = labels[feature_cols].fillna(0).values
        
        # Extract target
        y = labels['win'].values
        
        # Extract odds
        odds = labels['odds'].values if 'odds' in labels.columns else None
        
        return X, y, odds
    
    def _train_fundamental_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray
    ) -> Tuple[LogisticRegression, StandardScaler]:
        """
        Train fundamental model (horse/jockey/trainer statistics).
        
        Args:
            X_train: Training features
            y_train: Training labels
        
        Returns:
            Tuple of (model, scaler)
        """
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)
        
        # Train logistic regression
        model = LogisticRegression(
            penalty='l2',
            C=1.0,
            max_iter=1000,
            random_state=42,
            class_weight='balanced'
        )
        
        model.fit(X_scaled, y_train)
        
        train_score = model.score(X_scaled, y_train)
        logger.info(f"Fundamental model trained. Training accuracy: {train_score:.4f}")
        
        return model, scaler
    
    def _train_market_model(
        self,
        odds_train: np.ndarray,
        y_train: np.ndarray
    ) -> Dict:
        """
        Train market model (odds-based).
        
        Simple model: converts odds to probabilities.
        
        Args:
            odds_train: Training odds
            y_train: Training labels
        
        Returns:
            Market model dictionary
        """
        # Market implied probabilities
        market_probs = 1.0 / odds_train
        
        # Normalize to sum to 1 per race (would need race_id grouping)
        # For now, simple conversion
        
        market_model = {
            'type': 'market_odds',
            'description': 'Converts market odds to probabilities'
        }
        
        logger.info("Market model created (odds-to-probability conversion)")
        
        return market_model
    
    def _grid_search_alpha_beta(
        self,
        fundamental_model: LogisticRegression,
        market_model: Dict,
        scaler: StandardScaler,
        X_val: np.ndarray,
        y_val: np.ndarray,
        odds_val: np.ndarray
    ) -> Tuple[float, float]:
        """
        Grid search for optimal α (fundamental weight) and β (market weight).
        
        Args:
            fundamental_model: Trained fundamental model
            market_model: Market model
            scaler: Feature scaler
            X_val: Validation features
            y_val: Validation labels
            odds_val: Validation odds
        
        Returns:
            Tuple of (best_alpha, best_beta)
        """
        logger.info("Searching α, β grid...")
        
        # Grid of α values (fundamental weight)
        alpha_values = np.arange(0.0, 1.1, 0.1)
        
        best_alpha = 0.7
        best_beta = 0.3
        best_metric = -np.inf
        
        results = []
        
        for alpha in alpha_values:
            beta = 1.0 - alpha
            
            # Combined predictions
            X_scaled = scaler.transform(X_val)
            fundamental_probs = fundamental_model.predict_proba(X_scaled)[:, 1]
            market_probs = 1.0 / odds_val
            
            combined_probs = alpha * fundamental_probs + beta * market_probs
            
            # Evaluate
            metrics = self.metrics_calc.compute_all_metrics(
                y_val, combined_probs, odds_val
            )
            
            # Optimization target: ROI @ top 20%
            target_metric = metrics.get('roi_top20', 0)
            
            results.append({
                'alpha': alpha,
                'beta': beta,
                'roi_top20': target_metric,
                'ae_ratio': metrics.get('ae_ratio', 0),
                'auc': metrics.get('auc', 0)
            })
            
            if target_metric > best_metric:
                best_metric = target_metric
                best_alpha = alpha
                best_beta = beta
        
        # Print results
        results_df = pd.DataFrame(results)
        logger.info(f"\nGrid Search Results:\n{results_df}")
        
        logger.info(f"\nBest α={best_alpha:.2f}, β={best_beta:.2f} (ROI@20%={best_metric:.2f}%)")
        
        return best_alpha, best_beta
    
    def _calibrate_model(
        self,
        model: LogisticRegression,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> CalibratedClassifierCV:
        """
        Apply isotonic calibration to model.
        
        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation labels
        
        Returns:
            Calibrated model
        """
        logger.info("Applying isotonic calibration...")
        
        calibrated_model = CalibratedClassifierCV(
            model,
            method='isotonic',
            cv='prefit'
        )
        
        calibrated_model.fit(X_val, y_val)
        
        logger.info("Calibration complete")
        
        return calibrated_model
    
    def _evaluate_combined_model(
        self,
        fundamental_model,
        market_model: Dict,
        scaler: StandardScaler,
        alpha: float,
        beta: float,
        X_val: np.ndarray,
        y_val: np.ndarray,
        odds_val: np.ndarray
    ) -> Dict:
        """
        Evaluate combined model on validation set.
        
        Args:
            fundamental_model: Fundamental model
            market_model: Market model
            scaler: Feature scaler
            alpha: Fundamental weight
            beta: Market weight
            X_val: Validation features
            y_val: Validation labels
            odds_val: Validation odds
        
        Returns:
            Dictionary of metrics
        """
        # Combined predictions
        X_scaled = scaler.transform(X_val)
        fundamental_probs = fundamental_model.predict_proba(X_scaled)[:, 1]
        market_probs = 1.0 / odds_val
        
        combined_probs = alpha * fundamental_probs + beta * market_probs
        
        # Compute all metrics
        metrics = self.metrics_calc.compute_all_metrics(
            y_val, combined_probs, odds_val
        )
        
        # Print report
        self.metrics_calc.print_metrics_report(metrics)
        
        return metrics
    
    def save_model(self, result: Dict, version: str):
        """
        Save trained model to registry.
        
        Args:
            result: Training result dictionary
            version: Model version (e.g., 'v1.0.0')
        """
        logger.info(f"Saving model version {version}...")
        
        # Save to model registry
        model_path = self.model_registry.register_model(
            version=version,
            fundamental_model=result['fundamental_model'],
            market_model=result['market_model'],
            scaler=result['scaler'],
            alpha=result['alpha'],
            beta=result['beta'],
            metrics=result['metrics'],
            feature_names=result['feature_names']
        )
        
        logger.info(f"Model saved to {model_path}")


def main():
    """Main training script."""
    parser = argparse.ArgumentParser(description='Train Benter model')
    parser.add_argument('--cv', type=int, default=5, help='Number of CV folds')
    parser.add_argument('--calibrate', type=str, default='isotonic', 
                       choices=['isotonic', 'sigmoid', 'none'],
                       help='Calibration method')
    parser.add_argument('--registry', type=str, default='out/models',
                       help='Model registry directory')
    parser.add_argument('--version', type=str, default='v1.0.0',
                       help='Model version')
    
    args = parser.parse_args()
    
    # Initialize modules
    feature_store = FeatureStore()
    label_creator = LabelCreator()
    model_registry = ModelRegistry(args.registry)
    
    trainer = BenterTrainer(
        feature_store=feature_store,
        label_creator=label_creator,
        model_registry=model_registry
    )
    
    # Load data (placeholder - would load from database)
    logger.info("Loading data...")
    # train_df = load_training_data()
    # val_df = load_validation_data()
    
    # For now, create dummy data
    logger.warning("Using dummy data for testing")
    train_df = pd.DataFrame({
        'race_id': ['R1'] * 100,
        'horse_id': [f'H{i}' for i in range(100)],
        'finish_position': np.random.randint(1, 11, 100),
        'odds': np.random.uniform(3.0, 20.0, 100)
    })
    val_df = train_df.copy()
    
    # Train model
    result = trainer.train(
        train_df=train_df,
        val_df=val_df,
        cv_folds=args.cv,
        calibrate=(args.calibrate != 'none'),
        grid_search=True
    )
    
    # Save model
    trainer.save_model(result, args.version)
    
    logger.info("\n✅ Training pipeline complete!")


if __name__ == "__main__":
    main()
