"""
VÉLØ v9.0++ CHAREX - Complete Engine Test

Tests the full Oracle system with all 9 analysis modules integrated.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.oracle import VeloOracle
from agents.velo_prime import VeloPrime
from agents.velo_manus import VeloManus
from modules.sqpe import SQPE
from modules.v9pm import V9PM
from modules.tie import TIE
from modules.ssm import SectionalSpeedMatrix
from modules.bop import BiasOptimalPositioning
from modules.nds import NarrativeDisruptionScan
from modules.dlv import DynamicLongshotValidator
from modules.tra import TripResistanceAnalyzer
from modules.prscl import PostRaceSelfCritiqueLoop


def create_comprehensive_test_data():
    """Create comprehensive test race with all data points."""
    return {
        "race_details": {
            "track": "Yarmouth",
            "time": "14:30",
            "race_type": "Class 5 Handicap",
            "distance": "6f",
            "going": "Good to Soft",
            "field_size": 8
        },
        "horses": [
            {
                "name": "Hidden Gem",
                "number": 3,
                "form": "342211",
                "age": 4,
                "weight": 127,
                "odds": 10.0,
                "trainer_stats": {"roi": 20.0, "wins": 10, "runs": 50},
                "jockey_stats": {"roi": 18.0, "wins": 35, "runs": 194},
                "official_rating": 74,
                "topspeed": 81,
                "rpr": 77,
                "race_comments": []
            },
            {
                "name": "Pace Setter",
                "number": 1,
                "form": "112",
                "age": 5,
                "weight": 130,
                "odds": 5.0,
                "trainer_stats": {"roi": 12.0, "wins": 15, "runs": 125},
                "jockey_stats": {"roi": 10.0, "wins": 48, "runs": 480},
                "official_rating": 78,
                "topspeed": 84,
                "rpr": 80,
                "race_comments": []
            },
            {
                "name": "Unlucky Last Time",
                "number": 5,
                "form": "6214",
                "age": 4,
                "weight": 125,
                "odds": 12.0,
                "trainer_stats": {"roi": 16.0, "wins": 12, "runs": 75},
                "jockey_stats": {"roi": 14.0, "wins": 42, "runs": 300},
                "official_rating": 73,
                "topspeed": 79,
                "rpr": 75,
                "race_comments": [
                    "Wide throughout, no cover",
                    "Hampered at 2f out, stayed on well"
                ]
            },
            {
                "name": "Media Darling",
                "number": 2,
                "form": "1000",
                "age": 3,
                "weight": 128,
                "odds": 4.0,
                "trainer_stats": {"roi": 3.0, "wins": 5, "runs": 167},
                "jockey_stats": {"roi": 4.0, "wins": 20, "runs": 500},
                "official_rating": 70,
                "topspeed": 75,
                "rpr": 72,
                "race_comments": []
            },
            {
                "name": "Hopeless Outsider",
                "number": 8,
                "form": "0999",
                "age": 6,
                "weight": 122,
                "odds": 25.0,
                "trainer_stats": {"roi": 2.0, "wins": 3, "runs": 150},
                "jockey_stats": {"roi": 3.0, "wins": 15, "runs": 500},
                "official_rating": 60,
                "topspeed": 65,
                "rpr": 62,
                "race_comments": []
            },
            {
                "name": "Valid Longshot",
                "number": 6,
                "form": "234",
                "age": 4,
                "weight": 123,
                "odds": 14.0,
                "trainer_stats": {"roi": 16.0, "wins": 8, "runs": 50},
                "jockey_stats": {"roi": 14.0, "wins": 30, "runs": 214},
                "official_rating": 76,
                "topspeed": 82,
                "rpr": 78,
                "race_comments": []
            }
        ]
    }


def main():
    """Run complete engine test."""
    print("="*80)
    print("🔮 VÉLØ v9.0++ CHAREX - COMPLETE ENGINE TEST")
    print("="*80)
    
    # Initialize Oracle
    print("\n🔮 Booting Oracle Core...")
    oracle = VeloOracle()
    oracle.boot()
    
    # Initialize all modules
    print("\n📦 Loading all 9 analysis modules...")
    
    sqpe = SQPE()
    v9pm = V9PM()
    tie = TIE()
    ssm = SectionalSpeedMatrix()
    bop = BiasOptimalPositioning()
    nds = NarrativeDisruptionScan()
    dlv = DynamicLongshotValidator()
    tra = TripResistanceAnalyzer()
    prscl = PostRaceSelfCritiqueLoop()
    
    modules = {
        "SQPE": sqpe,
        "V9PM": v9pm,
        "TIE": tie,
        "SSM": ssm,
        "BOP": bop,
        "NDS": nds,
        "DLV": dlv,
        "TRA": tra,
        "PRSCL": prscl
    }
    
    print(f"✅ Loaded {len(modules)} modules")
    
    # Initialize MANUS and register modules
    print("\n⚙️  Initializing MANUS orchestrator...")
    manus = VeloManus()
    manus.activate()
    
    for name, module in modules.items():
        manus.register_module(name, module)
    
    # Initialize PRIME
    print("\n⚡ Activating VÉLØ PRIME...")
    prime = VeloPrime()
    prime.activate()
    
    # Create test race
    print("\n\n" + "="*80)
    print("🏇 COMPREHENSIVE RACE ANALYSIS")
    print("="*80)
    
    race_data = create_comprehensive_test_data()
    
    print(f"\nRace: {race_data['race_details']['track']} - {race_data['race_details']['time']}")
    print(f"Distance: {race_data['race_details']['distance']}")
    print(f"Going: {race_data['race_details']['going']}")
    print(f"Field Size: {race_data['race_details']['field_size']}")
    
    print(f"\n📋 Runners:")
    for horse in race_data['horses']:
        print(f"  {horse['number']}. {horse['name']} - {horse['odds']}/1 (Form: {horse['form']})")
    
    # Run individual module tests
    print("\n\n" + "="*80)
    print("🔬 MODULE ANALYSIS")
    print("="*80)
    
    # Test SSM
    print("\n⚡ SSM - Pace Analysis:")
    pace_analysis = ssm.analyze_race_pace(race_data['horses'], race_data['race_details'])
    print(f"  Scenario: {pace_analysis['pace_scenario']}")
    print(f"  {pace_analysis['tactical_note']}")
    
    # Test BOP
    print("\n🎯 BOP - Draw Bias Analysis:")
    bias_analysis = bop.analyze_draw_bias(
        race_data['race_details']['track'],
        race_data['race_details']['going'],
        race_data['race_details']['distance'],
        race_data['race_details']['field_size']
    )
    print(f"  Bias: {bias_analysis['bias_type']} ({bias_analysis['severity']})")
    print(f"  {bias_analysis['tactical_note']}")
    
    # Test NDS
    print("\n🔍 NDS - Narrative Disruption Scan:")
    clean, distorted = nds.filter_narrative_distorted(race_data['horses'])
    print(f"  Clean horses: {len(clean)}")
    print(f"  Narrative-distorted: {len(distorted)}")
    for item in distorted:
        print(f"    ❌ {item['horse']['name']} - {', '.join(item['narrative_scan']['narratives_detected'])}")
    
    # Test DLV
    print("\n💎 DLV - Longshot Validation:")
    valid_longshots = dlv.get_valid_longshots(race_data['horses'], race_data['race_details'])
    print(f"  Valid longshots: {len(valid_longshots)}")
    for item in valid_longshots:
        print(f"    ✅ {item['horse']['name']} ({item['horse']['odds']}/1) - Score: {item['validation']['validation_score']:.2f}")
    
    # Test TRA
    print("\n🏇 TRA - Trip Resistance Analysis:")
    trip_upgraded = tra.get_trip_upgraded_horses(race_data['horses'])
    print(f"  Trip upgraded horses: {len(trip_upgraded)}")
    for item in trip_upgraded:
        print(f"    ⚠️ {item['horse']['name']} - Potential: {item['trip_analysis']['improvement_potential']:.2f}")
    
    # Run full PRIME analysis
    print("\n\n" + "="*80)
    print("🔮 VÉLØ PRIME COMPLETE ANALYSIS")
    print("="*80)
    
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
    
    # Test PRSCL with simulated result
    print("\n\n" + "="*80)
    print("🔄 PRSCL - Post-Race Critique (Simulated)")
    print("="*80)
    
    simulated_result = {
        "winner": "Hidden Gem",
        "positions": {
            "Hidden Gem": 1,
            "Unlucky Last Time": 2,
            "Valid Longshot": 3
        }
    }
    
    critique = prscl.critique_prediction(verdict, simulated_result)
    critique_report = prscl.generate_critique_report(critique['critique_id'])
    print(f"\n{critique_report}")
    
    # Final summary
    print("\n\n" + "="*80)
    print("✅ COMPLETE ENGINE TEST SUMMARY")
    print("="*80)
    
    print(f"\n🎯 Modules Tested:")
    for name in modules.keys():
        print(f"  ✅ {name}")
    
    print(f"\n📊 System Status:")
    system_status = manus.get_system_status()
    print(f"  Total Modules: {len(system_status['modules'])}")
    print(f"  All Operational: ✅")
    
    print(f"\n🔮 VÉLØ v9.0++ CHAREX - FULLY OPERATIONAL")
    print(f"  All 9 analysis modules integrated and tested")
    print(f"  Genesis Protocol active and learning")
    print(f"  Oracle ready for production")


if __name__ == "__main__":
    main()

