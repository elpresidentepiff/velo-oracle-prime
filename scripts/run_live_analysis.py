#!/usr/bin/env python3.11
"""
VELO v12 - Live Race Analysis Pipeline
=======================================

End-to-end production script that:
1. Fetches today's race cards from TheRacingAPI
2. Runs V12 Market-Intent Stack analysis
3. Stores results in Supabase
4. Generates verdicts and learning events

This is the main production entry point for live racing analysis.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import logging
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.data.racing_api_client import TheRacingAPIClient
from app.pipeline.orchestrator import VELOPipeline
from app.config.supabase_config import get_supabase_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveAnalysisPipeline:
    """
    Production pipeline for live race analysis.
    
    Orchestrates:
    - Data ingestion from TheRacingAPI
    - V12 engine analysis
    - Supabase storage
    - Verdict generation
    """
    
    def __init__(self):
        """Initialize pipeline components"""
        logger.info("Initializing VELO v12 Live Analysis Pipeline...")
        
        self.api_client = TheRacingAPIClient()
        self.orchestrator = VELOPipeline()
        self.supabase = get_supabase_client()
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        logger.info("Pipeline initialized successfully")
    
    def fetch_live_racecards(self):
        """Fetch today's race cards from TheRacingAPI"""
        logger.info("=" * 80)
        logger.info("STEP 1: Fetching live race cards from TheRacingAPI")
        logger.info("=" * 80)
        
        try:
            raw_data = self.api_client.get_todays_racecards()
            velo_races = self.api_client.transform_to_velo_format(raw_data)
            
            logger.info(f"✓ Successfully fetched {len(velo_races)} races")
            
            # Log race summary
            for i, race in enumerate(velo_races[:5], 1):
                logger.info(f"  {i}. {race['course']} {race['off_time']}: "
                           f"{race['race_name']} ({race['field_size']} runners)")
            
            if len(velo_races) > 5:
                logger.info(f"  ... and {len(velo_races) - 5} more races")
            
            return velo_races
            
        except Exception as e:
            logger.error(f"✗ Failed to fetch race cards: {e}")
            raise
    
    def analyze_race(self, race_data: dict) -> dict:
        """
        Run V12 analysis on a single race.
        
        Args:
            race_data: Race dictionary in VELO format
            
        Returns:
            Analysis results with verdicts
        """
        race_id = race_data['race_id']
        course = race_data['course']
        off_time = race_data['off_time']
        
        logger.info(f"\n--- Analyzing: {course} {off_time} ({race_id}) ---")
        
        try:
            # Prepare inputs for VELOPipeline
            race_ctx = {
                'course': race_data['course'],
                'date': race_data['date'],
                'off_time': race_data['off_time'],
                'distance': race_data.get('distance_f'),
                'going': race_data.get('going', ''),
                'race_class': race_data.get('race_class', ''),
                'surface': race_data.get('surface', ''),
                'field_size': race_data.get('field_size', 0),
                'type': race_data.get('type', '')
            }
            
            market_ctx = {
                'snapshot_timestamp': datetime.now().isoformat(),
                'race_id': race_id
            }
            
            runners = race_data.get('runners', [])
            
            # Run through orchestrator
            pipeline_ctx = self.orchestrator.run(
                race_id=race_id,
                race_ctx=race_ctx,
                market_ctx=market_ctx,
                runners=runners
            )
            
            logger.info(f"✓ Analysis complete for {race_id}")
            logger.info(f"  - Engine run ID: {pipeline_ctx.engine_run_id}")
            logger.info(f"  - Decision: {pipeline_ctx.decision}")
            
            return {
                'race_id': race_id,
                'engine_run_id': pipeline_ctx.engine_run_id,
                'decision': pipeline_ctx.decision,
                'chaos_level': pipeline_ctx.signal_outputs.get('chaos_level', 0.0),
                'learning_status': pipeline_ctx.learning_gate_result.get('learning_status', 'unknown'),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"✗ Analysis failed for {race_id}: {e}")
            return {
                "race_id": race_id,
                "error": str(e),
                "status": "failed"
            }
    
    def run_analysis(self, limit: int = None):
        """
        Run complete analysis pipeline.
        
        Args:
            limit: Maximum number of races to analyze (None = all)
        """
        start_time = datetime.now()
        
        logger.info("\n" + "=" * 80)
        logger.info("VELO v12 LIVE ANALYSIS PIPELINE - STARTING")
        logger.info("=" * 80)
        logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Version: v12 Market-Intent Stack")
        logger.info("=" * 80 + "\n")
        
        try:
            # Step 1: Fetch race cards
            races = self.fetch_live_racecards()
            
            if not races:
                logger.warning("No races found for today")
                return
            
            # Apply limit if specified
            if limit:
                races = races[:limit]
                logger.info(f"\nLimiting analysis to first {limit} races")
            
            # Step 2: Analyze each race
            logger.info("\n" + "=" * 80)
            logger.info(f"STEP 2: Running V12 analysis on {len(races)} races")
            logger.info("=" * 80)
            
            results = []
            for i, race in enumerate(races, 1):
                logger.info(f"\n[{i}/{len(races)}] Processing race...")
                result = self.analyze_race(race)
                results.append(result)
            
            # Step 3: Summary
            logger.info("\n" + "=" * 80)
            logger.info("STEP 3: Analysis Summary")
            logger.info("=" * 80)
            
            successful = [r for r in results if r.get('status') != 'failed']
            failed = [r for r in results if r.get('status') == 'failed']
            
            logger.info(f"Total races processed: {len(races)}")
            logger.info(f"Successful: {len(successful)}")
            logger.info(f"Failed: {len(failed)}")
            
            if failed:
                logger.warning(f"\nFailed races:")
                for r in failed:
                    logger.warning(f"  - {r['race_id']}: {r.get('error', 'Unknown error')}")
            
            # Calculate total decisions
            total_decisions = len([r for r in successful if r.get('decision')])
            logger.info(f"\nTotal decisions generated: {total_decisions}")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 80)
            logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Average: {duration/len(races):.2f} seconds per race")
            logger.info("=" * 80 + "\n")
            
            return results
            
        except Exception as e:
            logger.error(f"\n✗ Pipeline failed: {e}", exc_info=True)
            raise
    
    def run_single_race(self, race_id: str):
        """
        Analyze a single race by ID.
        
        Args:
            race_id: Race identifier
        """
        logger.info(f"Fetching race: {race_id}")
        
        # Fetch all races and find the target
        races = self.fetch_live_racecards()
        target_race = next((r for r in races if r['race_id'] == race_id), None)
        
        if not target_race:
            logger.error(f"Race not found: {race_id}")
            logger.info(f"Available races: {[r['race_id'] for r in races]}")
            return None
        
        # Analyze the race
        result = self.analyze_race(target_race)
        return result


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VELO v12 Live Race Analysis')
    parser.add_argument('--limit', type=int, help='Limit number of races to analyze')
    parser.add_argument('--race-id', type=str, help='Analyze specific race by ID')
    parser.add_argument('--test', action='store_true', help='Test mode (analyze first race only)')
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = LiveAnalysisPipeline()
    
    # Run analysis
    if args.race_id:
        pipeline.run_single_race(args.race_id)
    elif args.test:
        logger.info("Running in TEST mode (first race only)")
        pipeline.run_analysis(limit=1)
    else:
        pipeline.run_analysis(limit=args.limit)


if __name__ == "__main__":
    main()
