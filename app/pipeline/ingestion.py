import json
from pathlib import Path

DATA_DIR = Path("data/incoming_races")

def ingest_local_pdfs():
    """
    Short-term ingestion layer.
    Loads structured JSON race files from data/incoming_races.
    """

    races = []

    if not DATA_DIR.exists():
        print(f"[INGESTION] Folder not found: {DATA_DIR}")
        return races

    for file in DATA_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                race_data = json.load(f)
                races.append(race_data)
                print(f"[INGESTION] Loaded {file.name}")
        except Exception as e:
            print(f"[INGESTION] Failed loading {file.name}: {e}")

    print(f"[INGESTION] Total races loaded: {len(races)}")
    return races
