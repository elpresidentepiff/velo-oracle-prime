"""
Simple diagnostic for Punchestown filters
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
    
    print(f"\n📋 Analyzing {len(race_data['horses'])} horses...\n")
    
    passed_horses = []
    
    for horse in race_data['horses']:
        result = filters.apply_all_filters(horse, race_data['race_details'])
        
        status = "✅ PASS" if result['passed_all'] else "❌ FAIL"
        print(f"\n{status} {horse['number']:2d}. {horse['name']:<25s} ({horse['odds']:>5.1f}/1) - {result['passed_count']}/5 filters")
        
        # Show which filters failed
        if not result['passed_all']:
            print(f"     Failed: {', '.join(result['failed_filters'])}")
            
            # Show specific reasons
            for filter_name in result['failed_filters']:
                filter_data = result['filters'][filter_name]
                print(f"       • {filter_name}: {filter_data['reason']}")
        else:
            passed_horses.append(horse)
    
    print(f"\n\n{'='*80}")
    print("🎯 SUMMARY")
    print(f"{'='*80}")
    
    print(f"\nTotal Horses: {len(race_data['horses'])}")
    print(f"Passed All Filters: {len(passed_horses)}")
    
    if passed_horses:
        print(f"\n✅ HORSES THAT PASSED:")
        for horse in passed_horses:
            print(f"  • {horse['name']} ({horse['odds']}/1)")
    else:
        print(f"\n❌ NO HORSES PASSED ALL FILTERS")
        print(f"\n🔮 VÉLØ's Verdict: STAND DOWN")
        print(f"This is the Oracle being disciplined - refusing to bet when no clear edge exists.")
        print(f"\nMost common failures:")
        print(f"  • Form Reality: Inconsistent recent form")
        print(f"  • Value Distortion: Odds don't represent true value overlay")


if __name__ == "__main__":
    main()

