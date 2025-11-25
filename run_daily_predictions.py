#!/usr/bin/env python3
"""
VELO Oracle - Daily Prediction Runner
Main automation script for daily predictions
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.pipeline.predictor import VeloPredictionPipeline

def main():
    """Run daily predictions"""
    
    # Configuration
    MODEL_PATH = "models/marathon_1hour/model_cycle_961_best_roi.pkl"
    MIN_EDGE = 0.05  # 5% minimum edge
    
    # Racing Post credentials (optional - for TS/RPR ratings)
    RP_USERNAME = os.getenv('RACING_POST_USERNAME')
    RP_PASSWORD = os.getenv('RACING_POST_PASSWORD')
    
    print("="*70)
    print("🏇 VELO ORACLE - DAILY PREDICTIONS")
    print("="*70)
    
    # Initialize pipeline
    pipeline = VeloPredictionPipeline(MODEL_PATH)
    
    # Initialize scraper with credentials if available
    if RP_USERNAME and RP_PASSWORD:
        print(f"✅ Using Racing Post account: {RP_USERNAME}")
        pipeline.initialize_scraper(RP_USERNAME, RP_PASSWORD)
    else:
        print("ℹ️  Using Racing Post free data (no TS/RPR ratings)")
        pipeline.initialize_scraper()
    
    # Load model
    if not pipeline.load_model():
        print("❌ Failed to load model")
        sys.exit(1)
    
    # Process today's races
    try:
        results = pipeline.process_todays_races(min_edge=MIN_EDGE)
        
        # Exit code based on results
        if results['high_value_bets']:
            print(f"\n✅ Found {len(results['high_value_bets'])} high-value bets!")
            sys.exit(0)
        else:
            print(f"\nℹ️  No high-value bets found today")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
