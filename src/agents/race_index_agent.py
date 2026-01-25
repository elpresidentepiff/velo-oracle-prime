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
from typing import Dict, List

def extract_race_index(pdf_path: Path) -> Dict:
    """
    REAL IMPLEMENTATION: parse PDF to extract race metadata.
    Returns venue, date, and list of races with times.
    """
    venue = "UNKNOWN"
    date = "UNKNOWN"
    races = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from first few pages
            all_text = ""
            for i, page in enumerate(pdf.pages[:3]):  # Check first 3 pages
                page_text = page.extract_text()
                if page_text:
                    all_text += page_text + "\n"
            
            if not all_text:
                raise ValueError(f"Could not extract text from PDF: {pdf_path}")
            
            # Extract venue - look for track names
            venue_patterns = [
                r'(NEWCASTLE|SOUTHWELL|CHELTENHAM|KEMPTON|AINTREE|ASCOT)',
                r'Venue[:\s]*([A-Z]+)',
                r'@\s*([A-Z]+)'
            ]
            
            for pattern in venue_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                if matches:
                    venue = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    venue = venue.upper()
                    break
            
            # Extract date - look for date patterns
            date_patterns = [
                r'(\d{1,2})[\s/.-](\d{1,2})[\s/.-](\d{2,4})',  # dd.mm.yy or dd/mm/yy
                r'(\d{4})[\s/.-](\d{1,2})[\s/.-](\d{1,2})',  # yyyy-mm-dd
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, all_text)
                if matches:
                    # Try to parse the first match
                    try:
                        if len(matches[0]) == 3:
                            day, month, year = matches[0]
                            if len(year) == 2:
                                year = f"20{year}"  # Assume 21st century
                            date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            break
                    except:
                        continue
            
            # If date not found in text, try to extract from filename
            if date == "UNKNOWN":
                filename = pdf_path.name
                date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
                if date_match:
                    year, month, day = date_match.groups()
                    date = f"{year}-{month}-{day}"
            
            # Extract race times - look for patterns like 4.05, 12:35, etc.
            all_times = set()
            race_details = {}
            
            for page_num, page in enumerate(pdf.pages[:3]):
                text = page.extract_text()
                if not text:
                    continue
                
                # Look for race time patterns
                time_pattern = r'\b(\d{1,2})\.(\d{2})\b'
                matches = re.findall(time_pattern, text)
                
                for hour_str, minute_str in matches:
                    try:
                        hour = int(hour_str)
                        minute = int(minute_str)
                        
                        # Filter for likely race times
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            time_str = f"{hour:02d}:{minute:02d}"
                            all_times.add(time_str)
                            
                            # Try to extract race name if available
                            if time_str not in race_details:
                                # Look for race name after time
                                race_name_pattern = rf'{hour_str}\.{minute_str}\s+([A-Za-z0-9\s\-\.\(\)\&\'\"]+)'
                                name_match = re.search(race_name_pattern, text)
                                if name_match:
                                    race_name = name_match.group(1).strip()
                                    # Clean up race name
                                    race_name = re.sub(r'\s+', ' ', race_name)
                                    race_name = race_name.split('(')[0].strip() if '(' in race_name else race_name
                                    race_details[time_str] = {"name": race_name[:100]}
                    except:
                        continue
                
                # Also look for distance and class
                for time_str in list(all_times):
                    hour_str, minute_str = time_str.split(':')
                    time_pattern_short = f"{int(hour_str)}.{int(minute_str):02d}"
                    
                    # Look for distance after time
                    distance_pattern = rf'{time_pattern_short}\s+[^\n]*?(\d+m\s*\d*f?\s*\d*y?)'
                    distance_match = re.search(distance_pattern, text, re.IGNORECASE)
                    if distance_match and time_str in race_details:
                        race_details[time_str]["distance"] = distance_match.group(1)
                    
                    # Look for class
                    class_pattern = rf'{time_pattern_short}[^\n]*?Class\s*(\d+)'
                    class_match = re.search(class_pattern, text, re.IGNORECASE)
                    if class_match and time_str in race_details:
                        race_details[time_str]["class"] = class_match.group(1)
            
            if not all_times:
                raise ValueError(f"No race times found in PDF: {pdf_path}")
            
            # Create race entries
            for time_str in sorted(all_times):
                details = race_details.get(time_str, {})
                races.append({
                    "race_time": time_str,
                    "race_name": details.get("name", "N/A"),
                    "distance": details.get("distance", "N/A"),
                    "class": details.get("class", "N/A"),
                    "going": "STANDARD",  # Default for AW
                    "prize_money": "N/A"
                })
            
            return {
                "venue": venue,
                "date": date,
                "races": races,
                "source_file": str(pdf_path.name),
                "extraction_timestamp": datetime.now().isoformat(),
                "race_count": len(races),
                "status": "SUCCESS"
            }
            
    except Exception as e:
        raise ValueError(f"Failed to parse PDF {pdf_path}: {str(e)}")

def main(pdf_path_str: str):
    """Entry point for the agent."""
    pdf_path = Path(pdf_path_str)
    try:
        index_data = extract_race_index(pdf_path)
        print(json.dumps(index_data, indent=2))
    except Exception as e:
        # Fail loud: print error and exit with non-zero code
        print(f"ERROR in RaceIndexAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python race_index_agent.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
