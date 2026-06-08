import duckdb
import sys
import argparse
from pathlib import Path

def run_query(sql):
    ROOT = Path(".")
    DB_PATH = ROOT / "data" / "analytics" / "velo_analytics.db"
    
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}. Run build_analytics_spine.py first.")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = con.execute(sql).fetchdf()
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        con.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SQL against the VÉLØ Analytics Spine")
    parser.add_argument("sql", help="The SQL query to execute")
    args = parser.parse_args()
    
    run_query(args.sql)
