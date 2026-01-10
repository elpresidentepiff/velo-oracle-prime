"""
VÉLØ Race Analysis CLI
Run complete race analysis with all 5 agents
"""
import os
import sys
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client, Client
from app.engine.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_race_from_database(race_id: str, client: Client) -> Optional[Dict[str, Any]]:
    """
    Load race data from Supabase database
    
    Args:
        race_id: Race identifier (e.g., "WOL_20260109_1625")
        client: Supabase client
        
    Returns:
        Race data dict or None if not found
    """
    try:
        # Parse race_id (format: COURSE_DATE_TIME)
        parts = race_id.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid race_id format: {race_id}")
            return None
        
        course = parts[0]
        date = parts[1]  # YYYYMMDD
        time = parts[2]  # HHMM
        
        # Format date and time for database query
        import_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        off_time = f"{time[:2]}:{time[2:4]}"
        
        logger.info(f"Querying race: course={course}, date={import_date}, time={off_time}")
        
        # Query races table
        race_result = client.table('races') \
            .select('*') \
            .eq('course', course.upper()) \
            .eq('import_date', import_date) \
            .eq('off_time', off_time) \
            .execute()
        
        if not race_result.data or len(race_result.data) == 0:
            logger.error(f"Race not found in database: {race_id}")
            return None
        
        race = race_result.data[0]
        race_uuid = race['id']
        
        # Query runners for this race
        runners_result = client.table('runners') \
            .select('*') \
            .eq('race_id', race_uuid) \
            .execute()
        
        if not runners_result.data:
            logger.warning(f"No runners found for race {race_id}")
            runners = []
        else:
            runners = runners_result.data
        
        # Build race data structure
        race_data = {
            'race_id': race_id,
            'course': race.get('course', ''),
            'off_time': race.get('off_time', ''),
            'race_name': race.get('race_name', ''),
            'distance': race.get('distance', ''),
            'going': race.get('going', ''),
            'race_type': race.get('race_type', ''),
            'class_band': race.get('class_band', ''),
            'runners': []
        }
        
        # Add runners
        for runner in runners:
            race_data['runners'].append({
                'horse_name': runner.get('horse_name', ''),
                'cloth_no': runner.get('cloth_no'),
                'trainer': runner.get('trainer', ''),
                'jockey': runner.get('jockey', ''),
                'form_figures': runner.get('form_figures', ''),
                'or_rating': runner.get('or_rating'),
                'rpr': runner.get('rpr'),
                'ts': runner.get('ts'),
                'age': runner.get('age'),
                'weight': runner.get('weight', ''),
                'draw': runner.get('draw'),
                'odds': None,  # Would need to be added from market data
                'raw': runner.get('raw', {})
            })
        
        logger.info(f"✓ Loaded race with {len(race_data['runners'])} runners")
        return race_data
    
    except Exception as e:
        logger.error(f"Failed to load race from database: {e}", exc_info=True)
        return None


def load_race_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Load race data from JSON file
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Race data dict or None if failed
    """
    try:
        with open(file_path, 'r') as f:
            race_data = json.load(f)
        
        logger.info(f"✓ Loaded race from file: {file_path}")
        return race_data
    
    except Exception as e:
        logger.error(f"Failed to load race from file: {e}")
        return None


def save_results(verdicts, output_path: str) -> None:
    """
    Save analysis results to JSON file
    
    Args:
        verdicts: List of BettingVerdict objects
        output_path: Output file path
    """
    # Convert verdicts to dict format
    results = {
        'verdicts': [
            {
                'horse_name': v.horse_name,
                'final_score': v.final_score,
                'action': v.action,
                'stake_pct': v.stake_pct,
                'reason': v.reason,
                'agent_scores': v.agent_scores,
                'evidence': v.evidence
            }
            for v in verdicts
        ],
        'summary': {
            'total_runners': len(verdicts),
            'back_plays': len([v for v in verdicts if v.action == 'BACK']),
            'lay_plays': len([v for v in verdicts if v.action == 'LAY']),
            'pass': len([v for v in verdicts if v.action == 'PASS'])
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"✓ Saved results to {output_path}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Run VÉLØ race analysis with all 5 agents'
    )
    parser.add_argument(
        '--race-id',
        help='Race ID (e.g., WOL_20260109_1625)',
        type=str,
        required=True
    )
    parser.add_argument(
        '--input',
        help='Input JSON file (optional, otherwise loads from database)',
        type=str
    )
    parser.add_argument(
        '--output',
        help='Output JSON file (default: results.json)',
        type=str,
        default='results.json'
    )
    parser.add_argument(
        '--verbose',
        help='Enable verbose logging',
        action='store_true'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY not set")
            client = None
        else:
            client = create_client(supabase_url, supabase_key)
        
        # Load race data
        if args.input:
            race_data = load_race_from_file(args.input)
        elif client:
            race_data = load_race_from_database(args.race_id, client)
        else:
            logger.error("No input file provided and no database connection available")
            sys.exit(1)
        
        if not race_data:
            logger.error("Failed to load race data")
            sys.exit(1)
        
        # Ensure race_id is set
        if 'race_id' not in race_data:
            race_data['race_id'] = args.race_id
        
        # Initialize orchestrator
        orchestrator = Orchestrator(supabase_url, supabase_key)
        
        # Run analysis
        logger.info("\n" + "="*60)
        logger.info("VÉLØ ORACLE - RACE ANALYSIS")
        logger.info("="*60 + "\n")
        
        verdicts = orchestrator.analyze_race(race_data)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("BETTING VERDICTS")
        logger.info("="*60 + "\n")
        
        for verdict in verdicts:
            if verdict.action != 'PASS':
                logger.info(f"{verdict.action} {verdict.horse_name}")
                logger.info(f"  Score: {verdict.final_score:.1f}/100")
                logger.info(f"  Stake: {verdict.stake_pct:.2f}% of bankroll")
                logger.info(f"  Reason: {verdict.reason}")
                logger.info("")
        
        # Count summary
        back_count = len([v for v in verdicts if v.action == 'BACK'])
        lay_count = len([v for v in verdicts if v.action == 'LAY'])
        pass_count = len([v for v in verdicts if v.action == 'PASS'])
        
        logger.info(f"Summary: {back_count} BACK, {lay_count} LAY, {pass_count} PASS")
        
        # Save results
        save_results(verdicts, args.output)
        
        logger.info("\n✅ Analysis complete!")
    
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
