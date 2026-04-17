#!/usr/bin/env python3
"""
VELO ORACLE - Daily Automation Script
Scrapes today's races and identifies value bets
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.scrapers.racing_post_scraper import main as scrape_races

async def main():
    """Run daily VELO ORACLE automation"""
    
    print(f"\n{'#'*70}")
    print(f"VELO ORACLE - Daily Automation")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}\n")
    
    # Step 1: Scrape today's races
    print("STEP 1: Scraping today's race cards from Racing Post...")
    print("-" * 70)
    
    try:
        await scrape_races()
        print("✅ Scraping complete\n")
    except Exception as e:
        print(f"❌ Scraping failed: {e}\n")
        return
    
    # Step 2: Analyze and identify value bets
    print("STEP 2: Analyzing races and identifying value bets...")
    print("-" * 70)
    
    try:
        # Import and run value betting analysis
        from app.pipeline.value_betting import main as analyze_value
        analyze_value()
        print("✅ Analysis complete\n")
    except Exception as e:
        print(f"❌ Analysis failed: {e}\n")
        return
    
    print(f"{'#'*70}")
    print(f"VELO ORACLE automation completed successfully!")
    print(f"{'#'*70}\n")

if __name__ == "__main__":
    asyncio.run(main())
