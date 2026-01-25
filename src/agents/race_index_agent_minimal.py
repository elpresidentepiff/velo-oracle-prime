"""
Minimal RaceIndexAgent for testing.
"""
import json
import re
from pathlib import Path

def extract_race_index(pdf_path: Path):
    # For now, return mock data to test the pipeline
    return {
        "venue": "NEWCASTLE",
        "date": "2026-01-24",
        "races": [
            {"race_time": "12:05", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "12:35", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "13:05", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "13:35", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "14:05", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "14:35", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
            {"race_time": "15:05", "race_name": "N/A", "distance": "N/A", "class": "N/A", "going": "N/A", "prize_money": "N/A"},
        ]
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python race_index_agent.py <pdf_path>")
        sys.exit(1)
    data = extract_race_index(Path(sys.argv[1]))
    print(json.dumps(data, indent=2))
