#!/usr/bin/env python3
"""
VÉLØ Oracle v9.0++ Analysis Script
Race #8: Chelmsford City 5:45
"""

import sys
import os
sys.path.insert(0, '/home/ubuntu/velo-oracle/src')

from chelmsford_545_race_data import race_data
from core.oracle import VeloOracle
import json

def main():
    print("=" * 80)
    print("VÉLØ ORACLE v9.0++ - CHAREX ENGINE")
    print("Race #8: Chelmsford City 5:45")
    print("=" * 80)
    print()
    
    # Initialize Oracle
    oracle = VeloOracle()
    oracle.boot()
    
    # Run full analysis
    print("\n🔮 Running full analytical engine with all 9 modules...")
    print("   SQPE | V9PM | TIE | SSM | BOP | NDS | DLV | TRA | PRSCL")
    print()
    
    verdict = oracle.analyze_race(race_data)
    
    # Save verdict
    with open('/home/ubuntu/velo-oracle/chelmsford_545_verdict.json', 'w') as f:
        json.dump(verdict, f, indent=2)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nVerdict saved to: chelmsford_545_verdict.json")
    
    # Display summary
    print("\n" + "🎯 VÉLØ VERDICT SUMMARY")
    print("=" * 80)
    
    if 'selections' in verdict:
        for i, pick in enumerate(verdict['selections'], 1):
            print(f"\n#{i} {pick['name']} @ {pick['odds']}")
            print(f"   Confidence: {pick.get('confidence', 'N/A')}")
            print(f"   Story: {pick.get('story', 'N/A')[:100]}...")
    
    print("\n" + "=" * 80)
    
    return verdict

if __name__ == "__main__":
    main()

