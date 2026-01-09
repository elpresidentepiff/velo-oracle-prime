"""
Execute VELO pipeline on benchmark manifest.
Deterministic: same manifest + as_of_date → same output.
"""
import json
import hashlib
import time
import argparse
from typing import Dict, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_benchmark(
    manifest_path: str,
    as_of_date: str,
    output_path: str,
    shard: int = None,
    total_shards: int = None
) -> Dict:
    """
    Run pipeline on all races in manifest.
    
    For each race:
    1. Get features (deterministic: uses as_of_date)
    2. Run Phase 2A scoring
    3. Generate Top-4 predictions
    
    Args:
        manifest_path: Path to manifest JSON
        as_of_date: Anchor date for feature extraction
        output_path: Output path for results
        shard: Shard number (1-indexed) for parallel execution
        total_shards: Total number of shards
    
    Returns:
        {
            "run_id": str,
            "manifest": str,
            "as_of_date": str,
            "races_processed": int,
            "results": [...]
        }
    """
    from app.engine.features import get_features_for_racecard
    from app.strategy.top4_ranker import rank_top4
    from workers.ingestion_spine.db import DatabaseClient
    
    # Load manifest
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    races = manifest["races"]
    
    # Apply sharding if specified
    if shard is not None and total_shards is not None:
        print(f"📊 Running shard {shard}/{total_shards}")
        # Shard is 1-indexed, convert to 0-indexed for slicing
        shard_idx = shard - 1
        races = [r for i, r in enumerate(races) if i % total_shards == shard_idx]
        print(f"   Processing {len(races)} races in this shard")
    
    db = DatabaseClient()
    results = []
    
    start_time = time.time()
    
    try:
        for idx, race in enumerate(races):
            race_id = race["race_id"]
            
            if (idx + 1) % 10 == 0:
                print(f"   Progress: {idx + 1}/{len(races)} races")
            
            try:
                # Get features (deterministic)
                features_df = await get_features_for_racecard(
                    db, 
                    race_id, 
                    as_of_date=as_of_date
                )
                
                # Convert DataFrame to profiles for ranking
                # The top4_ranker expects a list of profile dicts
                runner_profiles = []
                
                if not features_df.empty:
                    for _, row in features_df.iterrows():
                        profile = {
                            'runner_id': row.get('runner_id', 'unknown'),
                            'horse_name': row.get('horse_name', ''),
                            'market_role': 'NOISE',  # Default role, would come from market data
                            'odds_decimal': row.get('odds', 10.0),
                        }
                        runner_profiles.append(profile)
                    
                    # Build race context
                    race_ctx = {
                        'chaos_level': 0.5,  # Default, would be calculated
                        'field_size': len(runner_profiles),
                        'manipulation_risk': 0.3  # Default
                    }
                    
                    # Run ranking
                    top4_profiles, score_breakdowns = rank_top4(runner_profiles, race_ctx)
                    
                    # Format predictions
                    predictions = {
                        'top_4': [
                            {
                                'position': i + 1,
                                'runner_id': p.get('runner_id', 'unknown'),
                                'name': p.get('horse_name', ''),
                                'score': score_breakdowns.get(p.get('runner_id', 'unknown'), {}).get('total', 0.0)
                            }
                            for i, p in enumerate(top4_profiles[:4])
                        ]
                    }
                else:
                    predictions = {'top_4': []}
                
                results.append({
                    "race_id": race_id,
                    "runners_count": len(runner_profiles),
                    "predictions": predictions,
                    "status": "success"
                })
                
            except Exception as e:
                print(f"   ⚠️  Error processing race {race_id}: {e}")
                results.append({
                    "race_id": race_id,
                    "status": "error",
                    "error": str(e)
                })
    
    finally:
        await db.close()
    
    elapsed = time.time() - start_time
    
    # Output
    output = {
        "run_id": f"benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "manifest": manifest_path,
        "as_of_date": as_of_date,
        "shard": shard,
        "total_shards": total_shards,
        "races_processed": len(results),
        "successes": sum(1 for r in results if r["status"] == "success"),
        "failures": sum(1 for r in results if r["status"] == "error"),
        "elapsed_seconds": elapsed,
        "timestamp": datetime.utcnow().isoformat(),
        "results": results
    }
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Benchmark run complete")
    print(f"   Races: {output['races_processed']}")
    print(f"   Success: {output['successes']}")
    print(f"   Failures: {output['failures']}")
    print(f"   Time: {elapsed:.1f}s")
    
    return output


def main():
    parser = argparse.ArgumentParser(description="Run benchmark on manifest")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--as-of-date", required=True, help="Anchor date (YYYY-MM-DD)")
    parser.add_argument("--out", required=True, help="Output path for results")
    parser.add_argument("--shard", type=int, help="Shard number (1-indexed)")
    parser.add_argument("--total-shards", type=int, help="Total number of shards")
    
    args = parser.parse_args()
    
    if (args.shard is not None) != (args.total_shards is not None):
        print("Error: --shard and --total-shards must be used together")
        sys.exit(1)
    
    import asyncio
    asyncio.run(run_benchmark(
        args.manifest,
        args.as_of_date,
        args.out,
        args.shard,
        args.total_shards
    ))


if __name__ == "__main__":
    main()
