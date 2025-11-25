"""
VELO Oracle - Automated Prediction Pipeline
Fetches races, generates predictions, stores results
"""

import pickle
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import json
import os

from app.scrapers.racing_post import RacingPostScraper

class VeloPredictionPipeline:
    def __init__(self, model_path: str, db_connection=None):
        self.model_path = model_path
        self.model = None
        self.db = db_connection
        self.scraper = None
        
    def load_model(self) -> bool:
        """Load VELO model"""
        print("🤖 Loading VELO model...")
        
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            print("✅ Model loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def initialize_scraper(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Racing Post scraper"""
        self.scraper = RacingPostScraper(username, password)
    
    def prepare_features(self, runners: List[Dict]) -> pd.DataFrame:
        """
        Convert runner data to VELO model features
        
        Args:
            runners: List of runner dictionaries from Racing Post
        
        Returns:
            DataFrame with features for prediction
        """
        features = pd.DataFrame()
        
        # Extract odds
        odds_list = []
        for runner in runners:
            odds_str = runner.get('odds', '0')
            
            # Parse odds (handle formats like "5/2", "7.5", "EVS")
            try:
                if '/' in odds_str:
                    # Fractional odds (e.g., "5/2")
                    num, den = odds_str.split('/')
                    odds = (float(num) / float(den)) + 1
                elif odds_str == 'EVS':
                    odds = 2.0
                else:
                    # Decimal odds
                    odds = float(odds_str)
            except:
                odds = 0
            
            odds_list.append(odds)
        
        # Create features
        features['odds'] = odds_list
        features['log_odds'] = np.log(pd.Series(odds_list).clip(lower=1.01))
        features['implied_prob'] = 1 / pd.Series(odds_list).clip(lower=1.01)
        
        # Market features
        features['field_size'] = len(runners)
        features['is_favorite'] = (pd.Series(odds_list) == min(odds_list)).astype(int)
        features['odds_rank'] = pd.Series(odds_list).rank()
        
        # Normalized probability
        total_implied = features['implied_prob'].sum()
        features['normalized_prob'] = features['implied_prob'] / total_implied if total_implied > 0 else 0
        
        # TS/RPR ratings (if available)
        ts_list = []
        rpr_list = []
        
        for runner in runners:
            ts = runner.get('ts', 0)
            rpr = runner.get('rpr', 0)
            
            try:
                ts_list.append(float(ts) if ts else 0)
                rpr_list.append(float(rpr) if rpr else 0)
            except:
                ts_list.append(0)
                rpr_list.append(0)
        
        if any(ts_list):
            features['ts_rating'] = ts_list
            features['ts_rank'] = pd.Series(ts_list).rank(ascending=False)
        
        if any(rpr_list):
            features['rpr_rating'] = rpr_list
            features['rpr_rank'] = pd.Series(rpr_list).rank(ascending=False)
        
        # Fill missing values
        features = features.fillna(0)
        
        return features
    
    def predict_race(self, race: Dict) -> List[Dict]:
        """
        Generate predictions for a single race
        
        Args:
            race: Race dictionary with runners
        
        Returns:
            List of predictions for each runner
        """
        runners = race.get('runners', [])
        
        if not runners:
            return []
        
        # Prepare features
        X = self.prepare_features(runners)
        
        # Get predictions
        try:
            if hasattr(self.model, 'predict_proba'):
                probs = self.model.predict_proba(X)[:, 1]
            else:
                probs = self.model.predict(X)
        except Exception as e:
            print(f"⚠️ Prediction error: {e}")
            return []
        
        # Create predictions
        predictions = []
        
        for i, runner in enumerate(runners):
            odds = X['odds'].iloc[i]
            predicted_prob = probs[i]
            implied_prob = 1 / odds if odds > 0 else 0
            edge = predicted_prob - implied_prob
            
            # Calculate recommended stake (Kelly Criterion)
            if edge > 0 and odds > 0:
                kelly_fraction = edge / (odds - 1)
                # Use fractional Kelly for safety (25% of full Kelly)
                recommended_stake = max(0, kelly_fraction * 0.25 * 100)  # Assuming £100 bankroll
            else:
                recommended_stake = 0
            
            predictions.append({
                'runner_name': runner.get('name'),
                'runner_number': runner.get('number'),
                'odds': odds,
                'predicted_prob': float(predicted_prob),
                'implied_prob': float(implied_prob),
                'edge': float(edge),
                'edge_pct': float(edge * 100),
                'recommended_stake': float(recommended_stake),
                'confidence': 'HIGH' if edge > 0.10 else 'MEDIUM' if edge > 0.05 else 'LOW',
                'jockey': runner.get('jockey'),
                'trainer': runner.get('trainer'),
                'form': runner.get('form'),
                'ts': runner.get('ts'),
                'rpr': runner.get('rpr')
            })
        
        # Sort by edge (best bets first)
        predictions.sort(key=lambda x: x['edge'], reverse=True)
        
        return predictions
    
    def process_todays_races(self, min_edge: float = 0.05) -> Dict:
        """
        Complete pipeline: scrape, predict, filter
        
        Args:
            min_edge: Minimum edge to consider a bet (default 5%)
        
        Returns:
            Dictionary with all predictions and high-value bets
        """
        print("\n" + "="*70)
        print("🏇 VELO ORACLE - DAILY PREDICTION PIPELINE")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Minimum edge: {min_edge*100:.1f}%")
        print()
        
        # Step 1: Scrape races
        if not self.scraper:
            self.initialize_scraper()
        
        race_cards = self.scraper.scrape_todays_cards(save_to_file=False)
        
        if not race_cards:
            print("❌ No races found")
            return {'races': [], 'high_value_bets': []}
        
        # Step 2: Generate predictions
        print(f"\n🤖 Generating predictions for {len(race_cards)} races...")
        
        all_predictions = []
        high_value_bets = []
        
        for i, race in enumerate(race_cards, 1):
            course = race.get('course')
            time = race.get('time')
            
            print(f"\n[{i}/{len(race_cards)}] {course} {time}")
            
            predictions = self.predict_race(race)
            
            if predictions:
                # Add race info to predictions
                for pred in predictions:
                    pred['race_course'] = course
                    pred['race_time'] = time
                    pred['race_date'] = race.get('date')
                    pred['race_title'] = race.get('title', '')
                
                all_predictions.append({
                    'race': {
                        'course': course,
                        'time': time,
                        'date': race.get('date'),
                        'title': race.get('title', ''),
                        'distance': race.get('distance', ''),
                        'class': race.get('class', '')
                    },
                    'predictions': predictions
                })
                
                # Filter high-value bets
                for pred in predictions:
                    if pred['edge'] > min_edge and pred['odds'] > 0:
                        high_value_bets.append(pred)
                
                # Show top 3
                print(f"  Top 3 predictions:")
                for j, pred in enumerate(predictions[:3], 1):
                    print(f"    {j}. {pred['runner_name']}: "
                          f"Edge {pred['edge_pct']:.1f}%, "
                          f"Odds {pred['odds']:.2f}, "
                          f"Stake £{pred['recommended_stake']:.2f}")
        
        # Sort high-value bets by edge
        high_value_bets.sort(key=lambda x: x['edge'], reverse=True)
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print("="*70)
        print(f"Total races analyzed: {len(race_cards)}")
        print(f"Total predictions: {sum(len(r['predictions']) for r in all_predictions)}")
        print(f"High-value bets (>{min_edge*100:.0f}% edge): {len(high_value_bets)}")
        
        if high_value_bets:
            print(f"\n🎯 TOP 5 BETS:")
            for i, bet in enumerate(high_value_bets[:5], 1):
                print(f"{i}. {bet['race_course']} {bet['race_time']} - {bet['runner_name']}")
                print(f"   Edge: {bet['edge_pct']:.1f}%, Odds: {bet['odds']:.2f}, Stake: £{bet['recommended_stake']:.2f}")
        
        print("="*70)
        
        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'races': all_predictions,
            'high_value_bets': high_value_bets,
            'summary': {
                'total_races': len(race_cards),
                'total_predictions': sum(len(r['predictions']) for r in all_predictions),
                'high_value_bets_count': len(high_value_bets),
                'min_edge': min_edge
            }
        }
        
        # Save to file
        filename = f"velo_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Saved to {filename}")
        
        return results


if __name__ == "__main__":
    # Example usage
    
    MODEL_PATH = "model_cycle_961_best_roi.pkl"
    
    # Initialize pipeline
    pipeline = VeloPredictionPipeline(MODEL_PATH)
    
    # Load model
    if pipeline.load_model():
        # Process today's races
        results = pipeline.process_todays_races(min_edge=0.05)
