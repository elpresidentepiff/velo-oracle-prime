#!/usr/bin/env python3
"""
VÉLØ v9.0++ CHAREX - Kempton 4:40 Race Analysis
Five-Filter System Application
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from kempton_440_race_data import runners, race_info, race_context
# Imports not needed - analysis is self-contained

def analyze_race():
    """Run complete Five-Filter analysis on Kempton 4:40"""
    
    print("=" * 80)
    print("VÉLØ v9.0++ CHAREX - FIVE-FILTER SYSTEM")
    print(f"Race: {race_info['track']} {race_info['time']}")
    print(f"Date: {race_info['date']}")
    print(f"Surface: {race_info['surface']}")
    print(f"Field Size: {race_context['field_size']} runners")
    print("=" * 80)
    print()
    
    # Analysis is self-contained in this script
    
    # FILTER 1: STATISTICAL QUALIFICATION PROTOCOL ENGINE (SQPE)
    print("FILTER 1: STATISTICAL QUALIFICATION PROTOCOL ENGINE (SQPE)")
    print("-" * 80)
    
    sqpe_results = []
    for runner in runners:
        # Calculate SQPE score based on statistical factors
        score = 0
        reasons = []
        
        # Course form (25 points max)
        if runner['course_record']['win_rate'] >= 20:
            score += 25
            reasons.append(f"Excellent course form ({runner['course_record']['win_rate']}%)")
        elif runner['course_record']['win_rate'] >= 10:
            score += 15
            reasons.append(f"Good course form ({runner['course_record']['win_rate']}%)")
        elif runner['course_record']['win_rate'] > 0:
            score += 5
            reasons.append(f"Has won at course ({runner['course_record']['win_rate']}%)")
        
        # Going form (20 points max)
        if runner['going_record']['win_rate'] >= 30:
            score += 20
            reasons.append(f"Excellent going form ({runner['going_record']['win_rate']}%)")
        elif runner['going_record']['win_rate'] >= 20:
            score += 15
            reasons.append(f"Strong going form ({runner['going_record']['win_rate']}%)")
        elif runner['going_record']['win_rate'] >= 10:
            score += 10
            reasons.append(f"Good going form ({runner['going_record']['win_rate']}%)")
        
        # Distance form (20 points max)
        if runner['distance_record']['win_rate'] >= 20:
            score += 20
            reasons.append(f"Excellent distance record ({runner['distance_record']['win_rate']}%)")
        elif runner['distance_record']['win_rate'] >= 15:
            score += 15
            reasons.append(f"Strong distance record ({runner['distance_record']['win_rate']}%)")
        elif runner['distance_record']['win_rate'] >= 10:
            score += 10
            reasons.append(f"Good distance record ({runner['distance_record']['win_rate']}%)")
        
        # Trainer form (15 points max)
        if runner['trainer_stats']['last_14_days']['win_rate'] >= 20:
            score += 15
            reasons.append(f"Hot trainer ({runner['trainer_stats']['last_14_days']['win_rate']}% L14)")
        elif runner['trainer_stats']['last_14_days']['win_rate'] >= 10:
            score += 10
            reasons.append(f"In-form trainer ({runner['trainer_stats']['last_14_days']['win_rate']}% L14)")
        
        # Age factor (10 points max)
        if 4 <= runner['age'] <= 6:
            score += 10
            reasons.append(f"Prime age ({runner['age']}yo)")
        elif runner['age'] == 7 or runner['age'] == 8:
            score += 5
            reasons.append(f"Experienced ({runner['age']}yo)")
        
        # Weight factor (10 points max)
        weight_str = runner['weight']
        if '9-9' in weight_str or '9-8' in weight_str:
            score += 5
            reasons.append("Competitive weight")
        
        sqpe_results.append({
            'name': runner['name'],
            'score': score,
            'reasons': reasons,
            'pass': score >= 40
        })
    
    # Sort by score
    sqpe_results.sort(key=lambda x: x['score'], reverse=True)
    
    for result in sqpe_results:
        status = "✓ PASS" if result['pass'] else "✗ FAIL"
        print(f"\n{result['name']}: {result['score']}/100 {status}")
        for reason in result['reasons']:
            print(f"  • {reason}")
    
    qualified = [r for r in sqpe_results if r['pass']]
    print(f"\n{len(qualified)}/{len(runners)} horses qualified through SQPE")
    print()
    
    # FILTER 2: VALUE IDENTIFICATION ENGINE (VIE)
    print("\nFILTER 2: VALUE IDENTIFICATION ENGINE (VIE)")
    print("-" * 80)
    
    vie_results = []
    for runner in runners:
        # Find SQPE score
        sqpe_score = next(r['score'] for r in sqpe_results if r['name'] == runner['name'])
        
        # Calculate expected probability from SQPE score
        expected_prob = sqpe_score / 100
        
        # Calculate implied probability from odds
        implied_prob = 1 / runner['current_odds']
        
        # Calculate value
        value = (expected_prob - implied_prob) * 100
        
        # Check for value
        has_value = value > 10  # 10% edge minimum
        
        vie_results.append({
            'name': runner['name'],
            'odds': runner['current_odds'],
            'sqpe_score': sqpe_score,
            'expected_prob': expected_prob * 100,
            'implied_prob': implied_prob * 100,
            'value': value,
            'has_value': has_value
        })
    
    vie_results.sort(key=lambda x: x['value'], reverse=True)
    
    for result in vie_results:
        status = "✓ VALUE" if result['has_value'] else "✗ NO VALUE"
        print(f"\n{result['name']} @ {result['odds']:.2f}: {status}")
        print(f"  SQPE Score: {result['sqpe_score']}/100")
        print(f"  Expected Probability: {result['expected_prob']:.1f}%")
        print(f"  Implied Probability: {result['implied_prob']:.1f}%")
        print(f"  Value Edge: {result['value']:+.1f}%")
    
    value_horses = [r for r in vie_results if r['has_value']]
    print(f"\n{len(value_horses)} horses showing value")
    print()
    
    # FILTER 3: MARKET MANIPULATION DETECTOR (MMD)
    print("\nFILTER 3: MARKET MANIPULATION DETECTOR (MMD)")
    print("-" * 80)
    
    mmd_results = []
    for runner in runners:
        flags = []
        risk_score = 0
        
        # Check odds movement
        odds_movement = runner['odds_movement']
        if len(odds_movement) >= 3:
            if odds_movement[1] < odds_movement[0] * 0.85:
            # Significant shortening
                flags.append("⚠ Significant odds crash (>15%)")
                risk_score += 30
            elif odds_movement[1] > odds_movement[0] * 1.15:
                # Significant drift
                flags.append("✓ Drifting in market (potential value)")
                risk_score -= 10
        
        # Check jockey/trainer stats
        if runner['jockey_stats']['last_14_days']['win_rate'] == 0 and \
           runner['jockey_stats']['last_14_days']['runs'] >= 5:
            flags.append("⚠ Jockey 0% strike rate L14")
            risk_score += 15
        
        if runner['trainer_stats']['last_14_days']['win_rate'] == 0 and \
           runner['trainer_stats']['last_14_days']['runs'] >= 10:
            flags.append("⚠ Trainer 0% strike rate L14")
            risk_score += 15
        
        # Check for positive trainer form
        if runner['trainer_stats']['last_14_days']['win_rate'] >= 20:
            flags.append("✓ Hot trainer (20%+ L14)")
            risk_score -= 20
        
        # Check for market favorite status
        if runner.get('market_favorite'):
            flags.append("★ Market Favorite")
            if risk_score > 0:
                flags.append("⚠ Favorite with risk factors")
        
        # Overall assessment
        if risk_score >= 40:
            assessment = "HIGH RISK - AVOID"
        elif risk_score >= 20:
            assessment = "MODERATE RISK - CAUTION"
        elif risk_score <= -10:
            assessment = "LOW RISK - CLEAR"
        else:
            assessment = "NEUTRAL"
        
        mmd_results.append({
            'name': runner['name'],
            'risk_score': risk_score,
            'flags': flags,
            'assessment': assessment,
            'safe': risk_score < 40
        })
    
    mmd_results.sort(key=lambda x: x['risk_score'])
    
    for result in mmd_results:
        print(f"\n{result['name']}: {result['assessment']} (Risk: {result['risk_score']})")
        for flag in result['flags']:
            print(f"  {flag}")
    
    safe_horses = [r for r in mmd_results if r['safe']]
    print(f"\n{len(safe_horses)}/{len(runners)} horses cleared MMD")
    print()
    
    # FILTER 4: FORM CYCLE ANALYSIS (FCA)
    print("\nFILTER 4: FORM CYCLE ANALYSIS (FCA)")
    print("-" * 80)
    
    fca_results = []
    for runner in runners:
        form = runner['form_id']
        speed_figs = runner['speed_figures']
        
        # Analyze recent form
        recent_form = form[:3] if len(form) >= 3 else form
        
        # Count wins, places, and poor runs
        wins = recent_form.count('1')
        places = sum(1 for c in recent_form if c.isdigit() and int(c) <= 3)
        poor_runs = sum(1 for c in recent_form if c.isdigit() and int(c) >= 6)
        
        # Speed figure trend
        if len(speed_figs) >= 3:
            last_3_avg = sum(speed_figs[:3]) / 3
            prev_3_avg = sum(speed_figs[3:6]) / 3 if len(speed_figs) >= 6 else last_3_avg
            trend = last_3_avg - prev_3_avg
        else:
            trend = 0
        
        # Form assessment
        form_score = 0
        form_notes = []
        
        if wins >= 1:
            form_score += 30
            form_notes.append(f"✓ Recent win in last 3")
        
        if places >= 2:
            form_score += 20
            form_notes.append(f"✓ Consistent (2+ places in last 3)")
        
        if poor_runs == 0:
            form_score += 15
            form_notes.append(f"✓ No poor runs recently")
        elif poor_runs >= 2:
            form_score -= 20
            form_notes.append(f"⚠ Multiple poor runs ({poor_runs} in last 3)")
        
        if trend > 2:
            form_score += 15
            form_notes.append(f"✓ Improving speed figures (+{trend:.1f})")
        elif trend < -2:
            form_score -= 15
            form_notes.append(f"⚠ Declining speed figures ({trend:.1f})")
        
        # Best recent speed figure
        best_recent = max(speed_figs[:3]) if len(speed_figs) >= 3 else 0
        if best_recent >= 80:
            form_score += 10
            form_notes.append(f"✓ High-class speed figure ({best_recent})")
        
        fca_results.append({
            'name': runner['name'],
            'form': form,
            'form_score': form_score,
            'trend': trend,
            'best_recent': best_recent,
            'notes': form_notes,
            'in_form': form_score >= 30
        })
    
    fca_results.sort(key=lambda x: x['form_score'], reverse=True)
    
    for result in fca_results:
        status = "✓ IN FORM" if result['in_form'] else "✗ OUT OF FORM"
        print(f"\n{result['name']}: {result['form_score']}/100 {status}")
        print(f"  Recent Form: {result['form'][:6]}")
        print(f"  Speed Trend: {result['trend']:+.1f}")
        print(f"  Best Recent: {result['best_recent']}")
        for note in result['notes']:
            print(f"  {note}")
    
    in_form = [r for r in fca_results if r['in_form']]
    print(f"\n{len(in_form)} horses in good form")
    print()
    
    # FILTER 5: FINAL SYNTHESIS & VERDICT
    print("\nFILTER 5: FINAL SYNTHESIS & VERDICT")
    print("=" * 80)
    
    # Combine all filters
    final_scores = []
    for runner in runners:
        name = runner['name']
        
        # Get scores from each filter
        sqpe = next(r for r in sqpe_results if r['name'] == name)
        vie = next(r for r in vie_results if r['name'] == name)
        mmd = next(r for r in mmd_results if r['name'] == name)
        fca = next(r for r in fca_results if r['name'] == name)
        
        # Calculate composite score
        composite = (
            sqpe['score'] * 0.30 +  # 30% weight
            (vie['value'] + 50) * 0.25 +  # 25% weight (normalized)
            (100 - mmd['risk_score']) * 0.20 +  # 20% weight
            fca['form_score'] * 0.25  # 25% weight
        )
        
        # Pass/fail criteria
        passed_filters = sum([
            sqpe['pass'],
            vie['has_value'],
            mmd['safe'],
            fca['in_form']
        ])
        
        final_scores.append({
            'name': name,
            'odds': runner['current_odds'],
            'composite_score': composite,
            'passed_filters': passed_filters,
            'sqpe_score': sqpe['score'],
            'value_edge': vie['value'],
            'risk_score': mmd['risk_score'],
            'form_score': fca['form_score'],
            'recommended': passed_filters >= 3 and composite >= 50
        })
    
    final_scores.sort(key=lambda x: x['composite_score'], reverse=True)
    
    print("\nFINAL RANKINGS:")
    print("-" * 80)
    
    for i, result in enumerate(final_scores, 1):
        status = "✓ RECOMMENDED" if result['recommended'] else "✗ REJECT"
        print(f"\n{i}. {result['name']} @ {result['odds']:.2f} - {status}")
        print(f"   Composite Score: {result['composite_score']:.1f}/100")
        print(f"   Filters Passed: {result['passed_filters']}/4")
        print(f"   SQPE: {result['sqpe_score']}/100 | Value: {result['value_edge']:+.1f}% | Risk: {result['risk_score']} | Form: {result['form_score']}/100")
    
    # Generate betting recommendations
    print("\n" + "=" * 80)
    print("BETTING RECOMMENDATIONS")
    print("=" * 80)
    
    recommended = [r for r in final_scores if r['recommended']]
    
    if not recommended:
        print("\n⚠ NO BETS RECOMMENDED - Race does not meet system criteria")
        print("Recommendation: PASS on this race")
    else:
        print(f"\n{len(recommended)} horse(s) meet system criteria:\n")
        
        for rec in recommended:
            # Determine bet type based on odds
            if 8 <= rec['odds'] <= 14:
                bet_type = "PRIME E/W"
                stake = "2% bank"
                terms = "Top 4, 1/5 odds"
            elif 16 <= rec['odds'] <= 25:
                bet_type = "LONGSHOT E/W"
                stake = "1% bank"
                terms = "Top 3, 1/4 odds"
            elif 10 <= rec['odds'] <= 20:
                bet_type = "WIN ONLY"
                stake = "1.5% bank"
                terms = "Win bet"
            else:
                bet_type = "WATCH ONLY"
                stake = "0% bank"
                terms = "Outside system parameters"
            
            # Confidence rating
            if rec['composite_score'] >= 70:
                confidence = "HIGH"
            elif rec['composite_score'] >= 60:
                confidence = "MEDIUM-HIGH"
            elif rec['composite_score'] >= 50:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            
            print(f"🎯 {rec['name']} @ {rec['odds']:.2f}")
            print(f"   Bet Type: {bet_type}")
            print(f"   Stake: {stake}")
            print(f"   Terms: {terms}")
            print(f"   Confidence: {confidence}")
            print(f"   Score: {rec['composite_score']:.1f}/100")
            print()
    
    # Save results
    verdict = {
        'race_info': race_info,
        'race_context': race_context,
        'analysis_date': '2025-10-15',
        'system_version': 'VÉLØ v9.0++ CHAREX',
        'sqpe_results': sqpe_results,
        'vie_results': vie_results,
        'mmd_results': mmd_results,
        'fca_results': fca_results,
        'final_scores': final_scores,
        'recommendations': recommended
    }
    
    with open('kempton_440_verdict.json', 'w') as f:
        json.dump(verdict, f, indent=2)
    
    print("=" * 80)
    print("Analysis complete. Results saved to kempton_440_verdict.json")
    print("=" * 80)
    
    return verdict

if __name__ == '__main__':
    analyze_race()

