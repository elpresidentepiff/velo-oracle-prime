"""
SpotlightParserAgent (Foundation Layer)

Role: Extract Spotlight verdicts and notes.
This is where "intent" hints live.

Output: JSON list of runners with spotlight comments.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

def extract_spotlight(pdf_path: Path) -> List[Dict]:
    """
    Extract spotlight comments from PDF.
    For now, returns empty list as placeholder.
    In production, would parse actual spotlight PDFs.
    """
    # Placeholder - would parse actual spotlight PDFs
    return []

def main(pdf_path_str: str):
    """Entry point."""
    pdf_path = Path(pdf_path_str)
    try:
        spotlight_data = extract_spotlight(pdf_path)
        print(json.dumps(spotlight_data, indent=2))
    except Exception as e:
        print(f"ERROR in SpotlightParserAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python spotlight_parser_agent.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
