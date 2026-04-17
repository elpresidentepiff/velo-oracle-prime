"""
VÉLØ LightGBM Model Training
Trains core predictor with hyperparameter optimization.
"""

import json
import numpy as np
import lightgbm as lgb
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, log_loss, accuracy_score
from typing import Dict, Any, Tuple
import pickle

from training_data import TrainingDataManager


class VeloPredictor:
    """
    VÉLØ Core Predictor using LightGBM.
    
    Outputs:
    - p(win): Probability of winning the race
    - p(top4): Probability of finishing in top 4
    """
    
    def __init__(self):
        self.model_win = None
        self.model_top4 = None
        self.feature_names = None
        self.training_stats = {}
    
    def train(
        self,
        X_train: np.ndarray,
        y_train_win: np.ndarray,
        y_train_top4: np.ndarray,
        X_val: np.ndarray,
        y_val_win: np.ndarray,
        y_val_top4: np.ndarray,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Train both win and top4 models.
        
        Args:
            X_train: Training features (n_samples, 61)
            y_train_win: Win labels (n_samples,)
            y_train_top4: Top4 labels (n_samples,)
            X_val: Validation features
            y_val_win: Validation win labels
            y_val_top4: Validation top4 labels
            params: Optional hyperparameters
        
        Returns:
            Training statistics dict
        """
        if params is None:
            params = self._get_default_params()
        
        print("=" * 80)
        print("VÉLØ LightGBM Training")
        print("=" * 80)
        print()
        
        # Train win model
        print("Training WIN model...")
        self.model_win, win_stats = self._train_single_model(
            X_train, y_train_win, X_val, y_val_win, params, 'win'
        )
        
        print()
        
        # Train top4 model
        print("Training TOP4 model...")
        self.model_top4, top4_stats = self._train_single_model(
            X_train, y_train_top4, X_val, y_val_top4, params, 'top4'
        )
        
        self.training_stats = {
            'win': win_stats,
            'top4': top4_stats,
        }
        
        return self.training_stats
    
    def _train_single_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        params: Dict[str, Any],
        model_name: str
    ) -> Tuple[lgb.Booster, Dict[str, Any]]:
        """Train single LightGBM model."""
        
        # Create datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        # Train model
        callbacks = [
            lgb.log_evaluation(period=50),
            lgb.early_stopping(stopping_rounds=50, verbose=True)
        ]
        
        model = lgb.train(
            params,
            train_data,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            num_boost_round=1000,
            callbacks=callbacks
        )
        
        # Evaluate
        y_pred_train = model.predict(X_train)
        y_pred_val = model.predict(X_val)
        
        stats = {
            'train_auc': roc_auc_score(y_train, y_pred_train),
            'val_auc': roc_auc_score(y_val, y_pred_val),
            'train_logloss': log_loss(y_train, y_pred_train),
            'val_logloss': log_loss(y_val, y_pred_val),
            'n_trees': model.num_trees(),
            'best_iteration': model.best_iteration,
        }
        
        print(f"\n{model_name.upper()} Model Performance:")
        print(f"  Train AUC: {stats['train_auc']:.4f}")
        print(f"  Val AUC: {stats['val_auc']:.4f}")
        print(f"  Train LogLoss: {stats['train_logloss']:.4f}")
        print(f"  Val LogLoss: {stats['val_logloss']:.4f}")
        print(f"  Trees: {stats['n_trees']} (best: {stats['best_iteration']})")
        
        return model, stats
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default LightGBM hyperparameters."""
        return {
            'objective': 'binary',
            'metric': ['auc', 'binary_logloss'],
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_data_in_leaf': 20,
            'min_gain_to_split': 0.0,
            'lambda_l1': 0.0,
            'lambda_l2': 0.0,
            'verbose': -1,
            'seed': 42,
        }
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Generate predictions for runners.
        
        Args:
            X: Feature matrix (n_runners, 61)
        
        Returns:
            Dict with 'p_win' and 'p_top4' arrays
        """
        if self.model_win is None or self.model_top4 is None:
            raise ValueError("Models not trained. Call train() first.")
        
        p_win = self.model_win.predict(X)
        p_top4 = self.model_top4.predict(X)
        
        return {
            'p_win': p_win,
            'p_top4': p_top4,
        }
    
    def get_feature_importance(self, importance_type: str = 'gain') -> Dict[str, float]:
        """Get feature importance from win model."""
        if self.model_win is None:
            raise ValueError("Model not trained.")
        
        importance = self.model_win.feature_importance(importance_type=importance_type)
        feature_names = [f"feature_{i}" for i in range(len(importance))]
        
        return dict(zip(feature_names, importance))
    
    def save(self, filepath: str):
        """Save trained models to disk."""
        save_dict = {
            'model_win': self.model_win,
            'model_top4': self.model_top4,
            'training_stats': self.training_stats,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_dict, f)
        
        print(f"✅ Saved models to {filepath}")
    
    def load(self, filepath: str):
        """Load trained models from disk."""
        with open(filepath, 'rb') as f:
            save_dict = pickle.load(f)
        
        self.model_win = save_dict['model_win']
        self.model_top4 = save_dict['model_top4']
        self.training_stats = save_dict.get('training_stats', {})
        
        print(f"✅ Loaded models from {filepath}")


def main():
    """Train VÉLØ predictor on synthetic dataset."""
    
    # Load training data
    manager = TrainingDataManager()
    examples = manager.load_training_examples('synthetic_dataset_v1.json')
    
    # Convert to arrays
    X, y_win = manager.examples_to_arrays(examples, target='won')
    X, y_top4 = manager.examples_to_arrays(examples, target='top4')
    
    # Train/val split
    X_train, X_val, y_train_win, y_val_win = train_test_split(
        X, y_win, test_size=0.2, random_state=42, stratify=y_win
    )
    _, _, y_train_top4, y_val_top4 = train_test_split(
        X, y_top4, test_size=0.2, random_state=42, stratify=y_top4
    )
    
    print(f"Training set: {X_train.shape[0]} examples")
    print(f"Validation set: {X_val.shape[0]} examples")
    print()
    
    # Train model
    predictor = VeloPredictor()
    stats = predictor.train(
        X_train, y_train_win, y_train_top4,
        X_val, y_val_win, y_val_top4
    )
    
    # Save model
    model_dir = Path("/home/ubuntu/velo-oracle-prime/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    predictor.save(model_dir / "velo_predictor_v1.pkl")
    
    # Test prediction
    print()
    print("=" * 80)
    print("Testing Predictions")
    print("=" * 80)
    print()
    
    # Predict on first 5 validation examples
    X_test = X_val[:5]
    predictions = predictor.predict(X_test)
    
    print("Sample Predictions:")
    for i in range(5):
        print(f"  Runner {i+1}:")
        print(f"    p(win)  = {predictions['p_win'][i]:.3f}")
        print(f"    p(top4) = {predictions['p_top4'][i]:.3f}")
        print(f"    Actual: win={y_val_win[i]}, top4={y_val_top4[i]}")
    
    print()
    print("✅ Model training complete")


if __name__ == "__main__":
    main()
