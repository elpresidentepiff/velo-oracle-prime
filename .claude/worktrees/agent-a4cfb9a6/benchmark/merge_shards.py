"""
Merge benchmark shard results into a single output.
"""
import json
import argparse
import os
from typing import List, Dict
from pathlib import Path


def merge_shards(shards_dir: str, output_path: str):
    """
    Merge all shard JSON files from a directory.
    
    Args:
        shards_dir: Directory containing shard JSON files
        output_path: Output path for merged JSON
    """
    shards_path = Path(shards_dir)
    
    # Find all shard files
    shard_files = []
    
    # GitHub Actions artifact download creates subdirectories
    # Pattern: benchmark-shard-N/shard_N.json
    for shard_dir in sorted(shards_path.iterdir()):
        if shard_dir.is_dir() and shard_dir.name.startswith('benchmark-shard-'):
            for json_file in shard_dir.glob('*.json'):
                shard_files.append(json_file)
    
    # If no subdirectories, look for JSON files directly
    if not shard_files:
        shard_files = sorted(shards_path.glob('*.json'))
    
    if not shard_files:
        raise ValueError(f"No shard files found in {shards_dir}")
    
    print(f"📊 Found {len(shard_files)} shard files")
    
    # Load all shards
    shards_data = []
    for shard_file in sorted(shard_files):
        print(f"   Loading {shard_file.name}...")
        with open(shard_file) as f:
            shard_data = json.load(f)
            shards_data.append(shard_data)
    
    # Merge results
    all_results = []
    total_successes = 0
    total_failures = 0
    total_elapsed = 0.0
    
    manifest_path = None
    as_of_date = None
    
    for shard in shards_data:
        all_results.extend(shard.get("results", []))
        total_successes += shard.get("successes", 0)
        total_failures += shard.get("failures", 0)
        total_elapsed += shard.get("elapsed_seconds", 0)
        
        if manifest_path is None:
            manifest_path = shard.get("manifest")
        if as_of_date is None:
            as_of_date = shard.get("as_of_date")
    
    # Create merged output
    merged = {
        "run_id": f"benchmark_merged_{len(shards_data)}_shards",
        "manifest": manifest_path,
        "as_of_date": as_of_date,
        "shards_merged": len(shards_data),
        "races_processed": len(all_results),
        "successes": total_successes,
        "failures": total_failures,
        "elapsed_seconds": total_elapsed,
        "timestamp": shards_data[0].get("timestamp") if shards_data else None,
        "results": all_results
    }
    
    # Sort results by race_id for consistency
    merged["results"].sort(key=lambda x: x.get("race_id", ""))
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(merged, f, indent=2)
    
    print(f"✅ Merged {len(shards_data)} shards")
    print(f"   Total races: {len(all_results)}")
    print(f"   Successes: {total_successes}")
    print(f"   Failures: {total_failures}")
    print(f"   Total time: {total_elapsed:.1f}s")
    print(f"   Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Merge benchmark shard results")
    parser.add_argument("--shards-dir", required=True, help="Directory containing shard JSON files")
    parser.add_argument("--out", required=True, help="Output path for merged JSON")
    
    args = parser.parse_args()
    
    merge_shards(args.shards_dir, args.out)


if __name__ == "__main__":
    main()
