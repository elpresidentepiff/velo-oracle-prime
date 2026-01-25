"""
RatingsParserAgent (Foundation Layer) - REAL IMPLEMENTATION

Role: Extract historical performance metrics: OR, RPR, TS.
Explicit nulls only. Never inferred.

Output: JSON list of runners with ratings.
"""

import re
import json
import pdfplumber
import sys
from pathlib import Path
from typing import List, Dict

def extract_ratings(pdf_path: Path) -> List[Dict]:
    """
    REAL IMPLEMENTATION: Extract ratings from TS/RPR PDFs.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Get text from first page
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            if not text:
                raise ValueError(f"Could not extract text from PDF: {pdf_path}")
            
            # Simple pattern: look for horse names and ratings
            # In TS/RPR PDFs, format is different from XX PDFs
            # We'll implement a basic extractor for now
            
            ratings = []
            lines = [line.strip() for line in text.split('\n')]
            
            # Look for patterns with horse names and numbers
            for i, line in enumerate(lines):
                # Pattern for horse with ratings: "1 BAVARIA IRON 60 58 75"
                horse_match = re.match(r'^(\d+)\s+([A-Z][A-Z\s\-]+?)\s+(\d+|\-)\s+(\d+|\-)\s+(\d+|\-)', line)
                
                if horse_match:
                    horse_number = int(horse_match.group(1))
                    horse_name = horse_match.group(2).strip()
                    
                    # Parse ratings (could be numbers or dashes)
                    or_rating = horse_match.group(3)
                    ts_rating = horse_match.group(4)
                    rpr_rating = horse_match.group(5)
                    
                    # Convert dashes to None
                    or_rating = int(or_rating) if or_rating != '-' else None
                    ts_rating = int(ts_rating) if ts_rating != '-' else None
                    rpr_rating = int(rpr_rating) if rpr_rating != '-' else None
                    
                    ratings.append({
                        "horse_name": horse_name,
                        "horse_number": horse_number,
                        "official_rating": or_rating,
                        "rpr": rpr_rating,
                        "topspeed": ts_rating
                    })
            
            if not ratings:
                # Fallback: create empty ratings for known horses
                # In production, this would parse actual TS/RPR PDFs
                raise ValueError(f"No ratings found in PDF: {pdf_path}")
            
            return ratings
            
    except Exception as e:
        raise ValueError(f"Failed to parse ratings from PDF {pdf_path}: {str(e)}")

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
    if len(sys.argv) != 2:
        print("Usage: python ratings_parser_agent_real.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
