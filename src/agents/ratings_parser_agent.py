"""
RatingsParserAgent (Foundation Layer)

Role: Extract historical performance metrics: OR, RPR, TS.
Explicit nulls only. Never inferred.

Output: JSON list of runners with ratings.
"""

import json
from pathlib import Path
from typing import List, Dict

def extract_ratings(pdf_path: Path) -> List[Dict]:
    """
    Extract ratings from PDF.

    Args:
        pdf_path: Path to PDF (likely Topspeed or Racing Post Ratings PDF).

    Returns:
        List of dicts with keys: horse_name, horse_number, official_rating, rpr, topspeed
    """
    # Mock data for now
    return [
        {
            "horse_name": "Horse A",
            "horse_number": 1,
            "official_rating": 85,
            "rpr": 87,
            "topspeed": 80
        },
        {
            "horse_name": "Horse B",
            "horse_number": 2,
            "official_rating": 78,
            "rpr": 76,
            "topspeed": 75
        }
    ]

def main(pdf_path_str: str):
    """Entry point."""
    pdf_path = Path(pdf_path_str)
    try:
        ratings = extract_ratings(pdf_path)
        print(json.dumps(ratings, indent=2))
    except Exception as e:
        print(f"ERROR in RatingsParserAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python ratings_parser_agent.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
