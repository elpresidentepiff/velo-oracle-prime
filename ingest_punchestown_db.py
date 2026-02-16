import sqlite3
import json
from datetime import datetime

DB_PATH = "velo_memory.db"

# The 17 Selections from Punchestown (Hardcoded for this injection)
DATA = [
    {"race_time": "13:40", "horse": "D B Cooper", "odds": 5.0, "type": "Win", "confidence": "High"},
    {"race_time": "13:40", "horse": "Fleur In The Park", "odds": 6.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "14:10", "horse": "Kinturk Kalanisi", "odds": 7.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "14:10", "horse": "Slade Steel", "odds": 2.5, "type": "Win", "confidence": "High"},
    {"race_time": "14:40", "horse": "Built By Ballymore", "odds": 4.0, "type": "Win", "confidence": "High"},
    {"race_time": "14:40", "horse": "Answer To Kayf", "odds": 8.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "15:10", "horse": "Spillane's Tower", "odds": 3.5, "type": "Win", "confidence": "High"},
    {"race_time": "15:10", "horse": "Blood Destiny", "odds": 4.5, "type": "Win", "confidence": "Medium"},
    {"race_time": "15:40", "horse": "Maskada", "odds": 6.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "15:40", "horse": "Solness", "odds": 9.0, "type": "Win", "confidence": "Low"},
    {"race_time": "16:10", "horse": "Senior Chief", "odds": 5.5, "type": "Win", "confidence": "Medium"},
    {"race_time": "16:10", "horse": "The Goffer", "odds": 7.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "16:40", "horse": "Jalon D'oudairies", "odds": 2.2, "type": "Win", "confidence": "High"},
    {"race_time": "16:40", "horse": "Romeo Coolio", "odds": 3.0, "type": "Win", "confidence": "High"},
    {"race_time": "17:10", "horse": "Cantico", "odds": 4.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "17:10", "horse": "The Enabler", "odds": 6.0, "type": "Win", "confidence": "Medium"},
    {"race_time": "17:10", "horse": "Sounds Victorius", "odds": 8.0, "type": "Win", "confidence": "Low"}
]

def ingest():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create a dummy race for Punchestown
    race_id = "PUNCHESTOWN_20260215"
    cursor.execute("INSERT OR IGNORE INTO races (race_id, date, course, race_name) VALUES (?, ?, ?, ?)",
                   (race_id, "2026-02-15", "Punchestown", "Grand National Trial Day"))
    
    print(f"Injecting {len(DATA)} runners into memory...")
    
    for runner in DATA:
        runner_id = f"{race_id}_{runner['horse'].replace(' ', '_')}"
        cursor.execute('''
        INSERT OR REPLACE INTO runners (runner_id, race_id, horse_name, odds_opening, comment)
        VALUES (?, ?, ?, ?, ?)
        ''', (runner_id, race_id, runner['horse'], runner['odds'], f"{runner['type']} - {runner['confidence']}"))
        
    conn.commit()
    conn.close()
    print("✅ Punchestown Data Injection Complete.")

if __name__ == "__main__":
    ingest()
