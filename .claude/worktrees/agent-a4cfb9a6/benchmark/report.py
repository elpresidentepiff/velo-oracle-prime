"""
Generate baseline diff reports.
"""
import json
import argparse
import os
from typing import Dict


def generate_report(
    current_run_path: str,
    baseline_metrics_path: str,
    output_path: str = None
):
    """
    Generate regression report comparing current to baseline.
    
    Args:
        current_run_path: Path to current run output JSON
        baseline_metrics_path: Path to baseline metrics JSON
        output_path: Optional output path for report JSON
    
    Returns:
        Report dictionary
    """
    from benchmark.metrics import calculate_metrics
    from benchmark.tolerances import check_regression
    
    current_metrics = calculate_metrics(current_run_path)
    
    with open(baseline_metrics_path) as f:
        baseline_metrics = json.load(f)
    
    is_passing, violations = check_regression(current_metrics, baseline_metrics)
    
    # Calculate deltas
    coverage_delta = current_metrics["coverage_pct"] - baseline_metrics.get("coverage_pct", 0)
    
    runtime_delta = None
    if "runtime" in baseline_metrics and "runtime" in current_metrics:
        runtime_delta = current_metrics["runtime"]["avg_per_race"] - baseline_metrics["runtime"]["avg_per_race"]
    
    report = {
        "status": "PASS" if is_passing else "FAIL",
        "violations": violations,
        "current_metrics": current_metrics,
        "baseline_metrics": baseline_metrics,
        "deltas": {
            "coverage_delta": round(coverage_delta, 2),
            "runtime_delta": round(runtime_delta, 3) if runtime_delta is not None else None
        }
    }
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    # Print summary
    print("=" * 80)
    print("BENCHMARK REGRESSION REPORT")
    print("=" * 80)
    print(f"Status: {report['status']}")
    print(f"Coverage: {current_metrics['coverage_pct']:.2f}% (baseline: {baseline_metrics.get('coverage_pct', 0):.2f}%, delta: {coverage_delta:+.2f}%)")
    
    if runtime_delta is not None:
        print(f"Runtime: {current_metrics['runtime']['avg_per_race']:.3f}s/race "
              f"(baseline: {baseline_metrics['runtime']['avg_per_race']:.3f}s, delta: {runtime_delta:+.3f}s)")
    
    if violations:
        print("\n❌ VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
    else:
        print("\n✅ All checks passed")
    
    print("=" * 80)
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Generate regression report")
    parser.add_argument("--current", required=True, help="Path to current run output JSON")
    parser.add_argument("--baseline", required=True, help="Path to baseline metrics JSON")
    parser.add_argument("--out", help="Output path for report JSON")
    
    args = parser.parse_args()
    
    generate_report(args.current, args.baseline, args.out)


if __name__ == "__main__":
    main()
