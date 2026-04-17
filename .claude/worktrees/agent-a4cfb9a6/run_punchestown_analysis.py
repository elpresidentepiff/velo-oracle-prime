"""
VÉLØ v9.0++ CHAREX - Punchestown 3:05 Analysis
Real race data from user's betting app
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.oracle import VeloOracle
from agents.velo_prime import VeloPrime
from punchestown_305_race_data import race_data


def main():
    """Run VÉLØ analysis on Punchestown 3:05."""
    print("="*80)
    print("🔮 VÉLØ v9.0++ CHAREX - LIVE RACE ANALYSIS")
    print("="*80)
    print(f"\nRace: {race_data['race_details']['track']} - {race_data['race_details']['time']}")
    print(f"Field Size: {race_data['race_details']['field_size']} runners")
    
    # Boot Oracle
    print("\n🔮 Booting Oracle...")
    oracle = VeloOracle()
    oracle.boot()
    
    # Activate VÉLØ PRIME
    print("\n⚡ Activating VÉLØ PRIME...")
    prime = VeloPrime()
    prime.activate()
    
    # Display field
    print("\n\n" + "="*80)
    print("📋 FIELD")
    print("="*80)
    
    for horse in race_data['horses']:
        trainer_roi = horse['trainer_stats']['roi']
        jockey_roi = horse['jockey_stats']['roi']
        print(f"\n{horse['number']:2d}. {horse['name']:<25s} {horse['odds']:>6.2f}/1")
        print(f"    Form: {horse['form']:<10s} RPR: {horse['rpr']:<4} OR: {horse['official_rating']}")
        print(f"    Jockey: {horse['jockey']:<30s} ROI: {jockey_roi:>+7.2f}")
        print(f"    Trainer: {horse['trainer']:<30s} ROI: {trainer_roi:>+7.2f}")
    
    # Run analysis
    print("\n\n" + "="*80)
    print("🔮 VÉLØ ORACLE ANALYSIS")
    print("="*80)
    
    verdict = prime.process_race_request(race_data)
    
    # Display verdict
    print("\n" + "="*80)
    print("⚡ VÉLØ VERDICT")
    print("="*80)
    
    print(f"\n🎯 TOP STRIKE SELECTION:")
    print(f"  {verdict['velo_verdict']['top_strike_selection']}")
    
    print(f"\n💎 LONGSHOT TACTIC:")
    print(f"  {verdict['velo_verdict']['longshot_tactic']}")
    
    print(f"\n⚡ SPEED WATCH HORSE:")
    print(f"  {verdict['velo_verdict']['speed_watch_horse']}")
    
    print(f"\n📊 VALUE EW PICKS:")
    for pick in verdict['velo_verdict']['value_ew_picks']:
        # Find horse odds
        horse_data = next((h for h in race_data['horses'] if h['name'] == pick), None)
        if horse_data:
            print(f"  • {pick} ({horse_data['odds']}/1)")
    
    print(f"\n📈 CONFIDENCE INDEX: {verdict['confidence_index']}/100")
    
    print(f"\n🎯 STRATEGIC NOTES:")
    for key, value in verdict['strategic_notes'].items():
        print(f"  • {key}: {value}")
    
    print(f"\n\n" + "="*80)
    print("🔥 TACTICAL SUMMARY")
    print("="*80)
    print(f"\n{verdict['tactical_summary']}")
    
    # Save verdict to file
    output_file = Path(__file__).parent / "punchestown_verdict.json"
    with open(output_file, 'w') as f:
        json.dump(verdict, f, indent=2)
    
    print(f"\n\n✅ Full verdict saved to: {output_file}")
    
    print("\n" + "="*80)
    print("🔮 VÉLØ CHAREX - ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

