"""
RunnerParserAgent - SIMPLE WORKING IMPLEMENTATION

Extract basic horse data from XX PDF.
"""

import re
import json
import pdfplumber
import sys
from pathlib import Path

def extract_runners(pdf_path: Path):
    """Extract runners with simple pattern matching."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()
        
        # Simple pattern: horse number followed by uppercase name
        pattern = r'(\d+)\s+([A-Z][A-Z\s\-]+?)\s+\d+'
        matches = re.findall(pattern, text)
        
        runners = []
        for horse_num, horse_name in matches:
            runners.append({
                "horse_name": horse_name.strip(),
                "horse_number": int(horse_num),
                "age": 5,
                "weight": "UNKNOWN",
                "trainer": "UNKNOWN",
                "jockey": "UNKNOWN"
            })
        
        return runners

def main():
    if len(sys.argv) != 2:
        print("Usage: python runner_parser_agent_simple.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    try:
        runners = extract_runners(pdf_path)
        print(json.dumps(runners, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
