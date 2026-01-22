#!/usr/bin/env python3
"""
VÉLØ PRIME File Ingestion
Parses JSON/CSV race data and populates database
"""

import json
import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"
INCOMING_DIR = PRIME_DIR / "incoming"

def parse_json_races(json_path: Path) -> Tuple[Dict, List[Dict]]:
    """Parse JSON race file."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    metadata = data.get('metadata', {})
    races = data.get('races', [])
    
    return metadata, races

def ingest_races(json_path: Path):
    """Ingest races and runners from JSON into database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not initialized: {DB_PATH}")
    
    metadata, races = parse_json_races(json_path)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    venue = metadata.get('venue', 'UNKNOWN')
    race_date = metadata.get('date', datetime.now().isoformat()[:10])
    
    race_count = 0
    runner_count = 0
    
    for race in races:
        race_time = race.get('race_time', '')
        race_name = race.get('race_name', '')
        distance = race.get('distance', '')
        going = race.get('going', '')
        prize_money = race.get('prize_money', '')
        
        try:
            cursor.execute("""
                INSERT INTO races (venue, race_date, race_time, race_name, distance, going, prize_money, track_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (venue, race_date, race_time, race_name, distance, going, prize_money, metadata.get('track_type')))
            
            race_id = cursor.lastrowid
            race_count += 1
            
            # Ingest runners
            for horse in race.get('horses', []):
                try:
                    cursor.execute("""
                        INSERT INTO runners (
                            race_id, number, name, age, weight, form, jockey, trainer,
                            official_rating, topspeed, rpr, sire, dam, owner, commentary,
                            is_postdata_selection, is_topspeed_selection
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        race_id,
                        horse.get('number'),
                        horse.get('name'),
                        horse.get('age'),
                        horse.get('weight'),
                        horse.get('form'),
                        horse.get('jockey'),
                        horse.get('trainer'),
                        horse.get('official_rating'),
                        horse.get('topspeed'),
                        horse.get('rpr'),
                        horse.get('sire'),
                        horse.get('dam'),
                        horse.get('owner'),
                        horse.get('commentary'),
                        1 if horse.get('is_postdata_selection') else 0,
                        1 if horse.get('is_topspeed_selection') else 0
                    ))
                    runner_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"⚠️  Duplicate runner: {horse.get('name')} in race {race_time}")
        
        except sqlite3.IntegrityError as e:
            print(f"⚠️  Duplicate race: {venue} {race_date} {race_time}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Ingested {race_count} races, {runner_count} runners from {json_path.name}")
    return race_count, runner_count

if __name__ == "__main__":
    json_file = INCOMING_DIR / "gowran_race_data_final.json"
    if json_file.exists():
        ingest_races(json_file)
    else:
        print(f"❌ File not found: {json_file}")
