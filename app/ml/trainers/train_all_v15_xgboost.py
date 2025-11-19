"""
VÉLØ Oracle - Full Model Stack v15 (Production)
Real XGBoost implementation for all models
"""
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
from pathlib import Path

# Production imports
try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, log_loss
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("WARNING: xgboost not available. Install with: pip install xgboost scikit-learn")


def train_model(
    X_train, X_test, y_train, y_test,
    model_name: str,
    params: dict,
    output_dir: str
):
    """Train single XGBoost model"""
    
    print(f"\n{'='*60}")
    print(f"Training {model_name}")
    print(f"{'='*60}")
    
    # Create DMatrix
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)
    
    # Train
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=params.get('n_estimators', 200),
        evals=[(dtrain, 'train'), (dtest, 'test')],
        early_stopping_rounds=20,
        verbose_eval=50
    )
    
    # Predict
    y_pred_proba = model.predict(dtest)
    
    # Metrics
    auc = roc_auc_score(y_test, y_pred_proba)
    logloss = log_loss(y_test, y_pred_proba)
    
    print(f"\n✅ {model_name} Results:")
    print(f"   AUC: {auc:.4f}")
    print(f"   Log Loss: {logloss:.4f}")
    
    # Save
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    model_path = f"{output_dir}/{model_name.lower().replace(' ', '_')}.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    # Metadata
    metadata = {
        "version": "v15.0",
        "model_name": model_name,
        "model_type": "XGBoost",
        "auc": float(auc),
        "log_loss": float(logloss),
        "params": params,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "trained_at": datetime.utcnow().isoformat()
    }
    
    metadata_path = f"{output_dir}/metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return {
        "model_name": model_name,
        "auc": auc,
        "log_loss": logloss,
        "model_path": model_path
    }


def train_all_models_v15(
    dataset_path: str = "storage/velo-datasets/racing_full_1_7m.csv",
    sample_size: int = None,
    test_size: float = 0.2,
    random_state: int = 42
):
    """
    Train all 4 models with XGBoost
    
    Models:
    - SQPE v15: Speed/Quality/Pace/Efficiency
    - TIE v9: Trainer Intent Engine
    - Longshot v6: Longshot Detector
    - Overlay v5: Benter Overlay
    """
    if not XGBOOST_AVAILABLE:
        raise RuntimeError("xgboost not installed. Run: pip install xgboost scikit-learn")
    
    print("="*60)
    print("VÉLØ Oracle - Full Model Stack v15 Training")
    print("="*60)
    
    # Load data
    print(f"\nLoading dataset: {dataset_path}")
    if sample_size:
        df = pd.read_csv(dataset_path, nrows=sample_size)
    else:
        df = pd.read_csv(dataset_path)
    
    print(f"✅ Loaded {len(df):,} rows")
    
    # Prepare features
    df['target'] = (df['pos'] == '1').astype(int)
    
    feature_cols = []
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64'] and col not in ['target', 'race_id', 'pos']:
            feature_cols.append(col)
    
    X = df[feature_cols].fillna(0)
    y = df['target']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    print(f"\nTrain: {len(X_train):,} | Test: {len(X_test):,}")
    print(f"Features: {len(feature_cols)}")
    print(f"Positive rate: {y.mean():.4f}")
    
    # Model configurations
    models_config = {
        "SQPE v15": {
            "output_dir": "models/sqpe_v15",
            "params": {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'max_depth': 6,
                'learning_rate': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 50,
                'n_estimators': 200,
                'seed': random_state
            }
        },
        "TIE v9": {
            "output_dir": "models/tie_v9",
            "params": {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'max_depth': 5,
                'learning_rate': 0.03,
                'subsample': 0.7,
                'colsample_bytree': 0.7,
                'min_child_weight': 100,
                'n_estimators': 150,
                'seed': random_state
            }
        },
        "Longshot v6": {
            "output_dir": "models/longshot_v6",
            "params": {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'max_depth': 4,
                'learning_rate': 0.1,
                'subsample': 0.9,
                'colsample_bytree': 0.9,
                'min_child_weight': 20,
                'n_estimators': 100,
                'seed': random_state
            }
        },
        "Overlay v5": {
            "output_dir": "models/overlay_v5",
            "params": {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'max_depth': 5,
                'learning_rate': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 50,
                'n_estimators': 150,
                'seed': random_state
            }
        }
    }
    
    # Train all models
    results = []
    
    for model_name, config in models_config.items():
        result = train_model(
            X_train, X_test, y_train, y_test,
            model_name,
            config['params'],
            config['output_dir']
        )
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("Training Summary")
    print("="*60)
    
    for result in results:
        print(f"\n{result['model_name']}:")
        print(f"  AUC: {result['auc']:.4f}")
        print(f"  Log Loss: {result['log_loss']:.4f}")
        print(f"  Path: {result['model_path']}")
    
    # Save summary
    summary = {
        "training_date": datetime.utcnow().isoformat(),
        "dataset": dataset_path,
        "n_samples": len(df),
        "n_features": len(feature_cols),
        "models": results
    }
    
    summary_path = "models/training_summary_v15.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Summary saved to {summary_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train all models v15")
    parser.add_argument("--dataset", default="storage/velo-datasets/racing_full_1_7m.csv")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    
    args = parser.parse_args()
    
    results = train_all_models_v15(
        dataset_path=args.dataset,
        sample_size=args.sample,
        test_size=args.test_size,
        random_state=args.seed
    )
    
    print("\n✅ All models trained successfully")
