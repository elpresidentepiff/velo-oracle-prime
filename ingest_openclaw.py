import os
import json
import pandas as pd
from datetime import datetime

# Configuration
INCOMING_DIR = "/home/ubuntu/velo-oracle-prime/data/incoming/openclaw"
PROCESSED_DIR = "/home/ubuntu/velo-oracle-prime/data/processed"
LEDGER_FILE = "/home/ubuntu/velo-oracle-prime/ledger.json"

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r') as f:
            return json.load(f)
    return {"balance": 1000.0, "history": [], "pending_bets": []}

def save_ledger(ledger):
    with open(LEDGER_FILE, 'w') as f:
        json.dump(ledger, f, indent=4)

def process_json_card(filepath):
    print(f"Processing JSON Card: {filepath}...")
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Validate Schema (Basic Check)
        if 'meeting' not in data or 'races' not in data:
            print(f"Invalid JSON format in {filepath}. Missing 'meeting' or 'races'.")
            return

        ledger = load_ledger()
        if "pending_bets" not in ledger:
            ledger["pending_bets"] = []

        meeting_name = data.get('meeting')
        meeting_date = data.get('date')
        
        new_bets_count = 0

        for race in data['races']:
            race_time = race.get('time')
            race_name = race.get('name', f"Race {race.get('race_number')}")
            
            for selection in race.get('selections', []):
                bet = {
                    "date": meeting_date,
                    "meeting": meeting_name,
                    "time": race_time,
                    "race": race_name,
                    "horse": selection.get('horse'),
                    "type": selection.get('bet_type'),
                    "stake_pct": selection.get('stake_percentage'),
                    "confidence": selection.get('confidence'),
                    "edge": selection.get('edge'),
                    "analysis": selection.get('analysis'),
                    "metrics": selection.get('metrics'),
                    "status": "PENDING",
                    "ingested_at": datetime.now().isoformat()
                }
                ledger["pending_bets"].append(bet)
                new_bets_count += 1

        save_ledger(ledger)
        print(f"Successfully ingested {new_bets_count} bets for {meeting_name}.")
        
        # Move to processed directory
        filename = os.path.basename(filepath)
        os.rename(filepath, os.path.join(PROCESSED_DIR, filename))

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def main():
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    print(f"Watching {INCOMING_DIR} for new files...")
    files = [f for f in os.listdir(INCOMING_DIR) if os.path.isfile(os.path.join(INCOMING_DIR, f))]
    
    if not files:
        print("No new files found.")
        return

    for file in files:
        if file.endswith('.json'):
            process_json_card(os.path.join(INCOMING_DIR, file))
        else:
            print(f"Skipping non-JSON file: {file}")

if __name__ == "__main__":
    main()
