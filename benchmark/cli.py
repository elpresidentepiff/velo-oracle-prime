"""
CLI interface for benchmark commands.
"""
import argparse
import sys
import asyncio


def main():
    parser = argparse.ArgumentParser(
        description="VELO Benchmark Regression Protection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Freeze manifest
  python -m benchmark.cli freeze --as-of-date 2026-01-09 --out benchmark/manifest_2000.json
  
  # Run benchmark
  python -m benchmark.cli run --manifest benchmark/manifest_2000.json --as-of-date 2026-01-09 --out /tmp/results.json
  
  # Calculate metrics
  python -m benchmark.cli metrics --input /tmp/results.json --out /tmp/metrics.json
  
  # Generate report
  python -m benchmark.cli report --current /tmp/results.json --baseline benchmark/baseline_metrics.json
  
  # Merge shards
  python -m benchmark.cli merge --shards-dir /tmp/shards --out /tmp/merged.json
  
  # Check regression
  python -m benchmark.cli check --report /tmp/report.json --fail-on-violation
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Freeze command
    freeze_parser = subparsers.add_parser('freeze', help='Freeze benchmark manifest')
    freeze_parser.add_argument('--as-of-date', required=True, help='Anchor date (YYYY-MM-DD)')
    freeze_parser.add_argument('--months', type=int, default=36, help='Lookback months')
    freeze_parser.add_argument('--n-races', type=int, default=2000, help='Number of races')
    freeze_parser.add_argument('--out', required=True, help='Output JSON path')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run benchmark on manifest')
    run_parser.add_argument('--manifest', required=True, help='Path to manifest JSON')
    run_parser.add_argument('--as-of-date', required=True, help='Anchor date (YYYY-MM-DD)')
    run_parser.add_argument('--out', required=True, help='Output path for results')
    run_parser.add_argument('--shard', type=int, help='Shard number (1-indexed)')
    run_parser.add_argument('--total-shards', type=int, help='Total number of shards')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Calculate metrics')
    metrics_parser.add_argument('--input', required=True, help='Input run output JSON')
    metrics_parser.add_argument('--out', help='Output metrics JSON path')
    metrics_parser.add_argument('--hash', action='store_true', help='Calculate and print hash')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate regression report')
    report_parser.add_argument('--current', required=True, help='Path to current run output JSON')
    report_parser.add_argument('--baseline', required=True, help='Path to baseline metrics JSON')
    report_parser.add_argument('--out', help='Output path for report JSON')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge shard results')
    merge_parser.add_argument('--shards-dir', required=True, help='Directory containing shard JSON files')
    merge_parser.add_argument('--out', required=True, help='Output path for merged JSON')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check regression report')
    check_parser.add_argument('--report', required=True, help='Path to regression report JSON')
    check_parser.add_argument('--fail-on-violation', action='store_true', help='Exit with code 1 if violations found')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == 'freeze':
        from benchmark.freeze_manifest import freeze_manifest
        asyncio.run(freeze_manifest(args.as_of_date, args.months, args.n_races, args.out))
    
    elif args.command == 'run':
        from benchmark.runner import run_benchmark
        asyncio.run(run_benchmark(args.manifest, args.as_of_date, args.out, args.shard, args.total_shards))
    
    elif args.command == 'metrics':
        from benchmark.metrics import calculate_metrics, calculate_hash
        import json
        import os
        
        if args.hash:
            hash_value = calculate_hash(args.input)
            print(f"Hash: {hash_value}")
            if args.out:
                hash_path = args.out.replace('.json', '_hash.txt')
                os.makedirs(os.path.dirname(hash_path) if os.path.dirname(hash_path) else '.', exist_ok=True)
                with open(hash_path, 'w') as f:
                    f.write(hash_value)
                print(f"Saved hash to: {hash_path}")
        else:
            metrics = calculate_metrics(args.input)
            print("=" * 80)
            print("BENCHMARK METRICS")
            print("=" * 80)
            print(f"Coverage: {metrics['coverage_pct']:.2f}% ({metrics['scored_runners']}/{metrics['total_runners']} runners)")
            print(f"Races: {metrics['races_processed']}")
            print(f"Runtime: {metrics['runtime']['total_seconds']:.1f}s ({metrics['runtime']['avg_per_race']:.3f}s/race)")
            
            if args.out:
                os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else '.', exist_ok=True)
                with open(args.out, 'w') as f:
                    json.dump(metrics, f, indent=2)
                print(f"\nSaved metrics to: {args.out}")
    
    elif args.command == 'report':
        from benchmark.report import generate_report
        generate_report(args.current, args.baseline, args.out)
    
    elif args.command == 'merge':
        from benchmark.merge_shards import merge_shards
        merge_shards(args.shards_dir, args.out)
    
    elif args.command == 'check':
        from benchmark.check_regression import check_regression_report
        exit_code = check_regression_report(args.report, args.fail_on_violation)
        sys.exit(exit_code)


if __name__ == '__main__':
    main()
