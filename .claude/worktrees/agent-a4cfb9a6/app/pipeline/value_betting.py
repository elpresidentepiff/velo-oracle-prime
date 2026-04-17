#!/usr/bin/env python3
"""
VELO ORACLE - Value Betting System
Uses TS/RPR ratings to identify value bets vs market odds
"""

import json
import numpy as np
from datetime import datetime

def odds_to_probability(odds_str):
    """Convert fractional odds to probability"""
    try:
        if '/' in odds_str:
            num, den = odds_str.split('/')
            decimal = (float(num) / float(den)) + 1
            prob = 1 / decimal
            return prob, decimal
    except:
        pass
    return 0.5, 2.0

def rating_to_probability(rating, max_rating):
    """
    Convert rating to win probability
    Higher rating = higher probability
    """
    if rating <= 0 or max_rating <= 0:
        return 0.0
    
    # Normalize rating (0-1)
    norm_rating = rating / max_rating
    
    # Convert to probability (simple linear model)
    # Top rated horse gets ~40% win prob, others scale down
    prob = norm_rating * 0.4
    
    return prob

def analyze_race(race_data):
    """
    Analyze race and identify value bets
    """
    print(f"\n{'='*70}")
    print(f"RACE: {race_data['course']} {race_data['time']}")
    print(f"{'='*70}")
    
    runners = race_data['runners']
    
    # Extract ratings
    for runner in runners:
        # Parse ratings
        try:
            runner['ts_num'] = float(runner['ts']) if runner['ts'] and runner['ts'] != '-' else 0
        except:
            runner['ts_num'] = 0
        
        try:
            runner['rpr_num'] = float(runner['rpr']) if runner['rpr'] and runner['rpr'] != '-' else 0
        except:
            runner['rpr_num'] = 0
        
        try:
            runner['or_num'] = float(runner['or']) if runner['or'] and runner['or'] != '-' else 0
        except:
            runner['or_num'] = 0
        
        # Market probability
        runner['market_prob'], runner['decimal_odds'] = odds_to_probability(runner['odds'])
    
    # Find max ratings for normalization
    max_ts = max([r['ts_num'] for r in runners if r['ts_num'] > 0], default=100)
    max_rpr = max([r['rpr_num'] for r in runners if r['rpr_num'] > 0], default=100)
    max_or = max([r['or_num'] for r in runners if r['or_num'] > 0], default=100)
    
    # Calculate model probabilities and edges
    value_bets = []
    
    for runner in runners:
        # Calculate probabilities from each rating
        ts_prob = rating_to_probability(runner['ts_num'], max_ts)
        rpr_prob = rating_to_probability(runner['rpr_num'], max_rpr)
        or_prob = rating_to_probability(runner['or_num'], max_or)
        
        # Average rating probability (weighted)
        rating_probs = [p for p in [ts_prob, rpr_prob, or_prob] if p > 0]
        if rating_probs:
            model_prob = np.mean(rating_probs)
        else:
            model_prob = 0.1
        
        # Calculate edge
        edge = model_prob - runner['market_prob']
        edge_pct = edge * 100
        
        # Kelly Criterion stake
        if edge > 0:
            kelly = edge / (runner['decimal_odds'] - 1)
            kelly_pct = max(0, min(kelly * 100, 10))  # Cap at 10%
        else:
            kelly_pct = 0
        
        # Expected value
        ev = (model_prob * (runner['decimal_odds'] - 1)) - (1 - model_prob)
        ev_pct = ev * 100
        
        runner['model_prob'] = model_prob
        runner['edge'] = edge
        runner['edge_pct'] = edge_pct
        runner['kelly_pct'] = kelly_pct
        runner['ev_pct'] = ev_pct
        
        # Value bet criteria: edge > 3% OR EV > 10%
        if edge_pct > 3.0 or ev_pct > 10.0:
            value_bets.append(runner)
    
    # Sort by edge
    runners_sorted = sorted(runners, key=lambda x: x['edge'], reverse=True)
    
    # Print all runners
    print(f"\n{'#':<3} {'Horse':<25} {'Odds':<8} {'Mkt%':<7} {'Mod%':<7} {'Edge%':<7} {'EV%':<7} {'TS':<5} {'RPR':<5}")
    print(f"{'-'*90}")
    
    for i, runner in enumerate(runners_sorted, 1):
        marker = "🎯" if runner in value_bets else "  "
        print(f"{marker}{i:<2} {runner['horse']:<25} {runner['odds']:<8} "
              f"{runner['market_prob']*100:<7.1f} {runner['model_prob']*100:<7.1f} "
              f"{runner['edge_pct']:<7.1f} {runner['ev_pct']:<7.1f} "
              f"{runner['ts']:<5} {runner['rpr']:<5}")
    
    # Highlight value bets
    if value_bets:
        value_bets_sorted = sorted(value_bets, key=lambda x: x['edge_pct'], reverse=True)
        
        print(f"\n{'='*70}")
        print(f"🎯 VALUE BETS IDENTIFIED: {len(value_bets)}")
        print(f"{'='*70}")
        
        for i, bet in enumerate(value_bets_sorted, 1):
            print(f"\n#{i} 🐎 {bet['horse']}")
            print(f"   Odds: {bet['odds']} ({bet['decimal_odds']:.2f}) | Jockey: {bet['jockey']}")
            print(f"   Market Win%: {bet['market_prob']*100:.1f}% | Model Win%: {bet['model_prob']*100:.1f}%")
            print(f"   Edge: {bet['edge_pct']:+.1f}% | Expected Value: {bet['ev_pct']:+.1f}%")
            print(f"   Recommended Stake: {bet['kelly_pct']:.2f}% of bankroll")
            print(f"   Ratings - TS: {bet['ts']} | RPR: {bet['rpr']} | OR: {bet['or']}")
            print(f"   Form: {bet['form']} | Trainer: {bet['trainer']}")
            
            # Betting advice
            if bet['edge_pct'] > 10:
                print(f"   ⭐ STRONG VALUE - High confidence bet")
            elif bet['edge_pct'] > 5:
                print(f"   ✅ GOOD VALUE - Recommended bet")
            else:
                print(f"   ⚠️  MARGINAL VALUE - Small stake only")
    else:
        print(f"\n{'='*70}")
        print(f"⚠️  NO VALUE BETS FOUND")
        print(f"{'='*70}")
        print(f"Market odds appear efficient for this race.")
        print(f"Recommend: SKIP this race or wait for better opportunities.")
    
    return value_bets

def main():
    """Main value betting analysis"""
    
    print(f"\n{'#'*70}")
    print(f"VELO ORACLE - Value Betting System")
    print(f"Using TS/RPR ratings to identify market inefficiencies")
    print(f"{'#'*70}")
    
    # Load scraped race data
    today = datetime.now().strftime("%Y-%m-%d")
    race_file = f"/home/ubuntu/velo_races_{today}.json"
    
    print(f"\nLoading race data from: {race_file}")
    
    with open(race_file, 'r') as f:
        data = json.load(f)
    
    print(f"Date: {data['date']}")
    print(f"Races scraped: {data['races_scraped']}")
    
    # Analyze each race
    all_value_bets = []
    
    for race in data['races']:
        if race['success'] and race['runners']:
            value_bets = analyze_race(race)
            
            if value_bets:
                all_value_bets.append({
                    'race': f"{race['course']} {race['time']}",
                    'url': race['url'],
                    'bets': value_bets
                })
    
    # Summary
    print(f"\n{'#'*70}")
    print(f"SUMMARY")
    print(f"{'#'*70}")
    print(f"Total races analyzed: {len(data['races'])}")
    print(f"Races with value bets: {len(all_value_bets)}")
    print(f"Total value bets: {sum(len(r['bets']) for r in all_value_bets)}")
    
    # Save results
    output_file = f"/home/ubuntu/value_bets_{today}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'date': today,
            'generated_at': datetime.now().isoformat(),
            'races_analyzed': len(data['races']),
            'value_bets': all_value_bets
        }, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_file}")
    print(f"{'#'*70}\n")

if __name__ == "__main__":
    main()
