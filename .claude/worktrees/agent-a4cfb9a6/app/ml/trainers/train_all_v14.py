"""
VÉLØ Oracle - Train All Models v14
Unified training script for all 4 models
"""
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_all_models(
    dataset_path: str = "storage/velo-datasets/racing_full_1_7m.csv",
    sample_size: int = None,
    test_split: float = 0.2
):
    """
    Train all 4 models: SQPE, TIE, Longshot, Overlay
    
    Args:
        dataset_path: Path to training dataset
        sample_size: Number of samples to use (None = all)
        test_split: Fraction for validation
    """
    logger.info("="*60)
    logger.info("VÉLØ Oracle - Train All Models v14")
    logger.info("="*60)
    
    # Load dataset
    logger.info(f"\nLoading dataset: {dataset_path}")
    
    if sample_size:
        df = pd.read_csv(dataset_path, nrows=sample_size)
    else:
        df = pd.read_csv(dataset_path)
    
    logger.info(f"✅ Loaded {len(df):,} rows")
    
    # Prepare features and labels
    logger.info("\nPreparing features...")
    
    # Create target (1 if won, 0 otherwise)
    df['target'] = (df['pos'] == '1').astype(int)
    
    # Select numeric features (simplified)
    feature_cols = []
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64'] and col not in ['target', 'race_id', 'pos']:
            feature_cols.append(col)
    
    X = df[feature_cols].fillna(0)
    y = df['target']
    
    logger.info(f"Features: {len(feature_cols)}")
    logger.info(f"Positive rate: {y.mean():.4f}")
    
    # Train/val split
    split_idx = int(len(X) * (1 - test_split))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    logger.info(f"\nTrain: {len(X_train):,} samples")
    logger.info(f"Val: {len(X_val):,} samples")
    
    results = {}
    
    # 1. Train SQPE v14
    logger.info("\n" + "="*60)
    logger.info("1. Training SQPE v14 (GBM)")
    logger.info("="*60)
    
    from sklearn.ensemble import GradientBoostingClassifier
    
    sqpe = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        random_state=42
    )
    
    sqpe.fit(X_train, y_train)
    
    sqpe_pred = sqpe.predict_proba(X_val)[:, 1]
    sqpe_auc = calculate_auc(y_val, sqpe_pred)
    
    logger.info(f"✅ SQPE v14 AUC: {sqpe_auc:.4f}")
    
    # Save
    with open('models/sqpe_v14/sqpe_v14.pkl', 'wb') as f:
        pickle.dump(sqpe, f)
    
    results['sqpe_v14'] = {"auc": sqpe_auc, "model_type": "GBM"}
    
    # 2. Train TIE v9
    logger.info("\n" + "="*60)
    logger.info("2. Training TIE v9 (Neural Net)")
    logger.info("="*60)
    
    from sklearn.neural_network import MLPClassifier
    
    tie = MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation='relu',
        solver='adam',
        learning_rate_init=0.001,
        max_iter=100,
        random_state=42,
        verbose=False
    )
    
    tie.fit(X_train, y_train)
    
    tie_pred = tie.predict_proba(X_val)[:, 1]
    tie_auc = calculate_auc(y_val, tie_pred)
    
    logger.info(f"✅ TIE v9 AUC: {tie_auc:.4f}")
    
    # Save
    with open('models/tie_v9/tie_v9.pkl', 'wb') as f:
        pickle.dump(tie, f)
    
    results['tie_v9'] = {"auc": tie_auc, "model_type": "Neural Net"}
    
    # 3. Train Longshot v6
    logger.info("\n" + "="*60)
    logger.info("3. Training Longshot v6 (Random Forest)")
    logger.info("="*60)
    
    from sklearn.ensemble import RandomForestClassifier
    
    # Filter for longshots only (odds > 10)
    if 'odds_decimal' in df.columns:
        longshot_mask = df['odds_decimal'] > 10
        X_longshot = X[longshot_mask]
        y_longshot = y[longshot_mask]
        
        split_idx_ls = int(len(X_longshot) * (1 - test_split))
        X_train_ls = X_longshot[:split_idx_ls]
        y_train_ls = y_longshot[:split_idx_ls]
        X_val_ls = X_longshot[split_idx_ls:]
        y_val_ls = y_longshot[split_idx_ls:]
    else:
        X_train_ls, y_train_ls = X_train, y_train
        X_val_ls, y_val_ls = X_val, y_val
    
    longshot = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=50,
        random_state=42
    )
    
    longshot.fit(X_train_ls, y_train_ls)
    
    longshot_pred = longshot.predict_proba(X_val_ls)[:, 1]
    longshot_auc = calculate_auc(y_val_ls, longshot_pred)
    
    logger.info(f"✅ Longshot v6 AUC: {longshot_auc:.4f}")
    
    # Save
    with open('models/longshot_v6/longshot_v6.pkl', 'wb') as f:
        pickle.dump(longshot, f)
    
    results['longshot_v6'] = {"auc": longshot_auc, "model_type": "Random Forest"}
    
    # 4. Train Overlay v5
    logger.info("\n" + "="*60)
    logger.info("4. Training Overlay v5 (Logistic Regression)")
    logger.info("="*60)
    
    from sklearn.linear_model import LogisticRegression
    
    overlay = LogisticRegression(
        C=1.0,
        max_iter=1000,
        random_state=42
    )
    
    overlay.fit(X_train, y_train)
    
    overlay_pred = overlay.predict_proba(X_val)[:, 1]
    overlay_auc = calculate_auc(y_val, overlay_pred)
    
    logger.info(f"✅ Overlay v5 AUC: {overlay_auc:.4f}")
    
    # Save
    with open('models/overlay_v5/overlay_v5.pkl', 'wb') as f:
        pickle.dump(overlay, f)
    
    results['overlay_v5'] = {"auc": overlay_auc, "model_type": "Logistic Regression"}
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TRAINING SUMMARY")
    logger.info("="*60)
    
    for model_name, metrics in results.items():
        logger.info(f"{model_name}: AUC={metrics['auc']:.4f} ({metrics['model_type']})")
    
    # Save summary
    summary = {
        "trained_at": datetime.utcnow().isoformat(),
        "dataset": dataset_path,
        "n_samples": len(df),
        "n_features": len(feature_cols),
        "models": results
    }
    
    with open('models/training_summary_v14.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info("\n✅ All models trained successfully")
    
    return results


def calculate_auc(y_true, y_pred):
    """Calculate AUC-ROC"""
    from sklearn.metrics import roc_auc_score
    try:
        return roc_auc_score(y_true, y_pred)
    except:
        return 0.5


if __name__ == "__main__":
    # Train with sample (10K for testing)
    results = train_all_models(
        dataset_path="storage/velo-datasets/racing_full_1_7m.csv",
        sample_size=10000,
        test_split=0.2
    )
    
    print("\n✅ Training complete")
    print("Results:", results)
