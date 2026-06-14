"""
query_evidence_duckdb.py — Unified SQL Access for VELO Evidence Artifacts
"""
import duckdb
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "analytics" / "velo_analytics.db"
REPORT_DIR = ROOT / "data" / "reports" / "duckdb"

def load_db(read_only=True):
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}. Run build_analytics_spine.py first.")
        sys.exit(1)
    return duckdb.connect(str(DB_PATH), read_only=read_only)

def list_sources(con):
    print("\n=== Available Evidence Sources (Views) ===")
    views = con.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'main'").fetchall()
    for v in views:
        count = con.execute(f"SELECT count(*) FROM {v[0]}").fetchone()[0]
        print(f"  - {v[0].ljust(20)} : {count} rows")

def run_canned_query(con, query_name, output_format="text"):
    queries = {
        "prediction_counts": """
            SELECT 
                CAST(generated_at AS DATE) as pred_date, 
                COUNT(*) as signals,
                COUNT(DISTINCT race_id) as races
            FROM paper_predictions
            GROUP BY 1
            ORDER BY 1 DESC;
        """,
        "overlap_audit": """
            WITH old_v AS (
                SELECT race_id, top.horse as horse, 'OLD' as source
                FROM verdicts
                WHERE top.horse IS NOT NULL
            ),
            new_v AS (
                SELECT race_id, horse as horse, 'NEW' as source
                FROM paper_predictions
            )
            SELECT 
                o.race_id, 
                o.horse, 
                o.source as old_src, 
                n.source as new_src
            FROM old_v o
            INNER JOIN new_v n ON o.race_id = n.race_id AND o.horse = n.horse
            LIMIT 20;
        """,
        "feature_drift_summary": """
            -- Summary of features from fr_prerace_features_v2.parquet
            SELECT 
                count(*) as total_rows,
                count(DISTINCT horse) as distinct_horses,
                round(avg(CAST(lagged_rpr_last1 AS DOUBLE)), 2) as avg_rpr,
                count(*) FILTER (WHERE lagged_rpr_last1 IS NULL) as null_rpr
            FROM read_parquet('data/features/fr_prerace_features_v2.parquet');
        """
    }

    sql = queries.get(query_name)
    if not sql:
        print(f"Error: Unknown canned query '{query_name}'")
        return

    print(f"\nExecuting canned query: {query_name}")
    df = con.execute(sql).fetchdf()
    
    if output_format == "text":
        print(df.to_string(index=False))
    
    # Save to report directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"{query_name}_{timestamp}.csv"
    df.to_csv(report_file, index=False)
    print(f"\nReport saved to: {report_file}")

def main():
    parser = argparse.ArgumentParser(description="Query VELO Evidence via DuckDB")
    parser.add_argument("--list", action="store_true", help="List available evidence sources")
    parser.add_argument("--query", type=str, help="Run a custom SQL query")
    parser.add_argument("--canned", type=str, choices=["prediction_counts", "overlap_audit", "feature_drift_summary"], help="Run a predefined canned query")
    parser.add_argument("--format", choices=["text", "csv"], default="text", help="Output format")

    args = parser.parse_args()
    
    con = load_db()
    
    if args.list:
        list_sources(con)
    elif args.canned:
        run_canned_query(con, args.canned, args.format)
    elif args.query:
        df = con.execute(args.query).fetchdf()
        print(df.to_string(index=False))
        
    con.close()

if __name__ == "__main__":
    main()
