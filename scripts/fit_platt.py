#!/usr/bin/env python3
"""
Fit Platt Scaling Calibration Parameters

Platt scaling = logistic calibration layer that turns model scores into real probabilities.

Input: Historical (raw_score, outcome) pairs
Output: Calibration parameters (a, b) saved to app/model/platt_params.json

Formula: p_calibrated = 1 / (1 + exp(-(a*raw_score + b)))

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import json
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.calibration import calibration_curve
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_calibration_pairs(path: str = "data/calibration_pairs.jsonl"):
    """
    Load calibration pairs from JSONL file.
    
    Expected format (one JSON object per line):
    {"raw_score": 0.35, "y": 1}
    {"raw_score": 0.22, "y": 0}
    ...
    
    Args:
        path: Path to calibration pairs file
        
    Returns:
        (X, y) arrays
    """
    xs, ys = [], []
    
    file_path = Path(path)
    if not file_path.exists():
        logger.warning(f"Calibration pairs file not found: {path}")
        logger.info("Creating sample calibration pairs for demonstration")
        
        # Generate sample data for demonstration
        np.random.seed(42)
        n_samples = 1000
        
        # Simulate raw scores (slightly miscalibrated)
        raw_scores = np.random.beta(2, 5, n_samples)  # Skewed toward lower values
        
        # Simulate outcomes (with some noise)
        outcomes = (np.random.random(n_samples) < raw_scores * 0.8).astype(int)
        
        # Save sample data
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            for score, outcome in zip(raw_scores, outcomes):
                f.write(json.dumps({"raw_score": float(score), "y": int(outcome)}) + "\n")
        
        logger.info(f"Created sample calibration pairs: {path}")
        xs = raw_scores.reshape(-1, 1)
        ys = outcomes
    else:
        with open(path, 'r') as f:
            for line in f:
                row = json.loads(line)
                xs.append([row["raw_score"]])
                ys.append(row["y"])
        
        xs = np.array(xs)
        ys = np.array(ys)
    
    logger.info(f"Loaded {len(ys)} calibration pairs")
    return xs, ys


def fit_platt_calibration(X, y):
    """
    Fit Platt scaling parameters.
    
    Args:
        X: Raw scores (n_samples, 1)
        y: Outcomes (n_samples,)
        
    Returns:
        dict with calibration parameters and metrics
    """
    logger.info("Fitting Platt calibration...")
    
    # Fit logistic regression
    clf = LogisticRegression(solver="lbfgs", max_iter=1000)
    clf.fit(X, y)
    
    # Extract Platt parameters: p = sigmoid(a*x + b)
    a = float(clf.coef_[0][0])
    b = float(clf.intercept_[0])
    
    logger.info(f"Platt parameters: a={a:.4f}, b={b:.4f}")
    
    # Evaluate calibration
    p_calibrated = clf.predict_proba(X)[:, 1]
    
    # Metrics
    brier = brier_score_loss(y, p_calibrated)
    logloss = log_loss(y, p_calibrated)
    
    # Calibration curve
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y, p_calibrated, n_bins=10, strategy='uniform'
    )
    
    # Expected Calibration Error (ECE)
    ece = np.mean(np.abs(fraction_of_positives - mean_predicted_value))
    
    logger.info(f"Calibration metrics:")
    logger.info(f"  Brier score: {brier:.4f} (lower is better)")
    logger.info(f"  Log loss: {logloss:.4f} (lower is better)")
    logger.info(f"  ECE: {ece:.4f} (lower is better)")
    
    # Compare to uncalibrated (raw scores)
    brier_raw = brier_score_loss(y, X[:, 0])
    logloss_raw = log_loss(y, np.clip(X[:, 0], 0.001, 0.999))
    
    logger.info(f"Uncalibrated metrics:")
    logger.info(f"  Brier score: {brier_raw:.4f}")
    logger.info(f"  Log loss: {logloss_raw:.4f}")
    
    improvement = (brier_raw - brier) / brier_raw * 100
    logger.info(f"Calibration improvement: {improvement:.1f}%")
    
    return {
        "a": a,
        "b": b,
        "brier": float(brier),
        "logloss": float(logloss),
        "ece": float(ece),
        "brier_raw": float(brier_raw),
        "logloss_raw": float(logloss_raw),
        "improvement_pct": float(improvement),
        "n_samples": int(len(y))
    }


def save_calibration_params(params: dict, output_path: str = "app/model/platt_params.json"):
    """
    Save calibration parameters to JSON file.
    
    Args:
        params: Calibration parameters dict
        output_path: Output file path
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(params, f, indent=2)
    
    logger.info(f"Calibration parameters saved to: {output_path}")


def load_calibration_params(path: str = "app/model/platt_params.json"):
    """
    Load calibration parameters from JSON file.
    
    Args:
        path: Path to calibration params file
        
    Returns:
        dict with calibration parameters
    """
    with open(path, 'r') as f:
        return json.load(f)


def apply_platt_calibration(raw_scores: np.ndarray, a: float, b: float) -> np.ndarray:
    """
    Apply Platt calibration to raw scores.
    
    Formula: p = 1 / (1 + exp(-(a*raw + b)))
    
    Args:
        raw_scores: Raw model scores
        a: Platt parameter a
        b: Platt parameter b
        
    Returns:
        Calibrated probabilities
    """
    return 1.0 / (1.0 + np.exp(-(a * raw_scores + b)))


def main():
    """Main calibration fitting workflow."""
    logger.info("="*80)
    logger.info("VELO Platt Calibration Fitting")
    logger.info("="*80)
    
    # Load calibration pairs
    X, y = load_calibration_pairs("data/calibration_pairs.jsonl")
    
    # Fit Platt calibration
    params = fit_platt_calibration(X, y)
    
    # Save parameters
    save_calibration_params(params, "app/model/platt_params.json")
    
    logger.info("="*80)
    logger.info("Calibration fitting complete!")
    logger.info("="*80)
    
    # Print summary
    print("\n" + "="*80)
    print("CALIBRATION SUMMARY")
    print("="*80)
    print(f"Samples: {params['n_samples']}")
    print(f"Platt parameters: a={params['a']:.4f}, b={params['b']:.4f}")
    print(f"Brier score: {params['brier']:.4f} (uncalibrated: {params['brier_raw']:.4f})")
    print(f"Log loss: {params['logloss']:.4f} (uncalibrated: {params['logloss_raw']:.4f})")
    print(f"ECE: {params['ece']:.4f}")
    print(f"Improvement: {params['improvement_pct']:.1f}%")
    print("="*80)
    
    # Example usage
    print("\nExample usage:")
    print(">>> from scripts.fit_platt import load_calibration_params, apply_platt_calibration")
    print(">>> params = load_calibration_params()")
    print(">>> raw_scores = np.array([0.35, 0.22, 0.68])")
    print(">>> calibrated = apply_platt_calibration(raw_scores, params['a'], params['b'])")
    print(">>> print(calibrated)")


if __name__ == "__main__":
    main()
