"""
Diagnostic script to see why Punchestown horses failed filters
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from modules.five_filters import FiveFilters
from punchestown_305_race_data import race_data


def main():
    """Diagnose filter failures."""
    print("="*80)
    print("🔍 VÉLØ FILTER DIAGNOSTIC - Punchestown 3:05")
    print("="*80)
    
    filters = FiveFilters()
    
    print(f"\n📋 Testing {len(race_data['horses'])} horses...\n")
    
    for horse in race_data['horses']:
        print(f"\n{'='*80}")
        print(f"🐎 {horse['number']}. {horse['name']} ({horse['odds']}/1)")
        print(f"{'='*80}")
        
        # Test each filter
        result = filters.apply_all_filters(horse, race_data['race_details'])
        
        print(f"\n📊 Filter Results:")
        print(f"  Filter 1 (Form Reality):       {'✅ PASS' if result['filter_1_form_reality'] else '❌ FAIL'}")
        print(f"  Filter 2 (Intent Detection):   {'✅ PASS' if result['filter_2_intent_detection'] else '❌ FAIL'}")
        print(f"  Filter 3 (Sectional Suit):     {'✅ PASS' if result['filter_3_sectional_suitability'] else '❌ FAIL'}")
        print(f"  Filter 4 (Market Misdirection):{'✅ PASS' if result['filter_4_market_misdirection'] else '❌ FAIL'}")
        print(f"  Filter 5 (Value Distortion):   {'✅ PASS' if result['filter_5_value_distortion'] else '❌ FAIL'}")
        
        print(f"\n  Overall: {'✅ ALL PASSED' if result['passed_all_filters'] else '❌ FAILED'}")
        
        # Show specific failure reasons
        print(f"\n  Failure Reasons:")
        for reason in result['failure_reasons']:
            print(f"    • {reason}")
    
    print(f"\n\n{'='*80}")
    print("🎯 SUMMARY")
    print(f"{'='*80}")
    
    # Run full filter
    passed, failed = filters.filter_entire_field(race_data['horses'], race_data['race_details'])
    
    print(f"\nTotal Horses: {len(race_data['horses'])}")
    print(f"Passed All Filters: {len(passed)}")
    print(f"Failed Filters: {len(failed)}")
    
    if passed:
        print(f"\n✅ HORSES THAT PASSED:")
        for item in passed:
            print(f"  • {item['horse']['name']} ({item['horse']['odds']}/1)")
    else:
        print(f"\n❌ NO HORSES PASSED ALL FILTERS")
        print(f"\nThis is VÉLØ being disciplined - refusing to bet when no clear edge exists.")


if __name__ == "__main__":
    main()

