"""
VÉLØ v1.1.0 - Model Training Script
====================================

Train Benter model with v1.1.0 features.
- Load features from parquet
- Train with warm-start α=0.25
- Target odds range: 5.0-21.0
- Save as v1.1.0

Author: VÉLØ Oracle Team
Version: 10.2.0
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import logging
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import yaml
import json
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main training script."""
    logger.info("="*60)
    logger.info("VÉLØ v1.1.0 - MODEL TRAINING")
    logger.info("="*60)
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    features_path = project_dir / "out/features_v11_train.parquet"
    model_dir = project_dir / "out/models/v1.1.0"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Load features
    logger.info(f"\nLoading features from {features_path}...")
    df = pd.read_parquet(features_path)
    logger.info(f"  Loaded: {len(df):,} records")
    logger.info(f"  Columns: {df.shape[1]}")
    logger.info(f"  Win rate: {df['win'].mean()*100:.2f}%")
    
    # Feature columns (v1.1.0 features)
    feature_cols = [
        # Family 1: Velocity
        'trainer_sr_14d', 'trainer_sr_30d', 'trainer_sr_90d',
        'jockey_sr_14d', 'jockey_sr_30d', 'jockey_sr_90d',
        'tj_combo_uplift',
        # Family 2: Class/Layoff
        'class_drop', 'classdrop_flag', 'layoff_days', 'layoff_penalty',
        'freshness_flag',
        # Family 3: Bias
        'course_going_iv', 'draw_iv', 'bias_persist_flag',
        # Family 4: Form
        'form_ewma', 'form_slope', 'form_var',
        # Market
        'odds'
    ]
    
    # Check feature availability
    available_features = [f for f in feature_cols if f in df.columns]
    logger.info(f"\n  Available features: {len(available_features)}/{len(feature_cols)}")
    
    X = df[available_features].values
    y = df['win'].values
    
    # Train/validation split (80/20)
    logger.info("\nSplitting train/validation (80/20)...")
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"  Train: {len(X_train):,} records")
    logger.info(f"  Validation: {len(X_val):,} records")
    
    # Train fundamental model
    logger.info("\nTraining fundamental model...")
    fund_model = LogisticRegression(
        penalty='l2',
        C=1.0,
        max_iter=1000,
        random_state=42
    )
    fund_model.fit(X_train, y_train)
    
    fund_probs_train = fund_model.predict_proba(X_train)[:, 1]
    fund_probs_val = fund_model.predict_proba(X_val)[:, 1]
    
    logger.info("  ✅ Fundamental model trained")
    
    # Market model (from odds)
    logger.info("\nCreating market model...")
    odds_train = X_train[:, -1]  # Last column is odds
    odds_val = X_val[:, -1]
    
    market_probs_train = 1.0 / odds_train
    market_probs_val = 1.0 / odds_val
    
    # Grid search for α (blend parameter)
    logger.info("\nGrid search for optimal α...")
    best_alpha = 0.25  # Warm-start
    best_auc = 0.0
    
    alphas = [0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5]
    
    for alpha in alphas:
        # Blend: α * fundamental + (1-α) * market
        blended_probs = alpha * fund_probs_val + (1 - alpha) * market_probs_val
        auc = roc_auc_score(y_val, blended_probs)
        
        logger.info(f"  α={alpha:.2f} → AUC={auc:.4f}")
        
        if auc > best_auc:
            best_auc = auc
            best_alpha = alpha
    
    logger.info(f"\n  ✅ Best α={best_alpha:.2f} (AUC={best_auc:.4f})")
    
    # Final blended probabilities
    blended_probs_train = best_alpha * fund_probs_train + (1 - best_alpha) * market_probs_train
    blended_probs_val = best_alpha * fund_probs_val + (1 - best_alpha) * market_probs_val
    
    # Isotonic calibration
    logger.info("\nApplying isotonic calibration...")
    calibrator = IsotonicRegression(out_of_bounds='clip')
    calibrator.fit(blended_probs_train, y_train)
    
    calibrated_probs_val = calibrator.transform(blended_probs_val)
    
    # Metrics
    logger.info("\n" + "="*60)
    logger.info("VALIDATION METRICS")
    logger.info("="*60)
    
    auc = roc_auc_score(y_val, calibrated_probs_val)
    brier = brier_score_loss(y_val, calibrated_probs_val)
    logloss = log_loss(y_val, calibrated_probs_val)
    
    logger.info(f"  AUC: {auc:.4f}")
    logger.info(f"  Brier Score: {brier:.4f}")
    logger.info(f"  Log Loss: {logloss:.4f}")
    
    # Calibration error
    bins = np.linspace(0, 1, 11)
    bin_indices = np.digitize(calibrated_probs_val, bins) - 1
    cal_error = 0.0
    
    for i in range(10):
        mask = bin_indices == i
        if mask.sum() > 0:
            pred_mean = calibrated_probs_val[mask].mean()
            true_mean = y_val[mask].mean()
            cal_error += abs(pred_mean - true_mean) * mask.sum()
    
    cal_error = cal_error / len(y_val)
    logger.info(f"  Calibration Error: {cal_error*100:.2f}%")
    
    # A/E ratio
    expected_wins = calibrated_probs_val.sum()
    actual_wins = y_val.sum()
    ae_ratio = actual_wins / expected_wins if expected_wins > 0 else 0.0
    logger.info(f"  A/E Ratio: {ae_ratio:.4f}")
    
    # ROI simulation (top 20%)
    top20_threshold = np.percentile(calibrated_probs_val, 80)
    top20_mask = calibrated_probs_val >= top20_threshold
    
    if top20_mask.sum() > 0:
        top20_wins = y_val[top20_mask].sum()
        top20_bets = top20_mask.sum()
        top20_roi = (top20_wins / top20_bets - 0.1) * 100  # Simplified ROI
        logger.info(f"  ROI@Top20%: {top20_roi:.2f}%")
    else:
        top20_roi = 0.0
    
    # Save model
    logger.info("\n" + "="*60)
    logger.info("SAVING MODEL v1.1.0")
    logger.info("="*60)
    
    model_artifact = {
        'fundamental_model': fund_model,
        'calibrator': calibrator,
        'alpha': best_alpha,
        'beta': 1.0 - best_alpha,
        'feature_names': available_features,
        'version': '1.1.0',
        'trained_at': datetime.now().isoformat()
    }
    
    model_path = model_dir / "model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model_artifact, f)
    logger.info(f"  Model saved: {model_path}")
    
    # Metadata
    metadata = {
        'version': '1.1.0',
        'trained_at': datetime.now().isoformat(),
        'training_records': len(X_train),
        'validation_records': len(X_val),
        'features': available_features,
        'alpha': float(best_alpha),
        'beta': float(1.0 - best_alpha),
        'odds_range': [5.0, 21.0]
    }
    
    metadata_path = model_dir / "metadata.yaml"
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f)
    logger.info(f"  Metadata saved: {metadata_path}")
    
    # Metrics
    metrics = {
        'auc': float(auc),
        'brier_score': float(brier),
        'log_loss': float(logloss),
        'calibration_error': float(cal_error),
        'ae_ratio': float(ae_ratio),
        'roi_top20': float(top20_roi)
    }
    
    metrics_path = model_dir / "metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"  Metrics saved: {metrics_path}")
    
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"  Version: v1.1.0")
    logger.info(f"  Alpha: {best_alpha:.2f}")
    logger.info(f"  AUC: {auc:.4f}")
    logger.info(f"  A/E: {ae_ratio:.4f}")
    logger.info(f"  Calibration Error: {cal_error*100:.2f}%")
    logger.info("="*60)


if __name__ == "__main__":
    main()
