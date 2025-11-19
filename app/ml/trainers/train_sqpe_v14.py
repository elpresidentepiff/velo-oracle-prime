"""
VÉLØ Oracle - SQPE v14 Trainer
Sub-Quadratic Probability Engine using GBM/XGBoost
"""
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQPEv14Trainer:
    """
    SQPE v14 Trainer - Gradient Boosting Model
    Target: AUC 0.87+ (up from 0.83)
    """
    
    def __init__(self, model_version: str = "v14.0"):
        self.model_version = model_version
        self.model = None
        self.feature_names = []
        self.metrics = {}
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None
    ) -> Dict[str, Any]:
        """
        Train SQPE v14 model
        
        Args:
            X_train: Training features
            y_train: Training labels (1=won, 0=lost)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            
        Returns:
            Training metrics
        """
        logger.info("="*60)
        logger.info(f"Training SQPE {self.model_version}")
        logger.info("="*60)
        
        logger.info(f"Training samples: {len(X_train):,}")
        logger.info(f"Features: {X_train.shape[1]}")
        logger.info(f"Positive rate: {y_train.mean():.4f}")
        
        self.feature_names = list(X_train.columns)
        
        # Simulate GBM training (would use XGBoost/LightGBM in production)
        logger.info("\nTraining GBM model...")
        
        # Mock model (in production, use real XGBoost)
        from sklearn.ensemble import GradientBoostingClassifier
        
        self.model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            min_samples_split=100,
            min_samples_leaf=50,
            subsample=0.8,
            random_state=42,
            verbose=0
        )
        
        self.model.fit(X_train, y_train)
        
        # Training metrics
        train_pred = self.model.predict_proba(X_train)[:, 1]
        train_auc = self._calculate_auc(y_train, train_pred)
        train_logloss = self._calculate_logloss(y_train, train_pred)
        
        logger.info(f"\nTraining metrics:")
        logger.info(f"  AUC: {train_auc:.4f}")
        logger.info(f"  Log Loss: {train_logloss:.4f}")
        
        # Validation metrics
        if X_val is not None and y_val is not None:
            val_pred = self.model.predict_proba(X_val)[:, 1]
            val_auc = self._calculate_auc(y_val, val_pred)
            val_logloss = self._calculate_logloss(y_val, val_pred)
            
            logger.info(f"\nValidation metrics:")
            logger.info(f"  AUC: {val_auc:.4f}")
            logger.info(f"  Log Loss: {val_logloss:.4f}")
            
            self.metrics = {
                "train_auc": train_auc,
                "train_logloss": train_logloss,
                "val_auc": val_auc,
                "val_logloss": val_logloss,
                "version": self.model_version,
                "n_features": len(self.feature_names),
                "n_samples": len(X_train),
                "trained_at": datetime.utcnow().isoformat()
            }
        else:
            self.metrics = {
                "train_auc": train_auc,
                "train_logloss": train_logloss,
                "version": self.model_version,
                "n_features": len(self.feature_names),
                "n_samples": len(X_train),
                "trained_at": datetime.utcnow().isoformat()
            }
        
        logger.info("\n✅ Training complete")
        
        return self.metrics
    
    def save(self, model_path: str, metadata_path: str = None):
        """Save model and metadata"""
        logger.info(f"\nSaving model to {model_path}...")
        
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        if metadata_path:
            metadata = {
                "version": self.model_version,
                "feature_names": self.feature_names,
                "metrics": self.metrics,
                "model_type": "GradientBoostingClassifier",
                "saved_at": datetime.utcnow().isoformat()
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved metadata to {metadata_path}")
        
        logger.info("✅ Model saved")
    
    @staticmethod
    def _calculate_auc(y_true, y_pred):
        """Calculate AUC-ROC"""
        from sklearn.metrics import roc_auc_score
        try:
            return roc_auc_score(y_true, y_pred)
        except:
            return 0.5
    
    @staticmethod
    def _calculate_logloss(y_true, y_pred):
        """Calculate log loss"""
        from sklearn.metrics import log_loss
        try:
            return log_loss(y_true, y_pred)
        except:
            return 1.0


if __name__ == "__main__":
    # Test trainer
    print("SQPE v14 Trainer - Test")
    
    # Create sample data
    np.random.seed(42)
    n_samples = 1000
    n_features = 60
    
    X_train = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    y_train = pd.Series(np.random.randint(0, 2, n_samples))
    
    X_val = pd.DataFrame(
        np.random.randn(200, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    y_val = pd.Series(np.random.randint(0, 2, 200))
    
    # Train
    trainer = SQPEv14Trainer()
    metrics = trainer.train(X_train, y_train, X_val, y_val)
    
    print("\nMetrics:", metrics)
    
    # Save
    trainer.save("models/sqpe_v14/sqpe_v14.pkl", "models/sqpe_v14/metadata.json")
    
    print("\n✅ Test complete")
