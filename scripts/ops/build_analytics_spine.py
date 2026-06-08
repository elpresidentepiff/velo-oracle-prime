import duckdb
import os
from pathlib import Path

def build_analytics_spine():
    ROOT = Path(".")
    DB_PATH = ROOT / "data" / "analytics" / "velo_analytics.db"
    
    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Building Analytics Spine at {DB_PATH} ...")
    
    # Connect to DuckDB
    con = duckdb.connect(str(DB_PATH))
    
    # 1. Horse Passports (JSONL)
    passport_path = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
    if passport_path.exists():
        print("Creating view: passports")
        con.execute(f"CREATE OR REPLACE VIEW passports AS SELECT * FROM read_json_auto('{passport_path.as_posix()}');")
    
    # 2. Paper Predictions (JSONL)
    paper_pred_glob = ROOT / "data" / "new_build" / "paper_predictions" / "*.jsonl"
    # DuckDB handles globs directly
    if any(ROOT.glob("data/new_build/paper_predictions/*.jsonl")):
        print("Creating view: paper_predictions")
        con.execute(f"CREATE OR REPLACE VIEW paper_predictions AS SELECT * FROM read_json_auto('{paper_pred_glob.as_posix()}');")

    # 3. Verdicts (JSON files)
    verdict_glob = ROOT / "data" / "velo_prime_verdicts_*.json"
    if any(ROOT.glob("data/velo_prime_verdicts_*.json")):
        print("Creating view: verdicts")
        # Verdicts are list of objects, but some might be empty or small. 
        # We might need to handle schemas carefully if they differ.
        con.execute(f"CREATE OR REPLACE VIEW verdicts AS SELECT * FROM read_json_auto('{verdict_glob.as_posix()}', union_by_name=True);")

    # 4. Results (JSON files)
    results_glob = ROOT / "data" / "results" / "rp_results_*.json"
    if any(ROOT.glob("data/results/rp_results_*.json")):
        print("Creating view: results")
        con.execute(f"CREATE OR REPLACE VIEW results AS SELECT * FROM read_json_auto('{results_glob.as_posix()}', union_by_name=True);")

    # 5. Innovation Protocol (CSV)
    innovation_path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    if innovation_path.exists():
        print("Creating view: innovation_protocol")
        con.execute(f"CREATE OR REPLACE VIEW innovation_protocol AS SELECT * FROM read_csv_auto('{innovation_path.as_posix()}');")

    # 6. Sigma Audits (JSON)
    sigma_path = ROOT / "data" / "sigma_audits_dump.json"
    if sigma_path.exists():
        print("Creating view: sigma_audits")
        con.execute(f"CREATE OR REPLACE VIEW sigma_audits AS SELECT * FROM read_json_auto('{sigma_path.as_posix()}');")

    # 7. Sigma Memory (JSONL)
    sigma_mem_glob = ROOT / "data" / "sigma_memory" / "sigma_memory_*.jsonl"
    if any(ROOT.glob("data/sigma_memory/sigma_memory_*.jsonl")):
        print("Creating view: sigma_memory")
        con.execute(f"CREATE OR REPLACE VIEW sigma_memory AS SELECT * FROM read_json_auto('{sigma_mem_glob.as_posix()}');")

    print("\nSpine built successfully.")
    
    # Print summary of tables
    print("\nAvailable Analytics Views:")
    views = con.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'main'").fetchall()
    for v in views:
        count = con.execute(f"SELECT count(*) FROM {v[0]}").fetchone()[0]
        print(f"  - {v[0]}: {count} rows")
    
    con.close()

if __name__ == "__main__":
    build_analytics_spine()
