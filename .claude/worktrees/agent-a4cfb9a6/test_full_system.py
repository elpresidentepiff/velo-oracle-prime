"""
VÉLØ v9.0++ CHAREX - Full System Test

Tests the complete Oracle system with realistic race data.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.velo_prime import VeloPrime
from agents.velo_scout import VeloScout
from agents.velo_archivist import VeloArchivist
from agents.velo_synth import VeloSynth
from agents.velo_manus import VeloManus


def create_test_race_data():
    """Create realistic test race data."""
    return {
        "race_details": {
            "track": "Yarmouth",
            "time": "14:30",
            "race_type": "Class 5 Handicap",
            "distance": "6f",
            "going": "Good",
            "field_size": 8
        },
        "horses": [
            {
                "name": "Lady Roisia",
                "number": 1,
                "form": "121343",
                "age": 4,
                "weight": 130,
                "odds": 8.0,
                "trainer_stats": {"roi": 15.0, "wins": 12, "runs": 80},
                "jockey_stats": {"roi": 12.0, "wins": 45, "runs": 375},
                "official_rating": 75,
                "topspeed": 82,
                "rpr": 78
            },
            {
                "name": "Desert Storm",
                "number": 2,
                "form": "534221",
                "age": 5,
                "weight": 128,
                "odds": 12.0,
                "trainer_stats": {"roi": 18.0, "wins": 8, "runs": 45},
                "jockey_stats": {"roi": 14.0, "wins": 38, "runs": 290},
                "official_rating": 72,
                "topspeed": 80,
                "rpr": 76
            },
            {
                "name": "Swift Dancer",
                "number": 3,
                "form": "231124",
                "age": 3,
                "weight": 125,
                "odds": 6.0,
                "trainer_stats": {"roi": 22.0, "wins": 15, "runs": 68},
                "jockey_stats": {"roi": 16.0, "wins": 52, "runs": 325},
                "official_rating": 78,
                "topspeed": 85,
                "rpr": 81
            },
            {
                "name": "Market Favorite",
                "number": 4,
                "form": "111",
                "age": 4,
                "weight": 135,
                "odds": 2.5,  # Too short - will fail filter 4
                "trainer_stats": {"roi": 8.0, "wins": 20, "runs": 250},
                "jockey_stats": {"roi": 6.0, "wins": 65, "runs": 1083},
                "official_rating": 85,
                "topspeed": 90,
                "rpr": 88
            },
            {
                "name": "Long Shot Lucy",
                "number": 5,
                "form": "0000",  # Poor form - will fail filter 1
                "age": 6,
                "weight": 122,
                "odds": 25.0,  # Too long - will fail filter 4
                "trainer_stats": {"roi": 5.0, "wins": 3, "runs": 60},
                "jockey_stats": {"roi": 4.0, "wins": 12, "runs": 300},
                "official_rating": 60,
                "topspeed": 65,
                "rpr": 62
            },
            {
                "name": "Hidden Gem",
                "number": 6,
                "form": "342211",
                "age": 4,
                "weight": 127,
                "odds": 10.0,
                "trainer_stats": {"roi": 20.0, "wins": 10, "runs": 50},
                "jockey_stats": {"roi": 18.0, "wins": 35, "runs": 194},
                "official_rating": 74,
                "topspeed": 81,
                "rpr": 77
            }
        ]
    }


def main():
    """Run full system test."""
    print("="*80)
    print("🔮 VÉLØ v9.0++ CHAREX - FULL SYSTEM TEST")
    print("="*80)
    
    # Initialize all agents
    print("\n📋 Initializing agents...")
    
    prime = VeloPrime()
    scout = VeloScout()
    archivist = VeloArchivist()
    synth = VeloSynth()
    manus = VeloManus()
    
    # Activate all agents
    prime.activate()
    scout.activate()
    archivist.activate()
    synth.activate()
    manus.activate()
    
    # Register agents with MANUS
    print("\n⚙️  Registering agents with MANUS...")
    manus.register_agent("PRIME", prime)
    manus.register_agent("SCOUT", scout)
    manus.register_agent("ARCHIVIST", archivist)
    manus.register_agent("SYNTH", synth)
    
    # Get system status
    print("\n📊 System Status:")
    system_status = manus.get_system_status()
    print(json.dumps(system_status, indent=2))
    
    # Create test race data
    print("\n\n" + "="*80)
    print("🏇 ANALYZING TEST RACE")
    print("="*80)
    
    race_data = create_test_race_data()
    
    print(f"\nRace: {race_data['race_details']['track']} - {race_data['race_details']['time']}")
    print(f"Distance: {race_data['race_details']['distance']}")
    print(f"Going: {race_data['race_details']['going']}")
    print(f"Field Size: {race_data['race_details']['field_size']}")
    
    print(f"\n📋 Runners:")
    for horse in race_data['horses']:
        print(f"  {horse['number']}. {horse['name']} - {horse['odds']}/1 (Form: {horse['form']})")
    
    # Process race with VÉLØ PRIME
    print("\n\n🔮 VÉLØ PRIME ANALYSIS:")
    print("-"*80)
    
    verdict = prime.process_race_request(race_data)
    
    # Display verdict
    print(f"\n📊 VÉLØ VERDICT:")
    print(f"  Top Strike Selection: {verdict['velo_verdict']['top_strike_selection']}")
    print(f"  Longshot Tactic: {verdict['velo_verdict']['longshot_tactic']}")
    print(f"  Speed Watch Horse: {verdict['velo_verdict']['speed_watch_horse']}")
    print(f"  Value EW Picks: {', '.join(verdict['velo_verdict']['value_ew_picks'])}")
    
    print(f"\n📈 Confidence Index: {verdict['confidence_index']}/100")
    
    print(f"\n🎯 Strategic Notes:")
    for key, value in verdict['strategic_notes'].items():
        print(f"  {key}: {value}")
    
    print(f"\n🔥 Tactical Summary:")
    print(f"  {verdict['tactical_summary']}")
    
    # Display filter details
    if verdict.get('filter_details'):
        print(f"\n\n🎯 FIVE-FILTER BREAKDOWN:")
        print("-"*80)
        for detail in verdict['filter_details']:
            print(f"\n  Horse: {detail['horse']}")
            print(f"  Passed Filters: {detail['passed_filters']}/5")
            print(f"  Filter Breakdown:")
            for filter_name, passed in detail['filter_breakdown'].items():
                status = "✅" if passed else "❌"
                print(f"    {status} {filter_name}")
    
    # Log prediction with ARCHIVIST
    print("\n\n📚 Logging prediction with ARCHIVIST...")
    entry_id = archivist.log_prediction(
        race_id="TEST_RACE_001",
        race_details=race_data['race_details'],
        verdict=verdict
    )
    print(f"  Entry ID: {entry_id}")
    
    # Get ledger stats
    stats = archivist.get_ledger_stats()
    print(f"\n  Ledger Stats: {stats['total_predictions']} predictions logged")
    
    # Track odds with SYNTH
    print("\n\n📊 Tracking odds with SYNTH...")
    for horse in race_data['horses'][:3]:
        synth.record_odds(horse['name'], horse['odds'])
        print(f"  Recorded: {horse['name']} @ {horse['odds']}/1")
    
    print("\n\n" + "="*80)
    print("✅ FULL SYSTEM TEST COMPLETE")
    print("="*80)
    
    print("\n🎯 Summary:")
    print(f"  - All 5 agents operational")
    print(f"  - Five-Filter System active")
    print(f"  - {len(verdict.get('filter_details', []))} horses passed all filters")
    print(f"  - Prediction logged to Scout Ledger")
    print(f"  - Odds tracking active")
    
    print("\n🔮 VÉLØ CHAREX OPERATIONAL")


if __name__ == "__main__":
    main()

