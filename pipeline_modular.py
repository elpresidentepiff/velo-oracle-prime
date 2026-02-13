import os
import json
import re
from core.parser import RobustPDFParser
from core.schema import RaceCard

# Configuration
DATA_DIR = "/home/ubuntu/upload"
OUTPUT_FILE = "/home/ubuntu/velo-oracle-prime/data/chelmsford_modular_processed.json"

def main():
    print(f"Scanning {DATA_DIR} for Chelmsford files...")
    
    # 1. Identify Files
    files = os.listdir(DATA_DIR)
    # Updated for Chelmsford
    main_card = next((f for f in files if "XX" in f and "Chelmsford" in f and "0012" in f), None) 
    if not main_card:
        main_card = next((f for f in files if "XX" in f and "Chelmsford" in f), None)

    if not main_card:
        print("CRITICAL: No Main Card (XX) found for Chelmsford.")
        return

    print(f"Main Card: {main_card}")
    
    # 2. Parse Main Card
    print("Parsing Main Card...")
    parser = RobustPDFParser()
    
    # Load Aux Data (OR, TS, PM)
    or_file = next((f for f in files if "OR" in f and "Chelmsford" in f), None)
    ts_file = next((f for f in files if "TS" in f and "Chelmsford" in f), None)
    pm_file = next((f for f in files if "PM" in f and "Chelmsford" in f), None)
    
    aux_data = {}
    if or_file:
        print(f"Loading OR: {or_file}")
        aux_data['OR'] = parser.parse_auxiliary_file(os.path.join(DATA_DIR, or_file), 'OR')
    if ts_file:
        print(f"Loading TS: {ts_file}")
        aux_data['TS'] = parser.parse_auxiliary_file(os.path.join(DATA_DIR, ts_file), 'TS')
    if pm_file:
        print(f"Loading PM: {pm_file}")
        aux_data['PM'] = parser.parse_auxiliary_file(os.path.join(DATA_DIR, pm_file), 'PM')

    # Parse Main Card
    meeting = parser.parse_main_card(os.path.join(DATA_DIR, main_card))
    
    # 3. Merge Aux Data
    print(f"Aux Data Loaded: OR({len(aux_data.get('OR', {}))} races), TS({len(aux_data.get('TS', {}))} races), PM({len(aux_data.get('PM', {}))} races)")
    if 'OR' in aux_data:
        first_race = list(aux_data['OR'].keys())[0]
        print(f"DEBUG OR Keys for {first_race}: {list(aux_data['OR'][first_race].keys())}")
    
    for race_time, race in meeting.races.items():
        print(f"Merging Race {race_time}...")
        # Helper for fuzzy matching
        def find_value(name, data_dict):
            # Try exact match
            if name in data_dict: return data_dict[name]
            # Try case insensitive
            for k, v in data_dict.items():
                if k.lower() == name.lower(): return v
            # Try partial match (e.g. "JOSEPH" in "JOSEPH 23")
            for k, v in data_dict.items():
                if name in k or k in name: return v
            return None

        # Merge OR
        if 'OR' in aux_data and race_time in aux_data['OR']:
            for runner in race.runners:
                val = find_value(runner.horse_name, aux_data['OR'][race_time])
                if val: runner.official_rating = val
        
        # Merge TS
        if 'TS' in aux_data and race_time in aux_data['TS']:
            for runner in race.runners:
                val = find_value(runner.horse_name, aux_data['TS'][race_time])
                if val: runner.topspeed = val
        
        # Merge PM (Form) - Note: PM parser might need adjustment to match runner names perfectly
        if 'PM' in aux_data and race_time in aux_data['PM']:
             for runner in race.runners:
                if runner.horse_name in aux_data['PM'][race_time]:
                    # PM data usually contains form, we can enrich here if needed
                    pass

    # 4. Save Output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        # Use model_dump() for Pydantic v2, or dict() for v1
        try:
            data = meeting.model_dump()
        except AttributeError:
            data = meeting.dict()
        json.dump(data, f, indent=2)
    
    print(f"SUCCESS! Modular processed data saved to {OUTPUT_FILE}")
    
    # 5. Summary
    print("--- Modular Pipeline Summary ---")
    for race_time, race in meeting.races.items():
        winner_candidate = max(race.runners, key=lambda x: (x.official_rating or 0))
        print(f"  {race_time}: {winner_candidate.horse_name} | J: {winner_candidate.jockey} | T: {winner_candidate.trainer} | OR: {winner_candidate.official_rating}")

if __name__ == "__main__":
    main()
