"""
Freeze benchmark manifest: deterministic 2,000-race selection.
"""
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def freeze_manifest(
    as_of_date: str,
    months: int,
    n_races: int,
    output_path: str
):
    """
    Freeze deterministic benchmark manifest.
    
    Selection criteria:
    - Last N months ending at as_of_date
    - Stable ordering: ORDER BY race_date, race_id
    - Exactly n_races selected
    - Only races with batch_status IN ('validated', 'ready')
    
    Args:
        as_of_date: Anchor date (YYYY-MM-DD)
        months: Lookback window in months
        n_races: Number of races to select
        output_path: Output JSON path
    """
    from workers.ingestion_spine.db import DatabaseClient
    
    db = DatabaseClient()
    
    try:
        # Calculate date range
        end_date = datetime.strptime(as_of_date, "%Y-%m-%d")
        start_date = end_date - timedelta(days=months * 30)
        
        print(f"🔍 Querying races from {start_date.date()} to {end_date.date()}...")
        
        # Query races (deterministic ordering)
        # Note: Supabase client uses different syntax than asyncpg
        response = db.client.table('races')\
            .select('id, course, race_date, off_time, distance_yards, race_class, batch_id')\
            .gte('race_date', start_date.date().isoformat())\
            .lt('race_date', end_date.date().isoformat())\
            .order('race_date')\
            .order('id')\
            .limit(n_races * 2)\
            .execute()
        
        races_data = response.data if response.data else []
        
        # Filter by batch status
        print(f"📊 Fetched {len(races_data)} races, filtering by batch status...")
        
        valid_races = []
        batch_ids = list(set(r['batch_id'] for r in races_data if r.get('batch_id')))
        
        if batch_ids:
            # Get batch statuses
            batch_response = db.client.table('import_batches')\
                .select('id, status')\
                .in_('id', batch_ids)\
                .execute()
            
            valid_batch_ids = {
                b['id'] for b in batch_response.data 
                if b['status'] in ['validated', 'ready']
            }
            
            # Filter races by valid batches
            valid_races = [
                r for r in races_data 
                if r.get('batch_id') in valid_batch_ids
            ][:n_races]
        
        # Get runner counts for each race
        print(f"🏇 Fetching runner counts for {len(valid_races)} races...")
        
        races_with_counts = []
        for race in valid_races:
            runner_response = db.client.table('runners')\
                .select('id', count='exact')\
                .eq('race_id', race['id'])\
                .execute()
            
            race_data = {
                'race_id': race['id'],
                'course': race.get('course', ''),
                'race_date': race.get('race_date', ''),
                'off_time': race.get('off_time', ''),
                'distance_yards': race.get('distance_yards', 0),
                'race_class': race.get('race_class', ''),
                'runners_count': runner_response.count if hasattr(runner_response, 'count') else 0
            }
            races_with_counts.append(race_data)
        
        manifest = {
            "version": "1.0",
            "as_of_date": as_of_date,
            "window_months": months,
            "n_races": n_races,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "races": races_with_counts
        }
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        
        print(f"✅ Manifest frozen: {len(races_with_counts)} races")
        print(f"   Date range: {start_date.date()} to {end_date.date()}")
        print(f"   Output: {output_path}")
        
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description="Freeze benchmark manifest")
    parser.add_argument("--as-of-date", required=True, help="Anchor date (YYYY-MM-DD)")
    parser.add_argument("--months", type=int, default=36, help="Lookback months")
    parser.add_argument("--n-races", type=int, default=2000, help="Number of races")
    parser.add_argument("--out", required=True, help="Output JSON path")
    
    args = parser.parse_args()
    
    import asyncio
    asyncio.run(freeze_manifest(args.as_of_date, args.months, args.n_races, args.out))


if __name__ == "__main__":
    main()
