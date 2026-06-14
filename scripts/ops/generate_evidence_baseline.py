import duckdb
from pathlib import Path

def generate_baseline():
    ROOT = Path(".")
    DB_PATH = ROOT / "data" / "analytics" / "velo_analytics.db"
    REPORT_PATH = ROOT / "data" / "analytics" / "evidence_baseline_report.md"
    
    if not DB_PATH.exists():
        print("Error: Database not found.")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)
    
    print("Generating Evidence Baseline Report ...")
    
    # Define VP bands and calculate SR/ROI
    # We need to join verdicts with results. 
    # Verdicts top horse vs Results winner
    
    query = """
    WITH flat_verdicts AS (
        SELECT 
            race_id,
            top.horse as horse_name,
            top.velo_prime_prob as vp,
            date
        FROM verdicts
        WHERE top.horse IS NOT NULL
    ),
    flat_results AS (
        SELECT 
            race_id,
            winner_horse,
            winner_sp,
            date
        FROM results
        WHERE winner_horse IS NOT NULL
    ),
    joined AS (
        SELECT 
            v.race_id,
            v.horse_name,
            v.vp,
            v.date,
            r.winner_horse,
            r.winner_sp,
            CASE WHEN v.horse_name = r.winner_horse THEN 1 ELSE 0 END as is_win
        FROM flat_verdicts v
        JOIN flat_results r ON v.race_id = r.race_id
    ),
    binned AS (
        SELECT 
            CASE 
                WHEN vp < 0.20 THEN '1: VP < 0.20'
                WHEN vp < 0.30 THEN '2: 0.20 <= VP < 0.30'
                WHEN vp < 0.40 THEN '3: 0.30 <= VP < 0.40'
                ELSE '4: VP >= 0.40'
            END as vp_band,
            is_win,
            winner_sp
        FROM joined
    )
    SELECT 
        vp_band,
        COUNT(*) as total_signals,
        SUM(is_win) as wins,
        ROUND(AVG(is_win) * 100, 2) as strike_rate,
        ROUND(SUM(CASE WHEN is_win = 1 THEN winner_sp - 1 ELSE -1 END) / COUNT(*) * 100, 2) as roi_pct
    FROM binned
    GROUP BY 1
    ORDER BY 1;
    """
    
    try:
        df = con.execute(query).fetchdf()
        
        report = []
        report.append("# Evidence Baseline Report")
        report.append(f"Generated at: {Path('.').absolute()}")
        report.append("\n## Performance by VP Band (Verdicts vs Results)")
        report.append(df.to_markdown(index=False))
        
        # Also check innovation protocol for historical baseline
        ip_query = """
        SELECT 
            COUNT(*) as total,
            SUM(won) as wins,
            ROUND(AVG(won) * 100, 2) as sr
        FROM innovation_protocol;
        """
        ip_stats = con.execute(ip_query).fetchone()
        report.append("\n## Innovation Protocol Baseline")
        report.append(f"- Total Signals: {ip_stats[0]}")
        report.append(f"- Wins: {ip_stats[1]}")
        report.append(f"- Strike Rate: {ip_stats[2]}%")

        # Sigma Audits Baseline
        sigma_query = """
        SELECT 
            decision_tier,
            COUNT(*) as total,
            SUM(CASE WHEN top_strike_correct = true THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN top_strike_correct = true THEN 1 ELSE 0 END) * 100, 2) as sr
        FROM sigma_audits
        GROUP BY 1
        ORDER BY 1;
        """
        sigma_df = con.execute(sigma_query).fetchdf()
        report.append("\n## Sigma Audit Baseline")
        report.append(sigma_df.to_markdown(index=False))
        
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
            
        print(f"Report written to {REPORT_PATH}")
        print(df.to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        con.close()

if __name__ == "__main__":
    generate_baseline()
