"""
VÉLØ Oracle - SQPE v15 Trainer (Production)
Real sklearn/xgboost implementation
"""
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
from pathlib import Path

# Production imports (will work in production environment)
try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, log_loss, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("WARNING: sklearn not available. Install with: pip install scikit-learn")


def train_sqpe_v15(
    dataset_path: str = "storage/velo-datasets/racing_full_1_7m.csv",
    output_dir: str = "models/sqpe_v15",
    sample_size: int = None,
    test_size: float = 0.2,
    random_state: int = 42
):
    """
    Train SQPE v15 with real GradientBoostingClassifier
    
    Args:
        dataset_path: Path to training dataset
        output_dir: Output directory for model
        sample_size: Sample size (None = full dataset)
        test_size: Test split fraction
        random_state: Random seed
        
    Returns:
        Training results
    """
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("sklearn not installed. Run: pip install scikit-learn xgboost")
    
    print("="*60)
    print("VÉLØ Oracle - SQPE v15 Training")
    print("="*60)
    
    # Load data
    print(f"\nLoading dataset: {dataset_path}")
    if sample_size:
        df = pd.read_csv(dataset_path, nrows=sample_size)
    else:
        df = pd.read_csv(dataset_path)
    
    print(f"✅ Loaded {len(df):,} rows")
    
    # Prepare features
    print("\nPreparing features...")
    
    # Target: 1 if won (pos == '1'), 0 otherwise
    df['target'] = (df['pos'] == '1').astype(int)
    
    # Select numeric features
    feature_cols = []
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64'] and col not in ['target', 'race_id', 'pos']:
            feature_cols.append(col)
    
    X = df[feature_cols].fillna(0)
    y = df['target']
    
    print(f"Features: {len(feature_cols)}")
    print(f"Positive rate: {y.mean():.4f}")
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    print(f"\nTrain: {len(X_train):,} samples")
    print(f"Test: {len(X_test):,} samples")
    
    # Train model
    print("\n" + "="*60)
    print("Training SQPE v15 (GradientBoostingClassifier)")
    print("="*60)
    
    model = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        min_samples_split=100,
        min_samples_leaf=50,
        subsample=0.8,
        max_features='sqrt',
        random_state=random_state,
        verbose=1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    print("\n" + "="*60)
    print("Evaluation")
    print("="*60)
    
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    
    auc = roc_auc_score(y_test, y_pred_proba)
    logloss = log_loss(y_test, y_pred_proba)
    
    print(f"\nAUC: {auc:.4f}")
    print(f"Log Loss: {logloss:.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Features:")
    print(feature_importance.head(10).to_string(index=False))
    
    # Save model
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    model_path = f"{output_dir}/sqpe_v15.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"\n✅ Model saved to {model_path}")
    
    # Save metadata
    metadata = {
        "version": "v15.0",
        "model_type": "GradientBoostingClassifier",
        "n_estimators": 200,
        "learning_rate": 0.05,
        "max_depth": 6,
        "auc": float(auc),
        "log_loss": float(logloss),
        "n_features": len(feature_cols),
        "n_train_samples": len(X_train),
        "n_test_samples": len(X_test),
        "positive_rate": float(y.mean()),
        "trained_at": datetime.utcnow().isoformat(),
        "dataset": dataset_path,
        "feature_names": feature_cols,
        "top_10_features": feature_importance.head(10).to_dict('records')
    }
    
    metadata_path = f"{output_dir}/metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Metadata saved to {metadata_path}")
    
    # Save feature importance
    feature_importance_path = f"{output_dir}/feature_importance.csv"
    feature_importance.to_csv(feature_importance_path, index=False)
    
    print(f"✅ Feature importance saved to {feature_importance_path}")
    
    print("\n" + "="*60)
    print("SQPE v15 Training Complete")
    print("="*60)
    
    return {
        "auc": auc,
        "log_loss": logloss,
        "model_path": model_path,
        "metadata_path": metadata_path
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train SQPE v15")
    parser.add_argument("--dataset", default="storage/velo-datasets/racing_full_1_7m.csv")
    parser.add_argument("--output", default="models/sqpe_v15")
    parser.add_argument("--sample", type=int, default=None, help="Sample size (None = full)")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    
    args = parser.parse_args()
    
    results = train_sqpe_v15(
        dataset_path=args.dataset,
        output_dir=args.output,
        sample_size=args.sample,
        test_size=args.test_size,
        random_state=args.seed
    )
    
    print(f"\n✅ Training complete")
    print(f"AUC: {results['auc']:.4f}")
    print(f"Model: {results['model_path']}")
