"""
Check regression report and exit with appropriate code for CI.
"""
import json
import argparse
import sys


def check_regression_report(report_path: str, fail_on_violation: bool = False):
    """
    Check regression report and exit with appropriate code.
    
    Args:
        report_path: Path to regression report JSON
        fail_on_violation: If True, exit with code 1 on violations
    
    Returns:
        Exit code (0 = pass, 1 = fail)
    """
    with open(report_path) as f:
        report = json.load(f)
    
    status = report.get("status", "UNKNOWN")
    violations = report.get("violations", [])
    
    print("=" * 80)
    print("REGRESSION CHECK")
    print("=" * 80)
    print(f"Status: {status}")
    
    if violations:
        print("\n❌ Violations found:")
        for v in violations:
            print(f"  - {v}")
        print()
        
        if fail_on_violation:
            print("FAIL: Regression violations detected")
            return 1
        else:
            print("WARNING: Regression violations detected (not failing)")
            return 0
    else:
        print("\n✅ No violations - all checks passed")
        print()
        return 0


def main():
    parser = argparse.ArgumentParser(description="Check regression report")
    parser.add_argument("--report", required=True, help="Path to regression report JSON")
    parser.add_argument("--fail-on-violation", action="store_true", 
                       help="Exit with code 1 if violations found")
    
    args = parser.parse_args()
    
    exit_code = check_regression_report(args.report, args.fail_on_violation)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
