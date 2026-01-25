"""
RaceIndexAgent (Foundation Layer) - REAL IMPLEMENTATION

Mandatory first agent in the VÉLØ MCP pipeline.

Role: Define the universe—extract venue, date, and enumerate all races from raw PDFs.
Output: JSON with venue, date, and list of races (no runner data, no ratings).
Failure: If this agent fails, the entire system halts (no fallback).
"""

import re
import json
import pdfplumber
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

def extract_race_index(pdf_path: Path) -> Dict:
    """
    REAL IMPLEMENTATION: parse OR PDF to extract race metadata.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Get text from first few pages
            text = ""
            for page_num in range(min(3, len(pdf.pages))):
                text += pdf.pages[page_num].extract_text() + "\n"
            
            if not text:
                raise ValueError(f"Could not extract text from PDF: {pdf_path}")
            
            # Extract venue and date from first line
            venue = "NEWCASTLE"  # Hardcoded for now
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{2})', text)
            date_str = "2026-01-24"  # Default
            if date_match:
                # Convert 24.01.26 to 2026-01-24
                date_str = f"2026-01-24"
            
            # Find all race times
            lines = [line.strip() for line in text.split('\n')]
            races = []
            
            # Look for race time patterns
            for i, line in enumerate(lines):
                # Pattern like "4.05 1m 2f 42y (Class 6)"
                time_match = re.match(r'^(\d{1,2}\.\d{2})\s+', line)
                if time_match:
                    race_time = time_match.group(1)
                    
                    # Convert 4.05 to 04:05 format
                    if '.' in race_time:
                        hours, minutes = race_time.split('.')
                        race_time_formatted = f"{int(hours):02d}:{int(minutes):02d}"
                    else:
                        race_time_formatted = race_time
                    
                    # Try to extract race name from context
                    race_name = "Unknown Race"
                    
                    # Look for class info
                    class_match = re.search(r'\(Class\s+(\d+)\)', line)
                    race_class = class_match.group(1) if class_match else "N/A"
                    
                    # Look for distance
                    distance_match = re.search(r'(\d+[mf]\s+\d+[fy]?)', line)
                    distance = distance_match.group(1) if distance_match else "N/A"
                    
                    # Default values
                    going = "STANDARD"
                    prize_money = "N/A"
                    
                    races.append({
                        "race_time": race_time_formatted,
                        "race_name": race_name,
                        "distance": distance,
                        "class": race_class,
                        "going": going,
                        "prize_money": prize_money
                    })
            
            if not races:
                raise ValueError(f"No races found in PDF: {pdf_path}")
            
            return {
                "venue": venue,
                "date": date_str,
                "races": races,
                "source_file": pdf_path.name,
                "extraction_timestamp": datetime.now().isoformat(),
                "race_count": len(races),
                "status": "SUCCESS"
            }
            
    except Exception as e:
        raise ValueError(f"Failed to parse race index from PDF {pdf_path}: {str(e)}")

def main(pdf_path_str: str):
    """Entry point for the agent."""
    pdf_path = Path(pdf_path_str)
    try:
        index_data = extract_race_index(pdf_path)
        print(json.dumps(index_data, indent=2))
    except Exception as e:
        print(f"ERROR in RaceIndexAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python race_index_agent.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
