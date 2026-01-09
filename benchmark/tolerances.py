"""
Define regression tolerance thresholds.
"""

# Hard gates (CI fails if violated)
HARD_GATES = {
    "determinism": {
        "hash_must_match": True,
        "description": "Output hash must be identical on repeat runs"
    },
    "coverage": {
        "min_pct": 99.5,
        "tolerance_from_baseline": -0.5,
        "description": "Coverage must be ≥99.5% or baseline - 0.5%"
    },
    "garbage_patterns": {
        "max_all_zero_count": 0,
        "max_placeholder_count": 0,
        "description": "No all-zero scores or placeholder names"
    },
    "runtime": {
        "p95_multiplier": 1.30,
        "description": "p95 runtime ≤ baseline × 1.30"
    }
}

# Soft gates (warning but not blocking)
SOFT_GATES = {
    "roi": {
        "min_drop_pp": -2.0,
        "description": "ROI ≥ baseline - 2.0pp"
    },
    "logloss": {
        "max_multiplier": 1.05,
        "description": "Log-loss ≤ baseline × 1.05"
    }
}


def check_regression(current_metrics: dict, baseline_metrics: dict) -> tuple:
    """
    Check if current run violates regression thresholds.
    
    Args:
        current_metrics: Current run metrics
        baseline_metrics: Baseline metrics to compare against
    
    Returns:
        (is_passing, violations)
    """
    violations = []
    
    # Coverage check
    current_cov = current_metrics.get("coverage_pct", 0)
    baseline_cov = baseline_metrics.get("coverage_pct", 0)
    min_allowed_cov = max(
        HARD_GATES["coverage"]["min_pct"],
        baseline_cov + HARD_GATES["coverage"]["tolerance_from_baseline"]
    )
    
    if current_cov < min_allowed_cov:
        violations.append(
            f"Coverage regression: {current_cov:.2f}% < {min_allowed_cov:.2f}% "
            f"(baseline: {baseline_cov:.2f}%)"
        )
    
    # Garbage patterns
    garbage = current_metrics.get("garbage_patterns", {})
    if garbage.get("all_zero_count", 0) > HARD_GATES["garbage_patterns"]["max_all_zero_count"]:
        violations.append(f"All-zero scores detected: {garbage['all_zero_count']}")
    if garbage.get("placeholder_count", 0) > HARD_GATES["garbage_patterns"]["max_placeholder_count"]:
        violations.append(f"Placeholder names detected: {garbage['placeholder_count']}")
    
    # Runtime check (if baseline has runtime data)
    if "runtime" in baseline_metrics and "runtime" in current_metrics:
        baseline_runtime = baseline_metrics["runtime"].get("avg_per_race", 0)
        current_runtime = current_metrics["runtime"].get("avg_per_race", 0)
        max_allowed_runtime = baseline_runtime * HARD_GATES["runtime"]["p95_multiplier"]
        
        if current_runtime > max_allowed_runtime:
            violations.append(
                f"Runtime regression: {current_runtime:.3f}s > {max_allowed_runtime:.3f}s "
                f"(baseline: {baseline_runtime:.3f}s × 1.30)"
            )
    
    is_passing = len(violations) == 0
    return is_passing, violations


def check_hash_match(current_hash: str, baseline_hash: str) -> tuple:
    """
    Check if hash matches for determinism validation.
    
    Args:
        current_hash: Current run hash
        baseline_hash: Baseline hash
    
    Returns:
        (is_passing, violation_message)
    """
    is_passing = current_hash == baseline_hash
    violation = None if is_passing else f"Hash mismatch: {current_hash[:16]}... != {baseline_hash[:16]}..."
    return is_passing, violation
