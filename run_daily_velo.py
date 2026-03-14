#!/usr/bin/env python3

"""
VELO ORACLE – Daily Automation Script
Ingests manually supplied race PDFs and identifies value bets
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def main():
    """Run daily VELO ORACLE automation"""

    print(f"\n{'#' * 70}")
    print("VELO ORACLE – Daily Automation")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 70}\n")

    # STEP 1 — INGEST LOCAL PDF FILES
    print("STEP 1: Ingesting manually supplied race PDFs...")
    print("-" * 70)

    from app.pipeline.ingestion import ingest_local_pdfs

    try:
        json_file = ingest_local_pdfs()
        print(f"✅ Ingestion complete: {json_file}\n")
    except Exception as e:
        print(f"❌ Ingestion failed: {e}\n")
        return

    # STEP 2 — ANALYZE VALUE BETS
    print("STEP 2: Analyzing races and identifying value bets...")
    print("-" * 70)

    try:
        from app.pipeline.value_betting import main as analyze_value
        analyze_value()
        print("✅ Analysis complete\n")
    except Exception as e:
        print(f"❌ Analysis failed: {e}\n")
        return

    print(f"{'#' * 70}")
    print("VELO ORACLE automation completed successfully!")
    print(f"{'#' * 70}\n")


if __name__ == "__main__":
    asyncio.run(main())
