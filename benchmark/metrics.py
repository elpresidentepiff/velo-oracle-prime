"""
Calculate benchmark metrics for regression detection.
"""
import json
import hashlib
import numpy as np
from typing import Dict, List
import argparse
import os


def calculate_metrics(run_output_path: str) -> Dict:
    """
    Calculate coverage, runtime, distribution metrics.
    
    Metrics:
    - coverage_pct: % of runners with scores
    - runtime_p50/p95/p99: percentiles
    - score_distribution: min/max/mean/std
    - garbage_patterns: all-zero, placeholders, etc.
    """
    with open(run_output_path) as f:
        run = json.load(f)
    
    # Coverage
    total_runners = 0
    scored_runners = 0
    
    # Runtime (placeholder - need actual timing)
    runtimes = []
    
    # Scores
    all_scores = []
    
    # Garbage patterns
    all_zero_count = 0
    placeholder_count = 0
    
    for result in run["results"]:
        if result["status"] != "success":
            continue
        
        runners_count = result.get("runners_count", 0)
        total_runners += runners_count
        
        predictions = result.get("predictions", {})
        top4 = predictions.get("top_4", [])
        
        for pred in top4:
            score = pred.get("score", 0)
            name = pred.get("name", "")
            
            if score > 0:
                scored_runners += 1
                all_scores.append(score)
            else:
                all_zero_count += 1
            
            if name.upper() in ["TBD", "RUNNER A", "UNKNOWN", ""]:
                placeholder_count += 1
    
    coverage_pct = (scored_runners / total_runners * 100) if total_runners > 0 else 0
    
    # Runtime metrics from run data
    elapsed = run.get("elapsed_seconds", 0)
    races_processed = run.get("races_processed", 0)
    
    metrics = {
        "coverage_pct": round(coverage_pct, 2),
        "total_runners": total_runners,
        "scored_runners": scored_runners,
        "races_processed": races_processed,
        "runtime": {
            "total_seconds": elapsed,
            "avg_per_race": round(elapsed / races_processed, 3) if races_processed > 0 else 0
        },
        "score_distribution": {
            "min": float(np.min(all_scores)) if all_scores else 0,
            "max": float(np.max(all_scores)) if all_scores else 0,
            "mean": float(np.mean(all_scores)) if all_scores else 0,
            "std": float(np.std(all_scores)) if all_scores else 0,
            "p50": float(np.percentile(all_scores, 50)) if all_scores else 0,
            "p95": float(np.percentile(all_scores, 95)) if all_scores else 0,
            "p99": float(np.percentile(all_scores, 99)) if all_scores else 0
        },
        "garbage_patterns": {
            "all_zero_count": all_zero_count,
            "placeholder_count": placeholder_count
        }
    }
    
    return metrics


def calculate_hash(run_output_path: str) -> str:
    """
    Calculate deterministic hash of run output.
    Used for regression detection.
    """
    with open(run_output_path, 'rb') as f:
        content = f.read()
    
    # Use only deterministic fields for hash
    data = json.loads(content)
    
    # Extract only race_id + predictions (ignore timestamps)
    deterministic_data = [
        {
            "race_id": r["race_id"],
            "predictions": r.get("predictions", {})
        }
        for r in data["results"]
    ]
    
    # Sort by race_id for consistency
    deterministic_data.sort(key=lambda x: x["race_id"])
    
    deterministic_json = json.dumps(deterministic_data, sort_keys=True)
    return hashlib.sha256(deterministic_json.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Calculate benchmark metrics")
    parser.add_argument("--input", required=True, help="Input run output JSON")
    parser.add_argument("--out", help="Output metrics JSON path")
    parser.add_argument("--hash", action="store_true", help="Calculate and print hash")
    
    args = parser.parse_args()
    
    if args.hash:
        # Calculate hash
        hash_value = calculate_hash(args.input)
        print(f"Hash: {hash_value}")
        
        if args.out:
            # Save hash to file
            hash_path = args.out.replace('.json', '_hash.txt')
            with open(hash_path, 'w') as f:
                f.write(hash_value)
            print(f"Saved hash to: {hash_path}")
    else:
        # Calculate metrics
        metrics = calculate_metrics(args.input)
        
        print("=" * 80)
        print("BENCHMARK METRICS")
        print("=" * 80)
        print(f"Coverage: {metrics['coverage_pct']:.2f}% ({metrics['scored_runners']}/{metrics['total_runners']} runners)")
        print(f"Races: {metrics['races_processed']}")
        print(f"Runtime: {metrics['runtime']['total_seconds']:.1f}s ({metrics['runtime']['avg_per_race']:.3f}s/race)")
        print(f"Scores: min={metrics['score_distribution']['min']:.3f}, max={metrics['score_distribution']['max']:.3f}, mean={metrics['score_distribution']['mean']:.3f}")
        print(f"Garbage: {metrics['garbage_patterns']['all_zero_count']} zeros, {metrics['garbage_patterns']['placeholder_count']} placeholders")
        
        if args.out:
            os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else '.', exist_ok=True)
            with open(args.out, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"\nSaved metrics to: {args.out}")


if __name__ == "__main__":
    main()
