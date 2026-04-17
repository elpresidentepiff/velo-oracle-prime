"""
Betfair Market Sync Script
Maps internal race objects to Betfair market IDs and selection IDs
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from difflib import SequenceMatcher

from app.integrations.betfair_client import create_betfair_client, BetfairMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_venue_name(name: str) -> str:
    """Normalize venue name for matching"""
    return name.lower().replace(" ", "").replace("-", "").replace("(aw)", "").strip()


def normalize_runner_name(name: str) -> str:
    """Normalize runner name for matching"""
    # Remove common suffixes and normalize
    name = name.lower()
    name = name.replace("(ire)", "").replace("(fr)", "").replace("(gb)", "")
    name = name.replace("'", "").replace("-", "").replace(" ", "")
    return name.strip()


def string_similarity(a: str, b: str) -> float:
    """Calculate string similarity (0-1)"""
    return SequenceMatcher(None, a, b).ratio()


def match_venue(internal_venue: str, betfair_venue: str) -> float:
    """
    Match internal venue to Betfair venue
    
    Returns:
        Similarity score (0-1)
    """
    norm_internal = normalize_venue_name(internal_venue)
    norm_betfair = normalize_venue_name(betfair_venue)
    
    return string_similarity(norm_internal, norm_betfair)


def match_runners(
    internal_runners: List[Dict],
    betfair_runners: List[Dict],
    threshold: float = 0.8
) -> Dict[str, int]:
    """
    Match internal runners to Betfair selection IDs
    
    Args:
        internal_runners: List of internal runner dicts with 'name'
        betfair_runners: List of Betfair runner dicts with 'runner_name', 'selection_id'
        threshold: Minimum similarity threshold
    
    Returns:
        Dict mapping internal runner name → Betfair selection_id
    """
    mapping = {}
    
    for internal in internal_runners:
        internal_name = normalize_runner_name(internal['name'])
        best_match = None
        best_score = 0.0
        
        for betfair in betfair_runners:
            betfair_name = normalize_runner_name(betfair['runner_name'])
            score = string_similarity(internal_name, betfair_name)
            
            if score > best_score:
                best_score = score
                best_match = betfair
        
        if best_match and best_score >= threshold:
            mapping[internal['name']] = best_match['selection_id']
            logger.debug(
                f"Matched '{internal['name']}' → '{best_match['runner_name']}' "
                f"(selection_id: {best_match['selection_id']}, score: {best_score:.2f})"
            )
        else:
            logger.warning(
                f"No match found for '{internal['name']}' "
                f"(best score: {best_score:.2f})"
            )
    
    return mapping


def sync_race_to_betfair(
    race: Dict,
    betfair_markets: List[Dict],
    venue_threshold: float = 0.7,
    time_tolerance_minutes: int = 15
) -> Optional[Dict]:
    """
    Sync a single internal race to Betfair market
    
    Args:
        race: Internal race dict with venue, off_time, runners
        betfair_markets: List of Betfair markets
        venue_threshold: Minimum venue similarity
        time_tolerance_minutes: Max time difference in minutes
    
    Returns:
        Mapping dict with:
            - market_id
            - event_id
            - venue_match_score
            - runner_mappings: {internal_name: selection_id}
    """
    race_venue = race['venue']
    race_time = datetime.fromisoformat(race['off_time'])
    
    best_market = None
    best_score = 0.0
    
    for market in betfair_markets:
        # Check venue match
        venue_score = match_venue(race_venue, market['venue'])
        
        if venue_score < venue_threshold:
            continue
        
        # Check time match
        market_time = datetime.fromisoformat(market['market_start_time'])
        time_diff_minutes = abs((race_time - market_time).total_seconds() / 60)
        
        if time_diff_minutes > time_tolerance_minutes:
            continue
        
        # Combined score (venue 70%, time 30%)
        time_score = max(0, 1 - (time_diff_minutes / time_tolerance_minutes))
        combined_score = (venue_score * 0.7) + (time_score * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_market = market
    
    if not best_market:
        logger.warning(
            f"No Betfair market found for {race_venue} {race_time.strftime('%H:%M')}"
        )
        return None
    
    # Match runners
    runner_mappings = match_runners(race['runners'], best_market['runners'])
    
    if not runner_mappings:
        logger.warning(
            f"No runners matched for {race_venue} {race_time.strftime('%H:%M')}"
        )
        return None
    
    mapping = {
        'race_id': race.get('race_id'),
        'market_id': best_market['market_id'],
        'event_id': best_market['event_id'],
        'venue': best_market['venue'],
        'market_start_time': best_market['market_start_time'],
        'venue_match_score': best_score,
        'runner_mappings': runner_mappings,
        'matched_runners': len(runner_mappings),
        'total_runners': len(race['runners'])
    }
    
    logger.info(
        f"✅ Matched {race_venue} {race_time.strftime('%H:%M')} → "
        f"market {best_market['market_id']} "
        f"({len(runner_mappings)}/{len(race['runners'])} runners)"
    )
    
    return mapping


def sync_today_markets(
    internal_races: List[Dict],
    mode: BetfairMode = BetfairMode.SIM,
    output_file: Optional[str] = None
) -> List[Dict]:
    """
    Sync all internal races to Betfair markets for today
    
    Args:
        internal_races: List of internal race dicts
        mode: Betfair mode (SIM, DELAYED, LIVE)
        output_file: Optional JSON file to save mappings
    
    Returns:
        List of mapping dicts
    """
    logger.info(f"Syncing {len(internal_races)} races to Betfair ({mode} mode)")
    
    # Create Betfair client
    client = create_betfair_client(mode=mode)
    
    # Login
    if not client.login():
        logger.error("Failed to login to Betfair")
        return []
    
    # Get today's markets
    today = date.today()
    betfair_markets = client.list_markets_for_day(
        date=datetime.combine(today, datetime.min.time()),
        country_codes=["GB", "IE"],
        market_types=["WIN"]
    )
    
    logger.info(f"Found {len(betfair_markets)} Betfair markets for {today}")
    
    # Match each race
    mappings = []
    for race in internal_races:
        mapping = sync_race_to_betfair(race, betfair_markets)
        if mapping:
            mappings.append(mapping)
    
    logger.info(
        f"✅ Successfully matched {len(mappings)}/{len(internal_races)} races"
    )
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(mappings, f, indent=2)
        logger.info(f"Saved mappings to {output_file}")
    
    return mappings


def load_internal_races_from_file(filepath: str) -> List[Dict]:
    """Load internal races from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync internal races to Betfair markets")
    parser.add_argument(
        '--mode',
        choices=['SIM', 'DELAYED', 'LIVE'],
        default='SIM',
        help='Betfair mode'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input JSON file with internal races'
    )
    parser.add_argument(
        '--output',
        default='data/betfair_mappings.json',
        help='Output JSON file for mappings'
    )
    
    args = parser.parse_args()
    
    # Load internal races
    internal_races = load_internal_races_from_file(args.input)
    
    # Sync to Betfair
    mappings = sync_today_markets(
        internal_races=internal_races,
        mode=BetfairMode(args.mode),
        output_file=args.output
    )
    
    # Print summary
    print("\n" + "="*60)
    print(f"SYNC SUMMARY")
    print("="*60)
    print(f"Mode: {args.mode}")
    print(f"Internal races: {len(internal_races)}")
    print(f"Matched races: {len(mappings)}")
    print(f"Success rate: {len(mappings)/len(internal_races)*100:.1f}%")
    print(f"Output: {args.output}")
    print("="*60)


if __name__ == "__main__":
    main()
