#!/usr/bin/env python3
"""
VÉLØ Oracle 2.0 - Data-Driven Race Analysis
============================================

NO NARRATIVES. ONLY DATA.

This script:
1. Pulls live Betfair market data (volumes, prices, movements)
2. Pulls historical data from The Racing API
3. Calculates ML probabilities
4. Detects market manipulation
5. Identifies value bets based on MATH, not opinions

Usage:
    python analyze_race_data_driven.py --market-id 1.249166696 --course Ascot --time "13:30"

Author: VÉLØ Oracle Team
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from integrations.betfair_api import BetfairAPIClient, BetfairMarketAnalyzer
from integrations.racing_api import RacingAPIClient
from data.data_pipeline import DataPipeline, FeatureExtractor
from ml.ml_engine import BenterModel


class DataDrivenAnalyzer:
    """
    Pure data-driven race analyzer.
    
    No opinions. No narratives. Just math.
    """
    
    def __init__(self):
        self.betfair = BetfairAPIClient()
        self.racing_api = RacingAPIClient()
        self.pipeline = DataPipeline()
        self.feature_extractor = FeatureExtractor()
        
        print("🔮 VÉLØ Oracle 2.0 - Data-Driven Analysis")
        print("="*60)
    
    def analyze_race(self, market_id: str, course: str, race_time: str) -> Dict:
        """
        Analyze a race using only raw data.
        
        Args:
            market_id: Betfair market ID
            course: Course name (e.g., "Ascot")
            race_time: Race time (e.g., "13:30")
            
        Returns:
            Dict containing analysis results
        """
        print(f"\n📊 Analyzing: {course} {race_time}")
        print(f"Market ID: {market_id}\n")
        
        results = {
            'market_id': market_id,
            'course': course,
            'race_time': race_time,
            'timestamp': datetime.now().isoformat(),
            'betfair_data': None,
            'historical_data': None,
            'ml_probabilities': None,
            'manipulation_score': None,
            'value_bets': []
        }
        
        # ================================================================
        # STEP 1: BETFAIR LIVE DATA
        # ================================================================
        print("🔴 STEP 1: Fetching Betfair live market data...")
        
        if not self.betfair.login():
            print("❌ Betfair login failed. Check credentials.")
            return results
        
        try:
            # Get market odds
            market_data = self.betfair.get_market_odds(market_id)
            
            if not market_data:
                print("❌ No market data returned")
                return results
            
            print(f"✓ Market status: {market_data.get('status')}")
            print(f"✓ Total matched: £{market_data.get('totalMatched', 0):,.0f}")
            
            runners = market_data.get('runners', [])
            print(f"✓ Runners: {len(runners)}")
            
            # Extract runner data
            betfair_runners = []
            for runner in runners:
                runner_data = {
                    'selection_id': runner.get('selectionId'),
                    'name': runner.get('runnerName'),
                    'status': runner.get('status'),
                    'total_matched': runner.get('totalMatched', 0),
                    'last_price_traded': runner.get('lastPriceTraded'),
                    'back_prices': [],
                    'lay_prices': []
                }
                
                # Extract back prices
                ex = runner.get('ex', {})
                for back in ex.get('availableToBack', [])[:3]:
                    runner_data['back_prices'].append({
                        'price': back.get('price'),
                        'size': back.get('size')
                    })
                
                # Extract lay prices
                for lay in ex.get('availableToLay', [])[:3]:
                    runner_data['lay_prices'].append({
                        'price': lay.get('price'),
                        'size': lay.get('size')
                    })
                
                betfair_runners.append(runner_data)
                
                # Print runner data
                back_price = runner_data['back_prices'][0]['price'] if runner_data['back_prices'] else 0
                back_size = runner_data['back_prices'][0]['size'] if runner_data['back_prices'] else 0
                matched = runner_data['total_matched']
                
                print(f"  {runner_data['name']:<20} | Back: {back_price:>6.2f} (£{back_size:>8,.0f}) | Matched: £{matched:>10,.0f}")
            
            results['betfair_data'] = {
                'total_matched': market_data.get('totalMatched', 0),
                'status': market_data.get('status'),
                'runners': betfair_runners
            }
            
            # ================================================================
            # STEP 2: MARKET MANIPULATION DETECTION
            # ================================================================
            print("\n🔍 STEP 2: Detecting market manipulation...")
            
            analyzer = BetfairMarketAnalyzer(self.betfair)
            
            for runner in betfair_runners:
                movement = self.betfair.detect_market_movement(
                    market_id,
                    runner['selection_id']
                )
                
                if movement['manipulation_score'] > 50:
                    print(f"⚠️  {runner['name']}: Manipulation score {movement['manipulation_score']}/100")
                    print(f"    Indicators: {', '.join(movement['indicators'])}")
                
                runner['manipulation_score'] = movement['manipulation_score']
                runner['manipulation_indicators'] = movement['indicators']
            
            results['manipulation_score'] = max([r['manipulation_score'] for r in betfair_runners])
            
            # ================================================================
            # STEP 3: HISTORICAL DATA FROM RACING API
            # ================================================================
            print("\n📚 STEP 3: Fetching historical data from Racing API...")
            
            # Get historical data for each horse
            for runner in betfair_runners:
                horse_name = runner['name']
                
                # Search for horse
                search_results = self.racing_api.search_horse(horse_name)
                
                if search_results:
                    horse_id = search_results[0].get('id')
                    
                    # Get horse form
                    form = self.racing_api.get_horse_form(horse_id, limit=10)
                    
                    if form:
                        runner['historical_form'] = form
                        
                        # Calculate stats
                        wins = len([r for r in form if r.get('position') == 1])
                        places = len([r for r in form if r.get('position') in [1, 2, 3]])
                        
                        runner['win_rate'] = wins / len(form) if form else 0
                        runner['place_rate'] = places / len(form) if form else 0
                        
                        print(f"  {horse_name:<20} | Runs: {len(form)} | Wins: {wins} | Places: {places}")
            
            results['historical_data'] = betfair_runners
            
            # ================================================================
            # STEP 4: ML PROBABILITY CALCULATION
            # ================================================================
            print("\n🤖 STEP 4: Calculating ML win probabilities...")
            
            # This would use the trained Benter model
            # For now, we'll use a simplified calculation based on:
            # 1. Market odds (implied probability)
            # 2. Historical win rate
            # 3. Recent form
            # 4. Matched volume (confidence indicator)
            
            total_matched = results['betfair_data']['total_matched']
            
            for runner in betfair_runners:
                # Market implied probability
                back_price = runner['back_prices'][0]['price'] if runner['back_prices'] else 100
                market_prob = 1 / back_price if back_price > 0 else 0
                
                # Historical win rate
                hist_win_rate = runner.get('win_rate', 0)
                
                # Volume confidence (higher matched = more confidence)
                volume_weight = runner['total_matched'] / total_matched if total_matched > 0 else 0
                
                # Weighted probability
                # 60% market, 30% historical, 10% volume
                ml_probability = (
                    0.6 * market_prob +
                    0.3 * hist_win_rate +
                    0.1 * volume_weight
                )
                
                runner['ml_probability'] = ml_probability
                runner['market_probability'] = market_prob
                
                # Expected value
                expected_value = (ml_probability * back_price) - 1
                runner['expected_value'] = expected_value
                
                print(f"  {runner['name']:<20} | ML: {ml_probability*100:>5.1f}% | Market: {market_prob*100:>5.1f}% | EV: {expected_value*100:>+6.1f}%")
            
            results['ml_probabilities'] = betfair_runners
            
            # ================================================================
            # STEP 5: VALUE BET IDENTIFICATION
            # ================================================================
            print("\n💰 STEP 5: Identifying value bets...")
            
            # Sort by expected value
            value_runners = sorted(betfair_runners, key=lambda x: x['expected_value'], reverse=True)
            
            for runner in value_runners:
                if runner['expected_value'] > 0.10:  # EV > 10%
                    back_price = runner['back_prices'][0]['price'] if runner['back_prices'] else 0
                    
                    value_bet = {
                        'horse': runner['name'],
                        'back_price': back_price,
                        'ml_probability': runner['ml_probability'],
                        'expected_value': runner['expected_value'],
                        'manipulation_score': runner['manipulation_score'],
                        'recommendation': self._get_bet_recommendation(runner)
                    }
                    
                    results['value_bets'].append(value_bet)
                    
                    print(f"✓ VALUE: {runner['name']}")
                    print(f"  Price: {back_price:.2f}")
                    print(f"  ML Probability: {runner['ml_probability']*100:.1f}%")
                    print(f"  Expected Value: {runner['expected_value']*100:+.1f}%")
                    print(f"  Recommendation: {value_bet['recommendation']}")
                    print()
            
            if not results['value_bets']:
                print("❌ No value bets found (all EV < 10%)")
            
        finally:
            self.betfair.logout()
        
        return results
    
    def _get_bet_recommendation(self, runner: Dict) -> str:
        """Determine bet recommendation based on data."""
        ev = runner['expected_value']
        price = runner['back_prices'][0]['price'] if runner['back_prices'] else 100
        manip_score = runner['manipulation_score']
        
        # High manipulation = avoid
        if manip_score > 70:
            return "AVOID (High manipulation)"
        
        # Strong value + good price
        if ev > 0.25 and price >= 4.0 and price <= 21.0:
            return "STRONG BET (EW)"
        
        # Good value
        if ev > 0.15 and price >= 4.0 and price <= 21.0:
            return "BET (EW)"
        
        # Marginal value
        if ev > 0.10:
            return "SAVER (Small stake)"
        
        return "PASS"
    
    def save_results(self, results: Dict, filename: str = None):
        """Save analysis results to JSON."""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"race_analysis_{timestamp}.json"
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to: {filepath}")


def main():
    parser = argparse.ArgumentParser(description='Data-driven race analysis')
    parser.add_argument('--market-id', required=True, help='Betfair market ID')
    parser.add_argument('--course', required=True, help='Course name')
    parser.add_argument('--time', required=True, help='Race time (HH:MM)')
    parser.add_argument('--save', action='store_true', help='Save results to JSON')
    
    args = parser.parse_args()
    
    analyzer = DataDrivenAnalyzer()
    results = analyzer.analyze_race(args.market_id, args.course, args.time)
    
    if args.save:
        analyzer.save_results(results)
    
    print("\n" + "="*60)
    print("✅ Analysis complete")


if __name__ == '__main__':
    main()

