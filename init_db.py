import sqlite3
import os
from datetime import datetime

DB_PATH = "velo_memory.db"

def init_db():
    """Initialize the SQLite database with the VÉLØ schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Races Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS races (
        race_id TEXT PRIMARY KEY,
        date TEXT,
        course TEXT,
        time TEXT,
        race_name TEXT,
        distance TEXT,
        going TEXT,
        class TEXT,
        prize_money REAL
    )
    ''')
    
    # 2. Runners Table (The Core Data)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runners (
        runner_id TEXT PRIMARY KEY,
        race_id TEXT,
        horse_name TEXT,
        trainer TEXT,
        jockey TEXT,
        age INTEGER,
        weight TEXT,
        draw INTEGER,
        or_rating INTEGER,
        ts_rating INTEGER,
        rpr_rating INTEGER,
        form_figures TEXT,
        odds_opening REAL,
        odds_sp REAL,
        position INTEGER,
        comment TEXT,
        FOREIGN KEY(race_id) REFERENCES races(race_id)
    )
    ''')
    
    # 3. Trainers Pattern Table (Behavioral Intelligence)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trainer_patterns (
        trainer_name TEXT,
        course TEXT,
        pattern_type TEXT, -- e.g., "First Time Headgear", "Course Specialist"
        wins INTEGER,
        runs INTEGER,
        strike_rate REAL,
        last_updated TEXT,
        PRIMARY KEY (trainer_name, course, pattern_type)
    )
    ''')
    
    # 4. Bias Memory (Track Specifics)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS course_bias (
        course TEXT,
        distance TEXT,
        going TEXT,
        bias_note TEXT, -- e.g., "High draw advantage", "Rail dead"
        confidence_score INTEGER,
        last_verified TEXT,
        PRIMARY KEY (course, distance, going)
    )
    ''')

    conn.commit()
    conn.close()
    print(f"✅ VÉLØ Memory Vault initialized at {os.path.abspath(DB_PATH)}")

if __name__ == "__main__":
    init_db()
