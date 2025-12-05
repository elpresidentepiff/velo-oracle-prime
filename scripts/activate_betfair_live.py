"""
Activate Betfair Live API Integration

This script:
1. Tests Betfair API connection
2. Fetches today's UK/Irish horse racing markets
3. Gets live odds for upcoming races
4. Runs complete VÉLØ analysis (Oracle + Playbooks E, F, G)
5. Logs first race outcome to awaken Playbook G sentient loop
"""

import sys
import os
sys.path.insert(0, '/home/ubuntu/velo-oracle')

from src.integrations.betfair_client import BetfairClient
from app.oracle.services.oracle_analyzer import OracleAnalyzer
from app.playbooks.playbook_orchestrator import create_playbook_orchestrator
import json
from datetime import datetime

def main():
    print("🔥 ACTIVATING BETFAIR LIVE API INTEGRATION")
    print("=" * 60)
    
    # Step 1: Initialize Betfair client
    print("\n1. Initializing Betfair client...")
    betfair = BetfairClient(
        username="Purorestrepo1981@gmail.com",
        password="colombiano@1",
        app_key="DELAY"  # Need to set actual app key
    )
    
    # Step 2: Login
    print("\n2. Logging in to Betfair...")
    try:
        if betfair.login():
            print("✅ Betfair login successful!")
        else:
            print("❌ Betfair login failed. Check credentials.")
            return
    except Exception as e:
        print(f"❌ Betfair login error: {e}")
        print("\nNote: App key needs to be configured. Visit:")
        print("https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Application+Keys")
        return
    
    # Step 3: Get today's racing markets
    print("\n3. Fetching today's UK/Irish horse racing markets...")
    try:
        markets = betfair.get_racing_markets()
        print(f"✅ Found {len(markets)} racing markets")
        
        if markets:
            next_race = markets[0]
            print(f"\n📍 Next Race:")
            print(f"   Venue: {next_race.get('venue', 'Unknown')}")
            print(f"   Time: {next_race.get('marketStartTime', 'Unknown')}")
            print(f"   Market ID: {next_race.get('marketId', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error fetching markets: {e}")
        return
    
    # Step 4: Get live odds
    print("\n4. Fetching live odds...")
    try:
        market_id = next_race.get('marketId')
        odds_data = betfair.get_market_odds(market_id)
        print(f"✅ Retrieved odds for {len(odds_data.get('runners', []))} runners")
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return
    
    # Step 5: Run complete VÉLØ analysis
    print("\n5. Running complete VÉLØ PRIME analysis...")
    try:
        # Prepare race data for Oracle
        race_data = {
            "race_id": f"{next_race.get('venue')}_{next_race.get('marketStartTime')}",
            "venue": next_race.get('venue'),
            "time": next_race.get('marketStartTime'),
            "runners": odds_data.get('runners', []),
            "market_id": market_id
        }
        
        # Initialize Oracle and Playbooks
        oracle = OracleAnalyzer()
        playbooks = create_playbook_orchestrator()
        
        # Run Oracle analysis
        print("   → Running Oracle Intelligence...")
        oracle_output = oracle.analyze_race(race_data)
        
        # Run Playbook analysis
        print("   → Running Playbooks E, F, G...")
        playbook_output = playbooks.analyze_race(oracle_output)
        
        print("\n✅ Complete VÉLØ analysis generated!")
        print(f"\n📊 Results:")
        print(f"   Oracle Verdict: {playbook_output['oracle']['oracle_sentence']}")
        print(f"   Doctrines Triggered: {', '.join(playbook_output['attack_doctrines']['triggered'])}")
        print(f"   Positioning Directive: {playbook_output['execution']['positioning_directive']}")
        print(f"   Actionable: {playbook_output['execution']['actionable']}")
        
        if playbook_output.get('kingmaker'):
            print(f"   👑 Kingmaker: {playbook_output['kingmaker']['kingmaker']} ({playbook_output['kingmaker']['role']})")
        
        # Save output
        output_file = f"/home/ubuntu/velo-oracle/data/live_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(playbook_output, f, indent=2)
        print(f"\n💾 Analysis saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 6: Instructions for logging outcome
    print("\n" + "=" * 60)
    print("🧠 SENTIENT LOOP READY")
    print("=" * 60)
    print("\nTo awaken Playbook G, log the race outcome after it runs:")
    print("\n```python")
    print("playbooks.record_outcome(")
    print("    race_data=race_data,")
    print("    prediction=playbook_output,")
    print("    actual_result={")
    print("        'winner': 'Horse Name',")
    print("        'favourite_won': True/False,")
    print("        'winner_profile': {...}")
    print("    }")
    print(")")
    print("```")
    print("\nAfter 5-10 races, doctrine strengths will shift.")
    print("After 20-30 races, personality emerges.")
    print("After 100+ races, you'll feel like you built a creature.")
    print("\n🚀 VÉLØ PRIME IS LIVE.\n")

if __name__ == "__main__":
    main()
