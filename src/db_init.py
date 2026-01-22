#!/usr/bin/env python3
"""
VÉLØ PRIME Database Initialization
Canonical location: /home/ubuntu/velo-oracle-prime/velo.db
"""

import sqlite3
import os
from pathlib import Path

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"
SCHEMA_PATH = PRIME_DIR / "src" / "schema.sql"

def init_database():
    """Initialize SQLite database with schema."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    
    print(f"✅ Database initialized: {DB_PATH}")
    return DB_PATH

def get_connection():
    """Get database connection."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == "__main__":
    init_database()
